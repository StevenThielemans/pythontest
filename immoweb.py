import time, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
}

def parse_price(txt):
    if not txt: return None
    # Remove currency, spaces, dots, commas
    nums = re.sub(r"[^\d]", "", txt)
    return float(nums) if nums else None

def parse_area(txt):
    if not txt: return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m", txt.lower())
    if not m: return None
    return float(m.group(1).replace(",", "."))

def scrape_immoweb_listings(url, pages=1, pause=2.0):
    """Scrape Immoweb search result pages.
    NOTE: HTML structure can change. Update selectors if needed.
    """
    results = []
    page_url = url
    for page in range(1, pages+1):
        u = page_url if page == 1 else f"{url}&page={page}"
        r = requests.get(u, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            time.sleep(pause)
            continue
        soup = BeautifulSoup(r.text, "lxml")

        # Each card container
        cards = soup.select("div.card--result, div.search-results__item")
        if not cards:
            # Fallback to article elements
            cards = soup.select("article")
        for c in cards:
            # Link
            a = c.select_one("a") or c.find("a", href=True)
            link = a["href"] if a and a.has_attr("href") else None
            if link and link.startswith("/"):
                link = urljoin("https://www.immoweb.be", link)

            # Price
            price_el = c.select_one('[class*="price"], .card__price, .srp-card-price")
            price_txt = price_el.get_text(" ", strip=True) if price_el else None
            price = parse_price(price_txt)

            # Area
            # Try common detail items
            detail_txt = " ".join([x.get_text(" ", strip=True) for x in c.select("[class*='property-info'], li, span")])
            area = parse_area(detail_txt)

            # Beds
            beds = None
            m = re.search(r"(\d+)\s*(?:bed|slaap|chambre)", detail_txt, re.I)
            if m:
                beds = int(m.group(1))

            # City
            loc_el = c.select_one('[class*="locality"], [class*="location"], [class*="address"]')
            city = loc_el.get_text(" ", strip=True) if loc_el else ""

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
