
import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

st.set_page_config(page_title="Stock Scanner", layout="wide")
st.title("📈 Fundamental Stock Scanner")

tickers_input = st.text_input("Enter tickers separated by comma (e.g., AAPL, MSFT, NVDA)", "AAPL, MSFT, NVDA")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

max_pe = st.slider("Max PE Ratio", 0, 100, 20)
min_eps = st.slider("Min EPS Growth %", -100, 100, 10)
run = st.button("Run Scan")

if run:
    results = []
    for tkr in tickers:
        try:
            stock = yf.Ticker(tkr)
            info = stock.info
            pe = info.get("trailingPE", np.nan)
            eps_growth = info.get("earningsQuarterlyGrowth", np.nan) * 100 if info.get("earningsQuarterlyGrowth") else np.nan
            passes = (pe < max_pe) and (eps_growth > min_eps)
            results.append({
                "Ticker": tkr,
                "PE": pe,
                "EPS Growth %": eps_growth,
                "Passes": passes
            })
        except Exception:
            results.append({
                "Ticker": tkr,
                "PE": None,
                "EPS Growth %": None,
                "Passes": False
            })

    df = pd.DataFrame(results).set_index("Ticker")
    st.dataframe(df)
    st.download_button("Download Results", df.to_csv().encode("utf-8"), "stock_scan.csv", "text/csv")
