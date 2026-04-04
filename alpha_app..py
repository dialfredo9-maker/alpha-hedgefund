import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V5", layout="wide")

st.markdown("""
<style>
.report-box { font-family: 'Courier New'; background-color: #0d1117; padding: 25px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)

# --- API ---
GEMINI_API_KEY = os.getenv("AIzaSyCKlh0WwWhY6wdIWDvgTAdabUhJYPLCSIk")
client = genai.Client(api_key=GEMINI_API_KEY)

EXCEL_FILE = "Analisis_HedgeFund_V5.xlsx"

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

    if data["FCF_Margin"] and data["FCF_Margin"] < 10:
        alertas.append("🟠 Margen FCF débil")

    if data["CAGR_Precio_5Y"] and data["CAGR"]:
        if data["CAGR_Precio_5Y"] > data["CAGR"] * 1.5:
            alertas.append("🔴 Expansión de múltiplos (precio > fundamentos)")

    return alertas

# --- MANDATO ---
if 'mandato' not in st.session_state:
    st.session_state.mandato = {
        "Nombre": "Moderado/Medio",
        "Max_EV": 45,
        "Peso_CAGR": 1.2
    }

# --- CACHE IA ---
if "ultimo_input" not in st.session_state:
    st.session_state.ultimo_input = None
if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado = None

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

# --- IA V5 ---
def analizar_v5_ia(d, m):
    prompt = f"""
    ERES UN COMITÉ DE INVERSIÓN INSTITUCIONAL.

    MANDATO:
    {m}

    DATOS:
    {d}

    REGLAS:
    - No ignores datos
    - Usa CAGR vs EV/FCF
    - Usa histórico 5 años
    - Detecta expansión de múltiplos

    OUTPUT:

    IDENTIDAD:
    ...

    GARP:
    Score:
    Veredicto:
    Razón:

    VALUACIÓN:
    Estado:
    Razón:

    MACRO:
    Veredicto:
    Razón:

    RIESGO:
    Nivel:
    Razón:

    FINAL:
    Score:
    Veredicto:
    Plan:
    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V5")

ticker = st.text_input("Ticker").upper()

if ticker:
    tk = yf.Ticker(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow

        if inc.empty or cf.empty:
            st.error("❌ Datos financieros incompletos")
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

            # --- CAPEX ---
            capex = cf.loc['Capital Expenditure'].abs().dropna()[::-1]
            ciclo = "EXPANSIÓN" if capex.iloc[-1] > capex.mean() * 1.3 else "MANTENIMIENTO"

            # --- HISTÓRICO ---
            hist = tk.history(period="5y")

            if not hist.empty:
                price_now = hist["Close"].iloc[-1]
                price_5y = hist["Close"].iloc[0]
                price_cagr = (price_now / price_5y)**(1/5) - 1
            else:
                price_now = price_5y = price_cagr = None

            st.subheader(inf.get("longName"))

            # --- SNAPSHOT ---
            st.markdown("### 📊 Snapshot Rápido")

            col1, col2, col3 = st.columns(3)
            col1.metric("EV/FCF", ev_fcf)
            col2.metric("CAGR %", to_pct(cagr))
            col3.metric("FCF Margin %", to_pct(fcf_margin))

            # --- INPUTS ---
            colA, colB = st.columns(2)

            with colA:
                bn = st.number_input("Backlog (B)", value=0.0)
                m_sotp = st.number_input("Margen FCF (%)", value=float(to_pct(fcf_margin) or 0))

            with colB:
                ctx = st.text_area("Contexto")

            if st.button("Analizar"):
                br = bn * (m_sotp / 100)

                data = {
                    "Ticker": ticker,
                    "EV_FCF": ev_fcf,
                    "CAGR": to_pct(cagr),
                    "FCF_Margin": to_pct(fcf_margin),
                    "Precio_Actual": price_now,
                    "Precio_5Y": price_5y,
                    "CAGR_Precio_5Y": to_pct(price_cagr),
                    "Ciclo": ciclo,
                    "Backlog": bn,
                    "Backlog_Real": br,
                    "Contexto": ctx
                }

                # --- ALERTAS ---
                alertas = generar_alertas(data, m)

                if alertas:
                    st.markdown("### 🚨 Alertas del Sistema")
                    for a in alertas:
                        st.warning(a)
                else:
                    st.success("🟢 Sin alertas críticas")

                # --- IA (CON CACHE + CONTROL ERROR) ---
                with st.spinner("Analizando con IA..."):

                    if data == st.session_state.ultimo_input:
                        res = st.session_state.ultimo_resultado
                    else:
                        try:
                            res = analizar_v5_ia(data, m)
                            st.session_state.ultimo_input = data
                            st.session_state.ultimo_resultado = res

                        except Exception as e:
                            if "429" in str(e):
                                st.error("🚫 Límite de IA alcanzado. Espera o intenta más tarde.")
                                res = "⚠️ Análisis no disponible por límite de API."
                            else:
                                st.error(f"Error IA: {e}")
                                res = "⚠️ Error en análisis IA"

                st.markdown("### 🧠 Informe del Comité")
                st.markdown(f"<div class='report-box'>{res}</div>", unsafe_allow_html=True)

                # --- GUARDAR ---
                df = pd.DataFrame([{**data, "IA": res}])

                if os.path.exists(EXCEL_FILE):
                    df_old = pd.read_excel(EXCEL_FILE)
                    df = pd.concat([df_old, df], ignore_index=True)

                df.to_excel(EXCEL_FILE, index=False)

                st.success("✅ Guardado en Excel")

    except Exception as e:
        st.error(f"❌ Error: {e}")
