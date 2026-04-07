"""
Plataforma Institucional de Análisis Fundamental y Clasificación de Arquetipos
Arquitectura Optimizada: Streamlit, yfinance (Sectorización), API FMP (Bulk Metrics), y Google Gemini AI.
"""

import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import google.generativeai as genai
from urllib.error import HTTPError
import json
import time

# =====================================================================
# 1. CONFIGURACIÓN DEL ENTORNO, GESTIÓN DE ESTADO Y SECRETS
# =====================================================================
st.set_page_config(
    page_title="Terminal Institucional: Arquetipos Financieros", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Inicialización segura de claves de API
try:
    # Corrección: st.secrets se maneja como un diccionario
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("Error Crítico de Configuración: Las claves de API no están definidas en .streamlit/secrets.toml.")
    st.stop()

GEMINI_MODEL_NAME = 'gemini-1.5-flash'

# =====================================================================
# 2. CAPA DE EXTRACCIÓN DE DATOS: MEMOIZACIÓN Y RESILIENCIA
# =====================================================================

@st.cache_data(ttl=86400)
def fetch_sectorial_taxonomy(ticker: str) -> dict:
    """Recupera el mapeo ontológico GICS utilizando yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "sector": info.get("sector", "Desconocido"),
            "industry": info.get("industry", "Desconocido"),
            "market_cap": info.get("marketCap", 0),
            "beta": info.get("beta", 1.0)
        }
    except Exception as e:
        return {"error": str(e), "sector": "Desconocido", "industry": "Desconocido"}

@st.cache_data(ttl=3600)
def fetch_quantitative_metrics(ticker: str) -> dict:
    """Extrae ratios TTM y vectores de crecimiento corporativo desde FMP."""
    url_ratios = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
    url_growth = f"https://financialmodelingprep.com/api/v3/financial-growth/{ticker}?limit=4&apikey={FMP_API_KEY}"
    
    try:
        ratios_response = requests.get(url_ratios, timeout=5)
        growth_response = requests.get(url_growth, timeout=5)
        
        ratios_response.raise_for_status()
        growth_response.raise_for_status()
        
        ratios_json = ratios_response.json()
        growth_json = growth_response.json()
        
        metrics = {}
        # Corrección: FMP devuelve una LISTA de diccionarios. Se debe acceder al índice [0]
        if ratios_json and isinstance(ratios_json, list):
            data = ratios_json[0]
            metrics['pe_ratio'] = data.get('priceEarningsRatioTTM', 0)
            metrics['pb_ratio'] = data.get('priceToBookRatioTTM', 0)
            metrics['peg_ratio'] = data.get('pegRatioTTM', 0)
            metrics['roe'] = data.get('returnOnEquityTTM', 0)
            metrics['roic'] = data.get('returnOnCapitalEmployedTTM', 0)
            metrics['dividend_yield'] = data.get('dividendYieldTTM', 0)
            metrics['debt_equity'] = data.get('debtEquityRatioTTM', 0)
            metrics['ebitda_margin'] = data.get('ebitdaMarginTTM', 0) 
            metrics['payout_ratio'] = data.get('payoutRatioTTM', 0)

        if growth_json and isinstance(growth_json, list) and len(growth_json) > 0:
            # Corrección: Acceso a la propiedad dentro del primer elemento de la lista
            metrics['revenue_growth'] = growth_json[0].get('revenueGrowth', 0)
            rev_history = [period.get('revenueGrowth', 0) for period in growth_json]
            metrics['structural_decline'] = all(g < 0 for g in rev_history[:3])
        else:
            metrics['revenue_growth'] = 0
            metrics['structural_decline'] = False
            
        return metrics
    except Exception as e:
        st.warning(f"Excepción de conectividad FMP para {ticker}: {e}")
        return {}

# =====================================================================
# 3. NÚCLEO ALGORÍTMICO: MOTOR DE UMBRALES DINÁMICOS MULTI-SECTOR
# =====================================================================

def evaluate_financial_archetype(sector: str, metrics: dict) -> tuple:
    """Evalúa condicionalmente el vector de métricas contra umbrales mutables."""
    if not metrics:
        return "Análisis Abortado", "Datos fundamentales insuficientes para ejecución heurística."

    rev_growth_p = metrics.get('revenue_growth', 0) * 100
    ebitda_margin_p = metrics.get('ebitda_margin', 0) * 100
    roe_p = metrics.get('roe', 0) * 100
    roic_p = metrics.get('roic', 0) * 100
    div_yield_p = metrics.get('dividend_yield', 0) * 100
    debt_to_equity = metrics.get('debt_equity', 0)
    pb_ratio = metrics.get('pb_ratio', 0)
    pe_ratio = metrics.get('pe_ratio', 0)

    # 1. Filtro Excluyente Primario: Trampa de Valor
    if metrics.get('structural_decline') and debt_to_equity > 2.0:
        if pb_ratio < 1.5 or pe_ratio < 15:
            return "Trampa de Valor (Value Trap)", "Anomalía detectada: La valoración baja es engañosa. Ocurre una contracción secular de ingresos exacerbada por un apalancamiento agresivo."

    # 2. Motor Institucional: Financieras y Banca (Corrección: Lista de sectores añadida)
    if sector in ['Financial Services', 'Financials', 'Banks']:
        if roe_p > 10.0 and pb_ratio < 1.5:
            return "Financiera Prime (P/B-ROE Model)", f"Eficiencia de patrimonio óptima (ROE: {roe_p:.1f}%) con descuento contable (P/B: {pb_ratio:.2f}x)."
        elif roe_p < 6.0:
            return "Financiera Deteriorada", f"Incapacidad de superar el coste del capital social (ROE: {roe_p:.1f}%)."
        else:
            return "Financiera Consolidada", "Evaluación neutral en los modelos de fijación de precios bancarios."

    # 3. Motor de Rendimiento: Utilities y REITs (Corrección: Lista de sectores añadida)
    if sector in ['Utilities', 'Real Estate']:
        if div_yield_p > 3.5 and metrics.get('payout_ratio', 1) < 0.95:
            return "Generador de Rendimiento Sólido", f"Flujos inelásticos asegurando un dividendo del {div_yield_p:.2f}%, sostenido por métricas de pago razonables."
        else:
            return "Rendimiento Amenazado (Cut Risk)", "El rendimiento ofrecido no compensa el riesgo del sector o el ratio de pago denota estrés inminente."

    # 4. Motor de Hipercrecimiento: Rule of 40 (Corrección: Lista de sectores añadida)
    if sector in ['Technology', 'Communication Services']:
        rule_of_40_score = rev_growth_p + ebitda_margin_p
        if rule_of_40_score >= 40.0:
            return "SaaS/Tech Elite (Rule of 40)", f"Fuerte sincronización operativa; score de {rule_of_40_score:.1f}% (Crecimiento: {rev_growth_p:.1f}%, Margen: {ebitda_margin_p:.1f}%)."

    # 5. Motor Híbrido: GARP
    peg = metrics.get('peg_ratio', 99)
    if 0 < peg < 1.0 and 10 < pe_ratio < 25:
        return "GARP (Growth at a Reasonable Price)", f"Oportunidad asimétrica; fuerte expansión no descontada (PEG ratio: {peg:.2f})."

    # 6. Motor de Calidad y Moats (Corrección: Lista de sectores añadida)
    base_roic_threshold = 15.0 
    if sector == 'Aerospace/Defense': 
        base_roic_threshold = 20.0
    elif sector in ['Energy', 'Basic Materials', 'Industrials']: 
        base_roic_threshold = 10.0 
    
    if roic_p > base_roic_threshold and debt_to_equity < 1.5:
        return "Compuesto de Alta Calidad (Moat)", f"Excelencia en la asignación de capital operativo (ROIC del {roic_p:.1f}%) sin dependencia de deuda tóxica."

    # 7. Motor de Valor Residual
    if 0 < pb_ratio < 1.2 and 0 < pe_ratio < 12 and not metrics.get('structural_decline'):
         return "Valor Profundo Confirmado", f"Múltiplos en niveles de liquidación o desilusión máxima (P/B: {pb_ratio:.2f}) con fundamentales estabilizados."

    return "Cíclica Indefinida o Clasificación Neutral", "Los datos carecen de desviaciones suficientes para disparar algoritmos de convicción."

# =====================================================================
# 4. INGENIERÍA DE PROMPTS ORIGINAL Y AUDITORÍA DE IA
# =====================================================================

def execute_ai_risk_audit(ticker: str, sector: str, archetype: str, metrics: dict) -> str:
    """Fuerza a Gemini a realizar un análisis en segunda derivada."""
    prompt = f"""
    Misión: Actúa como el Analista Jefe de Riesgos Cuantitativos de un Fondo de Cobertura.
    
    Contexto de Evaluación:
    - Entidad: {ticker}
    - Segmento GICS: {sector}
    - Clasificación Algorítmica Preliminar: '{archetype}'
    
    Vector de Datos Suministrado:
    - Dinámica de Ventas (YoY): {metrics.get('revenue_growth', 0)*100:.1f}%
    - Eficiencia de Capital Operativo (ROIC): {metrics.get('roic', 0)*100:.1f}%
    - Múltiplo Precio/Beneficio al Crecimiento (PEG): {metrics.get('peg_ratio', 'N/A')}
    - Apalancamiento Estructural (Debt/Equity): {metrics.get('debt_equity', 'N/A')}
    - Prima Contable (P/B Ratio): {metrics.get('pb_ratio', 'N/A')}
    
    Instrucciones Estrictas:
    Basado en finanzas corporativas rigurosas, redacta una evaluación de no más de 3 párrafos formales abordando:
    1. Confirmación o refutación de la clasificación '{archetype}' en base a las distorsiones comunes del sector.
    2. Identificación del Foso Económico (Moat) o vulnerabilidades estructurales inherentes a este modelo de negocio.
    3. Alertas sobre falacias contables (p.ej. impacto silencioso de opciones sobre acciones en tecnológicas o la amenaza inminente de los tipos de interés en utilidades).
    NO uses listas, mantén un formato de narrativa fluida y altamente técnica.
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.2)
        )
        return response.text
    except Exception as e:
        return f"Error en la auditoría de inferencia del LLM: {str(e)}"

# =====================================================================
# 5. DESPLIEGUE DEL FRONTEND
# =====================================================================

def main():
    st.title("🏛️ Plataforma Institucional: Arquetipos Financieros y Análisis Cuantitativo")
    st.markdown("Motor heurístico de umbrales dinámicos apalancado por FMP, yfinance y validación de Segunda Derivada mediante Google Gemini.")

    with st.sidebar:
        st.header("Configuración de Portafolio")
        tickers_raw = st.text_input("Símbolos Bursátiles (Ticker CSV)", value="MSFT, JPM, O, LMT, INTC")
        st.markdown("---")
        st.caption("Arquitectura diseñada para mitigar el sesgo estático de valoración.")
        execute_button = st.button("Ejecutar Modelado Institucional", type="primary")

    if execute_button:
        tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
        
        if not tickers:
            st.error("Protocolo fallido: Proporcione al menos un símbolo bursátil.")
            return

        st.subheader("Auditoría Multifactorial en Tiempo Real")
        ui_progress = st.progress(0)
        
        # Corrección: Inicialización de lista de resultados
        portfolio_results = []
        
        for index, ticker in enumerate(tickers):
            with st.expander(f"Expediente de Valoración: {ticker}", expanded=True):
                
                taxonomy = fetch_sectorial_taxonomy(ticker)
                sector_gics = taxonomy.get("sector", "Desconocido")
                st.write(f"**Atribución Sectorial (GICS):** {sector_gics} | **Clúster Industrial:** {taxonomy.get('industry', 'Desconocida')}")
                
                raw_metrics = fetch_quantitative_metrics(ticker)
                
                if not raw_metrics:
                    st.warning(f"Insuficiencia de datos métricos primarios para {ticker}.")
                    continue
                
                archetype_label, rationale = evaluate_financial_archetype(sector_gics, raw_metrics)
                
                st.success(f"**Identidad de Arquetipo:** {archetype_label}")
                st.info(f"**Racionalidad Matemática:** {rationale}")
                
                with st.spinner('Ejecutando proceso de inferencia LLM...'):
                    risk_insight = execute_ai_risk_audit(ticker, sector_gics, archetype_label, raw_metrics)
                    st.markdown("#### 🧠 Dictamen de Riesgo (Modelado Cualitativo IA)")
                    st.write(risk_insight)
                
                portfolio_results.append({
                    "Activo": ticker,
                    "Dominio Sectorial": sector_gics,
                    "Clasificación Heurística": archetype_label,
                    "Expansión P/E": f"{raw_metrics.get('pe_ratio', 0):.1f}x",
                    "Eficiencia (ROIC)": f"{raw_metrics.get('roic', 0)*100:.1f}%",
                    "Apalancamiento (D/E)": f"{raw_metrics.get('debt_equity', 0):.2f}"
                })
            
            ui_progress.progress((index + 1) / len(tickers))
        
        if portfolio_results:
            st.markdown("### 📊 Matriz Consolidada de Exposición de Portafolio")
            df_portfolio = pd.DataFrame(portfolio_results)
            st.dataframe(df_portfolio, use_container_width=True)

if __name__ == "__main__":
    main()
