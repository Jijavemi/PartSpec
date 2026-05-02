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
    
    # Additional targeted searches for dimensions and weight
    dim_context = await duckduckgo_search(f"{query} dimensions")
    weight_context = await duckduckgo_search(f"{query} weight")
    
    combined = search_context
    if dim_context:
        combined += f"\n\n--- Additional dimension results ---\n{dim_context}"
    if weight_context:
        combined += f"\n\n--- Additional weight results ---\n{weight_context}"
    
    # Fallback if everything empty
    if not combined.strip():
        combined = "No search results."

    system_prompt = """You are PartSpec. Use the provided search results (especially the dimension-specific ones) to fill the 'dimensions' and 'weight' fields. You may also use your general knowledge for popular products.

Return ONLY valid JSON with fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications.

Rules:
- If dimensions are found anywhere (e.g., "folded: 200x150x20mm", "size: 11mm thin"), include them as a string.
- If weight is found (e.g., "0.5kg"), use it.
- If a field cannot be found, use null (not "N/A").
- Category must be a string, default "Other".
- Never invent specifications for unknown parts.
"""

    user_prompt = f"""User query: "{query}"
Search results (including dimension-specific searches):
{combined}
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
        # ... (the same conversion logic as before)
        # Make sure dimensions and weight are strings or null
        return PartSpec(**data)
    except Exception as e:
        # fallback
        return PartSpec(
            name="Service error",
            description=str(e),
            category="Error"
        )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search_part(q: str = Query(...)):
    return await get_part_specs(q)