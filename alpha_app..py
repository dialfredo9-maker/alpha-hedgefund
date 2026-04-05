import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
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
st.sidebar.markdown("### 🔑 API KEYS")

GEMINI_API_KEY = st.sidebar.text_input("Gemini API", type="password")
FMP_API_KEY = st.sidebar.text_input("FMP API", type="password")

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# --- UTILIDADES ---
def safe(x):
    if x is None or x == "N/D":
        return None
    return x

def division_segura(n, d):
    try:
        if n is None or d is None or d == 0:
            return None
        return n / d
    except:
        return None

def to_pct(x):
    return None if x is None else round(x * 100, 2)

# --- FMP FETCH ---
def get_fmp_data(ticker):
    try:
        url = f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker}?limit=1&apikey={FMP_API_KEY}"
        r = requests.get(url).json()[0]

        return {
            "roic": r.get("roic"),
            "net_debt": r.get("netDebtToEBITDA"),
            "pe": r.get("peRatio")
        }
    except:
        return {}

# --- BACKLOG → FCF ---
def calcular_backlog_fcf(backlog_b, margen, tipo):
    """
    backlog_b: en BILLIONS
    margen: %
    """
    if backlog_b is None or margen is None:
        return None

    backlog_usd = backlog_b * 1e9

    if tipo == "Software":
        conversion = 0.85
    else:
        conversion = 0.6

    return backlog_usd * conversion * (margen / 100)

# --- FORWARD MODEL ---
def modelo_forward(ev, fcf_actual, backlog_fcf):
    if fcf_actual is None:
        return {}

    fcf_forward = fcf_actual + (backlog_fcf or 0)

    ev_fcf_forward = division_segura(ev, fcf_forward)

    return {
        "FCF_Forward": fcf_forward,
        "EV_FCF_Forward": ev_fcf_forward
    }

# --- PEG REAL ---
def calcular_peg(ev_fcf_forward, cagr):
    if ev_fcf_forward is None or cagr is None or cagr == 0:
        return None
    return ev_fcf_forward / cagr

# --- IA ---
def analizar_ia(data):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    COMITÉ INSTITUCIONAL BUY-SIDE.

    DATOS YA PROCESADOS:
    {data}

    TAREAS:
    - Evaluar si el crecimiento justifica la valoración
    - Detectar riesgo de múltiplos
    - Validar backlog como fuente real de FCF
    - Confirmar o rechazar tesis

    OUTPUT:
    IDENTIDAD:
    ...
    VALUACIÓN:
    ...
    RIESGO:
    ...
    CONCLUSIÓN:
    ...
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V7")

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
            # --- FUNDAMENTALES ---
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1 if len(rev) > 1 else None

            fcf_ltm = fcf.iloc[-1]
            rev_ltm = rev.iloc[-1]

            ev = inf.get("enterpriseValue")

            ev_fcf = division_segura(ev, fcf_ltm)
            fcf_margin = division_segura(fcf_ltm, rev_ltm)

            # --- HISTÓRICO ---
            hist = tk.history(period="5y")
            price_cagr = None

            if not hist.empty:
                price_cagr = (hist["Close"].iloc[-1] / hist["Close"].iloc[0])**(1/5) - 1

            # --- FMP ---
            fmp = get_fmp_data(ticker) if FMP_API_KEY else {}

            # --- UI CORE ---
            st.subheader(inf.get("longName"))

            col1, col2, col3 = st.columns(3)
            col1.metric("EV/FCF", round(ev_fcf,2) if ev_fcf else None)
            col2.metric("CAGR %", to_pct(cagr))
            col3.metric("FCF Margin %", to_pct(fcf_margin))

            # --- BACKLOG INPUT ---
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
                    "EV_FCF": ev_fcf,
                    "CAGR": to_pct(cagr),
                    "FCF_Margin": to_pct(fcf_margin),
                    "CAGR_5Y_Price": to_pct(price_cagr),
                    "ROIC": fmp.get("roic"),
                    "NetDebt": fmp.get("net_debt"),
                    "Backlog_FCF": backlog_fcf,
                    "EV_FCF_Forward": forward.get("EV_FCF_Forward"),
                    "PEG": peg
                }

                st.markdown("### 📈 Modelo Forward")

                st.json({
                    "FCF Forward": forward.get("FCF_Forward"),
                    "EV/FCF Forward": forward.get("EV_FCF_Forward"),
                    "PEG": peg
                })

                # --- IA ---
                with st.spinner("IA..."):
                    try:
                        res = analizar_ia(data)
                    except Exception as e:
                        res = f"⚠️ Error IA: {e}"

                st.markdown("### 🧠 Informe")
                st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")
