import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from google import genai

# --- CONFIG ---
st.set_page_config(page_title="Alpha Boardroom V8 Institucional", layout="wide")

# --- API KEYS ---
st.sidebar.title("🔑 APIs")
GEMINI_API_KEY = st.sidebar.text_input("Gemini API Key", type="password")
FMP_API_KEY = st.sidebar.text_input("FMP API Key", type="password")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- UTILS ---
def safe_div(a, b):
    try:
        if a is None or b in [0, None]:
            return None
        return a / b
    except:
        return None

def pct(x):
    return round(x * 100, 2) if x is not None else None

# --- FMP ---
def get_fmp_data(ticker):
    if not FMP_API_KEY:
        return {}
    try:
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}?apikey={FMP_API_KEY}"
        r = requests.get(url).json()
        return r[0] if r else {}
    except:
        return {}

# --- CLASIFICACIÓN ---
def clasificar_empresa(tipo):
    return tipo

# --- DETECTORES ---
def detectar_reinversion(capex_ratio):
    return capex_ratio is not None and capex_ratio > 0.08

def normalizar_roic(roic):
    if roic and roic > 0.5:
        return None
    return roic

def calcular_peg(pe, growth):
    if pe and growth and growth > 0:
        return pe / (growth * 100)
    return None

# --- BACKLOG ---
def calcular_backlog(tipo, backlog_usd, conversion, fcf_margin):
    if tipo in ["Software", "Plataforma"]:
        return backlog_usd * (conversion / 100)
    else:
        if fcf_margin:
            return backlog_usd * (conversion / 100) * fcf_margin
    return 0

# --- SCORE INTELIGENTE ---
def calcular_score(data, tipo, reinvierte):
    score = 0

    # Calidad
    if data["FCF_Margin"] and data["FCF_Margin"] > 0.25:
        score += 2
    if data["ROIC"] and data["ROIC"] > 0.15:
        score += 2

    # Valuación base
    if data["EV_FCF"] and data["EV_FCF"] < 30:
        score += 2

    # PEG solo en software/plataforma
    if tipo in ["Software", "Plataforma"]:
        if data["PEG"] and data["PEG"] < 2:
            score += 2

    # FCF Yield contextual
    if tipo in ["Cíclica", "Industrial"]:
        if data["FCF_Yield"] and data["FCF_Yield"] > 0.05:
            score += 2
    else:
        if data["FCF_Yield"] and data["FCF_Yield"] > 0.025:
            score += 2

    # Bonus reinversión
    if reinvierte:
        score += 1

    return score

def señal(score):
    if score >= 8:
        return "🟢 BUY"
    elif score >= 5:
        return "🟡 HOLD"
    else:
        return "🔴 SELL"

# --- IA ---
def analizar_ia(data, tipo):
    if not client:
        return "⚠️ IA desactivada"

    prompt = f"""
    Eres comité institucional.

    Tipo empresa: {tipo}

    DATA:
    {data}

    IMPORTANTE:
    - Ajusta análisis según tipo de empresa
    - No uses PEG si es cíclica/industrial
    - Considera reinversión si CapEx alto

    Evalúa:
    - Calidad real
    - Valuación contextual
    - Riesgos reales (no genéricos)
    - Veredicto profesional

    """

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    ).text

# --- UI ---
st.title("🔬 Alpha Boardroom V8 - Institucional")

ticker = st.text_input("Ticker").upper()

if ticker:

    tk = yf.Ticker(ticker)
    fmp = get_fmp_data(ticker)

    try:
        info = tk.info
        inc = tk.financials
        cf = tk.cashflow
        bs = tk.balance_sheet

        if inc.empty or cf.empty:
            st.error("❌ Datos insuficientes")
        else:
            rev = inc.loc['Total Revenue'].dropna()[::-1]
            fcf = cf.loc['Free Cash Flow'].dropna()[::-1]

            rev_ltm = rev.iloc[-1]
            fcf_ltm = fcf.iloc[-1]

            ev = info.get("enterpriseValue")
            market_cap = info.get("marketCap")

            # --- CORE ---
            ev_fcf = safe_div(ev, fcf_ltm)
            fcf_margin = safe_div(fcf_ltm, rev_ltm)

            # CAGR ingresos
            cagr = None
            if len(rev) > 1:
                cagr = (rev.iloc[-1] / rev.iloc[0])**(1/(len(rev)-1)) - 1

            fcf_yield = safe_div(fcf_ltm, market_cap)

            capex = abs(cf.loc['Capital Expenditure'].dropna().iloc[-1]) if 'Capital Expenditure' in cf.index else None
            capex_ratio = safe_div(capex, rev_ltm)

            # ROIC simplificado
            equity = None
            for key in ["Total Stockholder Equity", "Total Equity Gross Minority Interest"]:
                if key in bs.index:
                    equity = bs.loc[key].dropna().iloc[0]
                    break

            roic = safe_div(fcf_ltm, equity) if equity else None
            roic = normalizar_roic(roic)

            # PEG real aproximado
            pe = info.get("trailingPE")
            peg = calcular_peg(pe, cagr)

            # --- INPUT MODELO ---
            st.subheader("⚙️ Modelo Forward")

            tipo = st.selectbox("Tipo empresa", [
                "Software", "Plataforma", "Industrial", "Defensa", "Cíclica"
            ])

            backlog = st.number_input("Backlog (Billions USD)", value=0.0)
            conversion = st.slider("Conversión %", 0, 100, 50)

            backlog_usd = backlog * 1e9
            backlog_fcf = calcular_backlog(tipo, backlog_usd, conversion, fcf_margin)

            fcf_forward = fcf_ltm + backlog_fcf
            ev_fcf_forward = safe_div(ev, fcf_forward)

            reinvierte = detectar_reinversion(capex_ratio)

            # --- DATA ---
            data = {
                "EV_FCF": ev_fcf,
                "FCF_Margin": fcf_margin,
                "ROIC": roic,
                "PEG": peg,
                "FCF_Yield": fcf_yield
            }

            # --- SCORE ---
            score = calcular_score(data, tipo, reinvierte)
            sig = señal(score)

            # --- DISPLAY ---
            st.subheader(info.get("longName"))

            st.write("📊 Core")
            st.json({
                "EV/FCF": round(ev_fcf,2) if ev_fcf else None,
                "CAGR %": pct(cagr),
                "FCF Margin %": pct(fcf_margin),
                "PE": pe
            })

            st.write("🧠 Calidad")
            st.json({
                "ROIC %": pct(roic),
                "CapEx %": pct(capex_ratio),
                "FCF Yield %": pct(fcf_yield),
                "Reinvierte": reinvierte
            })

            st.write("📈 Forward")
            st.json({
                "FCF Forward": int(fcf_forward),
                "EV/FCF Forward": round(ev_fcf_forward,2) if ev_fcf_forward else None,
                "PEG": round(peg,2) if peg else None
            })

            st.write("🎯 Score")
            st.metric("Score", f"{score}/10")
            st.metric("Señal", sig)

            if st.button("Analizar IA"):
                res = analizar_ia(data, tipo)
                st.markdown(res)

    except Exception as e:
        st.error(f"Error: {e}")
