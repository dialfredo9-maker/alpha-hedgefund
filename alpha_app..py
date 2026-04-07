"""
Plataforma Institucional de Análisis Fundamental y Clasificación de Arquetipos
Arquitectura Optimizada: Streamlit, yfinance, FMP API, Gemini AI.
"""

import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import google.generativeai as genai
import time

# =====================================================================
# 1. CONFIG
# =====================================================================

st.set_page_config(
    page_title="Terminal Institucional: Arquetipos Financieros",
    layout="wide"
)

# --- API KEYS CORREGIDO ---
try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except:
    st.warning("⚠️ Usando modo sin secrets (fallback manual)")
    FMP_API_KEY = ""
    GEMINI_API_KEY = ""

GEMINI_MODEL_NAME = "gemini-1.5-flash"

# =====================================================================
# 2. DATA LAYER (CON RATE LIMIT FIX)
# =====================================================================

@st.cache_data(ttl=86400)
def fetch_sectorial_taxonomy(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap", 0),
            "beta": info.get("beta", 1.0)
        }
    except:
        return {"sector": "Unknown", "industry": "Unknown"}


@st.cache_data(ttl=3600)
def fetch_quantitative_metrics(ticker):

    if not FMP_API_KEY:
        return {}

    try:
        url_ratios = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
        url_growth = f"https://financialmodelingprep.com/api/v3/financial-growth/{ticker}?limit=4&apikey={FMP_API_KEY}"

        ratios_res = requests.get(url_ratios, timeout=5)
        time.sleep(0.5)  # 🔥 anti rate limit
        growth_res = requests.get(url_growth, timeout=5)

        ratios_res.raise_for_status()
        growth_res.raise_for_status()

        ratios_json = ratios_res.json()
        growth_json = growth_res.json()

        metrics = {}

        # --- FIX LIST PARSING ---
        if isinstance(ratios_json, list) and len(ratios_json) > 0:
            data = ratios_json[0]

            metrics['pe_ratio'] = data.get('priceEarningsRatioTTM', 0)
            metrics['pb_ratio'] = data.get('priceToBookRatioTTM', 0)
            metrics['peg_ratio'] = data.get('pegRatioTTM', 0)
            metrics['roe'] = data.get('returnOnEquityTTM', 0)
            metrics['roic'] = data.get('returnOnCapitalEmployedTTM', 0)
            metrics['dividend_yield'] = data.get('dividendYieldTTM', 0)
            metrics['debt_equity'] = data.get('debtEquityRatioTTM', 0)
            metrics['ebitda_margin'] = data.get('ebitdaMarginTTM', 0)
            metrics['payout_ratio'] = data.get('payoutRatioTTM', 0)

        # --- FIX GROWTH ---
        if isinstance(growth_json, list) and len(growth_json) > 1:
            metrics['revenue_growth'] = growth_json[0].get('revenueGrowth', 0)

            rev_history = [p.get('revenueGrowth', 0) for p in growth_json[:3]]
            metrics['structural_decline'] = all(g < 0 for g in rev_history)
        else:
            metrics['revenue_growth'] = 0
            metrics['structural_decline'] = False

        return metrics

    except Exception as e:
        st.warning(f"FMP error {ticker}: {e}")
        return {}

# =====================================================================
# 3. MOTOR ARQUETIPO (FIX COMPLETO)
# =====================================================================

def evaluate_financial_archetype(sector, metrics):

    if not metrics:
        return "Abortado", "Sin datos"

    rev_growth = metrics.get('revenue_growth', 0) * 100
    ebitda = metrics.get('ebitda_margin', 0) * 100
    roe = metrics.get('roe', 0) * 100
    roic = metrics.get('roic', 0) * 100
    div = metrics.get('dividend_yield', 0) * 100
    debt = metrics.get('debt_equity', 0)
    pb = metrics.get('pb_ratio', 0)
    pe = metrics.get('pe_ratio', 0)

    # --- VALUE TRAP ---
    if metrics.get('structural_decline') and debt > 2:
        if pb < 1.5 or pe < 15:
            return "Value Trap", "Declive + deuda alta"

    # --- FINANCIALS ---
    if sector in ["Financial Services", "Banks"]:
        if roe > 10 and pb < 1.5:
            return "Financial Prime", "ROE alto + barato"
        elif roe < 6:
            return "Financial Weak", "ROE bajo"
        else:
            return "Financial Neutral", "Balanceado"

    # --- YIELD ---
    if sector in ["Real Estate", "Utilities"]:
        if div > 3.5 and metrics.get('payout_ratio', 1) < 0.95:
            return "Yield Strong", "Dividendo sólido"
        else:
            return "Yield Risk", "Riesgo dividendo"

    # --- SAAS ---
    if sector in ["Technology"]:
        rule40 = rev_growth + ebitda
        if rule40 > 40:
            return "SaaS Elite", f"Rule of 40: {rule40:.1f}"

    # --- GARP ---
    peg = metrics.get('peg_ratio', 99)
    if 0 < peg < 1 and 10 < pe < 25:
        return "GARP", "Crecimiento barato"

    # --- QUALITY ---
    if roic > 15 and debt < 1.5:
        return "Compounder", "Alta calidad"

    # --- DEEP VALUE ---
    if 0 < pb < 1.2 and 0 < pe < 12:
        return "Deep Value", "Barato real"

    return "Neutral", "Sin edge claro"

# =====================================================================
# 4. IA
# =====================================================================

def execute_ai_risk_audit(ticker, sector, archetype, metrics):

    if not GEMINI_API_KEY:
        return "IA no configurada"

    prompt = f"""
    Analiza {ticker} en sector {sector}.
    Clasificación: {archetype}

    Datos:
    {metrics}

    Evalúa riesgos reales institucionales.
    """

    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        res = model.generate_content(prompt)
        return res.text
    except Exception as e:
        return f"IA error: {e}"

# =====================================================================
# 5. UI
# =====================================================================

def main():

    st.title("🏛️ Terminal Institucional")

    tickers_raw = st.text_input("Tickers", "MSFT, JPM, O")

    if st.button("Ejecutar"):

        tickers = [t.strip().upper() for t in tickers_raw.split(",")]

        results = []

        for i, t in enumerate(tickers):

            with st.expander(t, expanded=True):

                taxonomy = fetch_sectorial_taxonomy(t)
                metrics = fetch_quantitative_metrics(t)

                if not metrics:
                    st.warning("Sin datos")
                    continue

                archetype, desc = evaluate_financial_archetype(
                    taxonomy["sector"], metrics
                )

                st.success(archetype)
                st.write(desc)

                ai = execute_ai_risk_audit(
                    t, taxonomy["sector"], archetype, metrics
                )
                st.write(ai)

                results.append({
                    "Ticker": t,
                    "Sector": taxonomy["sector"],
                    "Arquetipo": archetype,
                    "ROIC": metrics.get("roic"),
                    "PE": metrics.get("pe_ratio")
                })

                time.sleep(0.5)  # 🔥 evita ban API

        if results:
            df = pd.DataFrame(results)
            st.dataframe(df)

if __name__ == "__main__":
    main()
