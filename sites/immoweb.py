import requests
import re
import json
import time
from typing import List, Dict

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

def _extract_embedded_json(html: str):
    m = re.search(r"window\.classifieds\s*=\s*(\[\{.*?\}\]);", html, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None

def scrape_immoweb_listings(search_url: str, pages: int = 1, pause: float = 2.0) -> List[Dict]:
    results: List[Dict] = []
    for page in range(1, pages + 1):
        url = f"{search_url}&page={page}" if "page=" not in search_url else re.sub(r"page=\\d+", f"page={page}", search_url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as e:
            print(f"Request error on page {page}: {e}")
            break

        if r.status_code != 200:
            print(f"HTTP {r.status_code} on page {page}")
            break

        data = _extract_embedded_json(r.text)
        if not data:
            print(f"No embedded JSON found on page {page}")
            break

        for it in data:
            try:
                price_obj = it.get("price") or {}
                prop = it.get("property") or {}
                price = price_obj.get("mainValue") or it.get("priceValue")
                area = prop.get("netHabitableSurface")
                bedrooms = prop.get("bedroomCount")
                loc = prop.get("location") or {}
                city = loc.get("locality") or ""
                cid = it.get("id")
                link = f"https://www.immoweb.be/en/classified/{cid}" if cid else None
                if isinstance(price, str):
                    digits = re.sub(r"[^\d]", "", price)
                    price = int(digits) if digits else None
                if isinstance(area, str):
                    digits = re.sub(r"[^\d.]", "", area.replace(",", "."))
                    area = float(digits) if digits else None
                if price:
                    results.append({
                        "price": float(price),
                        "area_m2": float(area) if area else None,
                        "bedrooms": int(bedrooms) if bedrooms else None,
                        "city": city,
                        "url": link
                    })
            except Exception as e:
                print(f"Parse error: {e}")

        time.sleep(pause)

    return results
