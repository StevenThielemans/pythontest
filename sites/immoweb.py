import re, json, time
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def _clean_int(s):
    if s is None: return None
    if isinstance(s, (int, float)): return int(s)
    d = re.sub(r"[^\d]", "", str(s))
    return int(d) if d else None

def _clean_float(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    d = re.sub(r"[^\d.,]", "", str(s)).replace(",", ".")
    try:
        return float(d)
    except Exception:
        return None

def _extract_from_next_data(html: str):
    m = re.search(r'<script\s+id="__NEXT_DATA__"[^>]*>\s*({.+?})\s*</script>', html, re.S)
    if not m: return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    found = []
    def walk(o):
        if isinstance(o, dict):
            for k in ("classifieds","items","results","list","properties"):
                v = o.get(k)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    found.extend(v)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    return found or None

def _extract_from_window_initial_state(html: str):
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>", html, re.S)
    if not m: return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    found = []
    def walk(o):
        if isinstance(o, dict):
            for k in ("classifieds","items","results","list","properties"):
                v = o.get(k)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    found.extend(v)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    return found or None

def _extract_from_window_classifieds(html: str):
    m = re.search(r"window\.classifieds\s*=\s*(\[\s*{.*?}\s*]);", html, re.S)
    if not m: return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

def _normalize_json_items(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items:
        price_obj = it.get("price") or {}
        prop = it.get("property") or it.get("realEstate") or {}
        loc = prop.get("location") if isinstance(prop, dict) else {}
        cid = it.get("id") or it.get("classifiedId")
        price = price_obj.get("mainValue") or it.get("priceValue") or price_obj.get("value")
        area = prop.get("netHabitableSurface") or prop.get("livingArea") or prop.get("surface")
        bedrooms = prop.get("bedroomCount") or prop.get("bedrooms")
        city = (loc.get("locality") or loc.get("localityName") or "")
        postal = loc.get("postalCode") or ""
        if city and postal:
            city = f"{postal} {city}"
        price = _clean_int(price)
        area = _clean_float(area)
        bedrooms = _clean_int(bedrooms)
        link = f"https://www.immoweb.be/en/classified/{cid}" if cid else None
        if price:
            out.append({
                "price": float(price),
                "area_m2": float(area) if area else None,
                "bedrooms": bedrooms,
                "city": city,
                "url": link,
            })
    return out

def _extract_from_cards(html: str) -> List[Dict]:
    """
    Parse listing cards present in your saved page:
    - li.search-results__item > article#classified_...
    - price in p.card--result__price.price__formatted
    - details in p.card__information--property (e.g. '3 bdr. · 208 m²')
    - city in the next p.card__information (e.g. '5100 JAMBES')
    """
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select("li.search-results__item"):
        art = li.select_one("article[id^=classified_]")
        if not art:
            continue
        link_tag = art.select_one("h2 a[href]")
        url = link_tag["href"] if link_tag else None

        # Price
        price_el = art.select_one("p.card--result__price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        price = _clean_int(price_text)

        # Property info: bedrooms + m²
        info_prop = art.select_one("p.card__information--property")
        bedrooms = None
        area = None
        if info_prop:
            txt = info_prop.get_text(" ", strip=True)
            m_bed = re.search(r"(\d+)\s*bdr", txt, re.I)
            if m_bed: bedrooms = _clean_int(m_bed.group(1))
            m_area = re.search(r"(\d+[.,]?\d*)\s*m²", txt, re.I)
            if m_area: area = _clean_float(m_area.group(1))

        # City line: usually the next p.card__information in the same block
        city = None
        # Try the sibling info elements
        all_info = art.select("div.card__informations p.card__information")
        if all_info:
            for p in all_info:
                if "property" in p.get("class", []):
                    continue
                city = p.get_text(" ", strip=True)
                break

        if price:
            out.append({
                "price": float(price),
                "area_m2": float(area) if area else None,
                "bedrooms": bedrooms,
                "city": city,
                "url": url,
            })
    return out

def scrape_immoweb_listings(search_url: str, pages: int = 1, pause: float = 1.5) -> List[Dict]:
    results: List[Dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max(1, pages) + 1):
        url = search_url
        if "page=" in url:
            url = re.sub(r"page=\d+", f"page={page}", url)
        else:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}page={page}"

        r = session.get(url, timeout=30)
        if r.status_code != 200:
            print(f"HTTP {r.status_code} on page {page}")
            break

        html = r.text

        # 1) Try HTML cards (works on your file)
        card_items = _extract_from_cards(html)
        if card_items:
            results.extend(card_items)
            time.sleep(max(0.3, pause))
            continue

        # 2) Fallbacks: embedded JSON variants
        for extractor in (_extract_from_next_data, _extract_from_window_initial_state, _extract_from_window_classifieds):
            items = extractor(html)
            if items:
                results.extend(_normalize_json_items(items))
                break

        time.sleep(max(0.3, pause))

    # Deduplicate by URL
    seen = set()
    dedup = []
    for x in results:
        key = x.get("url") or (x.get("price"), x.get("area_m2"), x.get("city"))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(x)

    return dedup
