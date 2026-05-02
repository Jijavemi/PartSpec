from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search_part(q: str = Query(...)):
    return {
        "partNumber": "MOCK-001",
        "name": f"Test part for '{q}'",
        "description": "Server is working! Groq not used yet. Add API key later.",
        "category": "Mechanical",
        "material": "Aluminum",
        "weight": "0.5 kg",
        "dimensions": "10x5x2 cm",
        "tolerance": "±0.01mm",
        "finish": "Anodized",
        "manufacturer": "Demo Corp",
        "price": "$19.99",
        "stockStatus": "In Stock",
        "datasheetURL": None,
        "certifications": ["ISO 9001"]
    }