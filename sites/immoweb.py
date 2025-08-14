import requests
import re
import json
import time

def scrape_immoweb_listings(search_url, pages=1, pause=2.0):
    """
    Scrape Immoweb listings from their embedded JSON data.
    
    Args:
        search_url (str): Immoweb search URL without &page= parameter.
        pages (int): Number of pages to scrape.
        pause (float): Seconds between requests.
    
    Returns:
        list of dict: price, area, bedrooms, city, url.
    """
    listings = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }

    for page in range(1, pages + 1):
        url = f"{search_url}&page={page}"
        print(f"Fetching: {url}")

        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Error {resp.status_code} on page {page}")
            break

        html = resp.text

        # Immoweb embeds listings JSON in a <script> tag, usually in window.classifieds
        match = re.search(r"window\.classifieds\s*=\s*(\[\{.*?\}\]);", html, re.S)
        if not match:
            print(f"No JSON data found on page {page}")
            break

        json_data = json.loads(match.group(1))

        for item in json_data:
            try:
                price = item.get("price", {}).get("mainValue")
                area = item.get("property", {}).get("netHabitableSurface")
                bedrooms = item.get("property", {}).get("bedroomCount")
                city = item.get("property", {}).get("location", {}).get("locality")
                link = f"https://www.immoweb.be/en/classified/{item.get('id')}"

                listings.append({
                    "price": price,
                    "area": area,
                    "bedrooms": bedrooms,
                    "city": city,
                    "url": link
                })
            except Exception as e:
                print(f"Error parsing item: {e}")

        time.sleep(pause)

    return listings
