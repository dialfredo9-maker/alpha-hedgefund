"""
TERMINAL QUANTS PRO v9.0 - UNABRIDGED INSTITUTIONAL VERSION
----------------------------------------------------------
Seguridad: Tri-Layer Redundant Routing (Stable -> Raw -> yFinance)
Cálculo: Engine Contable Manual (ROIC, FCF Latente, Invested Capital)
IA: Gemini 2.5 Pro (Jerarquía Estricta + Informe de 500+ palabras)
"""

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import json
import time

# =====================================================================
# 1. INFRAESTRUCTURA DE INTERFAZ Y SEGURIDAD
# =====================================================================
st.set_page_config(
    page_title="Terminal Quants PRO: Sovereign Auditor", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Estilos CSS de Grado Institucional
st.markdown("""
    <style>
    .report-box { background-color: #f8f9fa; padding: 25px; border-left: 8px solid #1f77b4; border-radius: 8px; line-height: 1.6; }
    .metric-container { background-color: #ffffff; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px; text-align: center; }
    .warning-card { background-color: #fff3cd; color: #856404; padding: 20px; border-radius: 10px; border-left: 6px solid #ffc107; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception:
    st.error("Error Crítico: Verifique las credenciales en .streamlit/secrets.toml")
    st.stop()

GEMINI_MODEL_NAME = 'gemini-2.5-pro'

# =====================================================================
# 2. MOTOR DE DESCUBRIMIENTO (SCREENER)
# =====================================================================

def discovery_screener(limit=10):
    """Escanea el mercado en busca de anomalías de valor."""
    url = (f"https://financialmodelingprep.com/stable/company-screener?"
           f"marketCapMoreThan=1000000000&priceMoreThan=5&isEtf=false&"
           f"isActivelyTrading=true&limit={limit*2}&apikey={FMP_API_KEY}")
    try:
        resp = requests.get(url, timeout=10).json()
        return [stock['symbol'] for stock in resp] if isinstance(resp, list) else []
    except Exception:
        return []

# =====================================================================
# 3. ENGINE DE DATOS: RECONSTRUCCIÓN CONTABLE SOBERANA
# =====================================================================

def get_fmp_json(endpoint, symbol, params=""):
    url = f"https://financialmodelingprep.com/stable/{endpoint}?symbol={symbol}{params}&apikey={FMP_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=3600)
def fetch_quantitative_analysis(ticker: str) -> dict:
    """
    Motor central de datos. Extrae 5 años de estados financieros 
    y reconstruye manualmente las métricas ignorando los N/A de la API.
    """
    m = {}
    
    # --- 1. Perfil Institucional ---
    p_data = get_fmp_json("profile", ticker)
    if not p_data: return {"_error": f"Ticker {ticker} no encontrado en FMP."}
    p = p_data[0]
    mkt_cap = p.get('mktCap', 1)
    m['sector'] = p.get('sector', 'N/A')
    m['industry'] = p.get('industry', 'N/A')
    m['price'] = p.get('price', 0.0)
    m['mkt_cap'] = mkt_cap
    m['description'] = p.get('description', '')

    # --- 2. Ingesta de Estados Financieros (6 años para delta de crecimiento) ---
    is_j = get_fmp_json("income-statement", ticker, "&limit=6")
    bs_j = get_fmp_json("balance-sheet-statement", ticker, "&limit=6")
    cf_j = get_fmp_json("cash-flow-statement", ticker, "&limit=6")
    
    # Capa de Seguridad: Si FMP falla, intentamos yFinance como salvavidas
    if not is_j or not bs_j:
        try:
            s = yf.Ticker(ticker)
            info = s.info
            m.update({
                'pe_ratio': info.get('trailingPE'), 'fcf_yield': 0.0, 
                'source': "yFinance Fallback", 'roic_5y_avg': "N/A"
            })
            return m
        except: return {"_error": "Fallo total de conexión con bases de datos."}

    # --- 3. RECONSTRUCCIÓN CONTABLE MANUAL (Bypass de Ratios Premium) ---
    def calc_roic(idx):
        try:
            inc = is_j[idx]
            bal = bs_j[idx]
            ebit = inc.get('operatingIncome', 0)
            tax_rate = inc.get('incomeTaxExpense', 0) / inc.get('incomeBeforeTax', 1) if inc.get('incomeBeforeTax', 0) > 0 else 0.21
            # Búsqueda redundante de deuda (Total -> Short+Long -> N/A)
            debt = bal.get('totalDebt') or (bal.get('shortTermDebt', 0) + bal.get('longTermDebt', 0))
            equity = bal.get('totalStockholdersEquity', bal.get('totalEquity', 1))
            cash = bal.get('cashAndCashEquivalents', 0)
            invested_cap = debt + equity - cash
            return (ebit * (1 - tax_rate)) / invested_cap if invested_cap > 0 else None
        except: return None

    # Métricas Actuales
    i0, b0, c0 = is_j[0], bs_j[0], cf_j[0]
    m['roic'] = calc_roic(0)
    m['fcf'] = c0.get('freeCashFlow', 0)
    m['fcf_yield'] = m['fcf'] / mkt_cap if mkt_cap > 0 else "N/A"
    
    # Deuda y Solvencia Reconstruida
    cur_debt = b0.get('totalDebt') or (b0.get('shortTermDebt', 0) + b0.get('longTermDebt', 0))
    cur_equity = b0.get('totalStockholdersEquity', b0.get('totalEquity', 1))
    m['debt_equity'] = cur_debt / cur_equity if cur_equity > 0 else "N/A"
    m['interest_coverage'] = i0.get('operatingIncome', 0) / i0.get('interestExpense', 1) if i0.get('interestExpense', 0) != 0 else "N/A"
    
    # Valoración
    m['pe_ratio'] = mkt_cap / i0.get('netIncome', 1) if i0.get('netIncome', 0) > 0 else "N/A"
    m['ev_fcf'] = (mkt_cap + cur_debt - b0.get('cashAndCashEquivalents', 0)) / m['fcf'] if m['fcf'] > 0 else "N/A"
    
    # --- 4. CÁLCULO DE BACKLOG AJUSTADO (Agnóstico de Sector) ---
    deferred_rev = b0.get('deferredRevenue', 0) + b0.get('deferredRevenueNonCurrent', 0)
    gross_margin = i0.get('grossProfit', 0) / i0.get('revenue', 1) if i0.get('revenue', 0) > 0 else 0
    m['adj_backlog'] = deferred_rev * gross_margin

    # --- 5. BUCLE DE HISTORIAL 5 AÑOS (Promedios Reales) ---
    h_roic = []
    for idx in range(min(5, len(is_j))):
        val = calc_roic(idx)
        if val is not None: h_roic.append(val)
    m['roic_5y_avg'] = sum(h_roic)/len(h_roic) if h_roic else "N/A"
    
    h_rev = []
    for k in range(min(5, len(is_j)-1)):
        prev = is_j[k+1].get('revenue', 1)
        h_rev.append((is_j[k].get('revenue', 0) - prev) / prev)
    m['rev_growth_5y_avg'] = sum(h_rev)/len(h_rev) if h_rev else "N/A"

    m['source'] = "Institutional Sovereign Engine (Raw Statements)"
    return m

# =====================================================================
# 4. CEREBRO IA: AUDITORÍA DE ALTA DENSIDAD (GEMINI 2.5 PRO)
# =====================================================================

def execute_sovereign_audit(ticker: str, metrics: dict) -> dict:
    """
    Fuerza a la IA a realizar un cruce de datos técnico, 
    detectar catalizadores y alertar sobre contaminaciones narrativas.
    """
    def f_p(v): return f"{v*100:.2f}%" if v != "N/A" and v is not None else "N/A"
    def f_n(v): return f"{v:.2f}x" if v != "N/A" and v is not None else "N/A"

    prompt = f"""
    Misión: Analista Jefe Cuantitativo de Situaciones Especiales. 
    Activo: {ticker} | Sector: {metrics['sector']} | Precio: ${metrics['price']}
    
    AUDITORÍA CONTABLE (BACKBONE):
    - ROIC Actual: {f_p(metrics.get('roic'))} | Media 5A: {f_p(metrics.get('roic_5y_avg'))}
    - FCF Yield: {f_p(metrics.get('fcf_yield'))} | EV/FCF: {f_n(metrics.get('ev_fcf'))}
    - P/E Actual: {f_n(metrics.get('pe_ratio'))} | D/E: {f_n(metrics.get('debt_equity'))}
    - Crecimiento Ventas 5A: {f_p(metrics.get('rev_growth_5y_avg'))}
    - FCF Latente (Backlog Ajustado): ${metrics.get('adj_backlog'):,.0f}
    - Perfil: {metrics['description'][:1000]}

    DIRECTRICES DE RIGOR:
    1. PRIORIDAD BALANCE: El balance es la única verdad. Si el ROIC < 10% de forma persistente, el score NO puede superar 50.
    2. AJUSTE POR CATALIZADOR: Busca contratos con Hyperscalers (Microsoft, AWS, Google), reactivación de activos estratégicos (nuclear, defensa) u opcionalidad de IA.
    3. DETECCIÓN DE 'OLVIDO': ¿Por qué el mercado castiga este activo? ¿Es por aburrimiento o por deterioro real?
    4. EXTENSIÓN: El informe forense debe ser extenso (mínimo 4 párrafos técnicos), integrando las métricas arriba citadas.

    JSON OUTPUT REQUERIDO:
    {{
        "modelo_negocio": "Explicación clara de la generación de caja.",
        "analisis_balance": "Crítica técnica de la solvencia y eficiencia histórica.",
        "catalizadores_y_olvido": "Análisis de contratos futuros y por qué el mercado la ignora/sobrevalora.",
        "ajuste_narrativo": [true/false si subiste el score por eventos futuros],
        "score_contable": [0-100],
        "score_final": [0-100],
        "veredicto": "[Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Plan táctico (DCA Racional, Liquidez, etc)."
    }}
    """
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.15))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        return {"score_final": 0, "veredicto": "Error de Inferencia IA", "analisis_balance": f"Fallo: {str(e)}"}

# =====================================================================
# 5. UI: TERMINAL DE CONTROL INSTITUCIONAL
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: The Sovereign Auditor")
    st.caption("v9.0 | Unabridged Accounting Engine | Gemini 2.5 Pro")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Configuración de Radar")
        mode = st.radio("Método de Entrada", ["Manual (CSV)", "Descubrimiento (Screener)"])
        
        if mode == "Manual (CSV)":
            raw_input = st.text_input("Ingrese Tickers", value="GOOGL, CEG, VRT")
        else:
            limit_disc = st.slider("Candidatos a descubrir", 5, 20, 10)
        
        st.markdown("---")
        if st.button("INICIAR AUDITORÍA FORENSE", type="primary", use_container_width=True):
            st.session_state.execute = True
            if mode == "Manual (CSV)":
                st.session_state.tickers = [x.strip().upper() for x in raw_input.split(",") if x.strip()]
            else:
                with st.spinner("Escaneando el mercado..."):
                    st.session_state.tickers = discovery_screener(limit_disc)

    if "execute" in st.session_state and st.session_state.execute:
        summary_results = []
        
        for ticker in st.session_state.tickers:
            with st.container():
                st.markdown(f"## 📊 Informe de Activo: {ticker}")
                
                # Capa de Datos
                with st.spinner(f"Extrayendo y reconstruyendo balances de {ticker}..."):
                    metrics = fetch_quantitative_analysis(ticker)
                
                if "_error" in metrics:
                    st.error(f"Error en {ticker}: {metrics['_error']}")
                    continue

                st.caption(f"**Fuente:** {metrics['source']} | **Industria:** {metrics['industry']}")

                # Visualización de Métricas de Grado Quant
                m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
                
                def fmt(v, p=False):
                    if v == "N/A" or v is None: return "N/A"
                    return f"{v*100:.2f}%" if p else f"{v:.2f}x"

                m_c1.metric("ROIC 5Y (Avg)", fmt(metrics.get('roic_5y_avg'), True))
                m_c2.metric("FCF Yield", fmt(metrics.get('fcf_yield'), True))
                m_c3.metric("EV / FCF", fmt(metrics.get('ev_fcf')))
                m_c4.metric("Debt / Equity", fmt(metrics.get('debt_equity')))
                # Backlog Latente format
                b_val = metrics.get('adj_backlog')
                b_label = f"${b_val/1e6:.1f}M" if b_val != "N/A" and b_val < 1e9 else (f"${b_val/1e9:.1f}B" if b_val != "N/A" else "N/A")
                m_c5.metric("FCF Latente (Backlog)", b_label)

                # Capa de Inteligencia
                with st.spinner(f"Gemini 2.5 Pro cruzando datos de {ticker}..."):
                    audit = execute_sovereign_audit(ticker, metrics)
                
                # ADVERTENCIA DE AJUSTE (Prioridad Usuario)
                if audit.get("ajuste_narrativo"):
                    st.markdown(f"""
                        <div class="warning-card">
                            ⚠️ <b>ADVERTENCIA DE VALORACIÓN:</b> El Score Final de {ticker} ({audit['score_final']}) ha sido incrementado por factores cualitativos (contratos/catalizadores). <br>
                            <b>Score Contable (Basado en el Balance): {audit['score_contable']}</b>. <br>
                            El balance actual no justifica este precio; la inversión depende del éxito de eventos futuros.
                        </div>
                    """, unsafe_allow_html=True)

                res_l, res_r = st.columns([1.5, 2.5])
                with res_l:
                    color_map = {"Strong Buy": "🟢", "Buy": "🟩", "Hold": "🟨", "Sell": "🟧", "Strong Sell": "🔴"}
                    st.markdown(f"### {color_map.get(audit.get('veredicto'), '⚪')} {audit.get('veredicto')}")
                    st.progress(audit.get('score_final', 0)/100, text=f"Score de Convicción: {audit.get('score_final')}")
                    st.markdown("**Estrategia de Ejecución:**")
                    st.success(audit.get('estrategia', 'N/A'))
                
                with res_r:
                    st.markdown("<div class='report-box'>", unsafe_allow_html=True)
                    st.markdown(f"### 📝 Expediente Forense: {ticker}")
                    st.markdown("**Modelo de Negocio y Generación de Caja:**")
                    st.write(audit.get('modelo_negocio'))
                    st.markdown("---")
                    st.markdown("**Auditoría de Balance (La Realidad):**")
                    st.write(audit.get('analisis_balance'))
                    st.markdown("---")
                    st.markdown("**Catalizadores, Opcionalidad y 'Olvido':**")
                    st.write(audit.get('catalizadores_y_olvido'))
                    st.markdown("</div>", unsafe_allow_html=True)
                
                summary_results.append({
                    "Activo": ticker, "Score Final": audit.get('score_final'),
                    "Score Balance": audit.get('score_contable'), "Veredicto": audit.get('veredicto')
                })
                st.markdown("---")

        if summary_results:
            st.subheader("📋 Matriz Comparativa de Ejecución")
            st.dataframe(pd.DataFrame(summary_results).sort_values(by="Score Final", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
