import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V6.6", layout="wide")

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

EXCEL_FILE = "Analisis_HedgeFund_V6.xlsx"

# --- UTILIDADES ---
def division_segura(n, d):
    try:
        if n is None or d is None or d == 0:
            return None
        return n / d
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

    if data["FCF_Margin"] and data["FCF_Margin"] < 10:
        alertas.append("🟠 Margen FCF débil")

    if data["PEG"] and data["PEG"] > 2:
        alertas.append("🔴 Growth no justifica valoración (PEG alto)")

    return alertas

# --- CLASIFICADOR ---
def clasificar_empresa(data):
    cagr = data["CAGR"]
    price_cagr = data["CAGR_Precio_5Y"]
    fcf_margin = data["FCF_Margin"]

    if None in [cagr, price_cagr, fcf_margin]:
        return "⚪ Datos insuficientes"

    if cagr > 8 and fcf_margin > 15 and abs(price_cagr - cagr) < 5:
        return "🟢 Compounder sano"

    if cagr > 20 and price_cagr > cagr:
        return "🔵 Hipercrecimiento"

    if cagr > 5 and price_cagr < 0:
        return "🟡 Turnaround"

    if cagr < 5 and price_cagr < 0:
        return "🔴 Value trap"

    return "⚪ Neutral"

# --- BACKLOG REALISTA ---
def calcular_backlog_fcf(backlog_b, margen, tipo):
    if backlog_b is None or margen is None:
        return None

    backlog_usd = backlog_b * 1e9

    # 🔧 CORREGIDO (más realista)
    if tipo == "Software":
        conversion = 0.7
    else:
        conversion = 0.3

    return backlog_usd * conversion * (margen / 100)

# --- FORWARD ---
def modelo_forward(ev, fcf_actual, backlog_fcf):
    if fcf_actual is None:
        return {}

    fcf_forward = fcf_actual + (backlog_fcf or 0)
    ev_fcf_forward = division_segura(ev, fcf_forward)

    return {
        "FCF_Forward": fcf_forward,
        "EV_FCF_Forward": ev_fcf_forward
    }

# --- PEG CORREGIDO ---
def calcular_peg(ev_fcf_forward, cagr):
    if ev_fcf_forward is None or cagr is None or cagr == 0:
        return None

    return ev_fcf_forward / (cagr * 100)  # 🔥 FIX

# --- SIZING ---
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

    if data["FCF_Margin"] and data["FCF_Margin"] > 30:
        base += 0.05

    return round(base * 100, 1)

# --- IA ---
def analizar_v6_ia(d, m, clasificacion, sizing):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    COMITÉ INSTITUCIONAL.

    DATOS:
    {d}

    CLASIFICACIÓN: {clasificacion}
    SIZING: {sizing}%

    REGLAS:
    - Evaluar si el crecimiento justifica la valoración
    - Validar PEG
    - Evaluar calidad del backlog

    OUTPUT:
    IDENTIDAD:
    ...
    VALUACIÓN:
    ...
    RIESGO:
    ...
    FINAL:
    Veredicto:
    Sizing recomendado:
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V6.6")

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

            st.subheader(inf.get("longName"))

            col1, col2, col3 = st.columns(3)
            col1.metric("EV/FCF", round(ev_fcf,2) if ev_fcf else None)
            col2.metric("CAGR %", to_pct(cagr))
            col3.metric("FCF Margin %", to_pct(fcf_margin))

            # --- NUEVO INPUT PER ---
            st.markdown("### 📊 Input Opcional Profesional")
            per_manual = st.number_input("PER Ratio (opcional)", value=0.0)

            # --- BACKLOG ---
            st.markdown("### ⚙️ Modelo Forward")

            colA, colB, colC = st.columns(3)

            with colA:
                tipo = st.selectbox("Tipo empresa", ["Físico", "Software"])

            with colB:
                backlog_b = st.number_input("Backlog (Billions USD)", value=0.0)

            with colC:
                margen = st.number_input("Margen FCF (%)", value=float(to_pct(fcf_margin) or 0))

            if st.button("Analizar"):

                backlog_fcf = calcular_backlog_fcf(backlog_b, margen, tipo)
                forward = modelo_forward(ev, fcf_ltm, backlog_fcf)
                peg = calcular_peg(forward.get("EV_FCF_Forward"), cagr)

                data = {
                    "Ticker": ticker,
                    "EV_FCF": ev_fcf,
                    "CAGR": to_pct(cagr),
                    "FCF_Margin": to_pct(fcf_margin),
                    "CAGR_Precio_5Y": to_pct(price_cagr),
                    "EV_FCF_Forward": forward.get("EV_FCF_Forward"),
                    "PEG": peg,
                    "PER_Manual": per_manual if per_manual > 0 else None
                }

                clasificacion = clasificar_empresa(data)
                sizing = calcular_sizing(data, clasificacion, False)

                # ALERTAS
                alertas = generar_alertas(data, m)
                if alertas:
                    for a in alertas:
                        st.warning(a)
                else:
                    st.success("🟢 Sin alertas críticas")

                st.markdown("### 🧭 Clasificación")
                st.info(clasificacion)

                st.markdown("### 💰 Sizing sugerido")
                st.success(f"{sizing}% del portafolio")

                st.markdown("### 📈 Modelo Forward")
                st.json({
                    "FCF Forward": forward.get("FCF_Forward"),
                    "EV/FCF Forward": forward.get("EV_FCF_Forward"),
                    "PEG": peg
                })

                # IA
                with st.spinner("IA..."):
                    try:
                        res = analizar_v6_ia(data, m, clasificacion, sizing)
                    except:
                        res = "⚠️ IA no disponible"

                st.markdown("### 🧠 Informe")
                st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
