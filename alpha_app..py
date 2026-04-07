"""
Plataforma Institucional de Análisis Fundamental y Clasificación de Arquetipos
Arquitectura PRO: FMP API (Starter 5Y), Deep Metrics, Scoring y Gemini 2.5 Pro (JSON).
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

# =====================================================================
# SELECCIÓN DEL MODELO DE GRADO INSTITUCIONAL
# =====================================================================
# Se exige gemini-2.5-pro para máximo razonamiento deductivo y rigor en JSON.
GEMINI_MODEL_NAME = 'gemini-2.5-pro'

# =====================================================================
# 2. CAPA DE EXTRACCIÓN DE DATOS: DEEP METRICS (5 AÑOS)
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
    url_metrics = f"https://financialmodelingprep.com/stable/key-metrics?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    url_ratios = f"https://financialmodelingprep.com/stable/ratios?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    url_growth = f"https://financialmodelingprep.com/stable/financial-growth?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    
    metrics = {}
    
    def calc_avg(data_list, key1, key2=None):
        vals = []
        for d in data_list:
            v = d.get(key1) if d.get(key1) is not None else (d.get(key2) if key2 else None)
            if v is not None: vals.append(v)
        return sum(vals) / len(vals) if vals else "N/A"

    try:
        m_resp = requests.get(url_metrics, timeout=5).json()
        r_resp = requests.get(url_ratios, timeout=5).json()
        g_resp = requests.get(url_growth, timeout=5).json()
        
        # 1. Extracción de Key Metrics (Actual y 5Y Avg)
        if m_resp and isinstance(m_resp, list):
            curr_m = m_resp[0]
            metrics['pe_ratio'] = curr_m.get('peRatio', curr_m.get('priceEarningsRatio', "N/A"))
            metrics['pb_ratio'] = curr_m.get('pbRatio', curr_m.get('priceToBookRatio', "N/A"))
            metrics['roe'] = curr_m.get('roe', curr_m.get('returnOnEquity', "N/A"))
            metrics['roic'] = curr_m.get('roic', curr_m.get('returnOnCapitalEmployed', "N/A"))
            metrics['debt_equity'] = curr_m.get('debtToEquity', curr_m.get('debtEquityRatio', "N/A"))
            
            # Nuevas métricas avanzadas
            metrics['fcf_yield'] = curr_m.get('freeCashFlowYield', "N/A")
            metrics['ev_fcf'] = curr_m.get('evToFreeCashFlow', "N/A")
            metrics['interest_coverage'] = curr_m.get('interestCoverage', "N/A")
            metrics['current_ratio'] = curr_m.get('currentRatio', "N/A")
            
            # Promedios Históricos (5 Años)
            metrics['roic_5y_avg'] = calc_avg(m_resp, 'roic', 'returnOnCapitalEmployed')
            metrics['fcf_yield_5y_avg'] = calc_avg(m_resp, 'freeCashFlowYield')

        # 2. Extracción de Ratios
        if r_resp and isinstance(r_resp, list):
            curr_r = r_resp[0]
            metrics['peg_ratio'] = curr_r.get('pegRatio', "N/A")
            metrics['dividend_yield'] = curr_r.get('dividendYield', "N/A")
            metrics['ebitda_margin'] = curr_r.get('ebitdaMargin', "N/A")
            metrics['margin_5y_avg'] = calc_avg(r_resp, 'ebitdaMargin')

        # 3. Extracción de Crecimiento (Ventas y Efectivo)
        if g_resp and isinstance(g_resp, list) and len(g_resp) > 0:
            metrics['revenue_growth'] = g_resp[0].get('revenueGrowth', "N/A")
            metrics['fcf_growth'] = g_resp[0].get('freeCashFlowGrowth', "N/A")
            metrics['rd_growth'] = g_resp[0].get('rdexpenseGrowth', "N/A")
            
            metrics['rev_growth_5y_avg'] = calc_avg(g_resp, 'revenueGrowth')
            metrics['fcf_growth_5y_avg'] = calc_avg(g_resp, 'freeCashFlowGrowth')
            
            rev_history = [period.get('revenueGrowth', 0) for period in g_resp]
            metrics['structural_decline'] = all(g is not None and g < 0 for g in rev_history[:3])
        else:
            metrics['revenue_growth'] = "N/A"
            metrics['fcf_growth'] = "N/A"
            metrics['structural_decline'] = False

    except Exception:
        pass 

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
    int_coverage = get_num('interest_coverage')
    pb_ratio = get_num('pb_ratio')
    pe_ratio = get_num('pe_ratio')

    if metrics.get('structural_decline') or (debt_to_equity > 2.0 and int_coverage < 2.0 and int_coverage != 0):
        return "Alerta de Solvencia / Value Trap", "Deterioro secular de ingresos combinado con cobertura de intereses crítica."

    if sector in ['Financial Services', 'Financials', 'Banks']:
        if get_num('roe') * 100 > 10.0 and 0 < pb_ratio < 1.5: return "Financiera Prime", "ROE de doble dígito transando a descuento contable."
        return "Financiera Promedio", "Métricas bancarias sin convicción."

    if sector in ['Technology', 'Communication Services']:
        if (rev_growth_5y + margin_5y) >= 40.0:
            return "SaaS/Tech Elite Consolidada", f"Sincronización histórica (Score Rule of 40: {rev_growth_5y + margin_5y:.1f}%)."

    base_roic = 20.0 if sector == 'Aerospace/Defense' else 10.0 if sector in ['Energy', 'Basic Materials', 'Industrials'] else 15.0
    fcf_yield_5y = get_num('fcf_yield_5y_avg') * 100

    if roic_current > base_roic and roic_5y > base_roic:
        if fcf_yield_5y > 3.0:
            return "Monopolio de Efectivo (Deep Moat)", f"ROIC histórico {roic_5y:.1f}% con conversión de caja sólida."
        return "Compuesto de Calidad (Moat)", f"Excelencia en asignación (ROIC 5A: {roic_5y:.1f}%) pero conversión de caja moderada."

    return "Clasificación Neutral", "Métricas dentro de parámetros estadísticos normales."

# =====================================================================
# 4. PROMPT HÍBRIDO: GEMINI 2.5 PRO (JSON DECISIONAL RIGUROSO)
# =====================================================================

def execute_ai_risk_audit(ticker: str, sector: str, archetype: str, metrics: dict, price: float) -> dict:
    def f_pct(val): return f"{val*100:.1f}%" if val != "N/A" else "N/A"
    def f_num(val): return f"{val:.2f}" if val != "N/A" else "N/A"

    prompt = f"""
    Misión: Eres el Analista Jefe Cuantitativo de un Fondo Institucional, experto en modelado de flujos de caja y ventajas competitivas seculares.
    Activo: {ticker} | Sector: {sector} | Precio: ${price}
    Arquetipo Asignado: '{archetype}'
    
    Data Forense (Actual vs Promedio 5 Años):
    - ROIC: Actual {f_pct(metrics.get('roic'))} | Promedio 5A: {f_pct(metrics.get('roic_5y_avg'))}
    - Crec. Ventas: Actual {f_pct(metrics.get('revenue_growth'))} | Promedio 5A: {f_pct(metrics.get('rev_growth_5y_avg'))}
    - Crec. FCF: Actual {f_pct(metrics.get('fcf_growth'))} | Promedio 5A: {f_pct(metrics.get('fcf_growth_5y_avg'))}
    - FCF Yield: Actual {f_pct(metrics.get('fcf_yield'))}
    - Valoración P/E: {f_num(metrics.get('pe_ratio'))} | Múltiplo EV/FCF: {f_num(metrics.get('ev_fcf'))}
    - Solvencia: Debt/Equity {f_num(metrics.get('debt_equity'))} | Cobertura Intereses: {f_num(metrics.get('interest_coverage'))}
    
    Instrucciones: Analiza rigurosamente el activo utilizando tu máximo nivel de razonamiento lógico. Entrega tu output EXCLUSIVAMENTE en el siguiente formato JSON.
    {{
        "texto_libre": "Un párrafo extenso, técnico y riguroso evaluando la resiliencia del modelo de negocio, la generación real de efectivo (FCF vs Net Income), y cualquier riesgo de sobrevaloración o insolvencia detectado en la serie de 5 años.",
        "score": [Número entero del 0 al 100],
        "veredicto": "[Elegir estrictamente una: Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Proponer una táctica de despliegue de liquidez. Ejemplos: 'Iniciar DCA mensual agresivo utilizando herramientas de inversión fraccionada como Racional', 'Acumular tácticamente en correcciones del 10%', o 'Rotar a liquidez por sobrevaloración'."
    }}
    """
    try:
        # Se establece una temperatura bajísima para asegurar que el modelo no rompa el JSON
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
        
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        return {"texto_libre": f"Error IA: {str(e)}", "score": 0, "veredicto": "Hold", "estrategia": "Revisar conectividad API."}

# =====================================================================
# 5. UI: TABLERO DE CONTROL INSTITUCIONAL AVANZADO
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: Deep Metrics & GEMINI 2.5")
    st.markdown("Motor forense apalancado en FMP 5Y History y modelos de razonamiento avanzado.")

    with st.sidebar:
        st.header("Cribado de Activos")
        tickers_raw = st.text_input("Tickers (separados por coma)", value="NVDA, CEG, MSFT, VRT")
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
                
                st.caption(f"**Sector:** {sector_gics} | **Industria:** {profile.get('industry', 'N/A')} | **Precio Mkt:** ${current_price}")
                
                # Fila 1: Rentabilidad y Valoración
                col1, col2, col3, col4, col5 = st.columns(5)
                def fmt_m(val, is_pct=False):
                    if val == "N/A": return "N/A"
                    return f"{val*100:.1f}%" if is_pct else f"{val:.2f}x"

                col1.metric("Arquetipo Táctico", archetype_label)
                col2.metric("ROIC (Media 5Y)", fmt_m(raw_metrics.get('roic_5y_avg'), True))
                col3.metric("FCF Yield (Actual)", fmt_m(raw_metrics.get('fcf_yield'), True))
                col4.metric("EV / FCF", fmt_m(raw_metrics.get('ev_fcf')))
                col5.metric("Interest Coverage", fmt_m(raw_metrics.get('interest_coverage')))
                
                st.info(f"**Justificación Algorítmica:** {rationale}")
                
                with st.spinner('Sintetizando veredicto AI (Gemini 2.5 Pro)...'):
                    ai_data = execute_ai_risk_audit(ticker, sector_gics, archetype_label, raw_metrics, current_price)
                    
                    st.markdown("### 🧠 Veredicto Institucional y Ejecución")
                    
                    color_map = {"Strong Buy": "🟢", "Buy": "🟩", "Hold": "🟨", "Sell": "🟧", "Strong Sell": "🔴"}
                    icon = color_map.get(ai_data.get("veredicto", "Hold"), "⚪")
                    score_val = ai_data.get('score', 0)
                    
                    res_col1, res_col2 = st.columns([1.5, 2.5])
                    
                    with res_col1:
                        st.markdown(f"#### {icon} {ai_data.get('veredicto', 'N/A')}")
                        st.progress(score_val / 100, text=f"Score de Convicción: {score_val}/100")
                        st.markdown(f"**Táctica de Despliegue de Capital:**")
                        st.success(ai_data.get('estrategia', 'Sin estrategia definida.'))
                        
                    with res_col2:
                        with st.expander("📝 Leer Auditoría Forense Completa", expanded=True):
                            st.write(ai_data.get('texto_libre', 'Sin análisis detallado.'))
                
                st.markdown("---")
                
                portfolio_results.append({
                    "Activo": ticker,
                    "Veredicto": ai_data.get("veredicto"),
                    "Score": score_val,
                    "Arquetipo": archetype_label,
                    "ROIC 5Y Avg": fmt_m(raw_metrics.get('roic_5y_avg'), True),
                    "FCF Yield": fmt_m(raw_metrics.get('fcf_yield'), True)
                })
        
        if portfolio_results:
            st.markdown("### 📋 Matriz de Ejecución del Portafolio")
            df_portfolio = pd.DataFrame(portfolio_results).sort_values(by="Score", ascending=False).reset_index(drop=True)
            st.dataframe(df_portfolio, use_container_width=True)

if __name__ == "__main__":
    main()
