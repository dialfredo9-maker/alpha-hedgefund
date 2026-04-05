import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V6.5 FIX", layout="wide")

st.markdown("""
<style>
.report-box { font-family: 'Courier New'; background-color: #0d1117; padding: 25px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)

# --- API ---
st.sidebar.markdown("### 🔑 Configuración API")
GEMINI_API_KEY = st.sidebar.text_input("Ingresa tu API Key", type="password")

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

# --- ALERTAS ---
def generar_alertas(data, mandato):
    alertas = []

    if data["EV_FCF"] and data["EV_FCF"] > mandato["Max_EV"]:
        alertas.append("🔴 Sobrevaloración: EV/FCF elevado")

    if data["FCF_Margin"] and data["FCF_Margin"] < 0.10:
        alertas.append("🟠 Margen FCF débil")

    if data["CAGR_Precio_5Y"] and data["CAGR"]:
        if data["CAGR_Precio_5Y"] > data["CAGR"] * 1.5:
            alertas.append("🔴 Expansión de múltiplos")

    return alertas

# --- CLASIFICADOR CORREGIDO ---
def clasificar_empresa(data):
    cagr = data["CAGR"]
    price_cagr = data["CAGR_Precio_5Y"]
    fcf_margin = data["FCF_Margin"]

    if cagr is None or price_cagr is None or fcf_margin is None:
        return "⚪ Datos insuficientes"

    # 🔵 HIPERCRECIMIENTO REAL (FIX NVIDIA)
    if cagr > 0.4 and fcf_margin > 0.25:
        return "🔵 Hipercrecimiento"

    if cagr > 0.08 and fcf_margin > 0.15 and abs(price_cagr - cagr) < 0.05:
        return "🟢 Compounder sano"

    if cagr > 0.05 and price_cagr < 0:
        return "🟡 Turnaround"

    if cagr < 0.05 and price_cagr < 0:
        return "🔴 Value trap"

    return "⚪ Neutral"

# --- TRAMPA ALCISTA CORREGIDA ---
def detectar_trampa(data):
    if data["EV_FCF"] and data["CAGR"] and data["CAGR_Precio_5Y"]:
        if data["EV_FCF"] < 12 and data["CAGR"] < 0.15 and data["CAGR_Precio_5Y"] < 0:
            return True
    return False

# --- SIZING CORREGIDO ---
def calcular_sizing(data, clasificacion, trampa):
    base = 0

    if clasificacion == "🟢 Compounder sano":
        base = 0.25
    elif clasificacion == "🔵 Hipercrecimiento":
        base = 0.20
    elif clasificacion == "🟡 Turnaround":
        base = 0.15
    elif clasificacion == "🔴 Value trap":
        base = 0.05

    if trampa:
        base *= 0.5

    if data["FCF_Margin"] and data["FCF_Margin"] > 0.30:
        base += 0.05

    return round(base * 100, 1)

# --- MANDATO ---
if 'mandato' not in st.session_state:
    st.session_state.mandato = {
        "Nombre": "Moderado/Medio",
        "Max_EV": 45,
        "Peso_CAGR": 1.2
    }

with st.sidebar:
    st.title("📜 Mandato")

    riesgo = st.selectbox("Riesgo", ["Conservador", "Moderado", "Agresivo"])
    horizonte = st.selectbox("Horizonte", ["Corto", "Medio", "Largo"])

    if st.button("Calibrar"):
        m = {"Nombre": f"{riesgo}/{horizonte}", "Max_EV": 45, "Peso_CAGR": 1.2}

        if riesgo == "Agresivo" or horizonte == "Largo":
            m.update({"Max_EV": 85, "Peso_CAGR": 2.5})
        elif riesgo == "Conservador":
            m.update({"Max_EV": 30, "Peso_CAGR": 0.8})

        st.session_state.mandato = m

    st.write(st.session_state.mandato)

m = st.session_state.mandato

# --- IA ---
def analizar_v6_ia(d, m, clasificacion, sizing, trampa):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    COMITÉ INSTITUCIONAL.

    MANDATO: {m}
    DATOS: {d}

    CLASIFICACIÓN: {clasificacion}
    SIZING PROPUESTO: {sizing}%
    POSIBLE TRAMPA: {trampa}

    REGLAS:
    - CONFIRMA o REFUTA clasificación
    - DETECTA sobrevaloración o trampa
    - VALIDA sizing

    OUTPUT:
    IDENTIDAD:
    ...
    GARP:
    ...
    VALUACIÓN:
    ...
    RIESGO:
    ...
    FINAL:
    Veredicto:
    Sizing recomendado:
    Plan:
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V6.5 FIX")

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
                price_now = hist["Close"].iloc[-1]
                price_5y = hist["Close"].iloc[0]
                price_cagr = (price_now / price_5y)**(1/5) - 1
            else:
                price_now = price_5y = price_cagr = None

            st.subheader(inf.get("longName"))

            col1, col2, col3 = st.columns(3)
            col1.metric("EV/FCF", ev_fcf)
            col2.metric("CAGR %", to_pct(cagr))
            col3.metric("FCF Margin %", to_pct(fcf_margin))

            if st.button("Analizar"):

                data = {
                    "Ticker": ticker,
                    "EV_FCF": ev_fcf,
                    "CAGR": cagr,
                    "FCF_Margin": fcf_margin,
                    "CAGR_Precio_5Y": price_cagr
                }

                clasificacion = clasificar_empresa(data)
                trampa = detectar_trampa(data)
                sizing = calcular_sizing(data, clasificacion, trampa)

                st.markdown("### 🧭 Clasificación")
                st.info(clasificacion)

                if trampa:
                    st.error("🚨 POSIBLE VALUE TRAP / TRAMPA")

                st.markdown("### 💰 Sizing sugerido")
                st.success(f"{sizing}% del portafolio")

                with st.spinner("IA..."):
                    try:
                        res = analizar_v6_ia(data, m, clasificacion, sizing, trampa)
                    except Exception as e:
                        st.error(f"Error IA real: {e}")
                        res = "⚠️ IA no disponible"

                st.markdown("### 🧠 Informe")
                st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
