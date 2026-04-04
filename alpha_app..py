import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import os
from google import genai

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Alpha Boardroom V4.7", layout="wide")

st.markdown("""
    <style>
    .report-box { font-family: 'Courier New', monospace; background-color: #0d1117; padding: 20px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; font-size: 14px; }
    u { text-decoration: underline; color: #58a6ff; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = "AIzaSyC_P204qmsG4Xq0hHfRC8TvVgy_hsssm50" 
client = genai.Client(api_key=GEMINI_API_KEY)

def division_segura(n, d): return "N/D" if not n or not d or d == 0 else round(n / d, 4)
def to_pct(v): return "N/D" if v in [None, "N/D", np.nan] else round(v * 100, 2)

# --- PANEL LATERAL: MANDATO ---
if 'mandato' not in st.session_state:
    st.session_state.mandato = {"Nombre": "Moderado/Medio", "Max_EV": 45, "Peso_CAGR": 1.2}

with st.sidebar:
    st.title("📜 Mandato del Fondo")
    riesgo = st.selectbox("Perfil de Riesgo:", ["Conservador", "Moderado", "Agresivo"], index=1)
    
    if st.button("⚖️ CALIBRAR MANDATO"):
        m = {"Nombre": f"{riesgo}/Largo", "Max_EV": 45, "Peso_CAGR": 1.2}
        if riesgo == "Agresivo": m.update({"Max_EV": 85, "Peso_CAGR": 2.5})
        elif riesgo == "Conservador": m.update({"Max_EV": 30, "Peso_CAGR": 0.8})
        st.session_state.mandato = m
        st.success(f"Mandato {riesgo} Activo.")

    m = st.session_state.mandato
    st.info(f"**LUPA:** {m['Nombre']}\n**LIMITE EV/FCF:** {m['Max_EV']}x\n**PESO CAGR:** {m['Peso_CAGR']}x")

# --- FLUJO PRINCIPAL ---
st.title("🔬 Terminal Alpha: Boardroom V4.7")
ticker = st.text_input("👉 Introduce Ticker (Enter para biopsia):").upper()

if ticker:
    with st.spinner(f"Extrayendo biopsia de {ticker}..."):
        tk = yf.Ticker(ticker)
        inf = tk.info
        inc_hist, cf_hist = tk.financials, tk.cashflow
        
        if inc_hist.empty or cf_hist.empty:
            st.error("ERROR: Historial incompleto.")
        else:
            # Extracción limpia (Corregida cf_h -> cf_hist)
            rev_hist = inc_hist.loc['Total Revenue'].dropna()[::-1]
            fcf_hist = cf_hist.loc['Free Cash Flow'].dropna()[::-1]
            cagr = (rev_hist.iloc[-1] / rev_h.iloc[0])**(1/(len(rev_hist)-1)) - 1 if len(rev_hist) > 1 else 0
            fcf_ltm, rev_ltm = fcf_hist.iloc[-1], rev_hist.iloc[-1]
            
            capex_h = cf_hist.loc['Capital Expenditure'].abs().dropna()[::-1]
            ciclo = "EXPANSIÓN" if capex_h.iloc[-1] > capex_h.mean() * 1.3 else "MANTENIMIENTO"
            
            st.subheader(f"📊 Laboratorio: {inf.get('longName')}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                bn = st.number_input("👉 Backlog/RPO (Billones USD):", value=0.0)
                m_sotp = st.number_input(f"👉 Margen FCF Backlog (Auto: {to_pct(fcf_ltm/rev_ltm)}%):", value=float(to_pct(fcf_ltm/rev_ltm)))
            with col_b:
                ctx = st.text_area("👉 Contexto Estratégico Clave:")

            if st.button("⚖️ LANZAR JUNTA"):
                br = bn * (m_sotp / 100)
                datos = {
                    "Ticker": ticker, "Max_EV": m["Max_EV"], "Peso_CAGR": m["Peso_CAGR"],
                    "EV_FCF": division_segura(inf.get("enterpriseValue"), fcf_ltm),
                    "GM": to_pct(inf.get("grossMargins")), "FCF_M": to_pct(fcf_ltm/rev_ltm),
                    "CAGR": to_pct(cagr), "Ciclo": ciclo, "BN": bn, "BR": round(br, 2), "Ctx": ctx
                }

                # PROMPT DE ALTO RIGOR
                prompt = f"""
                ERES EL COMITÉ DE UN HEDGE FUND. MANDATO: {m['Nombre']} (Límite EV/FCF: {m['Max_EV']}x).
                DATOS: {datos}

                --- INSTRUCCIONES DE RIGOR ---
                1. NO divagues. NO saludes. Usa terminología de Capital Markets.
                2. Cruza la data: Si el EV/FCF ({datos['EV_FCF']}x) excede el límite ({m['Max_EV']}x), justifica por qué es o no una trampa de valor.
                3. EVALÚA EL BACKLOG: ¿El BR de ${datos['BR']}B justifica la tesis?

                --- FORMATO ---
                <u>1. AUDITOR GARP</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razonamiento: (Análisis CAGR vs EV/FCF).
                ---
                <u>2. ESTRATEGA MACRO</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razonamiento: (Foso y Ciclo {datos['Ciclo']}).
                ---
                <u>3. GESTOR DE RIESGOS</u>
                * Amenaza: [Nivel] | Certeza: [X]%
                * Razonamiento: (Cisne Negro).
                ---
                <u>SENTENCIA FINAL</u>
                * Veredicto: [COMPRA AGRESIVA / DCA / ESPERA / RECHAZO]
                * Tesis: (Conciliación técnica).
                * Plan: (Instrucción de ejecución).
                """
                
                with st.spinner("Junta deliberando..."):
                    try:
                        # MOTOR 2.5-FLASH-LITE SETEADO
                        response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
                        st.markdown("---")
                        st.markdown(f"<div class='report-box'>{response.text}</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Error de API: {e}")
