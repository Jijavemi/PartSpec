import os
import sys
import json
import asyncio
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from dotenv import load_dotenv
from groq import Groq
import httpx
from bs4 import BeautifulSoup

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("Missing GROQ_API_KEY")
groq_client = Groq(api_key=groq_api_key)

class PartSpec(BaseModel):
    partNumber: Optional[str] = None
    name: str
    description: str
    category: str
    material: Optional[str] = None
    weight: Optional[str] = None
    dimensions: Optional[str] = None
    tolerance: Optional[str] = None
    finish: Optional[str] = None
    manufacturer: Optional[str] = None
    price: Optional[str] = None
    stockStatus: Optional[str] = None
    datasheetURL: Optional[str] = None
    certifications: Optional[List[str]] = None
    specifications: Optional[List[Dict[str, str]]] = None   # new dynamic field

# ---------- search using standard DDG HTML ----------
async def duckduckgo_search(query: str, max_results: int = 4) -> str:
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers, params={"q": query})
            resp.raise_for_status()
        except Exception as e:
            print(f"Search failed: {e}")
            return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    results = soup.select(".result")
    output = []
    for r in results[:max_results]:
        title_tag = r.select_one(".result__a")
        snippet_tag = r.select_one(".result__snippet")
        if title_tag:
            title = title_tag.get_text(strip=True)
            link = title_tag.get("href")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            output.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}\n")
    return "\n".join(output) if output else ""

async def get_part_specs(query: str) -> PartSpec:
    # Primary search
    search_context = await duckduckgo_search(query)
    if not search_context or len(search_context.strip()) < 80:
        search_context = await duckduckgo_search(f"{query} specifications")

    system_prompt = system_prompt = """You are PartSpec, a technical assistant.

- Use the provided search results as your **primary source**.
- However, you may also rely on your **general technical knowledge** for well‑known parts (common electronics, standard hardware, popular brands like Huion, Logitech, etc.) when search results are sparse or missing.
- If a part is completely unknown or the search results contain no relevant information, set name = "Part not found" and description = "No reliable information found."

Return ONLY valid JSON with the following fields:
  partNumber, name, description, category, material, weight, dimensions, tolerance, finish,
  manufacturer, price, stockStatus, datasheetURL, certifications, specifications.

**specifications** must be a list of objects, each with "key" and "value".  
Choose 5–15 most important technical specifications based on the part's category.

### Fastener‑specific rules (apply to any fastener: bolt, screw, nut, washer, threaded rod, etc.):
- **ALWAYS include a "Torque" specification** with clear condition (dry or lubricated/plated).  
  - If the user provides a **specific thread size and grade**, give **both dry and lubricated** torque values when available. Use the most authoritative standard values (e.g., from Machinery's Handbook, ASTM, or industry typical).  
  - If the user provides only a grade without size, give an example torque for common sizes and note that torque depends on diameter and thread pitch.
  - If the user query lacks any size, state that torque depends on diameter, and provide an example.

- **Accurate torque values for Grade 8 fasteners (SAE J429 / ASTM A354 Grade BD):**
  - Use the following table for **dry** (plain, unplated) torque in ft·lbs. For **lubricated** (or zinc‑plated), reduce by ~25% or use the values in parentheses.
  - Coarse thread (UNC) – typical Grade 8 dry torque:
    - 1/4"-20 → 10 ft·lb
    - 5/16"-18 → 20 ft·lb
    - 3/8"-16 → 35 ft·lb
    - 7/16"-14 → 55 ft·lb
    - 1/2"-13 → 75 ft·lb
    - 9/16"-12 → 110 ft·lb
    - 5/8"-11 → 150 ft·lb
    - 3/4"-10 → 280 ft·lb   (lubricated ≈ 210 ft·lb)
    - 7/8"-9 → 440 ft·lb
    - 1"-8 → 660 ft·lb
  - Fine thread (UNF) – Grade 8 dry torque is approximately 10‑15% higher than coarse. For 3/4"-16 → dry ≈ 320 ft·lb, lubricated ≈ 240 ft·lb.
  - For metric Grade 8.8 or 10.9, use standard metric torque values.

- If the user query does not specify coarse or fine, assume **coarse (UNC)** as the default for inch sizes.

- Include at minimum: Thread Size, Thread Type (coarse/fine), Material Strength, Tensile Strength, Yield Strength, Proof Load, Hardness, Standards, and **Torque** (with condition: dry or lubricated).

- For Grade 8 fasteners, the fixed typical property values remain:
  - Tensile Strength: 150,000 psi
  - Yield Strength: 130,000 psi
  - Proof Load: 120,000 psi
  - Hardness: Rockwell C33–39
  - Standards: ASTM A354 Grade BD, SAE J429 Grade 8

- If the user query lacks a specific size, set the `partNumber` or `name` to include "Size unspecified" and note in `description` that torque values are examples for common sizes (e.g., 1/2", 3/4").

### For other categories (Electronics, Mechanical, etc.):
- Use the examples already provided.

For fields already covered by the fixed fields (material, weight, dimensions, etc.), you may still include them in specifications for completeness, but avoid duplication if possible.

Use `null` for unknown fixed fields.  
Never invent specifications for obscure proprietary part numbers.

Category must be one of: Mechanical, Electrical, Hydraulic, Pneumatic, Fasteners, RawMaterials, Other. Default "Other"."""
    user_prompt = f"""User query: "{query}"
Search results:
{search_context if search_context else "No search results."}
Return JSON part specs."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(response.choices[0].message.content)
        
        # Guarantee required fields
        if "category" not in data or data["category"] is None or not isinstance(data["category"], str):
            data["category"] = "Other"
        if "name" not in data or data["name"] is None:
            data["name"] = "Part not found"
        if "description" not in data or data["description"] is None:
            data["description"] = "No description available."
        
        string_fields = ["partNumber", "material", "weight", "dimensions", "tolerance", "finish", "manufacturer", "price", "stockStatus", "datasheetURL"]
        for field in string_fields:
            if field in data and data[field] is not None and not isinstance(data[field], str):
                data[field] = str(data[field])
        
        if "certifications" in data and data["certifications"] is not None:
            if not isinstance(data["certifications"], list):
                data["certifications"] = [str(data["certifications"])]
            else:
                data["certifications"] = [str(c) for c in data["certifications"]]
        
        # Parse specifications array
        specifications = None
        if "specifications" in data and isinstance(data["specifications"], list):
            specs_list = []
            for item in data["specifications"]:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    specs_list.append({"key": str(item["key"]), "value": str(item["value"])})
            if specs_list:
                specifications = specs_list
        
        return PartSpec(
            partNumber=data.get("partNumber"),
            name=data["name"],
            description=data["description"],
            category=data["category"],
            material=data.get("material"),
            weight=data.get("weight"),
            dimensions=data.get("dimensions"),
            tolerance=data.get("tolerance"),
            finish=data.get("finish"),
            manufacturer=data.get("manufacturer"),
            price=data.get("price"),
            stockStatus=data.get("stockStatus"),
            datasheetURL=data.get("datasheetURL"),
            certifications=data.get("certifications"),
            specifications=specifications
        )
    except Exception as e:
        print(f"LLM error: {e}")
        return PartSpec(
            name="Service error",
            description=f"Internal error: {str(e)}",
            category="Error"
        )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search_part(q: str = Query(...)):
    return await get_part_specs(q)