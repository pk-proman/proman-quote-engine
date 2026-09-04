# PROMAN Quotation Engine — Web App

FastAPI + vanilla-JS single-page app for generating techno-commercial proposals.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
uvicorn main:app --reload --port 8000

# 3. Open in browser
open http://localhost:8000
```

## Project Structure

```
proman-web/
├── main.py                         FastAPI application + all API routes
├── requirements.txt
├── engine/
│   ├── rate_card.py                Master equipment price database
│   ├── engine.py                   Quotation builder (PlantSpec → Quotation)
│   ├── triage.py                   Enquiry routing (out-of-scope / standalone / qualify / quote)
│   ├── generate_xlsx.py            Annexure-4 Excel price schedule
│   └── generate_offer_letter.py    Word offer letter (Cover + Annexures 1,3,4,5,6)
└── static/
    └── index.html                  Single-page frontend (no build step)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/triage` | Route a raw enquiry text |
| POST | `/api/quote` | Build a full plant quotation (JSON) |
| POST | `/api/quote/standalone` | Price a single equipment |
| POST | `/api/quote/download/xlsx` | Download price schedule as Excel |
| POST | `/api/quote/download/docx` | Download offer letter as Word |
| POST | `/api/quote/standalone/download/docx` | Standalone equipment offer letter |
| GET  | `/api/rate-card/equipment` | List all available models |
| GET  | `/health` | Health check |

## Example API Call

```python
import requests, json

req = {
    "client_name": "Ramesh Quarries",
    "tph": 500,
    "stages": 3,
    "material": "Granite",
    "products": ["GSB", "-40+20mm", "-20+10mm", "-10+6mm", "0-4.75mm"],
    "ref_no": "PR/09-26/N-002"
}

r = requests.post("http://localhost:8000/api/quote", json=req)
q = r.json()
print(f"Grand Total List: ₹{q['totals']['grand_total_list']}L")

# Download Excel
xlsx = requests.post("http://localhost:8000/api/quote/download/xlsx", json=req)
open("PriceSchedule.xlsx", "wb").write(xlsx.content)
```

## Updating Prices

Edit `engine/rate_card.py` — all prices are in `rate_card.py` as Python dicts.
No restart needed if running with `--reload`.

## Deployment

For production (e.g. on a VPS or internal server):

```bash
# With gunicorn
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or with Docker (add a Dockerfile)
docker build -t proman-quote .
docker run -p 8000:8000 proman-quote
```

## Flagged Items (confirm before client release)
- **VGF 1600×6000**: Price entered as ₹9.8L — confirm List vs Best split
- **Jaw 50"×40"**: Price ₹3.2L confirmed by sales — verify this is full crusher, not liner only
- **VSI 5080 2×300**: Single-tier price — confirm List/Best breakdown
