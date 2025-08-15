import json, re, time
from typing import List, Dict, Optional

import requests

# Optional browser fallback (Playwright)
try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except Exception:
    _PLAYWRIGHT_AVAILABLE = False

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.immoweb.be/",
}

def _clean_int(x):
    if x is None: return None
    if isinstance(x, (int, float)): return int(x)
    s = re.sub(r"[^\d]", "", str(x))
    return int(s) if s else None

def _clean_float(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = re.sub(r"[^\d.,]", "", str(x)).replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def _parse_from_next_data(html: str) -> Optional[List[Dict]]:
    """
    Primary: parse <script id="__NEXT_DATA__"> JSON (Next.js) and walk until classifieds.
    """
    m = re.search(r'<script\s+id="__NEXT_DATA__"[^>]*>\s*({.+?})\s*</script>', html, re.S)
    if not m: 
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    # Heuristic walk to find list-like classifieds
    found = []
    def walk(obj):
        if isinstance(obj, dict):
            # Common keys that hold listings arrays
            for k in ("classifieds", "items", "results", "list", "properties"):
                v = obj.get(k)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    found.extend(v)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    return found or None

def _parse_from_initial_state(html: str) -> Optional[List[Dict]]:
    """
    Secondary: parse window.__INITIAL_STATE__ = {...};
    """
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>", html, re.S)
    if not m: 
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    found = []
    def walk(obj):
        if isinstance(obj, dict):
            for k in ("classifieds", "items", "results", "list", "properties"):
                v = obj.get(k)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    found.extend(v)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    walk(data)
    return found or None

def _parse_from_window_classifieds(html: str) -> Optional[List[Dict]]:
    """
    Tertiary: window.classifieds = [ {...}, ... ];
    """
    m = re.search(r"window\.classifieds\s*=\s*(\[\s*{.*?}\s*]);", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

def _normalize_items(items: List[Dict]) -> List[Dict]:
    """
    Map Immoweb JSON variations to our common dict format.
    """
    out = []
    for it in items:
        # Some structures nest data under different keys
        price_obj = it.get("price") or {}
        prop = it.get("property") or it.get("realEstate") or {}
        loc = prop.get("location") if isinstance(prop, dict) else {}
        cid = it.get("id") or it.get("classifiedId")

        price = price_obj.get("mainValue") or it.get("priceValue") or price_obj.get("value")
        area = (prop.get("netHabitableSurface") or prop.get("netHabitable") or
                prop.get("livingArea") or prop.get("surface"))
        bedrooms = prop.get("bedroomCount") or prop.get("bedrooms")
        city = (loc.get("locality") or loc.get("localityName") or "")
        postal = (loc.get("postalCode") or "")
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

def _http_fetch(url: str, headers: Dict = None, timeout: int = 30) -> str:
    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.text

def _browser_fetch(url: str, wait_selector: str = "body", timeout_ms: int = 15000) -> str:
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=DEFAULT_HEADERS["User-Agent"], locale="en-US")
        page = context.new_page()
        # Try to click consent if present
        page.goto(url, timeout=timeout_ms)
        try:
            page.get_by_role("button", name=re.compile("accept|agree", re.I)).click(timeout=3000)
        except Exception:
            pass
        # Wait for network to be idle-ish
        page.wait_for_timeout(1200)
        html = page.content()
        context.close()
        browser.close()
        return html

def scrape_immoweb_listings(search_url: str, pages: int = 1, pause: float = 1.5,
                            use_browser: bool = False) -> List[Dict]:
    """
    Robust Immoweb scraper:
    - Tries to parse embedded JSON via HTTP (fast, low footprint).
    - If none found and use_browser=True, renders with Playwright and retries parsing.
    """
    results: List[Dict] = []
    for page in range(1, max(1, pages) + 1):
        url = search_url
        if "page=" in url:
            url = re.sub(r"page=\d+", f"page={page}", url)
        else:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}page={page}"

        html = ""
        try:
            html = _http_fetch(url)
        except Exception as e:
            # If HTTP failed and browser mode requested, try browser fetch
            if use_browser:
                try:
                    html = _browser_fetch(url)
                except Exception as be:
                    print(f"Browser fetch failed: {be}")
                    break
            else:
                print(f"HTTP fetch failed on page {page}: {e}")
                break

        items = (_parse_from_next_data(html) or
                 _parse_from_initial_state(html) or
                 _parse_from_window_classifieds(html))

        if not items and use_browser:
            # If HTTP didn’t surface JSON, try browser content explicitly
            try:
                html = _browser_fetch(url)
                items = (_parse_from_next_data(html) or
                         _parse_from_initial_state(html) or
                         _parse_from_window_classifieds(html))
            except Exception as be:
                print(f"Browser retry failed: {be}")

        if not items:
            # Stop paging if nothing is found on the first page (likely consent/structure change)
            print(f"No embedded listings JSON found on page {page}.")
            if page == 1:
                break
            else:
                continue

        normalized = _normalize_items(items)
        results.extend(normalized)
        time.sleep(max(0.3, pause))
    return results
