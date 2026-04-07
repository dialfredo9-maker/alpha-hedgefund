"""
TERMINAL QUANTS PRO v14.0 - THE ETERNAL SOVEREIGN
-------------------------------------------------
1. Radar: Manual (CSV) + Descubrimiento Automático (Screener).
2. Engine: Reconstrucción Contable Manual de 6 Años (ROIC, FCF, EV).
3. IA: Gemini 2.5 Pro (Dual-Score Audit + Tesis > 700 palabras).
4. Export: Matriz Global Acumulativa para Excel (Manual/Screener).
"""

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import json

# =====================================================================
# 1. INFRAESTRUCTURA DE INTERFAZ Y ESTILOS (GRADO PROFESIONAL)
# =====================================================================
st.set_page_config(
    page_title="Terminal Quants PRO: Eternal Sovereign", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .report-box { background-color: #ffffff; padding: 40px; border: 1px solid #cbd5e0; border-left: 14px solid #1a202c; border-radius: 4px; color: #1a202c; font-family: 'Inter', sans-serif; line-height: 1.8; }
    .metric-value { font-size: 30px; font-weight: 800; color: #2d3748; }
    .warning-banner { background-color: #fffaf0; color: #9c4221; padding: 30px; border-radius: 8px; border: 2px solid #fbd38d; margin-bottom: 35px; font-size: 1.15em; font-weight: 600; }
    .success-banner { background-color: #f0fff4; color: #22543d; padding: 30px; border-radius: 8px; border: 2px solid #9ae6b4; margin-bottom: 35px; }
    .stProgress > div > div > div > div { background-color: #1a202c; }
    </style>
""", unsafe_allow_html=True)

try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception:
    st.error("Error Crítico: Faltan API Keys en .streamlit/secrets.toml")
    st.stop()

GEMINI_MODEL_NAME = 'gemini-2.5-pro'

# =====================================================================
# 2. MOTOR DE DESCUBRIMIENTO (SCREENER DE MERCADO)
# =====================================================================

def discovery_screener(limit=10):
    """Escanea el universo de FMP en busca de activos con Market Cap > 1B y operativa activa."""
    url = (f"https://financialmodelingprep.com/stable/company-screener?"
           f"marketCapMoreThan=1000000000&priceMoreThan=5&isEtf=false&"
           f"isActivelyTrading=true&limit={limit*2}&apikey={FMP_API_KEY}")
    try:
        resp = requests.get(url, timeout=12).json()
        if isinstance(resp, list):
            return [stock['symbol'] for stock in resp]
        return []
    except Exception:
        return []

# =====================================================================
# 3. ENGINE DE DATOS: RECONSTRUCCIÓN CONTABLE SOBERANA (PROTECCIÓN TOTAL)
# =====================================================================

def get_fmp_raw(endpoint, symbol, limit=5):
    url = f"https://financialmodelingprep.com/stable/{endpoint}?symbol={symbol}&limit={limit}&apikey={FMP_API_KEY}"
    try:
        r = requests.get(url, timeout=15)
        return r.json() if r.status_code == 200 else None
    except: return None

@st.cache_data(ttl=3600)
def fetch_unabridged_accounting(ticker: str) -> dict:
    """Engine v14.0: Reconstrucción manual absoluta de estados financieros y arbitraje de Market Cap."""
    m = {}
    
    # Perfil y Arbitraje de Market Cap (Evitar error Alphabet/Google)
    prof_j = get_fmp_raw("profile", ticker, limit=1)
    if not prof_j: return {"_error": f"Ticker {ticker} no accesible en base de datos."}
    p = prof_j[0]
    
    price = p.get('price', 0.0)
    mkt_cap_raw = p.get('mktCap') or p.get('marketCap', 0)
    
    # Arbitraje: Si FMP entrega datos de escala errónea, yfinance actúa como árbitro
    if mkt_cap_raw < 100000000: # Menos de 100M para empresas GICS es sospechoso
        s_yf = yf.Ticker(ticker)
        mkt_cap = s_yf.info.get('marketCap', price * 1e6)
    else:
        mkt_cap = mkt_cap_raw

    m.update({
        'sector': p.get('sector', 'N/A'), 'industry': p.get('industry', 'N/A'),
        'price': price, 'mkt_cap': mkt_cap, 'description': p.get('description', '')
    })

    # Ingesta de Estados Financieros (6 Años para cálculos de tendencia)
    is_j = get_fmp_raw("income-statement", ticker, limit=6)
    bs_j = get_fmp_raw("balance-sheet-statement", ticker, limit=6)
    cf_j = get_fmp_raw("cash-flow-statement", ticker, limit=6)
    
    if not is_j or not bs_j or not cf_j: return {"_error": "Datos financieros insuficientes para auditoría."}

    # CÁLCULO MANUAL (AÑO ACTUAL - TTM)
    i0, b0, c0 = is_j[0], bs_j[0], cf_j[0]
    
    # 1. Reconstrucción de Deuda y Solvencia (Búsqueda redundante de llaves)
    t_debt = b0.get('totalDebt') if b0.get('totalDebt', 0) > 0 else (b0.get('shortTermDebt', 0) + b0.get('longTermDebt', 0))
    cash = b0.get('cashAndCashEquivalents', 0)
    equity = b0.get('totalStockholdersEquity', b0.get('totalEquity', 1))
    ebit = i0.get('operatingIncome', 0)
    
    # 2. ROIC Forense Soberano
    # NOPAT = EBIT * (1 - TaxRate)
    tax_exp = i0.get('incomeTaxExpense', 0)
    pretax = i0.get('incomeBeforeTax', 1)
    t_rate = tax_exp / pretax if pretax > 0 else 0.21
    nopat = ebit * (1 - t_rate)
    invested_cap = t_debt + equity - cash
    m['roic'] = nopat / invested_cap if invested_cap > 0 else 0.0

    # 3. Valoración y Eficiencia de Flujo (EV / FCF)
    fcf = c0.get('freeCashFlow', 0)
    m['fcf_yield'] = fcf / mkt_cap if mkt_cap > 0 else 0.0
    ev = mkt_cap + t_debt - cash
    m['ev_fcf'] = ev / fcf if fcf > 0 else 0.0
    m['pe_ratio'] = mkt_cap / i0.get('netIncome', 1) if i0.get('netIncome', 0) > 0 else 0.0
    
    # 4. Ratios de Riesgo y Balance
    m['debt_equity'] = t_debt / equity if equity > 0 else 0.0
    m['interest_coverage'] = ebit / (i0.get('interestExpense', 1) or 1)
    
    # 5. FCF Latente (Poder de Conversión de Backlog)
    def_rev = b0.get('deferredRevenue', 0) + b0.get('deferredRevenueNonCurrent', 0)
    gross_margin = i0.get('grossProfit', 0) / i0.get('revenue', 1) if i0.get('revenue', 0) > 0 else 0
    m['adj_backlog'] = def_rev * gross_margin

    # AUDITORÍA HISTÓRICA (BUCLE DE 5 AÑOS PARA PROMEDIOS REALES)
    h_roic = []
    for k in range(min(5, len(is_j), len(bs_j))):
        try:
            ei = is_j[k].get('operatingIncome', 0)
            di = bs_j[k].get('totalDebt') or (bs_j[k].get('shortTermDebt', 0) + bs_j[k].get('longTermDebt', 0))
            eqi = bs_j[k].get('totalStockholdersEquity', bs_j[k].get('totalEquity', 1))
            ci = bs_j[k].get('cashAndCashEquivalents', 0)
            ici = di + eqi - ci
            tr = is_j[k].get('incomeTaxExpense', 0) / is_j[k].get('incomeBeforeTax', 1) if is_j[k].get('incomeBeforeTax', 0) > 0 else 0.21
            if ici > 0: h_roic.append((ei * (1 - tr)) / ici)
        except: continue
    m['roic_5y_avg'] = sum(h_roic)/len(h_roic) if h_roic else 0.0
    
    h_rev = []
    for k in range(min(5, len(is_j)-1)):
        prev = is_j[k+1].get('revenue', 1)
        h_rev.append((is_j[k].get('revenue', 0) - prev) / prev)
    m['rev_growth_5y_avg'] = sum(h_rev)/len(h_rev) if h_rev else 0.0

    m['source'] = "Sovereign Engine v14.0 (Full Manual Reconstruction)"
    return m

# =====================================================================
# 4. CEREBRO IA: AUDITORÍA DE ALTA DENSIDAD (UNABRIDGED)
# =====================================================================

def run_unabridged_audit(ticker: str, metrics: dict) -> dict:
    """Instrucción de alta densidad para Gemini 2.5 Pro."""
    def fp(v): return f"{v*100:.2f}%" if v and v != "N/A" else "0.00%"
    def fn(v): return f"{v:.2f}x" if v and v != "N/A" else "0.00x"

    prompt = f"""
    Misión: Analista Jefe de Riesgo de un Hedge Fund Global. 
    Activo: {ticker} | Sector: {metrics['sector']} | Precio: ${metrics['price']}
    
    DATOS CONTABLES RECONSTRUIDOS (OBLIGATORIO CITAR):
    - ROIC Actual: {fp(metrics.get('roic'))} | Media 5A: {fp(metrics.get('roic_5y_avg'))}
    - FCF Yield: {fp(metrics.get('fcf_yield'))} | EV/FCF: {fn(metrics.get('ev_fcf'))}
    - P/E Actual: {fn(metrics.get('pe_ratio'))} | D/E: {fn(metrics.get('debt_equity'))}
    - Cobertura de Intereses: {fn(metrics.get('interest_coverage'))}
    - FCF Latente (Backlog Ajustado): ${metrics.get('adj_backlog'):,.0f}

    REGLAS DEL INFORME:
    1. EXTENSIÓN: Tesis doctoral de inversión (>700 palabras). No resumas ni omitas secciones.
    2. RIGOR: Cruza los datos de ROIC con la valoración de EV/FCF. ¿Es el foso económico real o especulativo?
    3. CATALIZADORES: Analiza contratos con Hyperscalers, reactivación de activos estratégicos u opcionalidad en IA.
    4. DUAL SCORING: Define un Score Contable (balance) y un Score Final (veredicto).

    JSON OUTPUT REQUERIDO:
    {{
        "modelo_negocio": "Explicación técnica de la generación de caja.",
        "auditoria_forense": "Tesis técnica extensa. Cruce detallado de ROIC, Solvencia y Calidad de Caja citando números.",
        "tesis_catalizadores": "Análisis de contratos futuros y opcionalidad estratégica.",
        "tipo_ajuste": "[Incremento, Decremento, Neutral]",
        "motivo_ajuste": "Justificación técnica del ajuste de score.",
        "score_contable": [0-100], "score_final": [0-100], "veredicto": "[Strong Buy...]", "estrategia": "Plan táctico."
    }}
    """
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.15))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: return {"score_final": 0, "veredicto": "Fallo IA", "auditoria_forense": "Error en generación."}

# =====================================================================
# 5. UI: TABLERO INSTITUCIONAL COMPLETO CON ACUMULADOR
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: The Eternal Sovereign")
    st.caption("Engine v14.0 Unabridged | Market Screener | Global Export Matrix | Gemini 2.5 Pro")
    st.markdown("---")

    # Acumulador persistente para la tabla de Excel
    if "export_data" not in st.session_state:
        st.session_state.export_data = []

    with st.sidebar:
        st.header("⚙️ Configuración")
        mode = st.radio("Modo de Radar", ["Manual (CSV)", "Descubrimiento (Automático)"])
        
        if mode == "Manual (CSV)":
            tk_in = st.text_input("Ingresar Tickers", value="GOOGL, CEG, NVDA")
        else:
            limit_disc = st.slider("Activos a escanear", 5, 20, 10)
        
        st.markdown("---")
        execute = st.button("INICIAR AUDITORÍA TOTAL", type="primary", use_container_width=True)
        if st.button("Limpiar Tabla de Exportación"):
            st.session_state.export_data = []
            st.rerun()

    if execute:
        # Selección de Tickers según modo
        if mode == "Manual (CSV)":
            tickers = [x.strip().upper() for x in tk_in.split(",") if x.strip()]
        else:
            with st.spinner("Escaneando el mercado..."):
                tickers = discovery_screener(limit_disc)
        
        # Procesamiento individual
        for t in tickers:
            with st.container():
                st.markdown(f"## 📊 Informe Forense: {t}")
                met = fetch_unabridged_accounting(t)
                if "_error" in met:
                    st.error(f"Error en {t}: {met['_error']}")
                    continue

                # Grid Visual de Métricas
                c1, c2, c3, c4, c5 = st.columns(5)
                def f_v(v, p=False): return f"{v*100:.2f}%" if p and v != "N/A" else (f"{v:.2f}x" if v != "N/A" else "N/A")
                c1.metric("ROIC 5Y (Avg)", f_v(met.get('roic_5y_avg'), True))
                c2.metric("FCF Yield", f_v(met.get('fcf_yield'), True))
                c3.metric("EV / FCF", f_v(met.get('ev_fcf')))
                c4.metric("Debt / Equity", f_v(met.get('debt_equity')))
                b_val = met.get('adj_backlog')
                c5.metric("FCF Latente", f"${b_val/1e6:.1f}M" if b_val < 1e9 else f"${b_val/1e9:.1f}B")

                with st.spinner(f"Auditando {t} con Gemini 2.5 Pro..."):
                    audit = run_unabridged_audit(t, met)
                
                # Advertencia de Ajuste Narrativo
                score_diff = audit.get('score_final', 0) - audit.get('score_contable', 0)
                if abs(score_diff) > 5:
                    st.markdown(f'<div class="warning-banner">⚠️ <b>ADVERTENCIA DE AJUSTE:</b> Score Balance: {audit["score_contable"]} | Score Final: {audit["score_final"]}.<br><b>Justificación:</b> {audit.get("motivo_ajuste")}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="success-banner">✅ <b>VALORACIÓN ANCLADA:</b> El veredicto es coherente con el balance actual.</div>', unsafe_allow_html=True)

                l_col, r_col = st.columns([1.2, 2.8])
                with l_col:
                    st.subheader(f"{audit['veredicto']}")
                    st.progress(audit['score_final']/100, text=f"Score: {audit['score_final']}/100")
                    st.success(f"**Táctica:** {audit['estrategia']}")
                with r_col:
                    st.markdown("<div class='report-box'>", unsafe_allow_html=True)
                    st.markdown(f"### 🖋️ Tesis Unabridged: {t}\n**Modelo:** {audit.get('modelo_negocio')}\n\n**Auditoría:** {audit.get('auditoria_forense')}\n\n**Catalizadores:** {audit.get('tesis_catalizadores')}")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # Acumulación para Exportación
                st.session_state.export_data.append({
                    "Ticker": t, "Veredicto": audit.get("veredicto"), "Score Final": audit.get("score_final"), "Score Balance": audit.get("score_contable"),
                    "ROIC 5Y": met.get("roic_5y_avg"), "FCF Yield": met.get("fcf_yield"), "EV/FCF": met.get("ev_fcf"), "D/E": met.get("debt_equity"), "Backlog": met.get("adj_backlog")
                })
                st.markdown("---")

    # =====================================================================
    # 6. MATRIZ GLOBAL DE EXPORTACIÓN (ESTILO EXCEL)
    # =====================================================================
    if st.session_state.export_data:
        st.subheader("📋 Matriz Global de Datos (Export Ready)")
        df_export = pd.DataFrame(st.session_state.export_data).drop_duplicates(subset=['Ticker'], keep='last')
        
        st.dataframe(df_export.style.format({
            "ROIC 5Y": "{:.2%}", "FCF Yield": "{:.2%}", "EV/FCF": "{:.2f}x", "D/E": "{:.2f}x", "Backlog": "${:,.0f}"
        }), use_container_width=True)
        
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Descargar Matriz Completa para Excel", data=csv, file_name='radar_quants_pro.csv', mime='text/csv')

if __name__ == "__main__":
    main()
