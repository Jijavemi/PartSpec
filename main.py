import os, json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Initialize Groq if key exists
groq_available = False
groq_client = None
if os.getenv("GROQ_API_KEY"):
    try:
        from groq import Groq
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        groq_available = True
        print("✅ Groq initialised")
    except Exception as e:
        print(f"Groq init error: {e}")

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

def mock_part(query: str) -> PartSpec:
    return PartSpec(
        name=f"Mock for '{query}' (install Groq & set API key for real data)",
        description="Set GROQ_API_KEY and redeploy to get detailed specifications.",
        category="Other"
    )

async def get_llm_specs(query: str) -> PartSpec:
    system = """You are PartSpec, a technical assistant. Return ONLY valid JSON with these fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications. Use null for unknown. Category one of: Mechanical, Electrical, Hydraulic, Pneumatic, Fasteners, RawMaterials, Other."""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Part: {query}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(response.choices[0].message.content)
        return PartSpec(**data)
    except Exception as e:
        print(f"LLM error: {e}")
        return mock_part(query)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search_part(q: str = Query(...)):
    if not groq_available:
        return mock_part(q)
    return await get_llm_specs(q)