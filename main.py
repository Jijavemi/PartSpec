import os
import json
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from groq import Groq

load_dotenv()

app = FastAPI(title="PartSpec API (Free Edition)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq (free)
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("Missing GROQ_API_KEY in .env")
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


def search_duckduckgo(query: str) -> str:
    """Free web search using DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if not results:
                return "No search results found."
            
            output = "Search Results:\n"
            for idx, r in enumerate(results, 1):
                output += f"{idx}. Title: {r.get('title', '')}\n"
                output += f"   Body: {r.get('body', '')}\n"
                output += f"   URL: {r.get('href', '')}\n\n"
            return output
    except Exception as e:
        return f"Search failed: {str(e)}"


async def extract_part_specs(query: str, search_context: str) -> PartSpec:
    system_prompt = """You are PartSpec, a technical assistant for engineers. Extract part specifications from the search results. Return ONLY valid JSON with these fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications. Use null for missing fields. Category must be one of: Mechanical, Electrical, Hydraulic, Pneumatic, Fasteners, RawMaterials, Other."""
    
    user_prompt = f"User query: '{query}'\n\n{search_context}\n\nReturn JSON part specs."
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # free tier
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    
    content = response.choices[0].message.content
    data = json.loads(content)
    return PartSpec(**data)


@app.get("/search", response_model=PartSpec)
async def search_part(q: str = Query(..., description="Part name or number")):
    search_context = search_duckduckgo(q)
    part_spec = await extract_part_specs(q, search_context)
    return part_spec


@app.get("/health")
async def health():
    return {"status": "ok"}