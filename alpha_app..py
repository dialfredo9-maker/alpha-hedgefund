import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import os
from google import genai

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Alpha Boardroom V4.8", layout="wide")

st.markdown("""
    <style>
    .report-box { font-family: 'Courier New', monospace; background-color: #0d1117; padding: 20px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; font-size: 14px; line-height: 1.6; }
    u { text-decoration: underline; color: #58a6ff; font-weight: bold; }
    b { color: #e1e4e8; }
    </style>
    """, unsafe_allow_html=True)

# --- CONECTIVIDAD ---
GEMINI_API_KEY = "AIzaSyC_P204qmsG4Xq0hHfRC8TvVgy_hsssm50" 
client = genai.Client(api_key=GEMINI_API_KEY)

# --- UTILIDADES ---
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

    m = st.session_state.mandate = st.session_state.mandato
    st.info(f"**LUPA:** {m['Nombre']}\n**LIMITE EV/FCF:** {m['Max_EV']}x\n**PESO CAGR:** {m['Peso_CAGR']}x")

# --- FLUJO PRINCIPAL ---
st.title("🔬 Terminal Alpha: Boardroom V4.8")
ticker = st.text_input("👉 Introduce Ticker (Ej: ADBE, TSLA, NVDA):").upper()

if ticker:
    with st.spinner(f"Extrayendo biopsia de {ticker}..."):
        tk = yf.Ticker(ticker)
        inf = tk.info
        inc_hist, cf_hist = tk.financials, tk.cashflow
        
        if inc_hist.empty or cf_hist.empty:
            st.error("ERROR: Datos financieros no disponibles en Yahoo Finance.")
        else:
            # --- EXTRACCIÓN SIN ERRORES DE NOMBRES ---
            rev_hist = inc_hist.loc['Total Revenue'].dropna()[::-1]
            fcf_hist = cf_hist.loc['Free Cash Flow'].dropna()[::-1]
            
            # Cálculo de CAGR corregido (rev_hist en ambos puntos)
            cagr = (rev_hist.iloc[-1] / rev_hist.iloc[0])**(1/(len(rev_hist)-1)) - 1 if len(rev_hist) > 1 else 0
            fcf_ltm, rev_ltm = fcf_hist.iloc[-1], rev_hist.iloc[-1]
            
            capex_h = cf_hist.loc['Capital Expenditure'].abs().dropna()[::-1]
            ciclo = "EXPANSIÓN" if capex_h.iloc[-1] > capex_h.mean() * 1.3 else "MANTENIMIENTO"
            
            st.subheader(f"📊 Análisis de Gabinete: {inf.get('longName')}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                bn = st.number_input("👉 Backlog/RPO (Billones USD):", value=0.0)
                # Sugerencia de margen basada en el LTM real
                m_sotp_base = float(to_pct(division_segura(fcf_ltm, rev_ltm)))
                m_sotp = st.number_input(f"👉 Margen FCF para SOTP (LTM: {m_sotp_base}%):", value=m_sotp_base)
            with col_b:
                ctx = st.text_area("👉 Contexto Estratégico Clave:", placeholder="Moat, Competencia, Riesgo de ejecución...")

            if st.button("⚖️ EJECUTAR JUNTA DE COMITÉ"):
                br = bn * (m_sotp / 100)
                datos_biopsia = {
                    "Ticker": ticker, "EV_FCF": division_segura(inf.get("enterpriseValue"), fcf_ltm),
                    "GM": to_pct(inf.get("grossMargins")), "FCF_M": to_pct(fcf_ltm/rev_ltm),
                    "CAGR": to_pct(cagr), "Ciclo": ciclo, "BN": bn, "BR": round(br, 2), "Ctx": ctx
                }

                # --- PROMPT DE ALTO RIGOR (V4.1 SPIRIT) ---
                prompt = f"""
                ERES EL COMITÉ DE UN HEDGE FUND. MANDATO: {m['Nombre']} (Límite EV/FCF: {m['Max_EV']}x, Prioridad CAGR: {m['Peso_CAGR']}x).
                DATOS BIOPSIA: {datos_biopsia}

                --- REGLAS DE RIGOR ---
                1. NO divagues. NO saludes. Usa terminología técnica (Terminal Value, Yield, RPO, Moat).
                2. Cruza la data: Evalúa si el EV/FCF ({datos_biopsia['EV_FCF']}x) es justificable con el CAGR ({datos_biopsia['CAGR']}%) bajo este mandato.
                3. EVALÚA EL BACKLOG: ¿El BR de ${datos_biopsia['BR']}B cambia la tesis de valoración?

                --- FORMATO DE SALIDA ---
                <u>1. AUDITOR GARP</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razón: Análisis CAGR vs Múltiplos.
                ---
                <u>2. ESTRATEGA MACRO</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razón: Foso y Ciclo de Inversión {datos_biopsia['Ciclo']}.
                ---
                <u>3. GESTOR DE RIESGOS</u>
                * Amenaza: [Nivel] | Certeza: [X]%
                * Razón: Riesgo estructural o Cisne Negro.
                ---
                <u>SENTENCIA FINAL</u>
                * Veredicto: [COMPRA AGRESIVA / DCA / ESPERA / RECHAZO]
                * Tesis: Conciliación técnica entre agentes.
                * Plan: Instrucción inmediata para el trader.
                """
                
                with st.spinner("Junta en sesión..."):
                    try:
                        # MOTOR ANCLADO EN 2.5-FLASH-LITE
                        response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
                        st.markdown("---")
                        st.markdown(f"<div class='report-box'>{response.text}</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Error de API: {e}")
