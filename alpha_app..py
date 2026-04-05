import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V7 PRO", layout="wide")

# --- API ---
st.sidebar.markdown("### 🔑 API Gemini")
API_KEY = st.sidebar.text_input("API KEY", type="password")

client = None
if API_KEY:
    client = genai.Client(api_key=API_KEY)

# --- UTILIDADES ---
def safe_div(n, d):
    try:
        if not n or not d or d == 0:
            return None
        return n / d
    except:
        return None

def pct(x):
    return None if x is None else round(x*100,2)

# --- PER (PIPELINE ECONÓMICO REAL) ---
def calcular_per(tipo, backlog, revenue, cagr, fcf_margin, conv):
    if tipo == "Físico":
        return backlog * conv * fcf_margin
    elif tipo == "Software":
        rev_fut = revenue * (1 + cagr)
        return rev_fut * fcf_margin
    return 0

# --- CICLO ---
def detectar_ciclo(cagr, price_cagr):
    if cagr is None or price_cagr is None:
        return "Indeterminado"

    delta = price_cagr - cagr

    if cagr > 0.5 and delta > 0.2:
        return "🔴 Pico ciclo"
    elif delta < 0:
        return "🟡 Compresión"
    return "🟢 Normal"

# --- CLASIFICADOR ---
def clasificar(cagr, margin):
    if cagr > 0.4 and margin > 0.25:
        return "🔵 Hipercrecimiento"
    if cagr > 0.08 and margin > 0.15:
        return "🟢 Compounder"
    if cagr > 0.05:
        return "🟡 Turnaround"
    return "🔴 Débil"

# --- UI ---
st.title("🔬 Alpha Boardroom V7 PRO")

ticker = st.text_input("Ticker").upper()

if ticker:
    tk = yf.Ticker(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow

        if inc.empty or cf.empty:
            st.error("Datos incompletos")
        else:
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            cagr = (rev.iloc[-1]/rev.iloc[0])**(1/(len(rev)-1))-1 if len(rev)>1 else None

            fcf_ltm = fcf.iloc[-1]
            rev_ltm = rev.iloc[-1]

            fcf_margin = safe_div(fcf_ltm, rev_ltm)

            ev = inf.get("enterpriseValue")
            ev_fcf = safe_div(ev, fcf_ltm)

            hist = tk.history(period="5y")
            price_cagr = None
            if not hist.empty:
                price_cagr = (hist["Close"].iloc[-1]/hist["Close"].iloc[0])**(1/5)-1

            st.subheader(inf.get("longName"))

            col1,col2,col3 = st.columns(3)
            col1.metric("EV/FCF", round(ev_fcf,2) if ev_fcf else None)
            col2.metric("CAGR %", pct(cagr))
            col3.metric("FCF Margin %", pct(fcf_margin))

            # --- INPUTS ---
            st.markdown("### ⚙️ Modelo Forward")

            tipo = st.selectbox("Tipo empresa", ["Auto","Físico","Software"])

            backlog = st.number_input("Backlog (B USD)", value=0.0)
            conv = st.slider("Conversión backlog %", 50,100,85)/100

            if tipo == "Auto":
                if fcf_margin and fcf_margin > 0.25:
                    tipo = "Software"
                else:
                    tipo = "Físico"

            # --- CÁLCULOS ---
            per = calcular_per(tipo, backlog, rev_ltm, cagr or 0, fcf_margin or 0, conv)

            fcf_fa = fcf_ltm + per if fcf_ltm else None

            ev_fcf_fwd = safe_div(ev, fcf_fa)

            peg_fcf = safe_div(ev_fcf_fwd, cagr) if cagr else None

            ciclo = detectar_ciclo(cagr, price_cagr)
            clasif = clasificar(cagr or 0, fcf_margin or 0)

            # --- OUTPUT CUANT ---
            st.markdown("### 📊 Modelo Cuantitativo")

            st.write({
                "Tipo": tipo,
                "PER_FCF": round(per,2),
                "FCF Forward": round(fcf_fa,2) if fcf_fa else None,
                "EV/FCF Forward": round(ev_fcf_fwd,2) if ev_fcf_fwd else None,
                "PEG_FCF": round(peg_fcf,2) if peg_fcf else None,
                "Ciclo": ciclo,
                "Clasificación": clasif
            })

            # --- IA ---
            if st.button("🧠 Analizar"):
                if not client:
                    st.warning("Sin API")
                else:
                    prompt = f"""
                    ERES UN COMITÉ INSTITUCIONAL.

                    DATOS PROCESADOS:
                    CAGR: {cagr}
                    FCF margin: {fcf_margin}
                    EV/FCF: {ev_fcf}
                    EV/FCF Forward: {ev_fcf_fwd}
                    PEG_FCF: {peg_fcf}
                    Ciclo: {ciclo}
                    Clasificación: {clasif}

                    REGLAS:
                    - NO recalcular
                    - SOLO interpretar
                    - validar si es compra

                    OUTPUT:
                    IDENTIDAD
                    VALUACIÓN
                    RIESGO
                    VEREDICTO
                    SIZING
                    """

                    try:
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"Error IA: {e}")

    except Exception as e:
        st.error(e)
