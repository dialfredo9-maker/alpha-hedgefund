import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V8", layout="wide")

st.markdown("""
<style>
.report-box { font-family: 'Courier New'; background-color: #0d1117; padding: 25px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)

# --- API KEYS ---
st.sidebar.markdown("### 🔑 APIs")
GEMINI_API_KEY = st.sidebar.text_input("Gemini API", type="password")
FMP_API_KEY = st.sidebar.text_input("FMP API", type="password")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- UTILIDADES ---
def div(n, d):
    try:
        if n is None or d is None or d == 0:
            return None
        return n / d
    except:
        return None

def pct(x):
    try:
        return None if x is None else round(x * 100, 2)
    except:
        return None

# --- BUSCADOR FLEXIBLE (FIX CLAVE) ---
def get_item(df, posibles_keys):
    for key in posibles_keys:
        if key in df.index:
            try:
                return df.loc[key].iloc[0]
            except:
                continue
    return None

# --- FMP ---
def get_fmp(ticker):
    if not FMP_API_KEY:
        return {}
    try:
        url = f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker}?limit=1&apikey={FMP_API_KEY}"
        return requests.get(url).json()[0]
    except:
        return {}

# --- IA ---
def analizar(data, m, score, senal):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    COMITÉ INSTITUCIONAL.

    DATA: {data}
    SCORE: {score}
    SEÑAL: {senal}
    MANDATO: {m}

    VALIDAR:
    - calidad (ROIC, SBC)
    - valoración (EV/FCF, PEG)
    - riesgos

    OUTPUT:
    IDENTIDAD
    VALUACIÓN
    RIESGO
    FINAL
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V8")

ticker = st.text_input("Ticker").upper()

if ticker:
    tk = yf.Ticker(ticker)
    fmp = get_fmp(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow
        bs = tk.balance_sheet

        # --- CORE ---
        rev = inc.loc['Total Revenue'].dropna()[::-1]
        fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

        cagr = (rev.iloc[-1]/rev.iloc[0])**(1/(len(rev)-1)) - 1 if len(rev)>1 else None
        fcf_cagr = (fcf.iloc[-1]/fcf.iloc[0])**(1/(len(fcf)-1)) - 1 if len(fcf)>1 else None

        fcf_ltm = fcf.iloc[-1]
        rev_ltm = rev.iloc[-1]

        ev = inf.get("enterpriseValue")
        market_cap = inf.get("marketCap")

        ev_fcf = div(ev, fcf_ltm)
        fcf_margin = div(fcf_ltm, rev_ltm)
        fcf_yield = div(fcf_ltm, market_cap)

        gross_margin = inf.get("grossMargins")

        capex = abs(cf.loc['Capital Expenditure'].dropna()[::-1].iloc[-1])
        capex_ratio = div(capex, rev_ltm)

        # --- BALANCE FIXEADO ---
        debt = get_item(bs, ['Total Debt', 'Long Term Debt'])
        cash = get_item(bs, ['Cash And Cash Equivalents', 'Cash'])
        equity = get_item(bs, [
            'Total Stockholder Equity',
            'Total Stockholders Equity',
            'Stockholders Equity',
            'Total Equity'
        ])

        net_debt = (debt - cash) if (debt is not None and cash is not None) else None

        # --- ROIC FIX ---
        op_income = get_item(inc, ['Operating Income'])

        tax = 0.25
        nopat = op_income * (1-tax) if op_income is not None else None

        if debt is not None and equity is not None and cash is not None:
            capital = debt + equity - cash
        else:
            capital = None

        roic = div(nopat, capital)

        # --- SBC ---
        sbc = fmp.get("stockBasedCompensation")
        sbc_ratio = div(sbc, rev_ltm) if sbc else None

        # --- HIST ---
        hist = tk.history(period="5y")
        price_cagr = None
        if not hist.empty:
            price_cagr = (hist["Close"].iloc[-1]/hist["Close"].iloc[0])**(1/5)-1

        # --- BACKLOG ---
        st.markdown("### ⚙️ Modelo Forward")
        backlog = st.number_input("Backlog (Billions USD)", value=0.0)
        conv = st.slider("Conversión %",0,100,50)

        backlog_usd = backlog * 1e9
        backlog_fcf = backlog_usd * (conv/100) * (fcf_margin if fcf_margin else 0)

        fcf_forward = fcf_ltm + backlog_fcf if fcf_ltm else None
        ev_fcf_forward = div(ev, fcf_forward)

        peg = div(ev_fcf_forward, pct(cagr))

        # --- SCORE ---
        score = 0
        if ev_fcf and ev_fcf < 45: score+=1
        if cagr and cagr>0.1: score+=1
        if fcf_margin and fcf_margin>0.15: score+=1
        if roic and roic>0.15: score+=1
        if fcf_yield and fcf_yield>0.05: score+=1

        senal = "🟢 COMPRA" if score>=4 else "🟡 HOLD" if score>=2 else "🔴 RECHAZO"

        # --- OUTPUT ---
        data = {
            "EV/FCF": round(ev_fcf,2) if ev_fcf else None,
            "EV/FCF Forward": round(ev_fcf_forward,2) if ev_fcf_forward else None,
            "CAGR %": pct(cagr),
            "FCF CAGR %": pct(fcf_cagr),
            "FCF Margin %": pct(fcf_margin),
            "ROIC %": pct(roic),
            "FCF Yield %": pct(fcf_yield),
            "Gross Margin %": pct(gross_margin),
            "CapEx %": pct(capex_ratio),
            "SBC %": pct(sbc_ratio),
            "Net Debt": net_debt,
            "PEG": round(peg,2) if peg else None
        }

        st.subheader(inf.get("longName"))
        st.json(data)

        st.metric("Score", score)
        st.success(f"Señal: {senal}")

        with st.spinner("IA..."):
            res = analizar(data, {}, score, senal)

        st.markdown("### 🧠 Informe")
        st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
