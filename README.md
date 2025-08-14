# Buy-to-Let Evaluator (Belgium/Generic)

This lightweight app scrapes listing pages (currently **Immoweb** and **Zimmo**) and
evaluates buy-to-let metrics (gross yield, net yield, cash flow, ROI).

> ⚠️ **Please respect each website's Terms of Service and robots.txt.**
> This tool is for educational use. If scraping is disallowed, use your own CSV
> (see `--csv` option) exported from the website or compiled manually.

## Features
- Scrape 1..N listing pages from Immoweb or Zimmo search results
- Parse price, bedrooms, area (m²), location, link
- Compute per-listing: price-per-m², gross yield, estimated rent, cash flow, net yield
- Configurable assumptions: registration duty, notary costs, vacancy, maintenance,
  property tax, insurance, mortgage rate/term/LTV, rent-per-m² baseline, etc.
- Output: CSV + on-screen summary of top candidates

## Quick Start

### 1) Install
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Run (Immoweb example)
```bash
python app.py   --source immoweb   --url "https://www.immoweb.be/en/search/house/for-sale/kortrijk?countries=BE&maxPrice=300000"   --pages 2   --city Kortrijk   --rent-per-m2 10.5   --ltv 0.8   --mortgage-rate 0.036   --mortgage-years 25   --registration-rate 0.10   --notary-rate 0.03
```

### 3) Run (Zimmo example)
```bash
python app.py   --source zimmo   --url "https://www.zimmo.be/en/kortrijk-8500/house/buy/"   --pages 2   --city Kortrijk
```

### 4) Run with your own CSV (no scraping)
Provide a CSV with columns: `price,area_m2,bedrooms,city,url` (headers required).
```bash
python app.py --csv my_listings.csv --city Kortrijk
```

### Notes
- HTML structures change. If parsing fails, check and update the adapters in `sites/`.
- Estimates are *rules of thumb*. Always verify rents with local comps and regulations.
- Registration duty, deductions, and rental rules differ by region and property type.
