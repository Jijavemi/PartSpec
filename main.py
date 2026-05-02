import os
import json
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI(title="PartSpec API (Free Edition)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq (free tier)
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("Missing GROQ_API_KEY in environment variables")
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


def fallback_part(query: str) -> PartSpec:
    """Return a mock part when the LLM call fails (for stability)."""
    return PartSpec(
        partNumber=None,
        name=f"Part matching '{query}'",
        description="Mock response – Groq API key may be missing or rate limited. Please verify your GROQ_API_KEY.",
        category="Other",
        material=None,
        weight=None,
        dimensions=None,
        tolerance=None,
        finish=None,
        manufacturer=None,
        price=None,
        stockStatus=None,
        datasheetURL=None,
        certifications=None
    )


async def extract_part_specs(query: str) -> PartSpec:
    """Call Groq LLM to get part specifications."""
    system_prompt = """You are PartSpec, a technical assistant for engineers. 
Given a part name or number, return ONLY valid JSON with these fields: 
partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications. 
Use null for missing fields. Category must be one of: Mechanical, Electrical, Hydraulic, Pneumatic, Fasteners, RawMaterials, Other."""
    
    user_prompt = f"Part query: '{query}'\n\nReturn JSON part specs."
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # free tier on Groq
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
    except Exception as e:
        print(f"Groq error: {e}")
        return fallback_part(query)


@app.get("/search", response_model=PartSpec)
async def search_part(q: str = Query(..., description="Part name or number")):
    """Search for a part and return specifications."""
    try:
        part_spec = await extract_part_specs(q)
        return part_spec
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}