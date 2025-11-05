import os
import json
import pandas as pd
from datetime import datetime
import yfinance as yf
import requests

# Get keys from GitHub Secrets (environment variables)
FMP_API_KEY = os.getenv('FMP_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

class StockUpdater:
    def __init__(self):
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'META', 'AMD', 'AMZN'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L', 'VOD.L', 'BARC.L', 'BP.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS', 'SAF.PA', 'BMW.DE', 'DB1.DE']
        }
    
    def get_yahoo_data(self, ticker):
        """Get stock data from Yahoo Finance (no API key needed)"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="2d")
            
            if len(hist) < 2:
                return None
                
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            return {
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_pct, 2),
                'volume': int(hist['Volume'].iloc[-1]),
                'company_name': info.get('longName', ticker)
            }
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    def calculate_confidence_score(self, stock_data):
        """Calculate a confidence score based on multiple factors"""
        score = 50  # Base score
        
        # Price momentum (up to 20 points)
        if stock_data['price_change_percent'] > 2:
            score += 15
        elif stock_data['price_change_percent'] > 1:
            score += 10
        elif stock_data['price_change_percent'] > 0:
            score += 5
            
        # Volume spike (up to 15 points)
        # Note: You'd need historical volume data for this
        # For now, we'll use a simple approach
        if stock_data.get('volume', 0) > 1000000:  # Arbitrary threshold
            score += 10
            
        # Add more factors here based on your research
        # - RSI values
        # - Moving average crossovers  
        # - News sentiment (using NewsAPI)
        # - Analyst ratings (using FMP API)
        
        return min(max(score, 0), 100)  # Ensure score between 0-100
    
    def get_analysis_comment(self, score, stock_data):
        """Generate analysis based on score and data"""
        if score >= 70:
            return "Strong momentum with positive technical indicators. High conviction setup."
        elif score >= 50:
            return "Moderate momentum showing potential. Monitor for confirmation."
        else:
            return "Needs more confirmation. Watch for volume increase and breakout."
    
    def update_all_stocks(self):
        """Update data for all stocks in watchlist"""
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            for ticker in tickers:
                print(f"Fetching data for {ticker}...")
                stock_data = self.get_yahoo_data(ticker)
                
                if stock_data:
                    # Add region and analysis
                    stock_data['region'] = region
                    stock_data['confidence_score'] = self.calculate_confidence_score(stock_data)
                    stock_data['analysis'] = self.get_analysis_comment(
                        stock_data['confidence_score'], stock_data
                    )
                    stock_data['catalyst'] = "Technical momentum and volume analysis"
                    
                    all_stocks.append(stock_data)
        
        # Save to JSON file
        output = {
            'last_updated': datetime.now().isoformat(),
            'stocks': all_stocks
        }
        
        os.makedirs('data/processed', exist_ok=True)
        with open('data/processed/latest_stocks.json', 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"Updated {len(all_stocks)} stocks")
        return all_stocks

if __name__ == "__main__":
    updater = StockUpdater()
    updater.update_all_stocks()
