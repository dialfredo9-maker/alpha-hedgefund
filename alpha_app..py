import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V9 Institucional", layout="wide")

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

# --- SCORE DINÁMICO ---
def calcular_score(data, tipo):
    score = 0

    # --- CALIDAD ---
    if data["ROIC"] and data["ROIC"] > 0.15:
        score += 2
    if data["FCF_Margin"] and data["FCF_Margin"] > 0.15:
        score += 2

    # --- VALUACIÓN ---
    if data["EV_FCF"] and data["EV_FCF"] < 25:
        score += 2
    if data["FCF_Yield"] and data["FCF_Yield"] > 0.04:
        score += 2

    # --- CRECIMIENTO ---
    if data["CAGR"] and data["CAGR"] > 0.08:
        score += 2

    # --- AJUSTE POR TIPO ---
    if tipo == "Plataforma":
        # penaliza menos FCF bajo si reinvierte
        if data["Reinvestment"] and data["Reinvestment"] > 0.4:
            score += 1

    return min(score, 10)

def señal(score):
    if score >= 8:
        return "🟢 BUY"
    elif score >= 5:
        return "🟡 HOLD"
    else:
        return "🔴 SELL"

# --- IA ---
def analizar_ia(data, tipo):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    Eres comité institucional profesional.

    Tipo empresa: {tipo}

    DATA:
    {data}

    Evalúa:
    - Calidad REAL (ajustada por tipo)
    - Valuación
    - Riesgo real (no genérico)
    - Validación del score

    Sé crítico y preciso.
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V9 - Institucional")

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
            pe = info.get("trailingPE")

            # --- CORE ---
            ev_fcf = safe_div(ev, fcf_ltm)
            fcf_margin = safe_div(fcf_ltm, rev_ltm)

            # CAGR
            cagr = None
            if len(rev) > 1:
                cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1

            fcf_yield = safe_div(fcf_ltm, market_cap)

            # --- CAPEX ---
            capex = abs(cf.loc['Capital Expenditure'].dropna().iloc[-1]) if 'Capital Expenditure' in cf.index else None
            capex_ratio = safe_div(capex, rev_ltm)

            # --- ROIC CORRECTO ---
            op_income = inc.loc['Operating Income'].dropna().iloc[0] if 'Operating Income' in inc.index else None
            tax_rate = 0.21
            nopat = op_income * (1 - tax_rate) if op_income else None

            debt = info.get("totalDebt", 0)
            cash = info.get("totalCash", 0)
            equity = bs.loc['Total Stockholder Equity'].dropna().iloc[0] if 'Total Stockholder Equity' in bs.index else None

            invested_capital = (equity + debt - cash) if equity else None
            roic = safe_div(nopat, invested_capital)

            # --- PEG CORRECTO ---
            peg = safe_div(pe, cagr * 100) if pe and cagr else None

            # --- REINVERSIÓN ---
            operating_cf = cf.loc['Operating Cash Flow'].dropna().iloc[0] if 'Operating Cash Flow' in cf.index else None
            reinvestment = safe_div(capex, operating_cf)

            # --- MODELO FORWARD ---
            st.subheader("⚙️ Modelo Forward")

            tipo = st.selectbox("Tipo empresa", ["Físico", "Software", "Plataforma"])

            backlog = st.number_input("Backlog (Billions USD)", value=0.0)
            conversion = st.slider("Conversión %", 0, 100, 50)

            backlog_usd = backlog * 1e9

            if tipo == "Físico":
                backlog_fcf = backlog_usd * (conversion / 100) * (fcf_margin if fcf_margin else 0)
                fcf_forward = fcf_ltm + backlog_fcf

            elif tipo == "Software":
                backlog_fcf = backlog_usd * (conversion / 100) * 0.8
                fcf_forward = fcf_ltm + backlog_fcf

            else:  # Plataforma
                # NO usar backlog → usar mejora de eficiencia
                improvement = 1 + (0.2 if reinvestment and reinvestment > 0.4 else 0.1)
                fcf_forward = fcf_ltm * improvement

            ev_fcf_forward = safe_div(ev, fcf_forward)

            # --- DATA ---
            data = {
                "EV_FCF": ev_fcf,
                "FCF_Margin": fcf_margin,
                "ROIC": roic,
                "PEG": peg,
                "FCF_Yield": fcf_yield,
                "CAGR": cagr,
                "Reinvestment": reinvestment
            }

            score = calcular_score(data, tipo)
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
                "CapEx %": pct(capex_ratio),
                "FCF Yield %": pct(fcf_yield),
                "Reinvestment %": pct(reinvestment)
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
                res = analizar_ia(data, tipo)
                st.markdown(res)

    except Exception as e:
        st.error(f"Error: {e}")
