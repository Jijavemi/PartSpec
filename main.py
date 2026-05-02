import os, json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

groq_client = None
if os.getenv("GROQ_API_KEY"):
    try:
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        print("✅ Groq ready")
    except Exception as e:
        print(f"Groq init error: {e}")

class PartSpec(BaseModel):
    partNumber: str | None = None
    name: str
    description: str
    category: str
    material: str | None = None
    weight: str | None = None
    dimensions: str | None = None
    tolerance: str | None = None
    finish: str | None = None
    manufacturer: str | None = None
    price: str | None = None
    stockStatus: str | None = None
    datasheetURL: str | None = None
    certifications: list[str] | None = None

def mock_part(query: str) -> PartSpec:
    return PartSpec(
        name=f"Mock for '{query}' (Groq not available)",
        description="Install groq==0.8.0 and set GROQ_API_KEY to enable AI.",
        category="Other"
    )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search_part(q: str = Query(...)):
    if not groq_client:
        return mock_part(q)
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return JSON with part specs: name, description, category"},
                {"role": "user", "content": f"Part: {q}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        data = json.loads(response.choices[0].message.content)
        return PartSpec(**data)
    except Exception as e:
        return mock_part(q)