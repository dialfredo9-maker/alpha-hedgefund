import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from google import genai
import requests

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V6.7", layout="wide")

st.markdown("""
<style>
.report-box { font-family: 'Courier New'; background-color: #0d1117; padding: 25px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)

# --- API CONFIG ---
st.sidebar.markdown("### 🔑 Configuración APIs")

GEMINI_API_KEY = st.sidebar.text_input("Gemini API Key", type="password")
FMP_API_KEY = st.sidebar.text_input("FMP API Key", type="password")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except:
        st.error("❌ Error con Gemini API")

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

# --- FMP FETCH ---
def get_fmp_data(ticker):
    if not FMP_API_KEY:
        return {}

    try:
        url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        data = requests.get(url).json()

        if data:
            return {
                "pe": data[0].get("pe"),
                "marketCap": data[0].get("mktCap")
            }
    except:
        return {}

    return {}

# --- ALERTAS ---
def generar_alertas(data, m):
    alertas = []

    if data["EV_FCF"] and data["EV_FCF"] > m["Max_EV"]:
        alertas.append("🔴 EV/FCF alto")

    if data["FCF_Margin"] and data["FCF_Margin"] < 10:
        alertas.append("🟠 Margen bajo")

    return alertas

# --- CLASIFICADOR ---
def clasificar(data):
    cagr = data["CAGR"]
    fcf = data["FCF_Margin"]
    price = data["CAGR_Precio_5Y"]

    if None in [cagr, fcf, price]:
        return "⚪ Datos insuficientes"

    if cagr > 8 and fcf > 15:
        return "🟢 Compounder"

    if cagr > 20:
        return "🔵 Hipercrecimiento"

    if price < 0:
        return "🟡 Turnaround"

    return "⚪ Neutral"

# --- TRAMPA ---
def detectar_trampa(data):
    if data["EV_FCF"] and data["CAGR"]:
        if data["EV_FCF"] > 40 and data["CAGR"] < 15:
            return True
    return False

# --- SIZING ---
def sizing(data, clasificacion, trampa):
    base = 5

    if clasificacion == "🟢 Compounder":
        base = 20
    elif clasificacion == "🔵 Hipercrecimiento":
        base = 15
    elif clasificacion == "🟡 Turnaround":
        base = 10

    if trampa:
        base *= 0.5

    return round(base, 1)

# --- MANDATO ---
if "mandato" not in st.session_state:
    st.session_state.mandato = {
        "Nombre": "Moderado",
        "Max_EV": 45
    }

m = st.session_state.mandato

# --- IA ---
def analizar_ia(data, m, clasificacion, size, trampa):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    COMITÉ INSTITUCIONAL.

    MANDATO: {m}
    DATOS: {data}

    CLASIFICACIÓN: {clasificacion}
    SIZING: {size}%
    TRAMPA: {trampa}

    Evalúa rigurosamente.

    OUTPUT:
    IDENTIDAD:
    ...
    VALUACIÓN:
    ...
    RIESGO:
    ...
    FINAL:
    """

    try:
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        ).text
    except Exception as e:
        return f"Error IA: {e}"

# --- UI ---
st.title("🔬 Alpha Boardroom V6.7")

ticker = st.text_input("Ticker").upper()

if ticker:
    tk = yf.Ticker(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow

        if inc.empty or cf.empty:
            st.error("❌ Datos incompletos")
        else:
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1 if len(rev) > 1 else None

            fcf_ltm = fcf.iloc[-1]
            rev_ltm = rev.iloc[-1]

            ev = inf.get("enterpriseValue")
            ev_fcf = division_segura(ev, fcf_ltm)
            fcf_margin = division_segura(fcf_ltm, rev_ltm)

            hist = tk.history(period="5y")

            if not hist.empty:
                price_cagr = (hist["Close"].iloc[-1] / hist["Close"].iloc[0])**(1/5) - 1
            else:
                price_cagr = None

            # --- FMP ---
            fmp = get_fmp_data(ticker)

            st.subheader(inf.get("longName"))

            st.markdown("### 📊 Core")
            st.json({
                "EV/FCF": ev_fcf,
                "CAGR %": to_pct(cagr),
                "FCF Margin %": to_pct(fcf_margin),
                "PE": fmp.get("pe")
            })

            if st.button("Analizar"):

                data = {
                    "EV_FCF": ev_fcf,
                    "CAGR": to_pct(cagr),
                    "FCF_Margin": to_pct(fcf_margin),
                    "CAGR_Precio_5Y": to_pct(price_cagr),
                    "PE": fmp.get("pe")
                }

                clas = clasificar(data)
                trampa = detectar_trampa(data)
                size = sizing(data, clas, trampa)

                st.markdown("### 🧭 Clasificación")
                st.info(clas)

                if trampa:
                    st.error("🚨 Posible trampa")

                st.markdown("### 💰 Sizing")
                st.success(f"{size}%")

                res = analizar_ia(data, m, clas, size, trampa)

                st.markdown("### 🧠 Informe")
                st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
