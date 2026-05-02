import os
import sys
import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# ---------- Debug logging ----------
print("🐍 Python version:", sys.version)
api_key = os.getenv("GROQ_API_KEY")
print(f"🔑 GROQ_API_KEY present: {'Yes' if api_key else 'No'}")
if api_key:
    print(f"   First 5 chars: {api_key[:5]}... (length {len(api_key)})")
else:
    print("   (Make sure it's set in Render Environment Variables)")

# ---------- Groq initialisation ----------
groq_available = False
groq_client = None

if api_key:
    try:
        from groq import Groq
        groq_client = Groq(api_key=api_key)
        groq_available = True
        print("✅ Groq client initialised successfully")
    except Exception as e:
        print(f"❌ Groq init error: {type(e).__name__}: {e}")
else:
    print("⚠️ GROQ_API_KEY not set – using mock responses only")

# ---------- Data model ----------
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

# ---------- Mock fallback (updated text) ----------
def mock_part(query: str) -> PartSpec:
    return PartSpec(
        name=f"Mock for '{query}' (Groq not available – check logs)",
        description="Either GROQ_API_KEY missing or Groq call failed. See Render logs for details.",
        category="Other"
    )

# ---------- LLM call ----------
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
        print(f"❌ LLM error: {type(e).__name__}: {e}")
        return mock_part(query)

# ---------- API endpoints ----------
@app.get("/version")
def version():
    return {"version": "3.0", "status": "New Groq code deployed"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search_part(q: str = Query(...)):
    if not groq_available:
        return mock_part(q)
    return await get_llm_specs(q)