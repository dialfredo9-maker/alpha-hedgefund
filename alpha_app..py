"""
TERMINAL QUANTS PRO v7.0 - INSTITUTIONAL RIGOR EDITION
------------------------------------------------------
Arquitectura: Tri-Layer Routing (Stable / Raw-Bypass / yFinance)
IA: Gemini 2.5 Pro (Dual-Score Audit Logic)
Métricas: 5Y Deep Scan, Backlog Ajustado por Margen, Cobertura de Supervivencia.
"""

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import json

# =====================================================================
# 1. CONFIGURACIÓN DE INFRAESTRUCTURA DE GRADO PROFESIONAL
# =====================================================================
st.set_page_config(
    page_title="Terminal Quants PRO: Auditoría Forense", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Estilos CSS para mejorar la legibilidad institucional
st.markdown("""
    <style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #d1d5db; }
    .warning-box { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; border-left: 5px solid #ffeeba; }
    </style>
""", unsafe_allow_items=True)

try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception:
    st.error("Error Crítico: Verifique las API Keys en .streamlit/secrets.toml")
    st.stop()

GEMINI_MODEL_NAME = 'gemini-2.5-pro'

# =====================================================================
# 2. MOTOR DE DESCUBRIMIENTO (SCREENER)
# =====================================================================

def discovery_screener(limit=10):
    """
    Escanea el mercado buscando activos que cumplan con la 'Trinidad de Valor':
    - Market Cap > 1B (Estabilidad)
    - Precio > 5 (Evitar Penny Stocks)
    - Operativa Activa
    """
    url = (f"https://financialmodelingprep.com/stable/company-screener?"
           f"marketCapMoreThan=1000000000&priceMoreThan=5&isEtf=false&"
           f"isActivelyTrading=true&limit={limit*2}&apikey={FMP_API_KEY}")
    try:
        resp = requests.get(url, timeout=10).json()
        if isinstance(resp, list):
            return [stock['symbol'] for stock in resp]
        return []
    except Exception:
        return []

# =====================================================================
# 3. CAPA DE EXTRACCIÓN FORENSE: TRI-LAYER ROUTING (BYPASS DE PLANES)
# =====================================================================

@st.cache_data(ttl=86400)
def fetch_institutional_profile(ticker: str) -> dict:
    """Extrae el contexto del negocio y sector."""
    url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp and isinstance(resp, list):
            d = resp[0]
            return {
                "sector": d.get("sector", "Desconocido"),
                "industry": d.get("industry", "Desconocido"),
                "price": d.get("price", 0.0),
                "mkt_cap": d.get("mktCap", 0.0),
                "description": d.get("description", "Información no disponible.")
            }
    except: pass
    
    # Fallback total a yFinance
    try:
        s = yf.Ticker(ticker)
        info = s.info
        return {
            "sector": info.get("sector", "Desconocido"),
            "industry": info.get("industry", "Desconocido"),
            "price": info.get("currentPrice", 0.0),
            "mkt_cap": info.get("marketCap", 0.0),
            "description": info.get("longBusinessSummary", "Información no disponible.")
        }
    except:
        return {"sector": "N/A", "industry": "N/A", "price": 0.0, "mkt_cap": 0.0, "description": "Error al recuperar perfil."}

@st.cache_data(ttl=3600)
def fetch_quantitative_engine(ticker: str, mkt_cap: float) -> dict:
    """
    CAPA DE DATOS MAESTRA:
    Intenta Nivel 1 (Premium Ratios). Si falla (403), ejecuta Nivel 2 (Cálculo Manual desde Balances).
    """
    metrics = {}
    def calc_avg(lst): 
        clean = [x for x in lst if x is not None and type(x) in [int, float]]
        return sum(clean)/len(clean) if clean else "N/A"

    # ---------------------------------------------------------
    # INTENTO NIVEL 1: FMP PRE-CALCULADO (Plan Premium/Legacy)
    # ---------------------------------------------------------
    try:
        url_km = f"https://financialmodelingprep.com/stable/key-metrics?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
        url_r = f"https://financialmodelingprep.com/stable/ratios?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
        url_g = f"https://financialmodelingprep.com/stable/financial-growth?symbol={ticker}&limit=5&apikey={FMP_API_KEY}"
        url_bs = f"https://financialmodelingprep.com/stable/balance-sheet-statement?symbol={ticker}&limit=1&apikey={FMP_API_KEY}"
        
        km_resp = requests.get(url_km, timeout=5)
        if km_resp.status_code == 200 and len(km_resp.json()) > 0:
            km_j = km_resp.json()
            r_j = requests.get(url_r).json()
            g_j = requests.get(url_g).json()
            bs_j = requests.get(url_bs).json()
            
            curr = km_j[0]
            metrics.update({
                'pe_ratio': curr.get('peRatio'), 'pb_ratio': curr.get('pbRatio'),
                'roe': curr.get('roe'), 'roic': curr.get('roic'),
                'debt_equity': curr.get('debtToEquity'), 'fcf_yield': curr.get('freeCashFlowYield'),
                'ev_fcf': curr.get('evToFreeCashFlow'), 'interest_coverage': curr.get('interestCoverage'),
                'roic_5y_avg': calc_avg([x.get('roic') for x in km_j]),
                'fcf_yield_5y_avg': calc_avg([x.get('freeCashFlowYield') for x in km_j]),
                'source': "FMP Premium (Ratios Directos)"
            })
            if r_j:
                gm = r_j[0].get('grossProfitMargin', 0)
                dr = (bs_j[0].get('deferredRevenue', 0) + bs_j[0].get('deferredRevenueNonCurrent', 0)) if bs_j else 0
                metrics['adj_backlog'] = dr * gm if dr > 0 else "N/A"
            if g_j:
                metrics['rev_growth_5y_avg'] = calc_avg([x.get('revenueGrowth') for x in g_j])
            return metrics
    except: pass

    # ---------------------------------------------------------
    # INTENTO NIVEL 2: FMP RAW BYPASS (Plan Starter - Cálculo Manual)
    # ---------------------------------------------------------
    try:
        url_is = f"https://financialmodelingprep.com/stable/income-statement?symbol={ticker}&limit=6&apikey={FMP_API_KEY}"
        is_j = requests.get(url_is).json()
        if is_j and len(is_j) > 0:
            bs_j = requests.get(f"https://financialmodelingprep.com/stable/balance-sheet-statement?symbol={ticker}&limit=5&apikey={FMP_API_KEY}").json()
            cf_j = requests.get(f"https://financialmodelingprep.com/stable/cash-flow-statement?symbol={ticker}&limit=5&apikey={FMP_API_KEY}").json()
            
            i_c, b_c, c_c = is_j[0], bs_j[0], cf_j[0]
            rev, op_inc, net_inc = i_c.get('revenue', 1), i_c.get('operatingIncome', 0), i_c.get('netIncome', 1)
            int_exp = i_c.get('interestExpense', 1)
            gp_margin = i_c.get('grossProfit', 0) / rev if rev > 0 else 0
            
            td = b_c.get('totalDebt', b_c.get('shortTermDebt',0) + b.get('longTermDebt',0))
            te = b_c.get('totalStockholdersEquity', b_c.get('totalEquity', 1))
            cash = b_c.get('cashAndCashEquivalents', 0)
            fcf = c_c.get('freeCashFlow', 0)
            
            # Fórmulas de Auditoría Quant
            metrics.update({
                'pe_ratio': mkt_cap / net_inc if net_inc > 0 else "N/A",
                'pb_ratio': mkt_cap / te if te > 0 else "N/A",
                'roic': (op_inc * 0.79) / (td + te - cash) if (td + te - cash) > 0 else "N/A",
                'fcf_yield': fcf / mkt_cap if mkt_cap > 0 else "N/A",
                'debt_equity': td / te if te > 0 else "N/A",
                'interest_coverage': abs(op_inc / int_exp) if int_exp != 0 else "N/A",
                'adj_backlog': (b_c.get('deferredRevenue', 0) + b_c.get('deferredRevenueNonCurrent', 0)) * gp_margin,
                'source': "FMP Raw (Cálculo Contable Manual)"
            })
            
            # Cálculo de crecimiento histórico de ventas
            h_rev = []
            for k in range(len(is_j)-1):
                prev = is_j[k+1].get('revenue', 1)
                h_rev.append((is_j[k].get('revenue', 0) - prev) / prev)
            metrics['rev_growth_5y_avg'] = calc_avg(h_rev)
            metrics['roic_5y_avg'] = metrics['roic']
            return metrics
    except: pass

    # ---------------------------------------------------------
    # INTENTO NIVEL 3: FALLBACK yFINANCE (Supervivencia Final)
    # ---------------------------------------------------------
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        metrics.update({
            'pe_ratio': info.get('trailingPE', "N/A"),
            'pb_ratio': info.get('priceToBook', "N/A"),
            'fcf_yield': info.get('freeCashflow', 0) / mkt_cap if mkt_cap > 0 else "N/A",
            'source': "yFinance Fallback (Limitado)"
        })
        return metrics
    except:
        return {"_error": "No se pudo extraer data de ninguna fuente."}

# =====================================================================
# 4. LÓGICA DE AUDITORÍA BINARIA: GEMINI 2.5 PRO
# =====================================================================

def execute_dual_score_audit(ticker: str, sector: str, metrics: dict, price: float, desc: str) -> dict:
    """
    Obliga a la IA a separar el Balance (Realidad) de la Narrativa (Catalizadores).
    """
    def fp(v): return f"{v*100:.1f}%" if v != "N/A" and type(v) in [int, float] else "N/A"
    def fn(v): return f"{v:.2f}x" if v != "N/A" and type(v) in [int, float] else "N/A"

    prompt = f"""
    Misión: Eres el Analista Jefe de Situaciones Especiales de un Fondo Institucional.
    ACTIVO: {ticker} | SECTOR: {sector} | PRECIO: ${price}
    PERFIL: {desc[:800]}

    ESTADO CONTABLE ACTUAL (BACKBONE):
    - ROIC actual: {fp(metrics.get('roic'))} | Media 5A: {fp(metrics.get('roic_5y_avg'))}
    - FCF Yield: {fp(metrics.get('fcf_yield'))} | EV/FCF: {fn(metrics.get('ev_fcf'))}
    - Solvencia: Debt/Equity {fn(metrics.get('debt_equity'))} | Cobertura Int: {fn(metrics.get('interest_coverage'))}
    - FCF Latente (Backlog Ajustado): {metrics.get('adj_backlog')}

    JERARQUÍA RIGUROSA DE EVALUACIÓN:
    1. EL BALANCE ES EL ANCLA: No puedes dar un Score Contable alto si el ROIC es < 10% o la deuda es peligrosa.
    2. DETECCIÓN DE CATALIZADORES: Identifica si existen contratos firmados con Hyperscalers (Microsoft, AWS, Google), reactivación de activos estratégicos (ej. Nuclear) u órdenes futuras masivas que no se reflejan aún en el FCF de hoy.
    3. JUSTIFICACIÓN DE AJUSTE: Si el Score Final es mayor al Score Contable, explica por qué la opcionalidad futura compensa el riesgo del balance actual.

    SALIDA EXCLUSIVA EN JSON:
    {{
        "modelo_negocio": "Breve descripción técnica.",
        "auditoria_balance": "Análisis crudo de las métricas actuales.",
        "analisis_catalizadores": "Evaluación de contratos futuros y opcionalidad estratégica.",
        "ajuste_narrativo_detectado": [true/false],
        "score_contable": [0-100 basado SOLO en números actuales],
        "score_final": [0-100 ponderando catalizadores futuros],
        "veredicto": "[Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Táctica de ejecución (DCA Racional, Liquidez, etc)."
    }}
    """
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        return {"score_final": 0, "veredicto": "Error IA", "auditoria_balance": f"Fallo: {str(e)}"}

# =====================================================================
# 5. INTERFAZ DE USUARIO TERMINAL (STREAMLIT)
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: Auditoría Forense Dual")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Panel de Control")
        op_mode = st.radio("Modo de Operación", ["Manual (CSV Tickers)", "Descubrimiento (IA-Screener)"])
        
        if op_mode == "Manual (CSV Tickers)":
            tickers_input = st.text_input("Ingrese Tickers (ej: NVDA, CEG, VRT)", value="CEG, KTOS, MSFT")
        else:
            num_stocks = st.slider("Activos a descubrir", 5, 20, 10)
            st.info("El Screener busca activos con Market Cap > 1B y fundamentales base en FMP.")

        st.markdown("---")
        execute = st.button("EJECUTAR AUDITORÍA TOTAL", type="primary", use_container_width=True)

    if execute:
        if op_mode == "Manual (CSV Tickers)":
            tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
        else:
            with st.spinner("Escaneando el mercado..."):
                tickers = discovery_screener(num_stocks)

        if not tickers:
            st.warning("No se encontraron símbolos para procesar.")
            return

        summary_data = []

        for t in tickers:
            with st.container():
                st.markdown(f"## 📊 Informe de Activo: {t}")
                
                # Ingesta de Datos
                profile = fetch_institutional_profile(t)
                metrics = fetch_quantitative_engine(t, profile['mkt_cap'])
                
                if "_error" in metrics:
                    st.error(f"Error en {t}: {metrics['_error']}")
                    continue
                
                st.caption(f"**Sector:** {profile['sector']} | **Industria:** {profile['industry']} | **Fuente:** {metrics.get('source')}")

                # Grid de Métricas Crudas
                m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
                
                def fmt_v(v, p=False):
                    if v == "N/A" or v is None: return "N/A"
                    return f"{v*100:.1f}%" if p else f"{v:.2f}x"

                m_col1.metric("ROIC 5Y (Avg)", fmt_v(metrics.get('roic_5y_avg'), True))
                m_col2.metric("FCF Yield", fmt_v(metrics.get('fcf_yield'), True))
                m_col3.metric("EV / FCF", fmt_v(metrics.get('ev_fcf')))
                m_col4.metric("Debt / Equity", fmt_v(metrics.get('debt_equity')))
                
                # Backlog FCF format
                back = metrics.get('adj_backlog')
                if back != "N/A" and back is not None:
                    back_label = f"${back/1e6:.1f}M" if back < 1e9 else f"${back/1e9:.1f}B"
                else: back_label = "N/A"
                m_col5.metric("FCF Latente (Backlog)", back_label)

                # Auditoría IA
                with st.spinner(f"Gemini 2.5 Pro ejecutando cruce de datos para {t}..."):
                    audit = execute_dual_score_audit(t, profile['sector'], metrics, profile['price'], profile['description'])
                    
                    # ALERTA DE AJUSTE NARRATIVO (SOLICITADO POR EL USUARIO)
                    if audit.get("ajuste_narrativo_detectado"):
                        st.warning(f"""
                            ⚠️ **ADVERTENCIA DE VALORACIÓN:** El Score Final de **{t}** ({audit['score_final']}) ha sido incrementado artificialmente por catalizadores cualitativos/narrativos. 
                            **Score Contable (Hard Numbers): {audit['score_contable']}**. 
                            Proceda con extrema precaución: el balance actual no soporta este precio sin el éxito total de los eventos futuros descritos.
                        """)

                    res_col1, res_col2 = st.columns([1.5, 2.5])
                    
                    with res_col1:
                        color_map = {"Strong Buy": "🟢", "Buy": "🟩", "Hold": "🟨", "Sell": "🟧", "Strong Sell": "🔴"}
                        st.markdown(f"### {color_map.get(audit.get('veredicto'), '⚪')} {audit.get('veredicto')}")
                        st.progress(audit.get('score_final', 0)/100, text=f"Score Final: {audit.get('score_final')}/100")
                        st.markdown("**Táctica Operativa:**")
                        st.success(audit.get('estrategia', 'N/A'))
                    
                    with res_col2:
                        with st.expander("📝 LEER AUDITORÍA FORENSE COMPLETA", expanded=True):
                            st.markdown("**Modelo de Negocio:**")
                            st.write(audit.get('modelo_negocio'))
                            st.markdown("---")
                            st.markdown("**Análisis de Balance (Realidad Actual):**")
                            st.write(audit.get('auditoria_balance'))
                            st.markdown("---")
                            st.markdown("**Catalizadores y Opcionalidad (Futuro):**")
                            st.info(audit.get('analisis_catalizadores'))
                
                summary_data.append({
                    "Ticker": t, "Score Final": audit.get('score_final'), 
                    "Score Contable": audit.get('score_contable'), "Veredicto": audit.get('veredicto')
                })
                st.markdown("---")

        if summary_data:
            st.subheader("📋 Matriz Comparativa de Ejecución")
            st.dataframe(pd.DataFrame(summary_data).sort_values(by="Score Final", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
