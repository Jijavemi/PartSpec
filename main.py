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
    weight: Optional[str] = None  # with unit
    dimensions: Optional[str] = None  # with unit
    tolerance: Optional[str] = None
    finish: Optional[str] = None
    manufacturer: Optional[str] = None
    price: Optional[str] = None
    stockStatus: Optional[str] = None
    datasheetURL: Optional[str] = None
    certifications: Optional[List[str]] = None

async def duckduckgo_search(query: str, max_results: int = 4) -> str:
    """Search DuckDuckGo and return formatted results."""
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    params = {"q": query}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
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
    # Try primary search
    search_context = await duckduckgo_search(query)
    if not search_context or len(search_context.strip()) < 50:
        # Try secondary search with "specifications" or "datasheet"
        alt_query = f"{query} specifications"
        search_context = await duckduckgo_search(alt_query)
    
    system_prompt = """You are PartSpec. Use the provided search results to answer. Return ONLY valid JSON.
    Fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications.
    
    IMPORTANT INSTRUCTIONS:
    - If the search results contain dimensions (e.g., "folded: 200x150x20 mm", "unfolded: 250x200x30 mm"), include them as a string in the 'dimensions' field.
    - For weight, include unit (e.g., "0.5 kg").
    - If a field cannot be found, use null (not "N/A").
    - Never invent specifications.
    - If the part is not found, set name = "Part not found" and description = "No reliable information found." """
    
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
        # Ensure string fields are strings or null
        string_fields = ["partNumber", "name", "description", "category", "material", "weight", "dimensions", "tolerance", "finish", "manufacturer", "price", "stockStatus", "datasheetURL"]
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
        return PartSpec(name="Service error", description=f"Error: {str(e)}", category="Error")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search_part(q: str = Query(...)):
    return await get_part_specs(q)