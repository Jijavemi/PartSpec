import os
import sys
import json
import asyncio
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
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

    system_prompt = """You are PartSpec, a technical assistant. 
- Use the provided search results as your **primary source**.
- However, you may also rely on your **general technical knowledge** for well‑known parts (common electronics, standard hardware, popular brands like Huion, Logitech, etc.) when search results are sparse or missing.
- If a part is completely unknown or the search results contain no relevant information, set name = "Part not found" and description = "No reliable information found."
- Return ONLY valid JSON with fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications.
- Category must be one of: Mechanical, Electrical, Hydraulic, Pneumatic, Fasteners, RawMaterials, Other. Default "Other".
- Use null for unknown fields.
- Never invent specifications for obscure proprietary part numbers (like internal inventory codes)."""

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
        
        return PartSpec(**data)
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