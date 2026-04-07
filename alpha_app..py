"""
Plataforma Institucional de Análisis Fundamental y Clasificación de Arquetipos
Arquitectura PRO: Enrutamiento Híbrido (FMP Stable + yFinance), Deep Metrics y Gemini 2.5 Pro.
"""

import streamlit as st
import requests
import yfinance as yf
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
# 2. CAPA DE EXTRACCIÓN: ENRUTAMIENTO HÍBRIDO (FMP -> YFINANCE)
# =====================================================================

@st.cache_data(ttl=86400)
def fetch_fmp_profile(ticker: str) -> dict:
    url_profile = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}"
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
    except:
        pass
    
    # Fallback YF
    try:
        info = yf.Ticker(ticker).info
        return {
            "sector": info.get("sector", "Desconocido"),
            "industry": info.get("industry", "Desconocido"),
            "price": info.get("currentPrice", 0.0),
            "mkt_cap": info.get("marketCap", 0.0)
        }
    except:
        return {"sector": "Desconocido", "industry": "Desconocido", "price": 0.0, "mkt_cap": 0.0}

@st.cache_data(ttl=3600)
def fetch_quantitative_metrics(ticker: str, mkt_cap: float) -> dict:
    """Intenta extracción primaria vía FMP Stable. Si falla, cálcula vía yFinance."""
    metrics = {}
    
    def calc_avg(data_list, key1, key2=None):
        vals = [d.get(key1, d.get(key2)) for d in data_list if d.get(key1) is not None or d.get(key2) is not None]
        return sum(vals) / len(vals) if vals else "N/A"

    # --- INTENTO 1: FMP API (Plan Starter 2026) ---
    url_metrics = f"https://financialmodelingprep.com/stable/key-metrics?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    url_ratios = f"https://financialmodelingprep.com/stable/ratios?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    url_growth = f"https://financialmodelingprep.com/stable/financial-growth?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
    
    fmp_success = False
    try:
        m_json = requests.get(url_metrics, timeout=5).json()
        r_json = requests.get(url_ratios, timeout=5).json()
        g_json = requests.get(url_growth, timeout=5).json()
        
        if m_json and isinstance(m_json, list) and len(m_json) > 0:
            curr_m = m_json[0]
            metrics['pe_ratio'] = curr_m.get('peRatio', curr_m.get('priceEarningsRatio', "N/A"))
            metrics['pb_ratio'] = curr_m.get('pbRatio', curr_m.get('priceToBookRatio', "N/A"))
            metrics['roe'] = curr_m.get('roe', curr_m.get('returnOnEquity', "N/A"))
            metrics['roic'] = curr_m.get('roic', curr_m.get('returnOnCapitalEmployed', "N/A"))
            metrics['debt_equity'] = curr_m.get('debtToEquity', curr_m.get('debtEquityRatio', "N/A"))
            metrics['fcf_yield'] = curr_m.get('freeCashFlowYield', "N/A")
            metrics['ev_fcf'] = curr_m.get('evToFreeCashFlow', "N/A")
            metrics['interest_coverage'] = curr_m.get('interestCoverage', "N/A")
            
            metrics['roic_5y_avg'] = calc_avg(m_json, 'roic', 'returnOnCapitalEmployed')
            metrics['fcf_yield_5y_avg'] = calc_avg(m_json, 'freeCashFlowYield')
            
            if r_json and len(r_json) > 0:
                metrics['peg_ratio'] = r_json[0].get('pegRatio', "N/A")
                metrics['ebitda_margin'] = r_json[0].get('ebitdaMargin', "N/A")
                metrics['margin_5y_avg'] = calc_avg(r_json, 'ebitdaMargin')
                
            if g_json and len(g_json) > 0:
                metrics['revenue_growth'] = g_json[0].get('revenueGrowth', "N/A")
                metrics['rev_growth_5y_avg'] = calc_avg(g_json, 'revenueGrowth')
                rev_hist = [g.get('revenueGrowth', 0) for g in g_json]
                metrics['structural_decline'] = all(g is not None and g < 0 for g in rev_hist[:3])
            
            fmp_success = True
    except Exception:
        pass

    # --- INTENTO 2: FALLBACK YFINANCE (Si FMP devuelve vacío o falla) ---
    if not fmp_success:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            inc = stock.financials
            bs = stock.balance_sheet
            cf = stock.cashflow
            
            if inc.empty or bs.empty: return {"_error": "Sin datos en FMP ni YF."}
            
            def get_val(df, row_names, col_idx=0):
                for name in row_names:
                    if name in df.index:
                        try:
                            v = df.iloc[:, col_idx].loc[name]
                            if pd.notna(v): return float(v)
                        except: continue
                return 0

            rev = get_val(inc, ['Total Revenue'])
            op_inc = get_val(inc, ['Operating Income'])
            int_exp = get_val(inc, ['Interest Expense'])
            ebitda = get_val(inc, ['EBITDA'])
            t_debt = get_val(bs, ['Total Debt'])
            t_eq = get_val(bs, ['Stockholders Equity'])
            cash = get_val(bs, ['Cash And Cash Equivalents'])
            fcf = get_val(cf, ['Free Cash Flow'])
            
            metrics['pe_ratio'] = info.get('trailingPE', "N/A")
            metrics['pb_ratio'] = info.get('priceToBook', "N/A")
            metrics['ebitda_margin'] = ebitda / rev if rev else "N/A"
            metrics['debt_equity'] = t_debt / t_eq if t_eq else "N/A"
            metrics['interest_coverage'] = op_inc / int_exp if int_exp else "N/A"
            metrics['fcf_yield'] = fcf / mkt_cap if mkt_cap else "N/A"
            metrics['ev_fcf'] = info.get('enterpriseValue', mkt_cap) / fcf if fcf > 0 else "N/A"
            
            inv_cap = t_debt + t_eq - cash
            metrics['roic'] = (op_inc * 0.79) / inv_cap if inv_cap > 0 else "N/A"
            
            # Histórico simplificado
            hist_rev_growth, hist_roic = [], []
            cols = min(5, len(inc.columns))
            for i in range(cols - 1):
                r_n = get_val(inc, ['Total Revenue'], i)
                r_p = get_val(inc, ['Total Revenue'], i+1)
                if r_p: hist_rev_growth.append((r_n - r_p) / r_p)
                
            for i in range(cols):
                oi = get_val(inc, ['Operating Income'], i)
                td = get_val(bs, ['Total Debt'], i)
                te = get_val(bs, ['Stockholders Equity'], i)
                csh = get_val(bs, ['Cash And Cash Equivalents'], i)
                ic = td + te - csh
                if ic > 0: hist_roic.append((oi * 0.79) / ic)

            metrics['revenue_growth'] = hist_rev_growth[0] if hist_rev_growth else "N/A"
            metrics['rev_growth_5y_avg'] = sum(hist_rev_growth)/len(hist_rev_growth) if hist_rev_growth else "N/A"
            metrics['roic_5y_avg'] = sum(hist_roic)/len(hist_roic) if hist_roic else "N/A"
            metrics['structural_decline'] = all(g < 0 for g in hist_rev_growth[:3]) if len(hist_rev_growth) >=3 else False
            metrics['peg_ratio'] = "N/A" # YF no da PEG histórico fácil
            
        except Exception as e:
            return {"_error": f"Fallo Híbrido: {str(e)}"}

    clean_metrics = {k: (v if v is not None else "N/A") for k, v in metrics.items()}
    clean_metrics['structural_decline'] = metrics.get('structural_decline', False)
    return clean_metrics

# =====================================================================
# 3. NÚCLEO ALGORÍTMICO Y 4. PROMPT GEMINI 2.5 PRO
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

    if metrics.get('structural_decline') or (debt_to_equity > 2.0 and int_coverage < 2.0 and int_coverage != 0):
        return "Alerta de Solvencia / Value Trap", "Deterioro secular y cobertura de intereses crítica."

    if sector in ['Technology', 'Communication Services']:
        if (rev_growth_5y + ebitda_margin) >= 40.0:
            return "SaaS/Tech Elite Consolidada", f"Sincronización histórica (Score Rule of 40: {rev_growth_5y + ebitda_margin:.1f}%)."

    base_roic = 20.0 if sector == 'Aerospace/Defense' else 10.0 if sector in ['Energy', 'Basic Materials', 'Industrials'] else 15.0
    fcf_yield_5y = get_num('fcf_yield_5y_avg') * 100

    if roic_current > base_roic and roic_5y > base_roic:
        if fcf_yield_5y > 3.0:
            return "Monopolio de Efectivo (Deep Moat)", f"ROIC histórico {roic_5y:.1f}% con conversión de caja sólida."
        return "Compuesto de Calidad (Moat)", f"Excelencia en asignación (ROIC 5A: {roic_5y:.1f}%)."

    return "Clasificación Neutral", "Métricas dentro de parámetros estadísticos."

def execute_ai_risk_audit(ticker: str, sector: str, archetype: str, metrics: dict, price: float) -> dict:
    def f_pct(val): return f"{val*100:.1f}%" if val != "N/A" and type(val) in [int, float] else "N/A"
    def f_num(val): return f"{val:.2f}" if val != "N/A" and type(val) in [int, float] else "N/A"

    prompt = f"""
    Misión: Eres el Analista Jefe Cuantitativo de un Fondo Institucional.
    Activo: {ticker} | Sector: {sector} | Precio: ${price}
    Arquetipo Asignado: '{archetype}'
    
    Data Forense (Actual vs Promedio 5 Años):
    - ROIC: Actual {f_pct(metrics.get('roic'))} | Promedio 5A: {f_pct(metrics.get('roic_5y_avg'))}
    - Crec. Ventas: Actual {f_pct(metrics.get('revenue_growth'))} | Promedio 5A: {f_pct(metrics.get('rev_growth_5y_avg'))}
    - FCF Yield: Actual {f_pct(metrics.get('fcf_yield'))} 
    - Valoración P/E: {f_num(metrics.get('pe_ratio'))} | Múltiplo EV/FCF: {f_num(metrics.get('ev_fcf'))}
    - Solvencia: Debt/Equity {f_num(metrics.get('debt_equity'))} | Cobertura Intereses: {f_num(metrics.get('interest_coverage'))}
    
    Instrucciones: Analiza rigurosamente el activo. Entrega tu output EXCLUSIVAMENTE en formato JSON.
    {{
        "texto_libre": "Un párrafo extenso y riguroso evaluando la generación real de efectivo (EV/FCF) y ventajas competitivas.",
        "score": [Número del 0 al 100],
        "veredicto": "[Elegir: Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Táctica de ejecución. Ej: Iniciar DCA asimétrico utilizando plataformas de inversión fraccionada como Racional, o rotar a liquidez en dólares/euros."
    }}
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        return {"texto_libre": f"Error IA: {str(e)}", "score": 0, "veredicto": "Hold", "estrategia": "N/A"}

# =====================================================================
# 5. UI: TABLERO DE CONTROL
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: Hybrid Routing & GEMINI 2.5")
    st.markdown("Motor forense con enrutamiento híbrido FMP-Stable / yFinance para eludir bloqueos.")

    with st.sidebar:
        st.header("Cribado de Activos")
        tickers_raw = st.text_input("Tickers (separados por coma)", value="NVDA, CEG, MSFT, VRT")
        st.markdown("---")
        execute_button = st.button("Ejecutar Análisis", type="primary", use_container_width=True)

    if execute_button:
        tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
        portfolio_results = []
        
        for ticker in tickers:
            with st.container():
                st.markdown(f"## 📈 {ticker}")
                
                profile = fetch_fmp_profile(ticker)
                sector_gics = profile.get("sector", "Desconocido")
                current_price = profile.get("price", 0.0)
                mkt_cap = profile.get("mkt_cap", 0.0)
                
                raw_metrics = fetch_quantitative_metrics(ticker, mkt_cap)
                
                if not raw_metrics or "_error" in raw_metrics:
                    st.error(f"Error de extracción para {ticker}: {raw_metrics.get('_error', '')}")
                    st.markdown("---")
                    continue
                
                archetype_label, rationale = evaluate_financial_archetype(sector_gics, raw_metrics)
                st.caption(f"**Sector:** {sector_gics} | **Precio Mkt:** ${current_price}")
                
                col1, col2, col3, col4, col5 = st.columns(5)
                def fmt_m(val, is_pct=False):
                    if val == "N/A": return "N/A"
                    return f"{val*100:.1f}%" if is_pct else f"{val:.2f}x"

                col1.metric("Arquetipo Táctico", archetype_label)
                col2.metric("ROIC (Media 5Y)", fmt_m(raw_metrics.get('roic_5y_avg'), True))
                col3.metric("FCF Yield", fmt_m(raw_metrics.get('fcf_yield'), True))
                col4.metric("EV / FCF", fmt_m(raw_metrics.get('ev_fcf')))
                col5.metric("Interest Coverage", fmt_m(raw_metrics.get('interest_coverage')))
                
                st.info(f"**Justificación Algorítmica:** {rationale}")
                
                with st.spinner('Sintetizando veredicto AI (Gemini 2.5 Pro)...'):
                    ai_data = execute_ai_risk_audit(ticker, sector_gics, archetype_label, raw_metrics, current_price)
                    
                    st.markdown("### 🧠 Veredicto Institucional")
                    color_map = {"Strong Buy": "🟢", "Buy": "🟩", "Hold": "🟨", "Sell": "🟧", "Strong Sell": "🔴"}
                    
                    res_col1, res_col2 = st.columns([1.5, 2.5])
                    with res_col1:
                        st.markdown(f"#### {color_map.get(ai_data.get('veredicto', 'Hold'), '⚪')} {ai_data.get('veredicto', 'N/A')}")
                        st.progress(ai_data.get('score', 0) / 100, text=f"Score: {ai_data.get('score', 0)}/100")
                        st.success(ai_data.get('estrategia', 'N/A'))
                    with res_col2:
                        with st.expander("📝 Leer Auditoría Completa", expanded=True):
                            st.write(ai_data.get('texto_libre', 'N/A'))
                
                st.markdown("---")
                portfolio_results.append({
                    "Activo": ticker, "Veredicto": ai_data.get("veredicto"),
                    "Score": ai_data.get("score"), "Arquetipo": archetype_label,
                    "ROIC 5Y Avg": fmt_m(raw_metrics.get('roic_5y_avg'), True)
                })
        
        if portfolio_results:
            st.markdown("### 📋 Matriz de Ejecución")
            st.dataframe(pd.DataFrame(portfolio_results).sort_values(by="Score", ascending=False).reset_index(drop=True), use_container_width=True)

if __name__ == "__main__":
    main()
