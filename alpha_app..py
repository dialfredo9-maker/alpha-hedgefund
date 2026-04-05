import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V8", layout="wide")

# --- API ---
st.sidebar.markdown("### 🔑 API Gemini")
API_KEY = st.sidebar.text_input("API KEY", type="password")

client = genai.Client(api_key=API_KEY) if API_KEY else None

# --- UTIL ---
def safe_div(n, d):
    try:
        if not n or not d or d == 0:
            return None
        return n/d
    except:
        return None

def pct(x):
    return None if x is None else round(x*100,2)

# --- SCRAPING SIMPLE BACKLOG ---
def scrap_backlog_simple(ticker):
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            if "backlog" in r.text.lower():
                return "Detectado (revisar manual)"
    except:
        pass
    return None

# --- ROIC ---
def calcular_roic(income, balance):
    try:
        ebit = income.loc['EBIT'].dropna()[0]
        debt = balance.loc['Total Debt'].dropna()[0]
        equity = balance.loc['Total Stockholder Equity'].dropna()[0]
        capital = debt + equity
        return safe_div(ebit, capital)
    except:
        return None

# --- SBC ---
def calcular_sbc(cf):
    try:
        return cf.loc['Stock Based Compensation'].dropna()[0]
    except:
        return None

# --- NET DEBT ---
def calcular_net_debt(balance):
    try:
        debt = balance.loc['Total Debt'].dropna()[0]
        cash = balance.loc['Cash And Cash Equivalents'].dropna()[0]
        return debt - cash
    except:
        return None

# --- PER ---
def calcular_per(tipo, backlog, revenue, cagr, margin, conv):
    if tipo == "Físico":
        return backlog * conv * margin
    elif tipo == "Software":
        return revenue * (1+cagr) * margin
    return 0

# --- UI ---
st.title("🔬 Alpha Boardroom V8")

ticker = st.text_input("Ticker").upper()

if ticker:
    tk = yf.Ticker(ticker)

    try:
        inf = tk.info
        inc = tk.financials
        cf = tk.cashflow
        bal = tk.balance_sheet

        if inc.empty or cf.empty:
            st.error("Datos incompletos")
        else:
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            cagr = (rev.iloc[-1]/rev.iloc[0])**(1/(len(rev)-1))-1 if len(rev)>1 else None

            fcf_ltm = fcf.iloc[-1]
            rev_ltm = rev.iloc[-1]

            fcf_margin = safe_div(fcf_ltm, rev_ltm)
            ev = inf.get("enterpriseValue")
            ev_fcf = safe_div(ev, fcf_ltm)

            hist = tk.history(period="5y")
            price_cagr = None
            if not hist.empty:
                price_cagr = (hist["Close"].iloc[-1]/hist["Close"].iloc[0])**(1/5)-1

            # --- NUEVAS MÉTRICAS ---
            roic = calcular_roic(inc, bal)
            sbc = calcular_sbc(cf)
            net_debt = calcular_net_debt(bal)

            st.subheader(inf.get("longName"))

            st.markdown("### 📊 Core")
            st.write({
                "EV/FCF": round(ev_fcf,2) if ev_fcf else None,
                "CAGR": pct(cagr),
                "FCF Margin": pct(fcf_margin)
            })

            st.markdown("### 🧠 Calidad / Riesgo")
            st.write({
                "ROIC": pct(roic),
                "SBC": sbc,
                "Net Debt": net_debt
            })

            # --- SCRAPING BACKLOG ---
            backlog_hint = scrap_backlog_simple(ticker)
            if backlog_hint:
                st.info(f"🔎 Backlog detectado: {backlog_hint}")

            # --- INPUTS ---
            tipo = st.selectbox("Tipo", ["Auto","Físico","Software"])
            backlog = st.number_input("Backlog (B USD)", value=0.0)
            conv = st.slider("Conversión %", 50,100,85)/100

            if tipo == "Auto":
                tipo = "Software" if fcf_margin and fcf_margin>0.25 else "Físico"

            # --- CALC ---
            per = calcular_per(tipo, backlog, rev_ltm, cagr or 0, fcf_margin or 0, conv)
            fcf_fwd = fcf_ltm + per
            ev_fcf_fwd = safe_div(ev, fcf_fwd)
            peg = safe_div(ev_fcf_fwd, cagr)

            st.markdown("### 📈 Modelo Forward")
            st.write({
                "PER_FCF": round(per,2),
                "EV/FCF Forward": round(ev_fcf_fwd,2) if ev_fcf_fwd else None,
                "PEG_FCF": round(peg,2) if peg else None
            })

            # --- IA ---
            if st.button("Analizar"):
                if not client:
                    st.warning("Sin API")
                else:
                    prompt = f"""
                    DATOS:
                    EV/FCF: {ev_fcf}
                    EV/FCF Forward: {ev_fcf_fwd}
                    CAGR: {cagr}
                    ROIC: {roic}
                    SBC: {sbc}
                    Net Debt: {net_debt}
                    PEG: {peg}

                    Analiza como fondo institucional.
                    """

                    try:
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.write(res.text)
                    except Exception as e:
                        st.error(e)

    except Exception as e:
        st.error(e)
