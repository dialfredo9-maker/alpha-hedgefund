import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V10 PRO", layout="wide")

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
        return float(a) / float(b)
    except:
        return None

def pct(x):
    return round(x * 100, 2) if x is not None else None

def clean_series(df, key):
    if key in df.index:
        s = df.loc[key].dropna()
        if len(s) > 0:
            return s[::-1]  # orden cronológico
    return None

# --- FMP ---
def get_fmp_data(ticker):
    if not FMP_API_KEY:
        return {}
    try:
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}?apikey={FMP_API_KEY}"
        r = requests.get(url).json()
        return r[0] if r else {}
    except:
        return {}

# --- SCORE PRO ---
def calcular_score(data):
    score = 0

    if data["FCF_Margin"] and data["FCF_Margin"] > 0.15:
        score += 2
    if data["ROIC"] and data["ROIC"] > 0.15:
        score += 2
    if data["EV_FCF"] and data["EV_FCF"] < 25:
        score += 2
    if data["PEG"] and 0 < data["PEG"] < 1.5:
        score += 2
    if data["FCF_Yield"] and data["FCF_Yield"] > 0.04:
        score += 2

    # Penalizaciones reales
    if data["ROIC"] is None:
        score -= 1
    if data["PEG"] and data["PEG"] > 3:
        score -= 1

    return max(score, 0)

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
    - Calidad REAL
    - Valuación
    - Riesgos reales (no genéricos)
    - Validación del score

    Sé directo, crítico y profesional.
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V10 PRO")

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

            # --- DATA LIMPIA ---
            rev = clean_series(inc, 'Total Revenue')
            op_cf = clean_series(cf, 'Operating Cash Flow')
            capex = clean_series(cf, 'Capital Expenditure')
            fcf_direct = clean_series(cf, 'Free Cash Flow')

            if rev is None or (fcf_direct is None and (op_cf is None or capex is None)):
                st.error("❌ Datos incompletos")
            else:

                # --- FCF REAL ---
                if fcf_direct is not None:
                    fcf = fcf_direct
                else:
                    fcf = op_cf + capex  # capex negativo correcto

                rev_ltm = rev.iloc[-1]
                fcf_ltm = fcf.iloc[-1]

                ev = info.get("enterpriseValue")
                market_cap = info.get("marketCap")
                pe = info.get("trailingPE")

                # --- CORE ---
                ev_fcf = safe_div(ev, fcf_ltm)
                fcf_margin = safe_div(fcf_ltm, rev_ltm)

                # CAGR REAL
                cagr = None
                if len(rev) > 1 and rev.iloc[0] > 0:
                    cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1

                fcf_yield = safe_div(fcf_ltm, market_cap)

                # --- ROIC CORRECTO (MISMO PERIODO) ---
                ebit_series = clean_series(inc, 'EBIT')

                if ebit_series is not None:
                    ebit = ebit_series.iloc[-1]
                else:
                    ebit = None

                tax_rate = 0.21
                nopat = ebit * (1 - tax_rate) if ebit else None

                debt_series = clean_series(bs, 'Total Debt')
                equity_series = clean_series(bs, 'Stockholders Equity')

                debt = debt_series.iloc[-1] if debt_series is not None else 0
                equity = equity_series.iloc[-1] if equity_series is not None else None

                invested_capital = debt + equity if equity else None
                roic = safe_div(nopat, invested_capital)

                # --- PEG FIX REAL (ERROR CLAVE ARREGLADO) ---
                peg = safe_div(pe, cagr) if cagr and pe else None

                # --- FORWARD ---
                st.subheader("⚙️ Modelo Forward")
                tipo = st.selectbox("Tipo empresa", ["Plataforma", "Software", "Industrial"])

                backlog = st.number_input("Backlog (Billions USD)", value=0.0)
                conversion = st.slider("Conversión %", 0, 100, 50)

                backlog_usd = backlog * 1e9
                backlog_fcf = backlog_usd * (conversion / 100) * (fcf_margin if fcf_margin else 0)

                fcf_forward = fcf_ltm + backlog_fcf
                ev_fcf_forward = safe_div(ev, fcf_forward)

                # --- DATA FINAL ---
                data = {
                    "EV_FCF": ev_fcf,
                    "FCF_Margin": fcf_margin,
                    "ROIC": roic,
                    "PEG": peg,
                    "FCF_Yield": fcf_yield,
                    "CAGR": cagr
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
                    "PE": pe
                })

                st.write("🧠 Calidad")
                st.json({
                    "ROIC %": pct(roic),
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

                if st.button("Analizar IA"):
                    res = analizar_ia(data)
                    st.markdown(res)

    except Exception as e:
        st.error(f"Error: {e}")
