import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V7 Institucional", layout="wide")

# --- API KEYS ---
st.sidebar.title("🔑 APIs")
GEMINI_API_KEY = st.sidebar.text_input("Gemini API Key", type="password")
FMP_API_KEY = st.sidebar.text_input("FMP API Key", type="password")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- UTILS ---
def safe_div(a, b):
    try:
        if a is None or b in [0, None]:
            return None
        return a / b
    except:
        return None

def pct(x):
    return round(x * 100, 2) if x is not None else None

# --- FMP FETCH ---
def get_fmp_data(ticker):
    if not FMP_API_KEY:
        return {}
    try:
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}?apikey={FMP_API_KEY}"
        r = requests.get(url).json()
        return r[0] if r else {}
    except:
        return {}

# --- SCORE ---
def calcular_score(data):
    score = 0

    # CORRECCIÓN DE DECIMALES PARA FCF MARGIN Y ROIC
    if data["FCF_Margin"] and data["FCF_Margin"] > 0.15:
        score += 2
    if data["ROIC"] and data["ROIC"] > 0.20:
        score += 2
    if data["EV_FCF"] and data["EV_FCF"] < 30:
        score += 2
    if data["PEG"] and data["PEG"] < 1.5:
        score += 2
    if data["FCF_Yield"] and data["FCF_Yield"] > 0.03:
        score += 2

    return score

def señal(score):
    if score >= 8:
        return "🟢 BUY"
    elif score >= 5:
        return "🟡 HOLD"
    else:
        return "🔴 SELL"

# --- IA ---
def analizar_ia(data):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    Eres comité institucional.

    DATA:
    {data}

    Evalúa:
    - Calidad
    - Valuación
    - Riesgo
    - Valida score

    Output profesional.
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V7 - Institucional")

ticker = st.text_input("Ticker").upper()

if ticker:

    tk = yf.Ticker(ticker)
    fmp = get_fmp_data(ticker)

    try:
        info = tk.info
        inc = tk.financials
        cf = tk.cashflow
        bs = tk.balance_sheet

        if inc.empty or cf.empty:
            st.error("❌ Datos insuficientes")
        else:
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            rev_ltm = rev.iloc[-1]
            fcf_ltm = fcf.iloc[-1]

            ev = info.get("enterpriseValue")
            market_cap = info.get("marketCap")

            # --- CORE ---
            ev_fcf = safe_div(ev, fcf_ltm)
            fcf_margin = safe_div(fcf_ltm, rev_ltm)

            # CAGR
            cagr = None
            if len(rev) > 1:
                cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1

            # --- NUEVO ---
            fcf_yield = safe_div(fcf_ltm, market_cap)

            capex = abs(cf.loc['Capital Expenditure'].dropna().iloc[-1]) if 'Capital Expenditure' in cf.index else None
            capex_ratio = safe_div(capex, rev_ltm)

            # SBC (FMP)
            sbc = fmp.get("stockBasedCompensation", None)
            sbc_ratio = safe_div(sbc, rev_ltm) if sbc else None

            # ROIC fallback
            equity = None
            for key in ["Total Stockholder Equity", "Total Equity Gross Minority Interest"]:
                if key in bs.index:
                    equity = bs.loc[key].dropna().iloc[0]
                    break

            roic = safe_div(fcf_ltm, equity) if equity else None

            # --- PEG CORRECTO ---
            peg = safe_div(ev_fcf, cagr * 100) if cagr else None

            # --- BACKLOG INPUT ---
            st.subheader("⚙️ Modelo Forward")
            tipo = st.selectbox("Tipo empresa", ["Físico", "Software"])

            backlog = st.number_input("Backlog (Billions USD)", value=0.0)
            conversion = st.slider("Conversión %", 0, 100, 50)

            backlog_usd = backlog * 1e9
            backlog_fcf = backlog_usd * (conversion / 100) * (fcf_margin if fcf_margin else 0)

            fcf_forward = fcf_ltm + backlog_fcf
            ev_fcf_forward = safe_div(ev, fcf_forward)

            # --- SCORE ---
            data = {
                "EV_FCF": ev_fcf,
                "FCF_Margin": fcf_margin,
                "ROIC": roic,
                "PEG": peg,
                "FCF_Yield": fcf_yield
            }

            score = calcular_score(data)
            sig = señal(score)

            # --- DISPLAY ---
            st.subheader(info.get("longName"))

            st.write("📊 Core")
            st.json({
                "EV/FCF": round(ev_fcf,2) if ev_fcf else None,
                "CAGR %": pct(cagr),
                "FCF Margin %": pct(fcf_margin),
                "PE": info.get("trailingPE")
            })

            st.write("🧠 Calidad")
            st.json({
                "ROIC %": pct(roic),
                "SBC %": pct(sbc_ratio),
                "CapEx %": pct(capex_ratio),
                "FCF Yield %": pct(fcf_yield)
            })

            st.write("📈 Forward")
            st.json({
                "FCF Forward": int(fcf_forward),
                "EV/FCF Forward": round(ev_fcf_forward,2) if ev_fcf_forward else None,
                "PEG": round(peg,2) if peg else None
            })

            st.write("🎯 Score")
            st.metric("Score", f"{score}/10")
            st.metric("Señal", sig)

            # --- IA ---
            if st.button("Analizar IA"):
                res = analizar_ia(data)
                st.markdown(res)

    except Exception as e:
        st.error(f"Error: {e}")
