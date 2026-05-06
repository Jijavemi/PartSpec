# PartSpec – Universal Technical Assistant

**PartSpec** helps engineers, machinists, procurement specialists, and DIY makers instantly look up technical specifications for any part – from common electronic components to industrial hardware. It bridges the gap between identifying a component and understanding its complete specifications.

## Project Submission (Final Project)

- **Team members:** Emily Jijavadze (individual)
- **Platform:** iOS (Xcode 15+, iOS 17+)
- **Submission date:** May 6, 2026

## Features

- **Instant local lookup** – Predefined parts (e.g., BRK-123, LM358) return specs immediately.
- **AI-powered web search** – For unknown part numbers or names, PartSpec searches the web and extracts structured data using Groq’s LLM (Llama 3.3 70B) and DuckDuckGo.
- **Clean spec display** – Part number, description, material, weight, dimensions, manufacturer, price, stock status, certifications, datasheet URL.
- **Honest “not found”** – No hallucinated data; the app clearly states when a part cannot be found.
- **Native iOS UI** – Built with UIKit and Auto Layout, follows Apple’s Human Interface Guidelines.

## Tech Stack

| Component | Technology |
|-----------|------------|
| iOS App | Swift, UIKit, URLSession |
| Backend API | FastAPI (Python) hosted on Render |
| LLM | Groq (Llama 3.3 70B) – free tier |
| Web Search | DuckDuckGo HTML scraping (fallback queries) |
| Parsing | BeautifulSoup, httpx |
| Hosting | Render (free tier) |

## Dependencies

### iOS App
- Xcode 15+
- iOS deployment target 17.0
- No third‑party Swift packages – uses UIKit, Foundation, URLSession only.

### Backend (if running locally)
- Python 3.11 (3.14 is not compatible with some libraries)
- FastAPI, Uvicorn, Groq, httpx, BeautifulSoup4 (see `requirements.txt`)
- A free **Groq API key** (get one at [console.groq.com](https://console.groq.com))


## Setup for Grader

### 1. Backend – Already Deployed
The backend is live at **`https://partspec.onrender.com`**. No local server setup is required – the iOS app is pre‑configured to use this URL.


### 2. Local Running - My Github
If you want to run your own instance:
```bash
git clone https://github.com/Jijavemi/PartSpec.git
cd PartSpec/backend
python -m venv venv
source venv/bin/activate                           # or venv\Scripts\activate on Windows
pip install -r requirements.txt
# Create .env file with GROQ_API_KEY=your_key
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Testing Examples

### App Testing:
Try these sample searches:
- BRK-123 → web search + LLM
- LM358 → web search + LLM
- Huion ST300 → web search + LLM
- C7CCGH00N72J → returns “Part not found” (no hallucination).

### API Testing - Terminal
Try these sample searches:
```bash
curl "https://partspec.onrender.com/search?q=LM358"
```
This would search up LM358 and return something like this:

{"partNumber":"LM358","name":"Dual Differential Input Operational Amplifier","description":"A general-purpose op amp that can operate at 30 V and 700 kHz","category":"Electrical","material":null,"weight":null,"dimensions":null,"tolerance":null,"finish":null,"manufacturer":"['Texas Instruments', 'Motorola, Inc', 'STMicroelectronics']","price":null,"stockStatus":null,"datasheetURL":"https://www.ti.com/product/LM358","certifications":null,"specifications":[{"key":"Operating Voltage","value":"30 V"},{"key":"Bandwidth","value":"700 kHz"},{"key":"Number of Channels","value":"2"},{"key":"Package Type","value":"SOIC, SOT23-8, etc."},{"key":"Operating Temperature","value":"-40 to 125°C (typical)"},{"key":"Supply Current","value":"0.5 to 2.5 mA (typical)"},{"key":"Offset Voltage","value":"2 to 5 mV (typical)"}]}

This a JSON response containing all the information the API found from the internet about part LM358