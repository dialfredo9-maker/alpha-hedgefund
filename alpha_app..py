"""
TERMINAL QUANTS PRO v12.5 - UNABRIDGED SOVEREIGN & EXPORT VERSION
------------------------------------------------------------------
Seguridad: Triple-Check Data Arbitrage (FMP Stable -> FMP Raw -> yFinance).
Cálculo: Engine de Reconstrucción Contable Manual Completo.
IA: Gemini 2.5 Pro (Tesis Doctorales > 700 palabras).
Nuevo: Matriz de Exportación Dinámica para Excel.
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
    .report-box { background-color: #ffffff; padding: 35px; border: 1px solid #e2e8f0; border-left: 12px solid #1a202c; border-radius: 4px; color: #1a202c; font-family: 'Inter', sans-serif; line-height: 1.8; }
    .metric-value { font-size: 28px; font-weight: 800; color: #2d3748; }
    .warning-banner { background-color: #fffaf0; color: #9c4221; padding: 25px; border-radius: 8px; border: 2px solid #fbd38d; margin-bottom: 30px; font-size: 1.1em; }
    .logic-header { color: #2c5282; border-bottom: 2px solid #ebf8ff; padding-bottom: 10px; margin-top: 35px; font-weight: bold; }
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
    """Engine v12.5: Reconstrucción manual absoluta de estados financieros."""
    m = {}
    
    # Perfil y Arbitraje de Market Cap
    prof_j = get_fmp_raw("profile", ticker, limit=1)
    if not prof_j: return {"_error": f"Ticker {ticker} no encontrado."}
    p = prof_j[0]
    
    # BLINDAJE ANTI-ERROR: Validación de Market Cap (Alphabet/Google Fix)
    price = p.get('price', 0.0)
    mkt_cap_raw = p.get('mktCap') or p.get('marketCap', 0)
    if mkt_cap_raw < 100000000:
        s_yf = yf.Ticker(ticker)
        mkt_cap = s_yf.info.get('marketCap', price * 1e6)
    else:
        mkt_cap = mkt_cap_raw

    m.update({
        'sector': p.get('sector', 'N/A'), 'industry': p.get('industry', 'N/A'),
        'price': price, 'mkt_cap': mkt_cap, 'description': p.get('description', '')
    })

    # Ingesta de Estados Financieros (6 Años)
    is_j, bs_j, cf_j = get_fmp_raw("income-statement", ticker, limit=6), get_fmp_raw("balance-sheet-statement", ticker, limit=6), get_fmp_raw("cash-flow-statement", ticker, limit=6)
    if not is_j or not bs_j or not cf_j: return {"_error": "Datos insuficientes."}

    # CÁLCULO MANUAL (AÑO ACTUAL)
    i0, b0, c0 = is_j[0], bs_j[0], cf_j[0]
    t_debt = b0.get('totalDebt') or (b0.get('shortTermDebt', 0) + b0.get('longTermDebt', 0))
    cash = b0.get('cashAndCashEquivalents', 0)
    equity = b0.get('totalStockholdersEquity', b0.get('totalEquity', 1))
    ebit = i0.get('operatingIncome', 0)
    
    # ROIC Forense
    tax_exp = i0.get('incomeTaxExpense', 0)
    pretax = i0.get('incomeBeforeTax', 1)
    t_rate = tax_exp / pretax if pretax > 0 else 0.21
    nopat = ebit * (1 - t_rate)
    invested_cap = t_debt + equity - cash
    m['roic'] = nopat / invested_cap if invested_cap > 0 else 0.0

    # Valoración
    fcf = c0.get('freeCashFlow', 0)
    m['fcf'] = fcf
    m['fcf_yield'] = fcf / mkt_cap if mkt_cap > 0 else 0.0
    ev = mkt_cap + t_debt - cash
    m['ev_fcf'] = ev / fcf if fcf > 0 else 0.0
    m['pe_ratio'] = mkt_cap / i0.get('netIncome', 1) if i0.get('netIncome', 0) > 0 else 0.0
    m['debt_equity'] = t_debt / equity if equity > 0 else 0.0
    m['interest_coverage'] = ebit / (i0.get('interestExpense', 1) or 1)
    
    # Backlog Ajustado
    def_rev = b0.get('deferredRevenue', 0) + b0.get('deferredRevenueNonCurrent', 0)
    gross_margin = i0.get('grossProfit', 0) / i0.get('revenue', 1) if i0.get('revenue', 0) > 0 else 0
    m['adj_backlog'] = def_rev * gross_margin

    # AUDITORÍA HISTÓRICA (5 AÑOS)
    h_roic = []
    for k in range(min(5, len(is_j), len(bs_j))):
        try:
            ei, di = is_j[k].get('operatingIncome', 0), (bs_j[k].get('totalDebt') or (bs_j[k].get('shortTermDebt', 0) + bs_j[k].get('longTermDebt', 0)))
            eqi, ci = bs_j[k].get('totalStockholdersEquity', bs_j[k].get('totalEquity', 1)), bs_j[k].get('cashAndCashEquivalents', 0)
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

    m['source'] = "Sovereign Engine v12.5 (Full Reconstruction)"
    return m

# =====================================================================
# 3. CEREBRO IA: AUDITORÍA DE ALTA DENSIDAD
# =====================================================================

def run_deep_audit_v12(ticker: str, metrics: dict) -> dict:
    def fp(v): return f"{v*100:.2f}%" if v and v != "N/A" else "0.00%"
    def fn(v): return f"{v:.2f}x" if v and v != "N/A" else "0.00x"

    prompt = f"""
    Misión: Analista Jefe de Riesgo de Situaciones Especiales. 
    Activo: {ticker} | Sector: {metrics['sector']} | Precio: ${metrics['price']}
    
    DATOS CONTABLES RECONSTRUIDOS:
    - ROIC Actual: {fp(metrics.get('roic'))} | Media 5A: {fp(metrics.get('roic_5y_avg'))}
    - FCF Yield: {fp(metrics.get('fcf_yield'))} | EV/FCF: {fn(metrics.get('ev_fcf'))}
    - P/E Actual: {fn(metrics.get('pe_ratio'))} | D/E: {fn(metrics.get('debt_equity'))}
    - FCF Latente (Backlog Ajustado): ${metrics.get('adj_backlog'):,.0f}

    REGLAS: Tesis institucional extensa (>700 palabras). Cruce técnico de datos. Justifica ajuste de score por catalizadores.
    
    JSON OUTPUT:
    {{
        "modelo_negocio": "...", "auditoria_forense": "...", "tesis_catalizadores": "...", 
        "tipo_ajuste": "...", "motivo_ajuste": "...", "score_contable": 0, "score_final": 0, 
        "veredicto": "...", "estrategia": "..."
    }}
    """
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.15))
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: return {"score_final": 0, "veredicto": "Fallo IA", "auditoria_forense": "Error en generación."}

# =====================================================================
# 4. INTERFAZ DE USUARIO (CON ACUMULADOR DE EXCEL)
# =====================================================================

def main():
    st.title("🏛️ Terminal Quants PRO: The Eternal Auditor")
    st.caption("Engine v12.5 Unabridged | Excel Export Support | Gemini 2.5 Pro")
    st.markdown("---")

    # Inicializar el acumulador de la tabla en el estado de la sesión
    if "export_data" not in st.session_state:
        st.session_state.export_data = []

    with st.sidebar:
        st.header("⚙️ Radar")
        tk_in = st.text_input("Ingresar Tickers (Separados por coma)", value="GOOGL, CEG, NVDA")
        st.markdown("---")
        if st.button("INICIAR AUDITORÍA TOTAL", type="primary", use_container_width=True):
            st.session_state.execute_run = True
            st.session_state.tickers_to_process = [x.strip().upper() for x in tk_in.split(",") if x.strip()]
            # Limpiar datos previos si es una nueva corrida completa
            st.session_state.export_data = []

    if "execute_run" in st.session_state and st.session_state.execute_run:
        for t in st.session_state.tickers_to_process:
            with st.container():
                st.markdown(f"## 📊 Informe Forense: {t}")
                met = fetch_unabridged_accounting(t)
                if "_error" in met:
                    st.error(f"Error en {t}: {met['_error']}")
                    continue

                # Grid Visual
                c1, c2, c3, c4, c5 = st.columns(5)
                def f_v(v, p=False): return f"{v*100:.2f}%" if p and v != "N/A" else (f"{v:.2f}x" if v != "N/A" else "N/A")
                c1.metric("ROIC 5Y (Avg)", f_v(met.get('roic_5y_avg'), True))
                c2.metric("FCF Yield", f_v(met.get('fcf_yield'), True))
                c3.metric("EV / FCF", f_v(met.get('ev_fcf')))
                c4.metric("Debt / Equity", f_v(met.get('debt_equity')))
                b_val = met.get('adj_backlog')
                c5.metric("FCF Latente", f"${b_val/1e6:.1f}M" if b_val < 1e9 else f"${b_val/1e9:.1f}B")

                with st.spinner(f"Auditando {t}..."):
                    audit = run_deep_audit_v12(t, met)
                
                # Advertencia Narrativa
                diff = audit.get('score_final', 0) - audit.get('score_contable', 0)
                if abs(diff) > 5:
                    st.markdown(f'<div class="warning-banner">⚠️ <b>AJUSTE ESTRATÉGICO:</b> Score Balance: {audit["score_contable"]} | Score Final: {audit["score_final"]}. Razón: {audit.get("motivo_ajuste")}</div>', unsafe_allow_html=True)

                l_col, r_col = st.columns([1.2, 2.8])
                with l_col:
                    st.subheader(f"{audit['veredicto']}")
                    st.progress(audit['score_final']/100, text=f"Score: {audit['score_final']}")
                    st.success(f"**Táctica:** {audit['estrategia']}")
                with r_col:
                    st.markdown("<div class='report-box'>", unsafe_allow_html=True)
                    st.markdown(f"### 🖋️ Tesis Unabridged: {t}\n**Modelo:** {audit.get('modelo_negocio')}\n\n**Auditoría:** {audit.get('auditoria_forense')}\n\n**Catalizadores:** {audit.get('tesis_catalizadores')}")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # GUARDAR EN EL ACUMULADOR PARA EXCEL
                st.session_state.export_data.append({
                    "Ticker": t,
                    "Veredicto": audit.get("veredicto"),
                    "Score Final": audit.get("score_final"),
                    "Score Balance": audit.get("score_contable"),
                    "ROIC 5Y Avg": met.get("roic_5y_avg"),
                    "FCF Yield": met.get("fcf_yield"),
                    "EV/FCF": met.get("ev_fcf"),
                    "Debt/Equity": met.get("debt_equity"),
                    "P/E Ratio": met.get("pe_ratio"),
                    "Backlog Adj": met.get("adj_backlog"),
                    "Estrategia": audit.get("estrategia")
                })
                st.markdown("---")

        # =====================================================================
        # 5. MATRIZ DE EXPORTACIÓN (EXCEL READY) AL FINAL
        # =====================================================================
        if st.session_state.export_data:
            st.subheader("📋 Matriz de Datos para Excel")
            st.markdown("Copia esta tabla y pégala directamente en tu hoja de cálculo Racional.")
            
            df_export = pd.DataFrame(st.session_state.export_data)
            
            # Formatear la tabla para que sea legible
            st.dataframe(
                df_export.style.format({
                    "ROIC 5Y Avg": "{:.2%}",
                    "FCF Yield": "{:.2%}",
                    "EV/FCF": "{:.2f}x",
                    "Debt/Equity": "{:.2f}x",
                    "P/E Ratio": "{:.2f}x",
                    "Backlog Adj": "${:,.0f}"
                }),
                use_container_width=True
            )
            
            # Botón de descarga CSV para flojera extrema
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Reporte como CSV (Excel)",
                data=csv,
                file_name='auditoria_quants_pro.csv',
                mime='text/csv',
            )

if __name__ == "__main__":
    main()
