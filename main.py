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
    system = """You are PartSpec, a technical assistant. Return ONLY valid JSON with these fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications. 
    IMPORTANT: weight, dimensions, and price must be strings (e.g., "0.5 kg", "10 x 5 x 2 cm", "$25.99"). Do not use numbers or objects."""
    
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
        
        # Convert any non-string values to strings (safety net)
        for key in ["weight", "dimensions", "price", "partNumber", "material", "tolerance", "finish", "manufacturer", "stockStatus", "datasheetURL"]:
            if key in data and data[key] is not None and not isinstance(data[key], str):
                data[key] = str(data[key])
        
        # Convert certifications list if present
        if "certifications" in data and data["certifications"] is not None:
            if not isinstance(data["certifications"], list):
                data["certifications"] = [str(data["certifications"])]
            else:
                data["certifications"] = [str(c) for c in data["certifications"]]
        
        return PartSpec(**data)
    except Exception as e:
        print(f"❌ LLM error: {type(e).__name__}: {e}")
        # Return a fallback that includes the error details (optional)
        return PartSpec(
            name=f"Fallback for '{query}'",
            description=f"Groq error: {str(e)}",
            category="Error"
        )

# ---------- API endpoints ----------
@app.get("/version")
def version():
    return {"version": "3.0", "status": "New Groq code deployed"}

@app.get("/debug")
def debug():
    return {"groq_available": groq_available, "api_key_set": bool(os.getenv("GROQ_API_KEY"))}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search_part(q: str = Query(...)):
    if not groq_available:
        return mock_part(q)
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a technical assistant. Return valid JSON with fields: partNumber, name, description, category, material, weight, dimensions, tolerance, finish, manufacturer, price, stockStatus, datasheetURL, certifications. Use null for unknown."},
                {"role": "user", "content": f"Part: {q}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(response.choices[0].message.content)
        return PartSpec(**data)
    except Exception as e:
        # Return the error as a PartSpec so you can see it in curl
        return PartSpec(
            name=f"Groq error: {type(e).__name__}",
            description=str(e),
            category="Error"
        )