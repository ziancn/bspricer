import time
import logging

import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

from utils import black_scholes, calc_hist_vol, get_risk_free_rate

logging.basicConfig(level=logging.INFO)



# Page configuration
st.set_page_config(
    page_title='Naïve Option Pricer',
    page_icon='🧸',
    layout='wide',
)



#  Zian Chen LinkedIn link
profile_url = 'https://www.linkedin.com/in/zian-zayn-chen'
icon_url = 'https://cdn-icons-png.flaticon.com/512/174/174857.png'
st.sidebar.markdown(f'<a href="{profile_url}" target="_blank" style="text-decoration: none; color: inherit;"><img src="{icon_url}" width="16" height="16" style="vertical-align: middle; margin-right: 10px;">`Zian (Zayn) Chen`</a>', unsafe_allow_html=True)



# SIDEBAR #
st.sidebar.title('Naïve Option Pricer')

use_real_data = st.sidebar.checkbox('Use real data (Yahoo Finance)', value=True)

ticker = st.sidebar.text_input('Ticker', value='NVDA', disabled=False if use_real_data else True)

if use_real_data:
    if ticker:
        try:
            with st.spinner(f'Fetching data for {ticker} from Yahoo Finance...'):
                stock = yf.Ticker(ticker)
                time.sleep(0.5)  # Avoid rate limiting
                stock_info = stock.info
                
                if 'currentPrice' not in stock_info or stock_info['currentPrice'] is None:
                    st.error(f"Unable to fetch current price for {ticker}. Possible reasons:\n- Yahoo Finance rate limiting\n- Invalid ticker symbol\n\nPlease try again later or use manual price input.")
                    use_real_data = False
                    last_px = 100
                else:
                    last_px = stock_info['currentPrice']
                    st.success(f"✓ Successfully fetched data for {ticker}")
            
            # Fetch risk-free rate (with caching and error handling)
            try:
                risk_free_rate = get_risk_free_rate()
            except Exception as e:
                logging.warning(f"Failed to fetch risk-free rate, using default value: {str(e)[:100]}")
                risk_free_rate = 0.02
        except Exception as e:
            st.error(f"Failed to fetch data for {ticker}\n\nError: {str(e)[:150]}\n\nPlease check the ticker symbol or try again later")
            use_real_data = False
            last_px = 100
            risk_free_rate = 0.02
    else:
        use_real_data = False
        last_px = 100
        risk_free_rate = 0.02
else:
    last_px = 100
    risk_free_rate = 0.02

spot_px = st.sidebar.number_input('Spot Ref', value=last_px if use_real_data else 100)

# Strike Price
k_col1, k_col2 = st.sidebar.columns([2,3])
with k_col1:
    strike_input_method = st.selectbox('Strike', ('Price', 'Percent'))
with k_col2:
    if strike_input_method == 'Price':
        strike_px = st.number_input('Strike Price', value=spot_px)
    else:
        strike_pct = st.number_input('% of Spot', value=100.0)
        strike_px = (spot_px * strike_pct) / 100

# Maturity
days_to_maturity = st.sidebar.number_input('Time to maturity (Days)', value=30, min_value=1)
t = days_to_maturity / 365  # Convert days to years for Black-Scholes calculation

# Risk free rate
rfr = st.sidebar.number_input('Risk free rate', value=risk_free_rate if use_real_data else 0.04, format="%.4f")

# Volatility
v_col1, v_col2 = st.sidebar.columns([2,3])
with v_col1:
    vol_type = st.selectbox('Vol Type', ['Hist 6mo', 'Hist 3mo', 'Hist 1mo'], disabled=False if use_real_data else True)
    period = vol_type.split()[-1]

vol_value = 0.2  # Default volatility

if use_real_data and ticker:
    try:
        with st.spinner(f'Calculating historical volatility for {ticker}...'):
            vol_value = calc_hist_vol(ticker, period)
            st.success(f"✓ Successfully calculated volatility: {vol_value:.2%}")
    except ValueError as ve:
        st.warning(f"Unable to calculate volatility: {str(ve)}\n\nUsing default value 20%")
        logging.warning(f"Failed to calculate volatility - {ticker} ({period}): {str(ve)}")
        vol_value = 0.2
    except Exception as e:
        st.error(f"Failed to fetch volatility data\n\nError: {str(e)[:150]}\n\nUsing default value 20%")
        logging.error(f"Exception fetching volatility - {ticker} ({period}): {str(e)}")
        vol_value = 0.2
else:
    vol_value = 0.2

with v_col2:
    vol = st.number_input('Vol', value=vol_value, disabled=True if use_real_data else False)

# If not using real data, allow manual `vol` input to override `vol_value` used in pricing
if not use_real_data:
    try:
        vol_value = float(vol)
    except Exception:
        logging.warning("Invalid manual volatility input; falling back to default 0.2")
        vol_value = 0.2



# Main Page

call_px = black_scholes(
    S=spot_px,
    K=strike_px,
    T=t,
    sigma=vol_value,
    r=rfr,
    option_type='call')

put_px = black_scholes(
    S=spot_px,
    K=strike_px,
    T=t,
    sigma=vol_value,
    r=rfr,
    option_type='put')

if use_real_data and ticker:
    try:
        with st.spinner(f'Loading 1-year historical data for {ticker}...'):
            time.sleep(0.5)  # Avoid rate limiting
            stock_data = yf.Ticker(ticker).history(period="1y")
            
            if stock_data is None or len(stock_data) == 0:
                st.error(f"Unable to fetch historical data for {ticker}")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data["Close"], mode="lines", name="Close Price"))
                fig.update_layout(
                    title=f'{ticker} - 1Y',
                    template="plotly_dark")
                st.plotly_chart(fig, width='stretch')
    except Exception as e:
        error_msg = str(e)[:150]
        st.error(f"Failed to fetch historical data\n\nError: {error_msg}\n\nPossible cause: Yahoo Finance rate limiting or network issue")
        logging.error(f"Exception fetching historical chart - {ticker}: {str(e)}")

st.markdown(f"""
    <style>
    .card-container {{
        display: flex;
        gap: 1rem;
        withth: 100%;
        margin: 0;
    }}
    .card {{
        flex-grow: 1;               
        min-width: 150px;    
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.2);
        text-align: center;
        font-size: 1rem;
        font-weight: bold;
    }}
    .call-card {{
        background-color: #b8f1b0;
        color: #006400;
    }}
    .put-card {{
        background-color: #f1b0b0;
        color: #8b0000;
    }}
    </style>
    
    <div style="display: flex; gap: 1rem; justify-content: center;">
        <div class="card call-card">
            CALL<br>
            Per unit: ${call_px:.2f} <br>
            Percentage: {call_px/spot_px*100:.2f}%
        </div>
        <div class="card put-card">
            PUT<br>
            Per unit: ${put_px:.2f} <br>
            Percentage: {put_px/spot_px*100:.2f}%
        </div>
    </div>
""", unsafe_allow_html=True)