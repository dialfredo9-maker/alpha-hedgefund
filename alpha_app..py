import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import os
from google import genai

# --- CONFIGURACIÓN DE INTERFAZ (MODO TERMINAL PRO) ---
st.set_page_config(page_title="Alpha Boardroom V5.0", layout="wide")

st.markdown("""
    <style>
    .report-box { font-family: 'Courier New', monospace; background-color: #0d1117; padding: 25px; border-radius: 10px; border: 1px solid #30363d; color: #c9d1d9; font-size: 14px; line-height: 1.6; }
    u { text-decoration: underline; color: #58a6ff; font-weight: bold; }
    b { color: #e1e4e8; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- CONECTIVIDAD ---
# Usamos tu clave de API proporcionada
GEMINI_API_KEY = "AIzaSyC_P204qmsG4Xq0hHfRC8TvVgy_hsssm50" 
client = genai.Client(api_key=GEMINI_API_KEY)

# --- UTILIDADES DE CÁLCULO V4.1 ---
def division_segura(n, d): return "N/D" if not n or not d or d == 0 else round(n / d, 4)
def to_pct(v): return "N/D" if v in [None, "N/D", np.nan] else round(v * 100, 2)

# --- MÓDULO DE MANDATO (PERSISTENCIA Y LÓGICA V4.1) ---
if 'mandato' not in st.session_state:
    # Estado inicial basado en la V4.1
    st.session_state.mandato = {
        "Nombre": "Moderado/Medio", 
        "Max_EV": 45, 
        "Peso_CAGR": 1.2, 
        "Umbral_M": 0.25, 
        "Riesgo": "Moderado", 
        "Horizonte": "Medio"
    }

with st.sidebar:
    st.title("📜 CONFIGURACIÓN DEL MANDATO")
    st.write("---")
    
    # Entradas de la V4.1
    nuevo_riesgo = st.selectbox("👉 Nivel de Riesgo:", ["Conservador", "Moderado", "Agresivo"], index=1)
    nuevo_horizonte = st.selectbox("👉 Horizonte Temporal:", ["Corto", "Medio", "Largo"], index=1)
    
    if st.button("⚖️ CALIBRAR ESTRATEGIA ALPHA"):
        # Replicamos exactamente la lógica de if/elif de tu código V4.1
        m = {
            "Nombre": f"{nuevo_riesgo}/{nuevo_horizonte}", 
            "Max_EV": 45, 
            "Peso_CAGR": 1.2, 
            "Umbral_M": 0.25,
            "Riesgo": nuevo_riesgo,
            "Horizonte": nuevo_horizonte
        }
        
        if nuevo_riesgo == "Agresivo" or nuevo_horizonte == "Largo":
            m.update({"Max_EV": 85, "Peso_CAGR": 2.5, "Umbral_M": 0.18})
        elif nuevo_riesgo == "Conservador":
            m.update({"Max_EV": 30, "Peso_CAGR": 0.8, "Umbral_M": 0.35})
            
        st.session_state.mandato = m
        st.success(f"✅ Mandato calibrado: {m['Nombre']}")

    # Display de parámetros activos (Visualización del Arsenal)
    m = st.session_state.mandato
    st.divider()
    st.markdown(f"""
    **ESTADO ACTUAL DEL MANDATO:**
    * **Perfil:** `{m['Nombre']}`
    * **Límite EV/FCF:** `{m['Max_EV']}x`
    * **Prioridad CAGR:** `{m['Peso_CAGR']}x`
    * **Umbral Margen:** `{m['Umbral_M']*100}%`
    """)

# --- FLUJO PRINCIPAL DE ANÁLISIS ---
st.title("🔬 Terminal Alpha: Boardroom V5.0")
ticker_input = st.text_input("👉 Ticker a Analizar (Ej: ADBE, TSLA, NVDA):").upper()

if ticker_input:
    with st.spinner(f"📡 Arsenal V5.0: Extrayendo biopsia de {ticker_input}..."):
        tk = yf.Ticker(ticker_input)
        inf = tk.info
        inc_hist, cf_hist = tk.financials, tk.cashflow
        
        if inc_hist.empty or cf_hist.empty:
            st.error("❌ ERROR: Historial financiero incompleto o no disponible.")
        else:
            # --- EXTRACCIÓN Y LIMPIEZA DE DATOS (REVISIÓN DE TYPOS) ---
            rev_hist = inc_hist.loc['Total Revenue'].dropna()[::-1]
            fcf_hist = cf_hist.loc['Free Cash Flow'].dropna()[::-1]
            
            # Cálculo de CAGR (Usando rev_hist para ambos puntos para evitar NameError)
            cagr = (rev_hist.iloc[-1] / rev_hist.iloc[0])**(1/(len(rev_hist)-1)) - 1 if len(rev_hist) > 1 else 0
            
            # Métricas LTM
            fcf_ltm = fcf_hist.iloc[-1]
            rev_ltm = rev_hist.iloc[-1]
            
            # Módulo de CapEx (Lógica V4.1)
            capex_hist = cf_hist.loc['Capital Expenditure'].abs().dropna()[::-1]
            ciclo = "EXPANSIÓN" if capex_hist.iloc[-1] > capex_hist.mean() * 1.3 else "MANTENIMIENTO"
            
            st.subheader(f"📊 Laboratorio de Gabinete: {inf.get('longName')}")
            
            # --- INTERVENCIÓN ESTRATÉGICA (SOTP) ---
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("### ⚠️ AJUSTE SOTP")
                bn = st.number_input("👉 Backlog/RPO (Billones USD):", value=0.0, step=0.1)
                
                # Cálculo automático del margen LTM para sugerencia
                margen_ltm_real = float(to_pct(division_segura(fcf_ltm, rev_ltm)))
                m_sotp = st.number_input(f"👉 Margen FCF para Backlog (LTM: {margen_ltm_real}%):", value=margen_ltm_real)
                
            with col_b:
                st.markdown("### 🧠 CONTEXTO")
                ctx = st.text_area("👉 Contexto Estratégico Clave (Moat, Riesgos, Competencia):", height=150)

            if st.button("⚖️ LANZAR JUNTA DE COMITÉ DE EXPERTOS"):
                # Cálculo de Backlog Real (BR)
                br_calculado = round(bn * (m_sotp / 100), 2)
                
                # Consolidación de datos para la IA
                datos_biopsia = {
                    "Ticker": ticker_input,
                    "PEG": inf.get("pegRatio", "N/D"),
                    "EV_FCF": division_segura(inf.get("enterpriseValue"), fcf_ltm),
                    "GM": to_pct(inf.get("grossMargins")),
                    "FCF_M": to_pct(division_segura(fcf_ltm, rev_ltm)),
                    "CAGR": to_pct(cagr),
                    "Ciclo": ciclo,
                    "BN": bn,
                    "BR": br_calculado,
                    "Ctx": ctx,
                    "Umbral_M_Mandato": m['Umbral_M']
                }

                # --- PROMPT RIGUROSO (MANTENIENDO LA ESENCIA Y AGENTES V4.1) ---
                prompt = f"""
                ERES EL COMITÉ DE UN HEDGE FUND. 
                MANDATO: {m['Nombre']} (Límite EV/FCF: {m['Max_EV']}x, Prioridad CAGR: {m['Peso_CAGR']}x, Umbral Margen: {m['Umbral_M']}).
                DATOS BIOPSIA: {datos_biopsia}

                --- REGLAS DE RIGOR INSTITUCIONAL ---
                1. NO saludes. NO divagues. Usa terminología de Capital Markets (Alpha, FCF Yield, Moat).
                2. CRUZA LA DATA: Evalúa si el EV/FCF de {datos_biopsia['EV_FCF']}x es justificable con el CAGR de {datos_biopsia['CAGR']}% para un horizonte {m['Horizonte']}.
                3. RIGOR EN EL MARGEN: Si el FCF_M ({datos_biopsia['FCF_M']}%) es menor al Umbral ({m['Umbral_M']*100}%), el Auditor debe ser severo.
                4. ANÁLISIS DE SOTP: ¿El Backlog Real de ${datos_biopsia['BR']}B cambia la tesis de valoración?

                --- FORMATO DE SALIDA (ESTRICTO) ---
                <u>IDENTIDAD CORPORATIVA</u>
                (Máximo 2 líneas sobre el foso y mercado).
                ---
                <u>1. AUDITOR GARP</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razonamiento Técnico: (Análisis de valoración vs crecimiento).
                ---
                <u>2. ESTRATEGA MACRO</u>
                * Veredicto: [SÍ/NO/CUIDADO] | Certeza: [X]%
                * Razonamiento Técnico: (Análisis de ciclo {datos_biopsia['Ciclo']} y potencial de Backlog).
                ---
                <u>3. GESTOR DE RIESGOS</u>
                * Nivel de Amenaza: [BAJO/MEDIO/ALTO/CRÍTICO] | Certeza: [X]%
                * Razonamiento Técnico: (Principal Cisne Negro o amenaza estructural).
                ---
                <u>SENTENCIA Y PLAN DE ACCIÓN</u>
                * Veredicto Final: [COMPRA AGRESIVA / DCA / LISTA ESPERA / RECHAZO]
                * Tesis: (Conciliación técnica de los agentes).
                * Plan: (Instrucción de ejecución inmediata para el horizonte {m['Horizonte']}).
                """
                
                with st.spinner("⚖️ Comité en sesión deliberativa..."):
                    try:
                        # MOTOR ANCLADO EN 2.5-FLASH-LITE
                        response = client.models.generate_content(
                            model="gemini-2.5-flash-lite", 
                            contents=prompt
                        )
                        st.markdown("---")
                        # Output con estilo de reporte institucional
                        st.markdown(f"<div class='report-box'>{response.text}</div>", unsafe_allow_html=True)
                        
                        # El guardado en Excel se puede reactivar aquí si es necesario
                    except Exception as e:
                        st.error(f"❌ Error Crítico de la IA: {e}")
