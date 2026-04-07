"""
Plataforma Institucional de Análisis Fundamental y Clasificación de Arquetipos
Arquitectura PRO: FMP API Raw Statements (Bypass Premium), Deep Metrics, Scoring y Gemini 2.5 Pro.
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

GEMINI_MODEL_NAME = 'gemini-2.5-pro'

# =====================================================================
# 2. CAPA DE EXTRACCIÓN: ESTADOS FINANCIEROS CRUDOS (STARTER PLAN)
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
                "price": data.get("price", 0.0),
                "mkt_cap": data.get("mktCap", 0.0)
            }
        return {"sector": "Desconocido", "industry": "Desconocido", "price": 0.0, "mkt_cap": 0.0}
    except:
        return {"sector": "Desconocido", "industry": "Desconocido", "price": 0.0, "mkt_cap": 0.0}

@st.cache_data(ttl=3600)
def fetch_and_calculate_metrics(ticker: str, current_price: float, mkt_cap: float) -> dict:
    """
    MOTOR QUANT: Bypass al muro de pago Premium. 
    Extrae los 3 estados financieros básicos y calcula las métricas avanzadas matemáticamente.
    """
    # Estos endpoints SÍ están incluidos en tu Plan Starter
    url_is = f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}?limit=6&apikey={FMP_API_KEY}" # 6 para calcular crecimiento del último año
    url_bs = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{ticker}?limit=5&apikey={FMP_API_KEY}"
    url_cf = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}?limit=5&apikey={FMP_API_KEY}"
    
    try:
        is_resp = requests.get(url_is, timeout=5)
        if is_resp.status_code != 200:
            return {"_error": f"FMP Error: {is_resp.text}"}
            
        is_data = is_resp.json()
        bs_data = requests.get(url_bs, timeout=5).json()
        cf_data = requests.get(url_cf, timeout=5).json()
        
        if not is_data or not bs_data or not cf_data:
            return {"_error": "FMP no devolvió los estados financieros completos."}

        metrics = {}
        
        # --- CÁLCULOS DEL AÑO ACTUAL (Índice 0) ---
        is_curr, bs_curr, cf_curr = is_data[0], bs_data[0], cf_data[0]
        
        rev_curr = is_curr.get('revenue', 1) or 1
        ebitda_curr = is_curr.get('ebitda', 0)
        net_inc_curr = is_curr.get('netIncome', 0)
        op_inc_curr = is_curr.get('operatingIncome', 0)
        eps_curr = is_curr.get('eps', 0.001) or 0.001
        int_exp_curr = is_curr.get('interestExpense', 0)
        tax_exp_curr = is_curr.get('incomeTaxExpense', 0)
        
        tot_debt_curr = bs_curr.get('totalDebt', 0)
        tot_eq_curr = bs_curr.get('totalEquity', 1) or 1
        cash_curr = bs_curr.get('cashAndCashEquivalents', 0)
        
        fcf_curr = cf_curr.get('freeCashFlow', 0)
        
        # 1. Valoración
        metrics['pe_ratio'] = current_price / eps_curr if eps_curr > 0 else "N/A"
        metrics['pb_ratio'] = mkt_cap / tot_eq_curr if tot_eq_curr > 0 else "N/A"
        
        # Enterprise Value y EV/FCF
        ev_curr = mkt_cap + tot_debt_curr - cash_curr
        metrics['ev_fcf'] = ev_curr / fcf_curr if fcf_curr > 0 else "N/A"
        metrics['fcf_yield'] = fcf_curr / mkt_cap if mkt_cap > 0 else "N/A"
        
        # 2. Eficiencia y Rentabilidad (ROIC y ROE)
        tax_rate = tax_exp_curr / (op_inc_curr - int_exp_curr) if (op_inc_curr - int_exp_curr) > 0 else 0.21
        invested_capital = tot_debt_curr + tot_eq_curr - cash_curr
        metrics['roic'] = (op_inc_curr * (1 - tax_rate)) / invested_capital if invested_capital > 0 else "N/A"
        metrics['roe'] = net_inc_curr / tot_eq_curr
        metrics['ebitda_margin'] = ebitda_curr / rev_curr
        
        # 3. Solvencia
        metrics['debt_equity'] = tot_debt_curr / tot_eq_curr
        metrics['interest_coverage'] = op_inc_curr / int_exp_curr if int_exp_curr > 0 else "N/A"
        
        # 4. Crecimiento Actual vs Año Anterior
        if len(is_data) > 1 and len(cf_data) > 1:
            rev_prev = is_data[1].get('revenue', 1) or 1
            metrics['revenue_growth'] = (rev_curr - rev_prev) / rev_prev
            
            fcf_prev = cf_data[1].get('freeCashFlow', 1) or 1
            metrics['fcf_growth'] = (fcf_curr - fcf_prev) / abs(fcf_prev)
        else:
            metrics['revenue_growth'] = "N/A"
            metrics['fcf_growth'] = "N/A"

        # --- PROMEDIOS HISTÓRICOS DE 5 AÑOS ---
        historico_roic = []
        historico_fcf_yield = []
        historico_rev_growth = []
        
        for i in range(min(5, len(is_data)-1)):
            # Crecimiento de ingresos
            rev = is_data[i].get('revenue', 1) or 1
            rev_prev = is_data[i+1].get('revenue', 1) or 1
            historico_rev_growth.append((rev - rev_prev) / rev_prev)
            
            # FCF Yield histórico aproximado (usando FCF del año / Mkt Cap actual como proxy)
            fcf = cf_data[i].get('freeCashFlow', 0)
            if mkt_cap > 0: historico_fcf_yield.append(fcf / mkt_cap)
            
            # ROIC histórico
            op_inc = is_data[i].get('operatingIncome', 0)
            t_debt = bs_data[i].get('totalDebt', 0)
            t_eq = bs_data[i].get('totalEquity', 1) or 1
            csh = bs_data[i].get('cashAndCashEquivalents', 0)
            inv_cap = t_debt + t_eq - csh
            if inv_cap > 0:
                historico_roic.append((op_inc * 0.79) / inv_cap) # Asumiendo 21% tax rate histórico estándar

        metrics['rev_growth_5y_avg'] = sum(historico_rev_growth)/len(historico_rev_growth) if historico_rev_growth else "N/A"
        metrics['roic_5y_avg'] = sum(historico_roic)/len(historico_roic) if historico_roic else "N/A"
        metrics['fcf_yield_5y_avg'] = sum(historico_fcf_yield)/len(historico_fcf_yield) if historico_fcf_yield else "N/A"
        
        # Value Trap check
        metrics['structural_decline'] = all(g < 0 for g in historico_rev_growth[:3]) if len(historico_rev_growth) >=3 else False

        return metrics

    except Exception as e:
        return {"_error": f"Fallo interno en cálculo de métricas: {str(e)}"}

# =====================================================================
# 3. NÚCLEO ALGORÍTMICO: MOTOR EVOLUCIONADO (SERIES DE TIEMPO)
# =====================================================================

def evaluate_financial_archetype(sector: str, metrics: dict) -> tuple:
    def get_num(key, default=0):
        val = metrics.get(key)
        return float(val) if val != "N/A" and type(val) in [int, float] else default

    roic_current = get_num('roic') * 100
    roic_5y = get_num('roic_5y_avg') * 100
    rev_growth_5y = get_num('rev_growth_5y_avg') * 100
    ebitda_margin = get_num('ebitda_margin') * 100
    debt_to_equity = get_num('debt_equity')
    int_coverage = get_num('interest_coverage', 99)
    pb_ratio = get_num('pb_ratio')
    pe_ratio = get_num('pe_ratio')

    if metrics.get('structural_decline') or (debt_to_equity > 2.0 and int_coverage < 2.0 and int_coverage != 0):
        return "Alerta de Solvencia / Value Trap", "Deterioro secular combinado con cobertura de intereses crítica."

    if sector in ['Financial Services', 'Financials', 'Banks']:
        if get_num('roe') * 100 > 10.0 and 0 < pb_ratio < 1.5: return "Financiera Prime", "ROE de doble dígito transando a descuento contable."
        return "Financiera Promedio", "Métricas bancarias sin convicción."

    if sector in ['Technology', 'Communication Services']:
        if (rev_growth_5y + ebitda_margin) >= 40.0:
            return "SaaS/Tech Elite Consolidada", f"Sincronización histórica (Score Rule of 40: {rev_growth_5y + ebitda_margin:.1f}%)."

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
    def f_pct(val): return f"{val*100:.1f}%" if val != "N/A" and type(val) in [int, float] else "N/A"
    def f_num(val): return f"{val:.2f}" if val != "N/A" and type(val) in [int, float] else "N/A"

    prompt = f"""
    Misión: Eres el Analista Jefe Cuantitativo de un Fondo Institucional, experto en modelado de flujos de caja y ventajas competitivas seculares.
    Activo: {ticker} | Sector: {sector} | Precio: ${price}
    Arquetipo Asignado: '{archetype}'
    
    Data Forense (Actual vs Promedio 5 Años):
    - ROIC: Actual {f_pct(metrics.get('roic'))} | Promedio 5A: {f_pct(metrics.get('roic_5y_avg'))}
    - Crec. Ventas: Actual {f_pct(metrics.get('revenue_growth'))} | Promedio 5A: {f_pct(metrics.get('rev_growth_5y_avg'))}
    - Crec. FCF: Actual {f_pct(metrics.get('fcf_growth'))}
    - FCF Yield: Actual {f_pct(metrics.get('fcf_yield'))} | Promedio 5A: {f_pct(metrics.get('fcf_yield_5y_avg'))}
    - Valoración P/E: {f_num(metrics.get('pe_ratio'))} | Múltiplo EV/FCF: {f_num(metrics.get('ev_fcf'))}
    - Solvencia: Debt/Equity {f_num(metrics.get('debt_equity'))} | Cobertura Intereses: {f_num(metrics.get('interest_coverage'))}
    
    Instrucciones: Analiza rigurosamente el activo utilizando tu máximo nivel de razonamiento lógico. Entrega tu output EXCLUSIVAMENTE en el siguiente formato JSON.
    {{
        "texto_libre": "Un párrafo extenso, técnico y riguroso evaluando la resiliencia del modelo de negocio, la generación real de efectivo (EV/FCF vs P/E), y cualquier riesgo de solvencia o de mercado.",
        "score": [Número entero del 0 al 100],
        "veredicto": "[Elegir estrictamente una: Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Proponer táctica de liquidez (Ej: Compra fraccionada, DCA agresivo mensual, etc)."
    }}
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
        
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        return {"texto_libre": f"Error IA: {str(e)}", "score": 0, "veredicto": "Hold", "estrategia": "Revisar logs del modelo IA."}

# =====================================================================
# 5. UI: TABLERO DE CONTROL INSTITUCIONAL AVANZADO
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: Raw Statements & GEMINI 2.5")
    st.markdown("Motor forense independiente que procesa Estados Financieros crudos desde FMP para eludir Paywalls.")

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
                mkt_cap = profile.get("mkt_cap", 0.0)
                
                # Motor de cálculo manual bypass
                raw_metrics = fetch_and_calculate_metrics(ticker, current_price, mkt_cap)
                
                if not raw_metrics or "_error" in raw_metrics:
                    error_msg = raw_metrics.get('_error', 'Fallo desconocido.') if raw_metrics else 'Conexión fallida.'
                    st.error(f"Error de red/API para {ticker}: {error_msg}")
                    st.markdown("---")
                    continue
                
                archetype_label, rationale = evaluate_financial_archetype(sector_gics, raw_metrics)
                
                st.caption(f"**Sector:** {sector_gics} | **Industria:** {profile.get('industry', 'N/A')} | **Precio Mkt:** ${current_price}")
                
                col1, col2, col3, col4, col5 = st.columns(5)
                def fmt_m(val, is_pct=False):
                    if val == "N/A" or val is None: return "N/A"
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
