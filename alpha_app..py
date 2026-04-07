"""
TERMINAL QUANTS PRO v12.0 - UNABRIDGED SOVEREIGN VERSION
--------------------------------------------------------
Seguridad: Triple-Check Data Arbitrage (FMP Stable -> FMP Raw -> yFinance).
Cálculo: Engine de Reconstrucción Contable Manual (Anti-N/A).
IA: Gemini 2.5 Pro (Informes Forenses > 700 palabras).
"""

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import json

# =====================================================================
# 1. INFRAESTRUCTURA DE INTERFAZ Y ESTILOS DE GRADO INVERSIÓN
# =====================================================================
st.set_page_config(
    page_title="Terminal Quants PRO: Eternal Auditor", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .report-box { 
        background-color: #ffffff; 
        padding: 35px; 
        border: 1px solid #e2e8f0; 
        border-left: 12px solid #1a202c; 
        border-radius: 4px; 
        color: #1a202c; 
        font-family: 'Inter', sans-serif; 
        line-height: 1.8; 
    }
    .metric-value { font-size: 28px; font-weight: 800; color: #2d3748; }
    .warning-banner { 
        background-color: #fffaf0; 
        color: #9c4221; 
        padding: 25px; 
        border-radius: 8px; 
        border: 2px solid #fbd38d; 
        margin-bottom: 30px; 
        font-size: 1.1em;
    }
    .logic-header { 
        color: #2c5282; 
        border-bottom: 2px solid #ebf8ff; 
        padding-bottom: 10px; 
        margin-top: 35px; 
        font-weight: bold;
    }
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
# 2. MOTOR DE RECONSTRUCCIÓN CONTABLE SOBERANO (REDUNDANCIA TOTAL)
# =====================================================================

def get_fmp_raw(endpoint, symbol, limit=5):
    url = f"https://financialmodelingprep.com/stable/{endpoint}?symbol={symbol}&limit={limit}&apikey={FMP_API_KEY}"
    try:
        r = requests.get(url, timeout=15)
        return r.json() if r.status_code == 200 else None
    except: return None

@st.cache_data(ttl=3600)
def fetch_unabridged_accounting(ticker: str) -> dict:
    """
    Engine v12.0: Reconstruye cada métrica desde los estados financieros brutos.
    No confía en los ratios pre-calculados de la API para evitar errores de escala.
    """
    m = {}
    
    # --- A. Perfil y Arbitraje de Market Cap ---
    prof_j = get_fmp_raw("profile", ticker, limit=1)
    if not prof_j: return {"_error": f"Ticker {ticker} no encontrado."}
    p = prof_j[0]
    
    # 🚨 BLINDAJE ANTI-ERROR (ALPHABET FIX): Validación de Market Cap
    price = p.get('price', 0.0)
    mkt_cap_raw = p.get('mktCap') or p.get('marketCap', 0)
    
    # Si el Market Cap es sospechosamente bajo (<100M para empresas GICS)
    if mkt_cap_raw < 100000000:
        s_yf = yf.Ticker(ticker)
        mkt_cap = s_yf.info.get('marketCap', price * 1e6)
    else:
        mkt_cap = mkt_cap_raw

    m.update({
        'sector': p.get('sector', 'N/A'),
        'industry': p.get('industry', 'N/A'),
        'price': price,
        'mkt_cap': mkt_cap,
        'description': p.get('description', '')
    })

    # --- B. Ingesta de Estados Financieros de 6 Años ---
    is_j = get_fmp_raw("income-statement", ticker, limit=6)
    bs_j = get_fmp_raw("balance-sheet-statement", ticker, limit=6)
    cf_j = get_fmp_raw("cash-flow-statement", ticker, limit=6)
    
    if not is_j or not bs_j or not cf_j:
        return {"_error": "Datos financieros insuficientes para auditoría forense."}

    # --- C. CÁLCULO MANUAL SOBERANO (AÑO ACTUAL) ---
    i0, b0, c0 = is_j[0], bs_j[0], cf_j[0]
    
    # 1. Reconstrucción de Deuda y Solvencia
    # Verificamos múltiples llaves para no dejar la deuda en N/A
    t_debt = b0.get('totalDebt') or (b0.get('shortTermDebt', 0) + b0.get('longTermDebt', 0))
    cash = b0.get('cashAndCashEquivalents', 0)
    equity = b0.get('totalStockholdersEquity', b0.get('totalEquity', 1))
    ebit = i0.get('operatingIncome', 0)
    
    # 2. ROIC Matemático: EBIT * (1-t) / Invested Capital
    tax_exp = i0.get('incomeTaxExpense', 0)
    pretax = i0.get('incomeBeforeTax', 1)
    t_rate = tax_exp / pretax if pretax > 0 else 0.21
    nopat = ebit * (1 - t_rate)
    invested_cap = t_debt + equity - cash
    m['roic'] = nopat / invested_cap if invested_cap > 0 else 0.0

    # 3. Valoración y Flujo de Caja (FCF)
    fcf = c0.get('freeCashFlow', 0)
    m['fcf_yield'] = fcf / mkt_cap if mkt_cap > 0 else 0.0
    # EV = Market Cap + Debt - Cash
    ev = mkt_cap + t_debt - cash
    m['ev_fcf'] = ev / fcf if fcf > 0 else 0.0
    m['pe_ratio'] = mkt_cap / i0.get('netIncome', 1) if i0.get('netIncome', 0) > 0 else 0.0
    
    # 4. Ratios de Balance
    m['debt_equity'] = t_debt / equity if equity > 0 else 0.0
    m['interest_coverage'] = ebit / (i0.get('interestExpense', 1) or 1)
    
    # 5. FCF Latente (Backlog / Ingresos Diferidos)
    def_rev = b0.get('deferredRevenue', 0) + b0.get('deferredRevenueNonCurrent', 0)
    gross_margin = i0.get('grossProfit', 0) / i0.get('revenue', 1) if i0.get('revenue', 0) > 0 else 0
    m['adj_backlog'] = def_rev * gross_margin

    # --- D. AUDITORÍA HISTÓRICA (PROMEDIOS DE 5 AÑOS) ---
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
    
    # Crecimiento CAGR de Ingresos
    h_rev = []
    for k in range(min(5, len(is_j)-1)):
        prev = is_j[k+1].get('revenue', 1)
        h_rev.append((is_j[k].get('revenue', 0) - prev) / prev)
    m['rev_growth_5y_avg'] = sum(h_rev)/len(h_rev) if h_rev else 0.0

    m['source'] = "Sovereign Engine v12.0 (Full Manual Reconstruction)"
    return m

# =====================================================================
# 3. CEREBRO IA: AUDITORÍA DE ALTA DENSIDAD (UNABRIDGED)
# =====================================================================

def run_deep_audit_v12(ticker: str, metrics: dict) -> dict:
    """
    Fuerza a Gemini 2.5 Pro a realizar una tesis técnica cruzando todas las métricas.
    """
    def fp(v): return f"{v*100:.2f}%" if v and v != "N/A" else "0.00%"
    def fn(v): return f"{v:.2f}x" if v and v != "N/A" else "0.00x"

    prompt = f"""
    Misión: Eres el Analista Principal de Riesgo de un Hedge Fund de Situaciones Especiales. 
    Tu tarea es auditar a {ticker} ({metrics['sector']}) y emitir una tesis de inversión de nivel institucional.

    DATOS CONTABLES RECONSTRUIDOS (OBLIGATORIO CITAR):
    - ROIC Actual: {fp(metrics.get('roic'))} | Media 5A: {fp(metrics.get('roic_5y_avg'))}
    - FCF Yield: {fp(metrics.get('fcf_yield'))} | EV/FCF: {fn(metrics.get('ev_fcf'))}
    - P/E Actual: {fn(metrics.get('pe_ratio'))} | D/E: {fn(metrics.get('debt_equity'))} | Cobertura Int: {fn(metrics.get('interest_coverage'))}
    - Crecimiento Ventas 5A: {fp(metrics.get('rev_growth_5y_avg'))}
    - FCF Latente (Backlog Ajustado): ${metrics.get('adj_backlog'):,.0f}

    REGLAS DE ORO DEL INFORME:
    1. EXTENSIÓN Y RIGOR: El informe forense debe ser una tesis extensa (mínimo 700 palabras). No resumas.
    2. INTEGRACIÓN DE DATOS: Cada párrafo DEBE citar los números proporcionados para validar la tesis (ej: "Con un ROIC del {fp(metrics.get('roic'))}, la empresa demuestra...").
    3. BALANCE VS NARRATIVA: Calcula un 'Score Contable' (puro balance) y compáralo con el 'Score Final' (balance + catalizadores).
    4. DETECCIÓN DE CATALIZADORES: Busca activamente contratos con Hyperscalers (Microsoft, AWS, Google), reactivación de activos estratégicos u opcionalidad en IA.

    JSON OUTPUT REQUERIDO (ESTRICTO):
    {{
        "modelo_negocio": "Explicación técnica y estratégica de la generación de valor.",
        "auditoria_forense": "Tesis técnica extensa. Cruce detallado de ROIC, Solvencia y Calidad de Caja citando cada métrica.",
        "tesis_catalizadores": "Análisis de contratos futuros, opcionalidad de IA y eventos estratégicos.",
        "tipo_ajuste": "[Incremento, Decremento, Neutral]",
        "motivo_ajuste": "Justificación de la brecha entre el balance actual y el veredicto final.",
        "score_contable": [0-100 basado solo en números actuales],
        "score_final": [0-100 veredicto total],
        "veredicto": "[Strong Buy, Buy, Hold, Sell, Strong Sell]",
        "estrategia": "Táctica operativa detallada (DCA Racional, Coberturas, etc)."
    }}
    """
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.15))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"score_final": 0, "veredicto": "Fallo IA", "auditoria_forense": "Error en la generación del reporte extenso."}

# =====================================================================
# 4. INTERFAZ DE USUARIO (UI TERMINAL)
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: The Eternal Auditor")
    st.caption("Engine v12.0 Unabridged | Redundant Accounting | Gemini 2.5 Pro")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Radar de Auditoría")
        tk_in = st.text_input("Ingresar Tickers (Separados por coma)", value="GOOGL, CEG, NVDA")
        st.markdown("---")
        execute = st.button("INICIAR AUDITORÍA TOTAL", type="primary", use_container_width=True)

    if execute:
        tickers = [x.strip().upper() for x in tk_in.split(",") if x.strip()]
        
        for t in tickers:
            with st.container():
                st.markdown(f"## 📊 Informe Forense de Activo: {t}")
                
                with st.spinner(f"Ejecutando reconstrucción contable para {t}..."):
                    met = fetch_unabridged_accounting(t)
                
                if "_error" in met:
                    st.error(f"Error en {t}: {met['_error']}")
                    continue

                st.caption(f"**Industria:** {met['industry']} | **Fuente:** {met['source']}")

                # Visualización de Métricas (Grado Quant)
                c1, c2, c3, c4, c5 = st.columns(5)
                def f_v(v, p=False): 
                    if v == "N/A" or v is None: return "N/A"
                    return f"{v*100:.2f}%" if p else f"{v:.2f}x"
                
                c1.metric("ROIC 5Y (Avg)", f_v(met.get('roic_5y_avg'), True))
                c2.metric("FCF Yield", f_v(met.get('fcf_yield'), True))
                c3.metric("EV / FCF", f_v(met.get('ev_fcf')))
                c4.metric("Debt / Equity", f_v(met.get('debt_equity')))
                # Formato monetario para Backlog
                back = met.get('adj_backlog')
                bl_label = f"${back/1e6:.1f}M" if back < 1e9 else f"${back/1e9:.1f}B"
                c5.metric("FCF Latente", bl_label)

                # Auditoría de Inteligencia
                with st.spinner(f"Analizando tesis de {t} con Gemini 2.5 Pro..."):
                    audit = run_deep_audit_v12(t, met)
                
                # ADVERTENCIA DE AJUSTE NARRATIVO
                score_diff = audit.get('score_final', 0) - audit.get('score_contable', 0)
                if abs(score_diff) > 5:
                    st.markdown(f"""
                        <div class="warning-banner">
                            ⚠️ <b>AJUSTE ESTRATÉGICO DETECTADO:</b> El veredicto de {t} ha sido modificado por factores cualitativos.<br>
                            <b>Score de Balance (Hard Numbers): {audit['score_contable']}</b> | <b>Score Final: {audit['score_final']}</b>.<br>
                            <b>Justificación:</b> {audit.get('motivo_ajuste', 'Ajuste por catalizadores futuros.')}
                        </div>
                    """, unsafe_allow_html=True)

                l_col, r_col = st.columns([1.2, 2.8])
                with l_col:
                    st.subheader(f"Veredicto: {audit['veredicto']}")
                    st.progress(audit['score_final']/100, text=f"Score: {audit['score_final']}/100")
                    st.success(f"**Estrategia:** {audit['estrategia']}")
                
                with r_col:
                    st.markdown("<div class='report-box'>", unsafe_allow_html=True)
                    st.markdown(f"### 🖋️ Tesis de Inversión Unabridged: {t}")
                    st.markdown("**Modelo de Negocio:**")
                    st.write(audit.get('modelo_negocio'))
                    st.markdown("---")
                    st.markdown("**Auditoría Contable y de Eficiencia:**")
                    st.write(audit.get('auditoria_forense'))
                    st.markdown("---")
                    st.markdown("**Catalizadores y Opcionalidad Estratégica:**")
                    st.write(audit.get('tesis_catalizadores'))
                    st.markdown("</div>", unsafe_allow_html=True)
                st.markdown("---")

if __name__ == "__main__":
    main()
