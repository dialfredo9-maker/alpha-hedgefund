import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V8 FIX", layout="wide")

# --- API ---
st.sidebar.markdown("### 🔑 API Gemini")
API_KEY = st.sidebar.text_input("API KEY", type="password")

client = genai.Client(api_key=API_KEY) if API_KEY else None

# --- UTILIDADES ---
def safe_div(n, d):
    try:
        if n is None or d is None or d == 0:
            return None
        return n / d
    except:
        return None

def pct(x):
    return None if x is None else round(x * 100, 2)

# --- ROIC ROBUSTO ---
def calcular_roic(income, balance):
    try:
        try:
            ebit = income.loc['Operating Income'].dropna()[0]
        except:
            ebit = income.loc['EBIT'].dropna()[0]

        debt = balance.loc['Total Debt'].dropna()[0]
        equity = balance.loc['Total Stockholder Equity'].dropna()[0]

        return safe_div(ebit, debt + equity)
    except:
        return None

# --- SBC DINÁMICO ---
def calcular_sbc(cf):
    try:
        for key in cf.index:
            if "Stock" in key and "Compensation" in key:
                return cf.loc[key].dropna()[0]
    except:
        pass
    return None

# --- NET DEBT ROBUSTO ---
def calcular_net_debt(balance):
    try:
        try:
            debt = balance.loc['Total Debt'].dropna()[0]
        except:
            debt = 0

        try:
            cash = balance.loc['Cash And Cash Equivalents'].dropna()[0]
        except:
            cash = 0

        return debt - cash
    except:
        return None

# --- PER (PIPELINE ECONÓMICO REAL) ---
def calcular_per(tipo, backlog, revenue, cagr, margin, conv):
    backlog_usd = backlog * 1e9  # 🔥 FIX CRÍTICO

    if tipo == "Físico":
        return backlog_usd * conv * margin

    elif tipo == "Software":
        rev_fut = revenue * (1 + cagr)
        return rev_fut * margin

    return 0

# --- UI ---
st.title("🔬 Alpha Boardroom V8 FIX")

ticker = st.text_input("Ticker").upper()

if ticker:
    tk = yf.Ticker(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow
        bal = tk.balance_sheet

        if inc.empty or cf.empty:
            st.error("❌ Datos incompletos")
        else:
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1 if len(rev) > 1 else None

            fcf_ltm = fcf.iloc[-1]
            rev_ltm = rev.iloc[-1]

            fcf_margin = safe_div(fcf_ltm, rev_ltm)

            ev = inf.get("enterpriseValue")
            ev_fcf = safe_div(ev, fcf_ltm)

            hist = tk.history(period="5y")
            price_cagr = None
            if not hist.empty:
                price_cagr = (hist["Close"].iloc[-1] / hist["Close"].iloc[0])**(1/5) - 1

            # --- NUEVAS MÉTRICAS ---
            roic = calcular_roic(inc, bal)
            sbc = calcular_sbc(cf)
            net_debt = calcular_net_debt(bal)

            st.subheader(inf.get("longName"))

            # --- CORE ---
            st.markdown("### 📊 Core")
            st.write({
                "EV/FCF": round(ev_fcf, 2) if ev_fcf else None,
                "CAGR %": pct(cagr),
                "FCF Margin %": pct(fcf_margin)
            })

            # --- CALIDAD ---
            st.markdown("### 🧠 Calidad / Riesgo")
            st.write({
                "ROIC %": pct(roic),
                "SBC": sbc,
                "Net Debt": net_debt
            })

            # --- INPUTS ---
            st.markdown("### ⚙️ Modelo Forward")

            tipo = st.selectbox("Tipo empresa", ["Auto", "Físico", "Software"])

            backlog = st.number_input("Backlog (B USD)", value=0.0)
            conv = st.slider("Conversión backlog %", 50, 100, 85) / 100

            if tipo == "Auto":
                if fcf_margin and fcf_margin > 0.25:
                    tipo = "Software"
                else:
                    tipo = "Físico"

            # --- CÁLCULOS ---
            per = calcular_per(tipo, backlog, rev_ltm, cagr or 0, fcf_margin or 0, conv)

            fcf_fwd = fcf_ltm + per if fcf_ltm else None

            ev_fcf_fwd = safe_div(ev, fcf_fwd)

            # 🔥 FIX PEG
            peg = safe_div(ev_fcf_fwd, (cagr * 100)) if cagr else None

            # --- VALIDACIONES ---
            if peg and peg > 5:
                st.warning("⚠️ PEG extremo → revisar modelo o sobrevaloración")

            if fcf_margin and fcf_margin < 0:
                st.error("🚨 FCF negativo → modelo no válido")

            # --- OUTPUT ---
            st.markdown("### 📈 Modelo Forward")
            st.write({
                "PER_FCF": round(per, 2),
                "FCF Forward": round(fcf_fwd, 2) if fcf_fwd else None,
                "EV/FCF Forward": round(ev_fcf_fwd, 2) if ev_fcf_fwd else None,
                "PEG_FCF": round(peg, 2) if peg else None
            })

            # --- IA ---
            if st.button("🧠 Analizar"):
                if not client:
                    st.warning("⚠️ IA desactivada (sin API)")
                else:
                    prompt = f"""
                    ERES UN COMITÉ INSTITUCIONAL.

                    DATOS PROCESADOS:
                    EV/FCF: {ev_fcf}
                    EV/FCF Forward: {ev_fcf_fwd}
                    CAGR: {cagr}
                    ROIC: {roic}
                    SBC: {sbc}
                    Net Debt: {net_debt}
                    PEG: {peg}

                    REGLAS:
                    - NO recalcular
                    - SOLO interpretar
                    - evaluar si es value trap o compounder

                    OUTPUT:
                    IDENTIDAD
                    VALUACIÓN
                    RIESGO
                    VEREDICTO
                    SIZING
                    """

                    try:
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"Error IA: {e}")

    except Exception as e:
        st.error(f"Error general: {e}")
