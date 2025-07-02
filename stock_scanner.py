
"""
Streamlit Stock Scanner Web App
==============================

A mobile-friendly web UI for the fundamental + quant stock scanner.

Features
--------
* **Undervalued** (PE < 15 or EV/EBITDA < 12)
* **Growth** (Revenue and EPS YoY > 10 %)
* **Risk-adjusted return** (Sortino > 1.0, 3-year daily)
* **Alpha vs SPY** (annualised α > 0)
* **Profitability** (CROCI > 15 %)
* Customisable thresholds via sidebar sliders
* Scan **S&P 500** or any user-typed list of tickers
* One-click **Excel download** of passing stocks
* Optional **Google Sheets upload** (service-account JSON uploader)

Run locally:
```bash
pip install -r requirements.txt
streamlit run stock_scanner.py
```

Deploy for free on **Streamlit Community Cloud**: push this repo to GitHub, create a new Streamlit app, set the main file to `stock_scanner.py`.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from scipy import stats

# --------------------------- Helper Functions ------------------------------ #

def sortino_ratio(returns: pd.Series, rf: float = 0.0) -> float:
    """Calculate the Sortino ratio (using downside deviation)."""
    downside = returns[returns < rf]
    downside_dev = np.sqrt((downside ** 2).mean())
    if downside_dev == 0 or np.isnan(downside_dev):
        return np.nan
    return (returns.mean() - rf) / downside_dev


def annualise(value: float, periods_per_year: int = 252) -> float:
    return value * periods_per_year


def get_alpha(returns: pd.Series, benchmark: pd.Series) -> float:
    """Jensen's alpha via CAPM regression."""
    aligned = pd.concat([returns, benchmark], axis=1, join="inner")
    y, x = aligned.iloc[:, 0], aligned.iloc[:, 1]
    if len(x) < 30:
        return np.nan
    slope, intercept, *_ = stats.linregress(x, y)
    return intercept


def get_croci(cash_flow: pd.DataFrame, balance: pd.DataFrame) -> float:
    """CROCI = (CFO − CapEx) / Invested Capital (latest FY)."""
    try:
        cfo = cash_flow.loc["Total Cash From Operating Activities"].iloc[0]
        capex = cash_flow.loc["Capital Expenditures"].iloc[0]
        equity = balance.loc["Total Stockholder Equity"].iloc[0]
        debt = balance.loc["Total Debt"].iloc[0]
        invested_capital = equity + debt
        return (cfo - capex) / invested_capital * 100
    except Exception:
        return np.nan


def growth(df: pd.DataFrame, metric: str) -> float:
    try:
        latest, prev = df.loc[metric].iloc[:2]
        return (latest - prev) / abs(prev) * 100
    except Exception:
        return np.nan


# --------------------------- Scanner Core ---------------------------------- #

def scan_ticker(
    ticker: str,
    benchmark_returns: pd.Series,
    thr: Dict[str, float],
) -> Optional[Dict[str, float]]:
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3y", interval="1d")["Close"].pct_change().dropna()
        if len(hist) < 252:
            return None

        info = tk.info or {}
        pe = info.get("trailingPE", np.nan)
        ev_ebitda = info.get("enterpriseToEbitda", np.nan)

        fin = tk.financials
        rev_growth = growth(fin, "Total Revenue")
        eps_growth = growth(fin, "Diluted EPS")

        sortino = sortino_ratio(hist)
        alpha = annualise(get_alpha(hist, benchmark_returns))

        croci = get_croci(tk.cashflow, tk.balance_sheet)

        passes = (
            (pe < thr["pe"] or ev_ebitda < thr["ev"])
            and (rev_growth > thr["rev"] and eps_growth > thr["eps"])
            and (sortino > thr["sortino"])
            and (alpha > thr["alpha"])
            and (croci > thr["croci"])
        )

        return {
            "Ticker": ticker,
            "PE": pe,
            "EV/EBITDA": ev_ebitda,
            "Rev YoY %": rev_growth,
            "EPS YoY %": eps_growth,
            "Sortino": sortino,
            "Alpha": alpha,
            "CROCI %": croci,
            "Pass": passes,
        }
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def get_benchmark_returns() -> pd.Series:
    return yf.Ticker("SPY").history(period="3y", interval="1d")["Close"].pct_change().dropna()


@st.cache_data(show_spinner=False)
def get_sp500() -> List[str]:
    return yf.tickers_sp500()


# --------------------------- Google Sheets --------------------------------- #

def upload_to_gsheets(df: pd.DataFrame, creds_json: bytes, sheet_url: str):
    import pygsheets  # local import to avoid heavy load if not needed

    gc = pygsheets.authorize(client_secret=json.loads(creds_json))
    sh = gc.open_by_url(sheet_url)
    wks = sh.sheet1
    wks.clear()
    wks.set_dataframe(df.reset_index(), start="A1", nan="")


# --------------------------- Streamlit UI ---------------------------------- #

st.set_page_config(page_title="Stock Scanner", layout="wide")
st.title("📈 Fundamental + Quant Stock Scanner")

st.markdown(
    "Scan undervalued growth stocks with healthy risk-adjusted returns and profitability.\n"
    "All calculations use the last 3 years of market & financial data from **Yahoo Finance**."
)

with st.sidebar:
    st.header("⚙️ Settings")

    default_universe = "S&P 500"
    universe_choice = st.radio("Universe", [default_universe, "Custom tickers"], horizontal=True)

    if universe_choice == default_universe:
        tickers = get_sp500()
        selected = st.multiselect("Optional: narrow to specific tickers", tickers)
        if selected:
            tickers = selected
    else:
        user_input = st.text_area("Enter tickers separated by space, comma, or newline")
        tickers = [t.strip().upper() for t in user_input.replace("\n", ",").replace(" ", ",").split(",") if t.strip()]

    st.subheader("Cut-off thresholds")
    thr = {
        "pe": st.number_input("Max PE", value=15.0),
        "ev": st.number_input("Max EV/EBITDA", value=12.0),
        "rev": st.number_input("Min Revenue YoY %", value=10.0),
        "eps": st.number_input("Min EPS YoY %", value=10.0),
        "sortino": st.number_input("Min Sortino", value=1.0),
        "alpha": st.number_input("Min Alpha (annualised)", value=0.0),
        "croci": st.number_input("Min CROCI %", value=15.0),
    }

    st.divider()
    gsheets_toggle = st.checkbox("Upload passing list to Google Sheets")
    sheet_url = ""
    creds_file = None
    if gsheets_toggle:
        sheet_url = st.text_input("Google Sheet URL")
        creds_file = st.file_uploader("Service account JSON", type="json")

run_btn = st.button("🚀 Run Scan", type="primary")

if run_btn:
    if not tickers:
        st.warning("Please specify at least one ticker.")
        st.stop()

    benchmark_returns = get_benchmark_returns()
    progress = st.progress(0, text=f"Scanning {len(tickers)} tickers…")
    rows = []
    for i, tkr in enumerate(tickers):
        res = scan_ticker(tkr, benchmark_returns, thr)
        if res:
            rows.append(res)
        progress.progress((i + 1) / len(tickers))

    df = pd.DataFrame(rows).set_index("Ticker")

    passing = (
        df[df["Pass"] == True]
        .drop(columns="Pass")
        .sort_values("Alpha", ascending=False)
    )

    st.subheader(f"✅ {len(passing)} stocks passed the screen")
    st.dataframe(passing, use_container_width=True, height=500)

    if len(passing):
        # Excel download
        def to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
            bio = BytesIO()
            with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                dataframe.to_excel(writer, sheet_name="Scan")
            return bio.getvalue()

        st.download_button(
            label="📥 Download Excel",
            data=to_excel_bytes(passing),
            file_name="stock_scanner_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Google Sheets
        if gsheets_toggle and sheet_url:
            if creds_file is None:
                st.warning("Please upload the service-account JSON to upload to Google Sheets.")
            else:
                try:
                    upload_to_gsheets(passing, creds_file.read(), sheet_url)
                    st.success("Uploaded to Google Sheets ✔️")
                except Exception as e:
                    st.error(f"Google Sheets error: {e}")

    else:
        st.info("No stocks met all the criteria.")
