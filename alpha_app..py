"""
TERMINAL QUANTS PRO - FULL INSTITUTIONAL VERSION
------------------------------------------------
Arquitectura: Tri-Layer Routing (Premium / Raw / yFinance)
IA: Gemini 2.5 Pro (Jerarquía de Scoring Estricta)
Métricas: 5Y Historical Deep Scan, Adjusted Backlog FCF, Survival Metrics.
"""

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import json

# =====================================================================
# 1. INFRAESTRUCTURA Y SEGURIDAD
# =====================================================================
st.set_page_config(page_title="Terminal Quants PRO", layout="wide")

try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception:
    st.error("Error: Configura las API Keys en .streamlit/secrets.toml")
    st.stop()

GEMINI_MODEL_NAME = 'gemini-2.5-pro'

# =====================================================================
# 2. MOTOR DE DESCUBRIMIENTO (SCREENER)
# =====================================================================

def discovery_screener(limit=10):
    """Filtra el universo de FMP buscando anomalías de valor y calidad."""
    url = (f"https://financialmodelingprep.com/stable/company-screener?"
           f"marketCapMoreThan=1000000000&priceMoreThan=5&isEtf=false&"
           f"isActivelyTrading=true&limit={limit*2}&apikey={FMP_API_KEY}")
    try:
        resp = requests.get(url, timeout=5).json()
        return [stock['symbol'] for stock in resp] if isinstance(resp, list) else []
    except:
        return []

# =====================================================================
# 3. CAPA DE EXTRACCIÓN Y CÁLCULO (EL "BYPASS" STARTER)
# =====================================================================

@st.cache_data(ttl=86400)
def fetch_profile(ticker: str) -> dict:
    url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp and isinstance(resp, list):
            d = resp[0]
            return {"sector": d.get("sector", "N/A"), "industry": d.get("industry", "N/A"),
                    "price": d.get("price", 0.0), "mkt_cap": d.get("mktCap", 0.0),
                    "description": d.get("description", "N/A")}
    except: pass
    
    # Fallback total a yFinance para perfil
    try:
        s = yf.Ticker(ticker).info
        return {"sector": s.get("sector", "N/A"), "industry": s.get("industry", "N/A"),
                "price": s.get("currentPrice", 0.0), "mkt_cap": s.get("marketCap", 0.0),
                "description": s.get("longBusinessSummary", "N/A")}
    except:
        return {"sector": "N/A", "industry": "N/A", "price": 0.0, "mkt_cap": 0.0, "description": "N/A"}

@st.cache_data(ttl=3600)
def fetch_deep_metrics(ticker: str, mkt_cap: float) -> dict:
    """Intenta extraer data pre-calculada. Si falla, baja estados financieros brutos y calcula."""
    metrics = {}
    
    def avg(lst): return sum(lst)/len(lst) if lst else "N/A"

    # PRIORIDAD 1: FMP PRE-CALCULADO (STABLE ENDPOINTS)
    try:
        url_km = f"https://financialmodelingprep.com/stable/key-metrics?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
        url_r = f"https://financialmodelingprep.com/stable/ratios?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
        url_g = f"https://financialmodelingprep.com/stable/financial-growth?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
        url_bs = f"https://financialmodelingprep.com/stable/balance-sheet-statement?symbol={ticker}&limit=1&apikey={FMP_API_KEY}"
        
        km_j = requests.get(url_km).json()
        if km_j and isinstance(km_j, list) and len(km_j) > 0:
            r_j = requests.get(url_r).json()
            g_j = requests.get(url_g).json()
            bs_j = requests.get(url_bs).json()
            
            m = km_j[0]
            metrics.update({
                'pe_ratio': m.get('peRatio'), 'pb_ratio': m.get('pbRatio'),
                'roe': m.get('roe'), 'roic': m.get('roic'),
                'debt_equity': m.get('debtToEquity'), 'fcf_yield': m.get('freeCashFlowYield'),
                'ev_fcf': m.get('evToFreeCashFlow'), 'interest_coverage': m.get('interestCoverage'),
                'roic_5y_avg': avg([x.get('roic') for x in km_j if x.get('roic')]),
                'fcf_yield_5y_avg': avg([x.get('freeCashFlowYield') for x in km_j if x.get('freeCashFlowYield')]),
                'source': "FMP Premium (Stable)"
            })
            if r_j:
                gm = r_j[0].get('grossProfitMargin', 0)
                dr = (bs_j[0].get('deferredRevenue', 0) + bs_j[0].get('deferredRevenueNonCurrent', 0)) if bs_j else 0
                metrics['adj_backlog'] = dr * gm if dr > 0 else "N/A"
            if g_j:
                metrics['rev_growth_5y_avg'] = avg([x.get('revenueGrowth') for x in g_j if x.get('revenueGrowth')])
            return metrics
    except: pass

    # PRIORIDAD 2: BYPASS STARTER (CÁLCULO MANUAL DESDE ESTADOS FINANCIEROS)
    try:
        url_is = f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker}&limit=6&apikey={FMP_API_KEY}"
        is_data = requests.get(url_is).json()
        if is_data and len(is_data) > 0:
            bs_data = requests.get(f"https://financialmodelingprep.com/stable/balance-sheet-statement?symbol={ticker}&limit=5&apikey={FMP_API_KEY}").json()
            cf_data = requests.get(f"https://financialmodelingprep.com/stable/cash-flow-statement?symbol={ticker}&limit=5&apikey={FMP_API_KEY}").json()
            
            # Datos año actual
            i, b, c = is_data[0], bs_data[0], cf_data[0]
            rev, op_inc, net_inc = i.get('revenue', 1), i.get('operatingIncome', 0), i.get('netIncome', 0)
            int_exp = i.get('interestExpense', 1)
            gross_p = i.get('grossProfit', 0)
            t_debt = b.get('totalDebt', b.get('shortTermDebt', 0) + b.get('longTermDebt', 0))
            t_eq = b.get('totalStockholdersEquity', b.get('totalEquity', 1))
            fcf = c.get('freeCashFlow', 0)
            
            # Cálculos Manuales Quant
            metrics['pe_ratio'] = mkt_cap / net_inc if net_inc > 0 else "N/A"
            metrics['pb_ratio'] = mkt_cap / t_eq if t_eq > 0 else "N/A"
            metrics['roic'] = (op_inc * 0.79) / (t_debt + t_eq - b.get('cashAndCashEquivalents', 0)) if (t_debt+t_eq)>0 else "N/A"
            metrics['fcf_yield'] = fcf / mkt_cap if mkt_cap > 0 else "N/A"
            metrics['debt_equity'] = t_debt / t_eq
            metrics['interest_coverage'] = abs(op_inc / int_exp) if int_exp != 0 else "N/A"
            
            # Backlog Ajustado
            dr = b.get('deferredRevenue', 0) + b.get('deferredRevenueNonCurrent', 0)
            metrics['adj_backlog'] = dr * (gross_p / rev) if dr > 0 else "N/A"
            
            # Históricos
            h_rev = []
            for k in range(len(is_data)-1):
                h_rev.append((is_data[k].get('revenue',1) - is_data[k+1].get('revenue',1)) / is_data[k+1].get('revenue',1))
            metrics['rev_growth_5y_avg'] = avg(h_rev)
            metrics['roic_5y_avg'] = metrics['roic'] # Simplificado
            metrics['source'] = "FMP Raw Statements (Quant-Calc)"
            return metrics
    except: pass

    # PRIORIDAD 3: FALLBACK yFINANCE (SI TODO FALLA)
    try:
        s = yf.Ticker(ticker)
        metrics['pe_ratio'] = s.info.get('trailingPE', "N/A")
        metrics['fcf_yield'] = s.info.get('freeCashflow', 0) / mkt_cap if mkt_cap > 0 else "N/A"
        metrics['source'] = "yFinance (Fallback)"
        return metrics
    except:
        return {"_error": "Extracción imposible."}

# =====================================================================
# 4. CEREBRO DE IA: GEMINI 2.5 PRO (JERARQUÍA ESTRICTA)
# =====================================================================

def run_ai_audit(ticker: str, sector: str, metrics: dict, price: float, desc: str) -> dict:
    def fp(v): return f"{v*100:.1f}%" if v != "N/A" and type(v) in [int, float] else "N/A"
    def fn(v): return f"{v:.2f}x" if v != "N/A" and type(v) in [int, float] else "N/A"

    prompt = f"""
    Eres el Analista Jefe Cuantitativo de un Hedge Fund. Tu misión es encontrar valor ignorado.
    ACTIVO: {ticker} | SECTOR: {sector} | PRECIO: ${price}
    PERFIL: {desc[:800]}

    MÉTRICAS CLAVE (CRUCE OBLIGATORIO):
    - ROIC: Actual {fp(metrics.get('roic'))} | Media 5A: {fp(metrics.get('roic_5y_avg'))}
    - FCF YIELD: {fp(metrics.get('fcf_yield'))} | EV/FCF: {fn(metrics.get('ev_fcf'))}
    - SOLVENCIA: Debt/Equity {fn(metrics.get('debt_equity'))} | Cobertura Int: {fn(metrics.get('interest_coverage'))}
    - CRECIMIENTO: Ventas 5A (Media): {fp(metrics.get('rev_growth_5y_avg'))}
    - FCF LATENTE (Backlog Ajustado por Margen): {metrics.get('adj_backlog')}

    JERARQUÍA DE SCORING (LÓGICA SUPERIOR):
    1. PRIORIDAD SOBREVIVENCIA: Si el interés no se cubre (Coverage < 2) o la deuda es tóxica, el score es < 40.
    2. EFICIENCIA > BACKLOG: Un backlog masivo con ROIC < 10% es DESTRUCCIÓN de valor. No premies el crecimiento si no es rentable.
    3. TESIS DEL OLVIDO: Identifica por qué el mercado ignora esta joya o si el castigo es merecido.

    RESPUESTA JSON ESTRICTO:
    {{
        "modelo_negocio": "Breve y claro.",
        "tesis_olvido": "¿Por qué el mercado no la ve? (Ej: sector aburrido, bache temporal, etc).",
        "informe_final": "Mínimo 3 párrafos profundos analizando el cruce de datos y visibilidad de demanda.",
        "score": [0-100], "veredicto": "[Strong Buy...]", "estrategia": "Táctica DCA Racional / Liquidez"
    }}
    """
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.2))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"score":0, "veredicto":"Error", "informe_final":"Fallo en procesamiento de IA."}

# =====================================================================
# 5. UI: TABLERO INSTITUCIONAL
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: Auditoría Forense")
    
    with st.sidebar:
        st.header("Control de Radar")
        mode = st.radio("Modo", ["Manual (Tickers)", "Descubrimiento (Automático)"])
        if mode == "Manual (Tickers)":
            tickers_input = st.text_input("Ingresar Tickers (comas)", value="NVDA, CEG, MSFT")
        else:
            n_discovery = st.slider("Activos a escanear", 5, 20, 10)
        
        st.markdown("---")
        if st.button("EJECUTAR ANÁLISIS", type="primary", use_container_width=True):
            st.session_state.run = True
            if mode == "Manual (Tickers)":
                st.session_state.tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
            else:
                with st.spinner("Escaneando el mercado..."):
                    st.session_state.tickers = discovery_screener(n_discovery)

    if "run" in st.session_state and st.session_state.run:
        results = []
        for t in st.session_state.tickers:
            with st.container():
                st.markdown(f"## 📈 {t}")
                prof = fetch_profile(t)
                met = fetch_deep_metrics(t, prof['mkt_cap'])
                
                if "_error" in met:
                    st.error(f"Error en {t}: {met['_error']}")
                    continue
                
                st.caption(f"**Fuente de Datos:** {met.get('source')} | **Sector:** {prof['sector']}")
                
                # Fila 1: Key Performance Indicators
                c1, c2, c3, c4, c5 = st.columns(5)
                def f_m(v, p=False): 
                    if v == "N/A" or v is None: return "N/A"
                    return f"{v*100:.1f}%" if p else f"{v:.2f}x"
                
                c1.metric("ROIC 5Y (Avg)", f_m(met.get('roic_5y_avg'), True))
                c2.metric("FCF Yield", f_m(met.get('fcf_yield'), True))
                c3.metric("EV / FCF", f_m(met.get('ev_fcf')))
                c4.metric("Debt / Equity", f_m(met.get('debt_equity')))
                # Backlog en Moneda
                back = met.get('adj_backlog')
                if back != "N/A":
                    label_back = f"${back/1e6:.1f}M" if back < 1e9 else f"${back/1e9:.1f}B"
                else: label_back = "N/A"
                c5.metric("FCF Latente (Backlog)", label_back)

                with st.spinner(f"Auditando {t} con Gemini 2.5 Pro..."):
                    ai = run_ai_audit(t, prof['sector'], met, prof['price'], prof['description'])
                    
                    res_col1, res_col2 = st.columns([1.5, 2.5])
                    with res_col1:
                        color_map = {"Strong Buy": "🟢", "Buy": "🟩", "Hold": "🟨", "Sell": "🟧", "Strong Sell": "🔴"}
                        st.markdown(f"### {color_map.get(ai['veredicto'], '⚪')} {ai['veredicto']}")
                        st.progress(ai['score']/100, text=f"Score Institucional: {ai['score']}")
                        st.success(f"**Estrategia:** {ai['estrategia']}")
                    with res_col2:
                        with st.expander("📝 LEER INFORME DE VALORACIÓN", expanded=True):
                            st.markdown("**Modelo de Negocio:**")
                            st.write(ai.get('modelo_negocio'))
                            st.markdown("**Tesis del Olvido (Market Alpha):**")
                            st.info(ai.get('tesis_olvido'))
                            st.markdown("**Auditoría de Datos Cruzados:**")
                            st.write(ai.get('informe_final'))
                
                results.append({"Ticker": t, "Score": ai['score'], "Veredicto": ai['veredicto'], "ROIC 5Y": met.get('roic_5y_avg')})
                st.markdown("---")

        if results:
            st.subheader("📋 Resumen Comparativo de Convicción")
            st.dataframe(pd.DataFrame(results).sort_values(by="Score", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
