# 2026.05.08  18.00
from fastapi import APIRouter
import requests
import re
import os
import dlt
from datetime import datetime
from pydantic import BaseModel
from bs4 import BeautifulSoup

class SerperRequest(BaseModel):
    city: str
    limit: int = 10

SERPER_KEY = os.getenv("SERPER_API_KEY")
DB_CONFIG = {"host": "postgresql", "port": 5432, "database": "n8n", "username": "sql_admin", "password": "sql_pass", "connect_timeout": 15}

router = APIRouter()

# --- dlt resource ---
@dlt.resource(name="companies_email", max_table_nesting=0)
def companies_resource(data):
    yield from data

# --- Email helpers ---
EMAIL_REGEX = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"

def scrape_emails_from_url(url: str) -> list[str]:
    try:
        resp = requests.get(url, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        emails = re.findall(EMAIL_REGEX, soup.get_text())
        return list(set(emails))
    except Exception:
        return []

def search_email_via_serper(company_name: str, address: str) -> list[str]:
    try:
        url = "https://google.serper.dev/search"
        payload = {"q": f"{company_name} {address} email contact"}
        resp = requests.post(url, headers={'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}, json=payload)
        resp.raise_for_status()
        emails = re.findall(EMAIL_REGEX, json.dumps(resp.json()))
        return list(set(emails))
    except Exception:
        return []

def find_emails(website: str, company_name: str, address: str) -> str:
    emails = []
    if website and website != "UNKNOWN":
        emails = scrape_emails_from_url(website)
    if not emails:
        emails = search_email_via_serper(company_name, address)
    return ", ".join(emails) if emails else "UNKNOWN"

# --- Core logic ---
def fetch_serper(city: str, limit: int):
    url = "https://google.serper.dev/places"

    variations = [
        "shipping", "transport", "logistics", "freight forwarding", "warehouse", "shopping", "delivery", "factory", "producing", "transportation",
        "apartment", "hotel", "guesthouse", "car service", "company", "business", "office", "IT company", "restaurant"]

    results_map = {}

    for v in variations:
        if len(results_map) >= limit:
            break

        payload = {"q": f"{v} in {city}", "gl": "hu", "hl": "hu"}
        resp = requests.post(url, headers={'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}, json=payload)
        resp.raise_for_status()
        places = resp.json().get("places", [])

        for p in places:
            key = (p.get("title"), p.get("address"))

            if key not in results_map:
                name    = p.get("title") or "UNKNOWN"
                address = p.get("address") or "UNKNOWN"
                website = p.get("website") or "UNKNOWN"

                results_map[key] = {
                    "cid":         p.get("cid"),
                    "name":        name,
                    "address":     address,
                    "rating":      p.get("rating") or "UNKNOWN",
                    "reviews":     p.get("ratingCount") or "UNKNOWN",
                    "latitude":    p.get("latitude") or "UNKNOWN",
                    "longitude":   p.get("longitude") or "UNKNOWN",
                    "category":    p.get("category") or "UNKNOWN",
                    "phoneNumber": p.get("phoneNumber") or "UNKNOWN",
                    "website":     website,
                    "email":       find_emails(website, name, address), 
                    "city":        city,
                    "_ingested_at": datetime.utcnow().isoformat()
                }

    return list(results_map.values())[:limit]

# -----------------------------------------------------------------------------
@router.post("/")
def get_companies(req: SerperRequest):
    data = fetch_serper(req.city, req.limit)

    pipeline = dlt.pipeline(
        pipeline_name="serper_companies",
        destination=dlt.destinations.postgres(credentials=DB_CONFIG),
        dataset_name="serper"
    )

    try:
        load_info = pipeline.run(companies_resource(data), write_disposition="merge", primary_key=["name", "address"])
    except Exception as e:
        print(f"Pipeline failed: {e}")
        raise

    return {"rows": len(data), "status": "loaded", "load_info": str(load_info), "sample": data[:3]}
