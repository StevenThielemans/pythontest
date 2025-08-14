#!/usr/bin/env python3
import argparse, math, sys, csv, time, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd

from sites.immoweb import scrape_immoweb_listings
from sites.zimmo import scrape_zimmo_listings

def annuity_payment(principal: float, annual_rate: float, years: int) -> float:
    """Monthly annuity payment (principal+interest)."""
    if annual_rate <= 0:
        return principal / (years * 12)
    r = annual_rate / 12
    n = years * 12
    return principal * (r * (1 + r)**n) / ((1 + r)**n - 1)

def evaluate_listing(row, args):
    price = float(row.get("price", 0) or 0)
    area = float(row.get("area_m2", 0) or 0)

    # Estimated rent baseline: rent-per-m2 (user supplied) with min/max guardrails
    rent_pm2 = args.rent_per_m2
    est_rent = rent_pm2 * area if (rent_pm2 and area) else args.fallback_rent
    # Clamp to sensible bounds if provided
    if args.min_rent and est_rent < args.min_rent:
        est_rent = args.min_rent
    if args.max_rent and est_rent > args.max_rent:
        est_rent = args.max_rent

    # Purchase costs
    registration = price * args.registration_rate
    notary = price * args.notary_rate
    purchase_total = price + registration + notary + args.renovation_buffer

    # Financing
    loan_amt = price * args.ltv
    equity = purchase_total - loan_amt
    monthly_pi = annuity_payment(loan_amt, args.mortgage_rate, args.mortgage_years)

    # Operating costs (monthly)
    vacancy = est_rent * args.vacancy_rate
    maintenance = est_rent * args.maintenance_rate
    prop_tax = args.property_tax_monthly
    insurance = args.insurance_monthly
    mgmt = est_rent * args.management_rate

    monthly_costs = monthly_pi + vacancy + maintenance + prop_tax + insurance + mgmt
    monthly_net = est_rent - monthly_costs
    annual_net = monthly_net * 12

    gross_yield = (est_rent * 12) / price if price else 0
    net_yield_on_price = annual_net / price if price else 0
    net_yield_on_equity = annual_net / equity if equity else 0

    return {
        **row,
        "purchase_price": price,
        "purchase_total": purchase_total,
        "equity_needed": equity,
        "est_rent_month": est_rent,
        "monthly_PI": monthly_pi,
        "monthly_costs": monthly_costs,
        "monthly_net_cashflow": monthly_net,
        "annual_net_cashflow": annual_net,
        "gross_yield": gross_yield,
        "net_yield_on_price": net_yield_on_price,
        "net_yield_on_equity": net_yield_on_equity,
        "ppsqm": (price / area) if area else None,
    }

def fetch_listings(args):
    listings = []
    if args.csv:
        df = pd.read_csv(args.csv)
        listings = df.to_dict(orient="records")
    elif args.source == "immoweb":
        listings = scrape_immoweb_listings(args.url, args.pages, args.pause)
    elif args.source == "zimmo":
        listings = scrape_zimmo_listings(args.url, args.pages, args.pause)
    else:
        raise SystemExit("Provide --source immoweb|zimmo or --csv <file>.")
    # Filter by city if provided
    if args.city:
        listings = [x for x in listings if args.city.lower() in str(x.get("city","")).lower()]
    return listings

def main():
    p = argparse.ArgumentParser(description="Buy-to-Let evaluator from scraped listings or CSV")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--source", choices=["immoweb","zimmo"], help="Listing site adapter")
    src.add_argument("--csv", help="CSV with columns: price,area_m2,bedrooms,city,url")

    p.add_argument("--url", help="Search/result URL to scrape")
    p.add_argument("--pages", type=int, default=1, help="How many pages to fetch")
    p.add_argument("--pause", type=float, default=2.0, help="Seconds between requests (be polite)")
    p.add_argument("--city", help="Filter by city name (contains)")

    # Assumptions
    p.add_argument("--rent-per-m2", dest="rent_per_m2", type=float, default=10.0)
    p.add_argument("--fallback-rent", type=float, default=1000.0)
    p.add_argument("--min-rent", type=float, default=None)
    p.add_argument("--max-rent", type=float, default=None)

    p.add_argument("--ltv", type=float, default=0.8)
    p.add_argument("--mortgage-rate", type=float, default=0.036)
    p.add_argument("--mortgage-years", type=int, default=25)

    p.add_argument("--registration-rate", type=float, default=0.10)
    p.add_argument("--notary-rate", type=float, default=0.03)
    p.add_argument("--renovation-buffer", type=float, default=10000.0)

    p.add_argument("--vacancy-rate", type=float, default=0.05)
    p.add_argument("--maintenance-rate", type=float, default=0.05)
    p.add_argument("--management-rate", type=float, default=0.0)

    p.add_argument("--property-tax-monthly", type=float, default=75.0)
    p.add_argument("--insurance-monthly", type=float, default=25.0)

    p.add_argument("--out", default="listings_evaluated.csv")

    args = p.parse_args()

    # Fetch
    listings = fetch_listings(args)
    if not listings:
        print("No listings fetched. Check your URL/CSV/filters.", file=sys.stderr)
        sys.exit(1)

    # Evaluate
    evaluated = [evaluate_listing(x, args) for x in listings]
    df = pd.DataFrame(evaluated)

    # Ranking heuristics
    df["rank_score"] = (
        (df["gross_yield"].fillna(0) * 0.4) +
        (df["net_yield_on_equity"].fillna(0) * 0.4) +
        (df["monthly_net_cashflow"].fillna(0) / 1000.0 * 0.2)
    )
    df = df.sort_values(by="rank_score", ascending=False)

    # Save CSV
    df.to_csv(args.out, index=False)
    print(f"Saved evaluated listings to {args.out}")
    # Show top 10 summary
    cols = ["price","area_m2","bedrooms","city","ppsqm","est_rent_month",
            "gross_yield","net_yield_on_equity","monthly_net_cashflow","url"]
    print(df[cols].head(10).to_string(index=False))

if __name__ == "__main__":
    main()
