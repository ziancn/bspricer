import math
import streamlit as st
from scipy.stats import norm
import numpy as np
import yfinance as yf
import logging
import time
from functools import wraps



logging.basicConfig(level=logging.INFO)



# Retry decorator - handle rate limiting and temporary errors
def retry_with_backoff(max_retries=3, backoff_factor=1.5):
    """Retry decorator with exponential backoff to handle Yahoo Finance rate limiting"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logging.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}. Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"All retries failed: {str(e)[:100]}")
                        raise
        return wrapper
    return decorator



def black_scholes(S, K, T, r, sigma, option_type="call"):
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        return None
    


@retry_with_backoff(max_retries=3, backoff_factor=1.5)
def calc_hist_vol(ticker, period):
    """Calculate historical volatility with retry mechanism
    
    Args:
        ticker: Stock ticker symbol
        period: Time period ('1mo', '3mo', '6mo', etc.)
    
    Returns:
        float: Annualized volatility
        
    Raises:
        ValueError: When unable to fetch or calculate volatility
    """
    try:
        # Use progress=False to avoid cluttering output
        data = yf.download(ticker, period=period, progress=False)['Close']
        
        if data is None or len(data) < 2:
            raise ValueError(f"Unable to fetch valid historical data for {ticker}")
        
        log_returns = np.log(data / data.shift(1)).dropna()
        
        if len(log_returns) == 0:
            raise ValueError(f"Unable to calculate log returns for {ticker}")
        
        hist_vol = log_returns.std() * np.sqrt(252)  # Annualize
        # Convert to scalar if Series
        hist_vol = hist_vol.iloc[0] if hasattr(hist_vol, 'iloc') else float(hist_vol)
        
        if hist_vol <= 0 or np.isnan(hist_vol):
            raise ValueError(f"Calculated volatility is invalid: {hist_vol}")
        
        return hist_vol
    except Exception as e:
        logging.error(f"calc_hist_vol failed - {ticker} ({period}): {str(e)}")
        raise



@st.cache_data(ttl=86400)
@retry_with_backoff(max_retries=3, backoff_factor=1.5)
def get_risk_free_rate():
    """Fetch risk-free rate with retry mechanism, returns default value on failure
    
    Uses ^IRX (3-Month Treasury Bill) as a proxy for the risk-free rate
    
    Returns:
        float: Risk-free rate in decimal form (e.g., 0.05 represents 5%)
    """
    try:
        ticker = yf.Ticker('^IRX')
        time.sleep(0.5)  # Avoid rate limiting, request interval
        risk_free_rate = ticker.fast_info.get('lastPrice', None)
        logging.info(f'^IRX data: {risk_free_rate}')
        
        if risk_free_rate and risk_free_rate > 0:
            result = risk_free_rate / 100
            logging.info(f"Successfully fetched risk-free rate: {result:.4f}")
            return result
        else:
            logging.warning("Unable to fetch ^IRX price, using default risk-free rate 0.02")
            return 0.02
    except Exception as e:
        logging.error(f"Failed to fetch risk-free rate: {str(e)[:100]}, using default value 0.02")
        return 0.02