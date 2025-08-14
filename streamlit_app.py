import streamlit as st
import pandas as pd
from io import StringIO
from sites.immoweb import scrape_immoweb_listings
from sites.zimmo import scrape_zimmo_listings
from app import evaluate_listing

st.set_page_config(page_title="Buy-to-Let Evaluator", layout="wide")
st.title("🏠 Buy-to-Let Property Evaluator")

st.markdown("Paste a search URL from **Immoweb** or **Zimmo**, set your assumptions, and get yield/cashflow rankings.")

with st.sidebar:
    st.header("Data source")
    source = st.selectbox("Listing source", ["immoweb", "zimmo", "CSV upload"])
    url = ""
    pages = 1
    uploaded_csv = None
    if source in ("immoweb", "zimmo"):
        url = st.text_input("Search URL", "")
        pages = st.number_input("Pages to scrape", min_value=1, max_value=10, value=1)
    else:
        uploaded_csv = st.file_uploader("Upload CSV", type="csv")

    st.header("Filters")
    city = st.text_input("City filter (optional)", "")

    st.header("Rent assumptions")
    rent_per_m2 = st.number_input("Rent per m² (€)", value=10.0, step=0.5)
    fallback_rent = st.number_input("Fallback rent (€)", value=1000.0, step=50.0)
    min_rent = st.number_input("Min rent (€)", value=0.0, step=50.0)
    max_rent = st.number_input("Max rent (€)", value=0.0, step=50.0)

    st.header("Financing")
    ltv = st.slider("Loan-to-Value (LTV)", 0.0, 1.0, 0.8, 0.05)
    mortgage_rate = st.number_input("Mortgage rate (annual, decimal)", value=0.036, step=0.001, format="%.3f")
    mortgage_years = st.number_input("Mortgage years", value=25, step=1)

    st.header("Purchase costs")
    registration_rate = st.number_input("Registration rate", value=0.10, step=0.01, format="%.2f")
    notary_rate = st.number_input("Notary rate", value=0.03, step=0.01, format="%.2f")
    renovation_buffer = st.number_input("Renovation buffer (€)", value=10000.0, step=1000.0)

    st.header("Operating costs")
    vacancy_rate = st.number_input("Vacancy rate", value=0.05, step=0.01, format="%.2f")
    maintenance_rate = st.number_input("Maintenance rate", value=0.05, step=0.01, format="%.2f")
    management_rate = st.number_input("Management rate", value=0.0, step=0.01, format="%.2f")
    property_tax_monthly = st.number_input("Property tax monthly (€)", value=75.0, step=5.0)
    insurance_monthly = st.number_input("Insurance monthly (€)", value=25.0, step=5.0)

if st.button("Fetch & Evaluate Listings"):
    listings = []
    if source == "CSV upload" and uploaded_csv:
        df = pd.read_csv(uploaded_csv)
        listings = df.to_dict(orient="records")
    elif source == "immoweb" and url:
        listings = scrape_immoweb_listings(url, pages, pause=2.0)
    elif source == "zimmo" and url:
        listings = scrape_zimmo_listings(url, pages, pause=2.0)

    if city:
        listings = [x for x in listings if city.lower() in str(x.get("city","")).lower()]

    if not listings:
        st.warning("No listings found. Check URL or CSV.")
    else:
        class Args: pass
        args = Args()
        args.rent_per_m2 = rent_per_m2
        args.fallback_rent = fallback_rent
        args.min_rent = min_rent or None
        args.max_rent = max_rent or None
        args.ltv = ltv
        args.mortgage_rate = mortgage_rate
        args.mortgage_years = mortgage_years
        args.registration_rate = registration_rate
        args.notary_rate = notary_rate
        args.renovation_buffer = renovation_buffer
        args.vacancy_rate = vacancy_rate
        args.maintenance_rate = maintenance_rate
        args.management_rate = management_rate
        args.property_tax_monthly = property_tax_monthly
        args.insurance_monthly = insurance_monthly

        evaluated = [evaluate_listing(x, args) for x in listings]
        df = pd.DataFrame(evaluated)
        df["rank_score"] = (
            (df["gross_yield"].fillna(0) * 0.4) +
            (df["net_yield_on_equity"].fillna(0) * 0.4) +
            (df["monthly_net_cashflow"].fillna(0) / 1000.0 * 0.2)
        )
        df = df.sort_values(by="rank_score", ascending=False)

        st.success(f"Evaluated {len(df)} listings")
        st.dataframe(df)

        csv_buf = StringIO()
        df.to_csv(csv_buf, index=False)
        st.download_button("Download CSV", csv_buf.getvalue(), "evaluated_listings.csv", "text/csv")
