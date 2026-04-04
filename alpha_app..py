import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import os
from google import genai

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Alpha Boardroom V4.5", layout="wide")

# Estilo visual de terminal institucional
st.markdown("""
    <style>
    .report-box { font-family: 'Courier New', monospace; background-color: #0d1117; padding: 20px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; }
    u { text-decoration: underline; color: #58a6ff; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = "AIzaSyC_P204qmsG4Xq0hHfRC8TvVgy_hsssm50" 
client = genai.Client(api_key=GEMINI_API_KEY)

# --- LÓGICA V4.1 RESPETADA AL 100% ---
def division_segura(n, d): return "N/D" if not n or not d or d == 0 else round(n / d, 4)
def to_pct(v): return "N/D" if v in [None, "N/D", np.nan] else round(v * 100, 2)

# --- PANEL LATERAL: MANDATO (PERSISTENCIA) ---
with st.sidebar:
    st.title("📜 Mandato del Fondo")
    # Mantener el estado del mandato hasta que se cambie
    if 'mandato' not in st.session_state:
        st.session_state.mandato = {"Nombre": "Moderado/Medio", "Max_EV": 45, "Peso_CAGR": 1.2, "Umbral_M": 0.25}

    horizonte = st.selectbox("Horizonte:", ["Corto", "Medio", "Largo"], index=1)
    riesgo = st.selectbox("Perfil de Riesgo:", ["Conservador", "Moderado", "Agresivo"], index=1)
    
    if st.button("⚖️ CALIBRAR MANDATO"):
        m = {"Nombre": f"{riesgo}/{horizonte}", "Max_EV": 45, "Peso_CAGR": 1.2, "Umbral_M": 0.25}
        if riesgo == "Agresivo" or horizonte == "Largo":
            m.update({"Max_EV": 85, "Peso_CAGR": 2.5, "Umbral_M": 0.18})
        elif riesgo == "Conservador":
            m.update({"Max_EV": 30, "Peso_CAGR": 0.8, "Umbral_M": 0.35})
        st.session_state.mandato = m
        st.success(f"Mandato {m['Nombre']} Activo.")

    st.divider()
    m = st.session_state.mandato
    st.info(f"**LUPA:** {m['Nombre']}\n\n**LIMITE EV/FCF:** {m['Max_EV']}x\n\n**PESO CAGR:** {m['Peso_CAGR']}x")

# --- FLUJO DE TRABAJO ---
st.title("🔬 Terminal Alpha: Boardroom V4.5")
ticker = st.text_input("👉 Introduce Ticker (Enter para biopsia):").upper()

if ticker:
    with st.spinner(f"Extrayendo biopsia de {ticker}..."):
        tk = yf.Ticker(ticker)
        inf = tk.info
        inc_hist, cf_hist = tk.financials, tk.cashflow
        
        if inc_hist.empty or cf_hist.empty:
            st.error("ERROR: Historial incompleto en Yahoo Finance.")
        else:
            # Extracción exacta de tu V4.1
            rev_h = inc_hist.loc['Total Revenue'].dropna()[::-1]
            fcf_h = cf_h.loc['Free Cash Flow'].dropna()[::-1]
            cagr = (rev_h.iloc[-1] / rev_h.iloc[0])**(1/(len(rev_h)-1)) - 1 if len(rev_h) > 1 else 0
            fcf_ltm, rev_ltm = fcf_h.iloc[-1], rev_h.iloc[-1]
            capex_h = cf_h.loc['Capital Expenditure'].abs().dropna()[::-1]
            ciclo = "EXPANSIÓN" if capex_h.iloc[-1] > capex_h.mean() * 1.3 else "MANTENIMIENTO"
            
            st.subheader(f"📊 Laboratorio: {inf.get('longName')}")
            
            # Ajuste SOTP e Intervención Estratégica
            col_a, col_b = st.columns(2)
            with col_a:
                bn = st.number_input("👉 Backlog/RPO (Billones USD):", value=0.0)
                m_sotp_suggested = to_pct(division_segura(fcf_ltm, rev_ltm))
                m_sotp = st.number_input(f"👉 Margen FCF Backlog (Sugerido: {m_sotp_suggested}%):", value=float(m_sotp_suggested))
            with col_b:
                ctx = st.text_area("👉 Contexto Estratégico Clave:", placeholder="Foso, Competencia, Riesgo tecnológico...")

            if st.button("⚖️ LANZAR JUNTA DE COMITÉ"):
                br = bn * (m_sotp / 100)
                datos = {
                    "Ticker": ticker, "Nombre": inf.get("longName"), "Mandato": m["Nombre"],
                    "Max_EV": m["Max_EV"], "Peso_CAGR": m["Peso_CAGR"],
                    "EV_FCF": division_segura(inf.get("enterpriseValue"), fcf_ltm),
                    "GM": to_pct(inf.get("grossMargins")), "FCF_M": to_pct(division_segura(fcf_ltm, rev_ltm)),
                    "CAGR": to_pct(cagr), "Ciclo": ciclo, "BN": bn, "BR": round(br, 2), "Ctx": ctx
                }

                # --- PROMPT RIGUROSO (MANTENIENDO LA ESENCIA V4.1) ---
                prompt = f"""
                ERES EL COMITÉ DE UN HEDGE FUND. MANDATO: {m['Nombre']} (EV/FCF Límite: {m['Max_EV']}x, Prioridad CAGR: {m['Peso_CAGR']}x).
                DATOS BIOPSIA: {datos}

                --- INSTRUCCIONES DE RIGOR ---
                1. NO divagues. NO saludes. Usa terminología de alto nivel (Alpha, FCF Yield, Moat, CapEx Cycle).
                2. Cruza la data: Si el CAGR es alto pero el CapEx es bajo, cuestiona la sostenibilidad.
                3. EVALÚA EL PRECIO: Si el EV/FCF supera el límite del mandato ({m['Max_EV']}x), el Auditor GARP debe ser agresivo.

                --- FORMATO ---
                <u>1. AUDITOR GARP</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razonamiento: (Cruza CAGR {datos['CAGR']}% con EV/FCF {datos['EV_FCF']}x).
                ---
                <u>2. ESTRATEGA MACRO (LOGÍSTICA Y DOMINANCIA)</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razonamiento: (Foso, Ciclo {datos['Ciclo']} y conversión de Backlog Real ${datos['BR']}B).
                ---
                <u>3. GESTOR DE RIESGOS</u>
                * Amenaza: [Nivel] | Certeza: [X]%
                * Razonamiento: (Principal Cisne Negro estructural).
                ---
                <u>SENTENCIA Y PLAN DE ACCIÓN</u>
                * Veredicto Final: [COMPRA AGRESIVA / DCA / LISTA ESPERA / RECHAZO]
                * Tesis: (Conciliación técnica de los agentes).
                * Plan: (Instrucción inmediata para el trader: Puntos de entrada o cautela).
                """
                
                with st.spinner("Debatiendo en la junta..."):
                    try:
                        # Usamos 3.1 Flash para máxima velocidad y rigor en 2026
                        response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
                        st.markdown("---")
                        st.markdown(f"<div class='report-box'>{response.text}</div>", unsafe_allow_html=True)
                        
                        # Opción de guardar (Manteniendo tu lógica de Excel)
                        # guardar_excel(datos, response.text)
                    except Exception as e:
                        st.error(f"Error de Comunicación con la IA: {e}")
