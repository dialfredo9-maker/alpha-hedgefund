import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import json
import os
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Hedge Fund Alpha V4.2", layout="wide", initial_sidebar_state="expanded")

# --- ESTILO CSS PARA MÓVIL Y "MODO PRO" ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    .report-text { font-family: 'Courier New', Courier, monospace; background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; }
    u { text-decoration: underline; color: #58a6ff; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURACIÓN DE APIS ---
GEMINI_API_KEY = "AIzaSyCxbTsTBKXYPGEZW8gT4JLHm7XBvl27eII"
client = genai.Client(api_key=GEMINI_API_KEY)
CONFIG_FILE = "mandato_config.json"
EXCEL_FILE = "Analisis_App_Alpha.xlsx"

# --- PERSISTENCIA: CARGAR/GUARDAR MANDATO ---
def cargar_mandato():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return {"Riesgo": "Moderado", "Horizonte": "Medio", "Max_EV": 45, "Peso_CAGR": 1.2}

def guardar_mandato(m):
    with open(CONFIG_FILE, 'w') as f: json.dump(m, f)

# --- LÓGICA DE BACKEND (MANTENIDA 100%) ---
def division_segura(n, d): return "N/D" if not n or not d or d == 0 else round(n / d, 4)
def to_pct(v): return "N/D" if v in [None, "N/D", np.nan] else round(v * 100, 2)

# --- INTERFAZ LATERAL (PANEL DE CONTROL) ---
with st.sidebar:
    st.title("🛡️ Panel de Mandato")
    m = cargar_mandato()
    
    nuevo_horizonte = st.selectbox("Horizonte:", ["Corto", "Medio", "Largo"], index=["Corto", "Medio", "Largo"].index(m["Horizonte"]))
    st.write("Selecciona Nivel de Riesgo:")
    col1, col2, col3 = st.columns(3)
    
    if col1.button("Cons"): m.update({"Riesgo": "Conservador", "Max_EV": 30, "Peso_CAGR": 0.8})
    if col2.button("Mod"): m.update({"Riesgo": "Moderado", "Max_EV": 45, "Peso_CAGR": 1.2})
    if col3.button("Agr"): m.update({"Riesgo": "Agresivo", "Max_EV": 85, "Peso_CAGR": 2.5})
    
    m["Horizonte"] = nuevo_horizonte
    guardar_mandato(m)
    
    st.divider()
    st.info(f"**Lupa Actual:** {m['Riesgo']} / {m['Horizonte']}\n\nLímite EV/FCF: {m['Max_EV']}x")

# --- CUERPO PRINCIPAL ---
st.title("🔬 Terminal Alpha Boardroom")
ticker = st.text_input("Introduce Ticker:", placeholder="ej: NVDA, TSLA, PLTR").upper()

if ticker:
    # 1. TRIAGE AUTOMÁTICO
    tk = yf.Ticker(ticker)
    inf = tk.info
    if 'sector' not in inf:
        st.error("Ticker no encontrado.")
    else:
        st.subheader(f"📊 Análisis Estratégico: {inf.get('longName')}")
        
        # Extracción de datos
        with st.expander("👁️ Ver Biopsia de Datos Automática", expanded=False):
            inc_h = tk.financials
            cf_h = tk.cashflow
            rev_h = inc_h.loc['Total Revenue'].dropna()[::-1]
            fcf_h = cf_h.loc['Free Cash Flow'].dropna()[::-1]
            cagr = (rev_h.iloc[-1] / rev_h.iloc[0])**(1/(len(rev_h)-1)) - 1 if len(rev_h) > 1 else 0
            fcf_ltm, rev_ltm = fcf_h.iloc[-1], rev_h.iloc[-1]
            
            st.write(f"**CAGR 5Y:** {to_pct(cagr)}% | **FCF Margin:** {to_pct(fcf_ltm/rev_ltm)}%")
            st.write(f"**EV/FCF Actual:** {division_segura(inf.get('enterpriseValue'), fcf_ltm)}x")

        # 2. INTERVENCIÓN DEL DOCTOR (INPUTS PRO)
        col_a, col_b = st.columns(2)
        with col_a:
            bn = st.number_input("Backlog/RPO (Billones USD):", value=0.0)
            m_sotp = st.number_input("Margen SOTP Ajustado (%):", value=float(to_pct(fcf_ltm/rev_ltm)))
        with col_b:
            ctx = st.text_area("Contexto Estratégico Clave:", placeholder="Guerra de precios, nuevos productos, etc.")
        
        if st.button("🚀 LANZAR COMITÉ DE EXPERTOS"):
            br = bn * (m_sotp / 100)
            datos = {
                "Ticker": ticker, "Nombre": inf.get("longName"), "Resumen": inf.get("longBusinessSummary", "")[:300],
                "Mandato": f"{m['Riesgo']}/{m['Horizonte']}", "Max_EV": m["Max_EV"], "Peso_CAGR": m["Peso_CAGR"],
                "EV_FCF": division_segura(inf.get("enterpriseValue"), fcf_ltm),
                "GM": to_pct(inf.get("grossMargins")), "FCF_M": to_pct(fcf_ltm/rev_ltm),
                "CAGR": to_pct(cagr), "BN": bn, "BR": round(br, 2), "Ctx": ctx
            }
            
            # 3. LLAMADA A LA IA
            with st.spinner("El Comité está deliberando..."):
                prompt = f"ERES EL COMITÉ DE UN HEDGE FUND. ANALIZA BAJO MANDATO {m['Riesgo']}: {datos}. Usa formato con <u>Encabezados</u> y Veredictos por Agente."
                try:
                    # Usamos 1.5 Flash para evitar el error 429
                    response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
                    st.markdown("---")
                    st.markdown(f"<div class='report-text'>{response.text}</div>", unsafe_allow_html=True)
                    
                    # 4. GUARDAR RESULTADO
                    df = pd.DataFrame([{**datos, "Verdict": response.text}])
                    if os.path.exists(EXCEL_FILE):
                        df = pd.concat([pd.read_excel(EXCEL_FILE), df], ignore_index=True)
                    df.to_excel(EXCEL_FILE, index=False)
                    st.success("✅ Análisis guardado en el historial.")
                except Exception as e:
                    st.error(f"Error de IA: {e}")