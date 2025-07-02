# Stock Scanner Web App

A Streamlit web application that scans for undervalued growth stocks with healthy risk‑adjusted returns and profitability.  

## Features

- **Valuation:** PE < 15 *or* EV/EBITDA < 12  
- **Growth:** Revenue & EPS YoY > 10 %  
- **Risk-adjusted return:** Sortino > 1.0 (3‑year)  
- **Alpha:** Annualised α vs SPY > 0  
- **Profitability:** CROCI > 15 %  
- Customisable thresholds, S&P 500 or custom universe, Excel download, optional Google Sheets upload.

## Local run

```bash
pip install -r requirements.txt
streamlit run stock_scanner.py
```

Open the URL Streamlit prints (e.g. `http://localhost:8501`) in your browser or phone on the same Wi‑Fi network.

## Deploy on Streamlit Cloud (free)

1. Push these files to GitHub.  
2. Go to [share.streamlit.io](https://share.streamlit.io) → “New app”  
3. Select your repo, set **Main file** to `stock_scanner.py`, and deploy.  

Enjoy scanning! 📈