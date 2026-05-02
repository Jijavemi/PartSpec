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

# Groq init
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

async def duckduckgo_search(query: str, max_results: int = 4) -> str:
    """Search DuckDuckGo Lite - more stable HTML."""
    url = "https://lite.duckduckgo.com/lite/"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    params = {"q": query}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
        except Exception as e:
            print(f"Search request failed: {e}")
            return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table[class='result'] tr")
    results = []
    current = {}
    for row in rows:
        if row.get("class") and "result-snippet" in row.get("class"):
            snippet = row.get_text(strip=True)
            if current:
                current["snippet"] = snippet
                results.append(current)
                current = {}
        elif row.get("class") and "result-url" in row.get("class"):
            link = row.find("a")
            if link:
                current["url"] = link.get("href")
        elif row.get("class") and "result-title" in row.get("class"):
            title_tag = row.find("a")
            if title_tag:
                current["title"] = title_tag.get_text(strip=True)
    output = []
    for r in results[:max_results]:
        output.append(f"Title: {r.get('title', '')}\nSnippet: {r.get('snippet', '')}\nURL: {r.get('url', '')}\n")
    return "\n".join(output) if output else ""

async def get_part_specs(query: str) -> PartSpec:
    # Search
    search_context = await duckduckgo_search(query)
    if not search_context or len(search_context.strip()) < 80:
        search_context = await duckduckgo_search(f"{query} specifications")
    
    system_prompt = """You are PartSpec. Use the search results to answer. Return ONLY valid JSON with these fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications.
    IMPORTANT: 
    - The 'category' field must be a string, one of: Mechanical, Electrical, Hydraulic, Pneumatic, Fasteners, RawMaterials, Other. If none fits, use "Other".
    - If any field is unknown, use null (not "N/A").
    - Never invent specifications. If part not found, set name = "Part not found" and description = "No reliable information found." and category = "Other".
    """
    
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
        
        # ---- Guarantee required fields ----
        # Category must be a string, default to "Other"
        if "category" not in data or data["category"] is None or not isinstance(data["category"], str):
            data["category"] = "Other"
        
        # Name and description must be strings (fallback)
        if "name" not in data or data["name"] is None:
            data["name"] = "Part not found"
        if "description" not in data or data["description"] is None:
            data["description"] = "No description available."
        
        # Convert any non-string values to strings for optional fields
        string_fields = ["partNumber", "material", "weight", "dimensions", "tolerance", "finish", "manufacturer", "price", "stockStatus", "datasheetURL"]
        for field in string_fields:
            if field in data and data[field] is not None and not isinstance(data[field], str):
                data[field] = str(data[field])
        
        # Handle certifications list
        if "certifications" in data and data["certifications"] is not None:
            if not isinstance(data["certifications"], list):
                data["certifications"] = [str(data["certifications"])]
            else:
                data["certifications"] = [str(c) for c in data["certifications"]]
        
        return PartSpec(**data)
    except Exception as e:
        print(f"LLM error: {e}")
        # Return a safe fallback that never causes validation errors
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