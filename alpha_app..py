import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V7", layout="wide")

st.markdown("""
<style>
.report-box { font-family: 'Courier New'; background-color: #0d1117; padding: 25px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)

# --- API KEYS ---
st.sidebar.markdown("### 🔑 APIs")

GEMINI_API_KEY = st.sidebar.text_input("Gemini API", type="password")
FMP_API_KEY = st.sidebar.text_input("FMP API", type="password")

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# --- UTILIDADES ---
def division_segura(n, d):
    try:
        if n is None or d is None or d == 0:
            return None
        return round(n / d, 4)
    except:
        return None

def to_pct(v):
    try:
        if v is None or np.isnan(v):
            return None
        return round(v * 100, 2)
    except:
        return None

# --- FMP FALLBACK ---
def obtener_fmp(ticker):
    if not FMP_API_KEY:
        return {}
    try:
        url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        data = requests.get(url).json()
        return data[0] if data else {}
    except:
        return {}

# --- CLASIFICADOR ---
def clasificar(data):
    cagr = data["CAGR"]
    price_cagr = data["CAGR_Precio_5Y"]
    fcf = data["FCF_Margin"]

    if None in [cagr, price_cagr, fcf]:
        return "⚪ Neutral"

    if cagr > 15 and fcf > 15:
        return "🟢 Compounder"

    if cagr > 25:
        return "🔵 Hipercrecimiento"

    if cagr > 5 and price_cagr < 0:
        return "🟡 Turnaround"

    return "🔴 Débil"

# --- TRAMPA ---
def detectar_trampa(data):
    if data["EV_FCF"] and data["CAGR"] and data["CAGR_Precio_5Y"]:
        if data["EV_FCF"] < 15 and data["CAGR"] < 10 and data["CAGR_Precio_5Y"] < 0:
            return True
    return False

# --- SIZING ---
def sizing(clasificacion, trampa):
    base = 0.1
    if "Compounder" in clasificacion:
        base = 0.2
    if "Hiper" in clasificacion:
        base = 0.15
    if trampa:
        base *= 0.5
    return round(base * 100,1)

# --- SCORE ---
def calcular_score(data, mandato):
    score = 0

    if data["EV_FCF"] and data["EV_FCF"] < mandato["Max_EV"]:
        score += 2

    if data["CAGR"] and data["CAGR"] > 10:
        score += 2

    if data["FCF_Margin"] and data["FCF_Margin"] > 15:
        score += 2

    if data["PEG"] and data["PEG"] < 2:
        score += 2

    return score

# --- SEÑAL ---
def generar_senal(score, trampa):
    if trampa:
        return "🚫 RECHAZO"
    if score >= 6:
        return "🟢 COMPRA"
    if score >= 4:
        return "🟡 HOLD"
    return "🔴 RECHAZO"

# --- IA ---
def analizar_ia(data, m, clasificacion, sizing, score, senal):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    COMITÉ INSTITUCIONAL BUY-SIDE

    MANDATO: {m}

    DATA: {data}

    CLASIFICACIÓN: {clasificacion}
    SIZING: {sizing}%
    SCORE: {score}
    SEÑAL: {senal}

    VALIDAR:
    - valoración vs crecimiento
    - si es trampa de múltiplos
    - si el sizing es correcto

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

# --- MANDATO ---
if 'mandato' not in st.session_state:
    st.session_state.mandato = {
        "Nombre": "Moderado",
        "Max_EV": 45
    }

m = st.session_state.mandato

# --- UI ---
st.title("🔬 Alpha Boardroom V7")

ticker = st.text_input("Ticker").upper()

if ticker:

    tk = yf.Ticker(ticker)
    fmp = obtener_fmp(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow

        rev = inc.loc['Total Revenue'].dropna()[::-1]
        fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

        cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1 if len(rev) > 1 else None

        fcf_ltm = fcf.iloc[-1]
        rev_ltm = rev.iloc[-1]

        ev = inf.get("enterpriseValue")
        ev_fcf = division_segura(ev, fcf_ltm)
        fcf_margin = division_segura(fcf_ltm, rev_ltm)

        hist = tk.history(period="5y")
        price_cagr = None
        if not hist.empty:
            price_cagr = (hist["Close"].iloc[-1] / hist["Close"].iloc[0])**(1/5) - 1

        # --- INPUT BACKLOG ---
        st.markdown("### ⚙️ Modelo Forward")

        tipo = st.selectbox("Tipo empresa", ["Físico","Software"])
        backlog = st.number_input("Backlog (Billions USD)", value=0.0)
        conv = st.slider("Conversión backlog %", 0,100,50)

        backlog_usd = backlog * 1_000_000_000
        backlog_fcf = backlog_usd * (conv/100) * (fcf_margin if fcf_margin else 0)

        fcf_forward = fcf_ltm + backlog_fcf if fcf_ltm else None
        ev_fcf_forward = division_segura(ev, fcf_forward)

        # --- PEG REAL ---
        peg = division_segura(ev_fcf, (to_pct(cagr) or 1))

        data = {
            "EV_FCF": ev_fcf,
            "CAGR": to_pct(cagr),
            "FCF_Margin": to_pct(fcf_margin),
            "CAGR_Precio_5Y": to_pct(price_cagr),
            "PEG": peg,
            "EV_FCF_Forward": ev_fcf_forward
        }

        clasificacion = clasificar(data)
        trampa = detectar_trampa(data)
        siz = sizing(clasificacion, trampa)
        score = calcular_score(data, m)
        senal = generar_senal(score, trampa)

        # --- UI OUTPUT ---
        st.subheader(inf.get("longName"))

        st.markdown("### 📊 Core")
        st.json(data)

        st.markdown("### 🧭 Clasificación")
        st.info(clasificacion)

        if trampa:
            st.error("🚨 Posible trampa")

        st.markdown("### 💰 Sizing")
        st.success(f"{siz}%")

        st.markdown("### 🧠 Score")
        st.metric("Score Total", score)

        st.markdown("### 🎯 Señal")
        st.success(senal)

        with st.spinner("IA..."):
            try:
                res = analizar_ia(data, m, clasificacion, siz, score, senal)
            except Exception as e:
                res = f"⚠️ IA error: {e}"

        st.markdown("### 🧠 Informe")
        st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
