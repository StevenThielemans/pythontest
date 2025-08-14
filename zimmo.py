import time, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
}

def parse_price(txt):
    if not txt: return None
    nums = re.sub(r"[^\d]", "", txt)
    return float(nums) if nums else None

def parse_area(txt):
    if not txt: return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m", txt.lower())
    if not m: return None
    return float(m.group(1).replace(",", "."))

def scrape_zimmo_listings(url, pages=1, pause=2.0):
    results = []
    for page in range(1, pages+1):
        u = url if page == 1 else (url.rstrip("/") + f"/?page={page}")
        r = requests.get(u, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            time.sleep(pause)
            continue
        soup = BeautifulSoup(r.text, "lxml")

        cards = soup.select("article.property-item, div.property-item")
        if not cards:
            cards = soup.select("a[href*='/en/'], a[href*='/nl/']")
        for c in cards:
            # Link
            a = c.select_one("a[href]") if hasattr(c, "select_one") else c
            link = a["href"] if a and a.has_attr("href") else None
            if link and link.startswith("/"):
                link = urljoin("https://www.zimmo.be", link)

            # Price
            price_el = c.select_one('[class*="price"], .property-price, .price')
            price_txt = price_el.get_text(" ", strip=True) if price_el else None
            price = parse_price(price_txt)

            # Area & beds
            meta_txt = " ".join([x.get_text(" ", strip=True) for x in c.select("li, span, div")])
            area = parse_area(meta_txt)

            beds = None
            m = re.search(r"(\d+)\s*(?:bed|slaap|chambre)", meta_txt, re.I)
            if m:
                beds = int(m.group(1))

            # City
            city_el = c.select_one('[class*="location"], [class*="city"], [class*="address"]')
            city = city_el.get_text(" ", strip=True) if city_el else ""

            if price:
                results.append({
                    "price": price,
                    "area_m2": area,
                    "bedrooms": beds,
                    "city": city,
                    "url": link
                })
        time.sleep(pause)
    return results
