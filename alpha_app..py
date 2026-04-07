"""
Plataforma Institucional de Análisis Fundamental y Clasificación de Arquetipos
Arquitectura PRO: FMP API (Starter - 5Y Historical Data), Scoring y Google Gemini AI.
"""

import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
import json

# =====================================================================
# 1. CONFIGURACIÓN DEL ENTORNO Y SECRETS
# =====================================================================
st.set_page_config(
    page_title="Terminal Institucional: Arquetipos Financieros", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, Exception):
    st.error("Error Crítico: Configura las API Keys en .streamlit/secrets.toml.")
    st.stop()

GEMINI_MODEL_NAME = 'gemini-1.5-flash'

# =====================================================================
# 2. CAPA DE EXTRACCIÓN DE DATOS: HISTÓRICO DE 5 AÑOS (STARTER PLAN)
# =====================================================================

@st.cache_data(ttl=86400)
def fetch_fmp_profile(ticker: str) -> dict:
    url_profile = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url_profile, timeout=5).json()
        if resp and isinstance(resp, list):
            data = resp[0]
            return {
                "sector": data.get("sector", "Desconocido"),
                "industry": data.get("industry", "Desconocido"),
                "price": data.get("price", 0.0)
            }
        return {"sector": "Desconocido", "industry": "Desconocido", "price": 0.0}
    except:
        return {"sector": "Desconocido", "industry": "Desconocido", "price": 0.0}

@st.cache_data(ttl=3600)
def fetch_quantitative_metrics(ticker: str) -> dict:
    """Motor de Extracción Profunda. Utiliza el límite de 5 años del Plan Starter."""
    url_metrics = f"https://financialmodelingprep.com/stable/key-metrics?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    url_ratios = f"https://financialmodelingprep.com/stable/ratios?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    url_growth = f"https://financialmodelingprep.com/stable/financial-growth?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    
    metrics = {}
    
    def calc_avg(data_list, key1, key2=None):
        """Calcula el promedio de 5 años omitiendo valores nulos."""
        vals = []
        for d in data_list:
            v = d.get(key1) if d.get(key1) is not None else (d.get(key2) if key2 else None)
            if v is not None: vals.append(v)
        return sum(vals) / len(vals) if vals else "N/A"

    try:
        m_resp = requests.get(url_metrics, timeout=5).json()
        r_resp = requests.get(url_ratios, timeout=5).json()
        g_resp = requests.get(url_growth, timeout=5).json()
        
        # 1. Datos Actuales (Reporte más reciente -> índice 0)
        if m_resp and isinstance(m_resp, list):
            curr_m = m_resp[0]
            metrics['pe_ratio'] = curr_m.get('peRatio', curr_m.get('priceEarningsRatio', "N/A"))
            metrics['pb_ratio'] = curr_m.get('pbRatio', curr_m.get('priceToBookRatio', "N/A"))
            metrics['roe'] = curr_m.get('roe', curr_m.get('returnOnEquity', "N/A"))
            metrics['roic'] = curr_m.get('roic', curr_m.get('returnOnCapitalEmployed', "N/A"))
            metrics['debt_equity'] = curr_m.get('debtToEquity', curr_m.get('debtEquityRatio', "N/A"))
            
            # Promedios Históricos (5 Años)
            metrics['roic_5y_avg'] = calc_avg(m_resp, 'roic', 'returnOnCapitalEmployed')
            metrics['pe_5y_avg'] = calc_avg(m_resp, 'peRatio', 'priceEarningsRatio')

        if r_resp and isinstance(r_resp, list):
            curr_r = r_resp[0]
            metrics['peg_ratio'] = curr_r.get('pegRatio', "N/A")
            metrics['dividend_yield'] = curr_r.get('dividendYield', "N/A")
            metrics['ebitda_margin'] = curr_r.get('ebitdaMargin', "N/A")
            
            metrics['margin_5y_avg'] = calc_avg(r_resp, 'ebitdaMargin')

        if g_resp and isinstance(g_resp, list) and len(g_resp) > 0:
            metrics['revenue_growth'] = g_resp[0].get('revenueGrowth', "N/A")
            metrics['rev_growth_5y_avg'] = calc_avg(g_resp, 'revenueGrowth')
            
            rev_history = [period.get('revenueGrowth', 0) for period in g_resp]
            metrics['structural_decline'] = all(g is not None and g < 0 for g in rev_history[:3])
        else:
            metrics['revenue_growth'] = "N/A"
            metrics['rev_growth_5y_avg'] = "N/A"
            metrics['structural_decline'] = False

    except Exception:
        pass 

    # Normalización de N/A
    clean_metrics = {k: (v if v is not None else "N/A") for k, v in metrics.items()}
    clean_metrics['structural_decline'] = metrics.get('structural_decline', False)
    return clean_metrics

# =====================================================================
# 3. NÚCLEO ALGORÍTMICO: MOTOR EVOLUCIONADO (SERIES DE TIEMPO)
# =====================================================================

def evaluate_financial_archetype(sector: str, metrics: dict) -> tuple:
    def get_num(key, default=0):
        val = metrics.get(key)
        return float(val) if val != "N/A" else default

    roic_current = get_num('roic') * 100
    roic_5y = get_num('roic_5y_avg') * 100
    rev_growth_5y = get_num('rev_growth_5y_avg') * 100
    margin_5y = get_num('margin_5y_avg') * 100
    debt_to_equity = get_num('debt_equity')
    pb_ratio = get_num('pb_ratio')
    pe_ratio = get_num('pe_ratio')
    pe_5y = get_num('pe_5y_avg')

    # 1. Trampa de Valor Confirmada por Tendencia
    if metrics.get('structural_decline') and debt_to_equity > 2.0:
        return "Trampa de Valor Histórica", "Contracción de ingresos sostenida por múltiples periodos y riesgo de solvencia."

    # 2. Financieras
    if sector in ['Financial Services', 'Financials', 'Banks']:
        if get_num('roe') * 100 > 10.0 and 0 < pb_ratio < 1.5: return "Financiera Prime", "ROE de doble dígito transando a descuento."
        return "Financiera Promedio", "Métricas bancarias sin anomalías positivas."

    # 3. SaaS/Tech (Rule of 40 a 5 años)
    if sector in ['Technology', 'Communication Services']:
        if (rev_growth_5y + margin_5y) >= 40.0:
            return "SaaS/Tech Elite Consolidada", f"Supera la Rule of 40 en promedio histórico (Score 5Y: {rev_growth_5y + margin_5y:.1f}%)."

    # 4. Calidad y Moat (Foso Económico Demostrado)
    base_roic = 20.0 if sector == 'Aerospace/Defense' else 10.0 if sector in ['Energy', 'Basic Materials', 'Industrials'] else 15.0
    # Exigimos que tanto el actual como el promedio de 5 años superen el umbral para ser un "Moat" real
    if roic_current > base_roic and roic_5y > base_roic and debt_to_equity < 1.5:
        return "Monopolio Operativo (Deep Moat)", f"Excelencia consistente: ROIC actual {roic_current:.1f}%, Promedio 5A {roic_5y:.1f}%."

    # 5. Valor Profundo vs Histórico
    if 0 < pe_ratio < pe_5y * 0.7 and 0 < pb_ratio < 1.2:
         return "Deep Value (Descuento Histórico)", f"Transando a un 30%+ de descuento respecto a su media histórica de P/E."

    return "Clasificación Neutral", "No dispara alertas de convicción a nivel histórico."

# =====================================================================
# 4. PROMPT HÍBRIDO: TEXTO LIBRE RIGUROSO + JSON DECISIONAL
# =====================================================================

def execute_ai_risk_audit(ticker: str, sector: str, archetype: str, metrics: dict, price: float) -> dict:
    def f_pct(val): return f"{val*100:.1f}%" if val != "N/A" else "N/A"
    def f_num(val): return f"{val:.2f}" if val != "N/A" else "N/A"

    prompt = f"""
    Misión: Eres el Analista Jefe Cuantitativo de un Fondo Institucional.
    Activo: {ticker} | Sector: {sector} | Precio: ${price}
    Arquetipo Asignado: '{archetype}'
    
    Métricas Clave (Actual vs Promedio 5 Años):
    - ROIC: Actual {f_pct(metrics.get('roic'))} | Promedio 5A: {f_pct(metrics.get('roic_5y_avg'))}
    - Crec. Ventas: Actual {f_pct(metrics.get('revenue_growth'))} | Promedio 5A: {f_pct(metrics.get('rev_growth_5y_avg'))}
    - P/E Ratio: Actual {f_num(metrics.get('pe_ratio'))} | Promedio 5A: {f_num(metrics.get('pe_5y_avg'))}
    - Deuda/Patrimonio: {f_num(metrics.get('debt_equity'))}
    - PEG Ratio: {f_num(metrics.get('peg_ratio'))}
    
    Instrucciones: Analiza rigurosamente la sostenibilidad del negocio y entrega tu output EXCLUSIVAMENTE en el siguiente formato JSON.
    {{
        "texto_libre": "Un único párrafo de texto libre (extenso y riguroso) evaluando la resiliencia del modelo de negocio, el foso económico frente al historial de 5 años, e identificando falacias contables o vulnerabilidades macro.",
        "score": [Número entero del 0 al 100],
        "veredicto": "[Elegir: Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Sugerencia operativa enfocada en gestión de flujo de caja de mediano plazo. Ejemplos de estilo: 'Iniciar DCA mensual agresivo utilizando herramientas de inversión fraccionada como Racional', o 'Rotar exposición a liquidez en dólares/euros debido a sobrevaloración histórica', etc."
    }}
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.2))
        
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        return {"texto_libre": f"Error IA: {str(e)}", "score": 0, "veredicto": "Hold", "estrategia": "Error en parseo."}

# =====================================================================
# 5. UI: TABLERO DE CONTROL INSTITUCIONAL
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants: Análisis Histórico & Ejecución")
    st.markdown("Motor apalancado en Series de Tiempo de 5 Años (FMP) y Dictamen de Ejecución IA.")

    with st.sidebar:
        st.header("Cribado de Activos")
        tickers_raw = st.text_input("Tickers (separados por coma)", value="NVDA, MSFT, O")
        st.markdown("---")
        execute_button = st.button("Ejecutar Análisis y Scoring", type="primary", use_container_width=True)

    if execute_button:
        tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
        if not tickers:
            st.error("Proporcione al menos un símbolo bursátil.")
            return

        portfolio_results = []
        
        for ticker in tickers:
            with st.container():
                st.markdown(f"## 📈 {ticker}")
                
                profile = fetch_fmp_profile(ticker)
                sector_gics = profile.get("sector", "Desconocido")
                current_price = profile.get("price", 0.0)
                
                raw_metrics = fetch_quantitative_metrics(ticker)
                
                if not raw_metrics or raw_metrics.get('pe_ratio') == "N/A":
                    st.warning(f"Datos fundamentales insuficientes en FMP para {ticker}.")
                    st.markdown("---")
                    continue
                
                archetype_label, rationale = evaluate_financial_archetype(sector_gics, raw_metrics)
                
                st.caption(f"**Sector:** {sector_gics} | **Precio Mkt:** ${current_price}")
                
                # Fila de métricas comparativas (Actual vs 5 Años)
                col1, col2, col3, col4 = st.columns(4)
                def fmt_m(val, is_pct=False):
                    if val == "N/A": return "N/A"
                    return f"{val*100:.1f}%" if is_pct else f"{val:.2f}x"

                col1.metric("Arquetipo Táctico", archetype_label)
                col2.metric("ROIC (Actual vs Media 5Y)", fmt_m(raw_metrics.get('roic'), True), delta=fmt_m(raw_metrics.get('roic_5y_avg'), True), delta_color="off")
                col3.metric("Crecimiento (Actual vs 5Y)", fmt_m(raw_metrics.get('revenue_growth'), True), delta=fmt_m(raw_metrics.get('rev_growth_5y_avg'), True), delta_color="off")
                col4.metric("P/E (Actual vs Media 5Y)", fmt_m(raw_metrics.get('pe_ratio')), delta=fmt_m(raw_metrics.get('pe_5y_avg')), delta_color="inverse")
                
                st.info(f"**Justificación Algorítmica:** {rationale}")
                
                with st.spinner('Auditando histórico y generando tesis...'):
                    ai_data = execute_ai_risk_audit(ticker, sector_gics, archetype_label, raw_metrics, current_price)
                    
                    st.markdown("### 🧠 Veredicto Institucional y Tesis de Inversión")
                    
                    color_map = {"Strong Buy": "🟢", "Buy": "🟩", "Hold": "🟨", "Sell": "🟧", "Strong Sell": "🔴"}
                    icon = color_map.get(ai_data.get("veredicto", "Hold"), "⚪")
                    score_val = ai_data.get('score', 0)
                    
                    res_col1, res_col2 = st.columns([1.5, 2.5])
                    
                    with res_col1:
                        st.markdown(f"#### {icon} {ai_data.get('veredicto', 'N/A')}")
                        st.progress(score_val / 100, text=f"Score de Convicción: {score_val}/100")
                        st.markdown(f"**Táctica Sugerida:**")
                        st.success(ai_data.get('estrategia', 'Sin estrategia.'))
                        
                    with res_col2:
                        # Aquí volvemos al texto libre extenso y riguroso que querías, pero en un contenedor limpio
                        with st.expander("📝 Leer Auditoría Forense Completa", expanded=True):
                            st.write(ai_data.get('texto_libre', 'Sin análisis detallado.'))
                
                st.markdown("---")
                
                portfolio_results.append({
                    "Activo": ticker,
                    "Veredicto": ai_data.get("veredicto"),
                    "Score": score_val,
                    "Arquetipo": archetype_label,
                    "ROIC 5Y Avg": fmt_m(raw_metrics.get('roic_5y_avg'), True)
                })
        
        if portfolio_results:
            st.markdown("### 📋 Matriz de Ejecución del Portafolio")
            df_portfolio = pd.DataFrame(portfolio_results).sort_values(by="Score", ascending=False).reset_index(drop=True)
            st.dataframe(df_portfolio, use_container_width=True)

if __name__ == "__main__":
    main()
