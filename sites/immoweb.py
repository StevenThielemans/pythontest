import requests
from bs4 import BeautifulSoup
import time

def scrape_immoweb_listings(search_url, pages=1, pause=2.0):
    """
    Scrapes Immoweb property listings from a search URL.
    
    Args:
        search_url (str): Base search URL from Immoweb (no pagination parameter needed).
        pages (int): Number of pages to scrape.
        pause (float): Seconds to wait between page requests.
    
    Returns:
        list of dict: Each dict contains listing info (price, area, bedrooms, city, URL).
    """
    listings = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0.0.0 Safari/537.36"
    }
    
    for page in range(1, pages + 1):
        url = f"{search_url}&page={page}"
        print(f"Fetching page {page}: {url}")
        
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch page {page}: HTTP {resp.status_code}")
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Immoweb listings are inside <li> tags with class "search-results__item"
        items = soup.select("li.search-results__item")
        if not items:
            print(f"No listings found on page {page}.")
            break
        
        for item in items:
            try:
                link_tag = item.find("a", href=True)
                link = link_tag["href"] if link_tag else None
                
                price_tag = item.select_one(".card__price, .sr_price")
                price_text = price_tag.get_text(strip=True).replace("€", "").replace(",", "").replace(".", "")
                price = int(price_text) if price_text.isdigit() else None
                
                area_tag = item.select_one(".card__information--property")
                area = None
                if area_tag:
                    # Example: "145 m²"
                    area_str = area_tag.get_text(strip=True).lower().replace("m²", "").strip()
                    if area_str.isdigit():
                        area = int(area_str)
                
                beds_tag = item.find("li", {"class": "card__information--bedroom"})
                bedrooms = None
                if beds_tag:
                    beds_str = beds_tag.get_text(strip=True)
                    if beds_str.isdigit():
                        bedrooms = int(beds_str)
                
                city_tag = item.select_one(".card__title, .sr_location")
                city = city_tag.get_text(strip=True) if city_tag else None
                
                listings.append({
                    "price": price,
                    "area": area,
                    "bedrooms": bedrooms,
                    "city": city,
                    "url": link
                })
            except Exception as e:
                print(f"Error parsing listing: {e}")
        
        time.sleep(pause)
    
    return listings
