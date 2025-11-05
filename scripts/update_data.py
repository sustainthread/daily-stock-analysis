import os
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime
import yfinance as yf

class AdvancedStockAnalyzer:
    def __init__(self):
        # Reduced watchlist for testing
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS']
        }
    
    def get_stock_data_safe(self, ticker):
        """Get stock data with error handling and rate limiting"""
        try:
            print(f"📊 Fetching {ticker}...")
            stock = yf.Ticker(ticker)
            
            # Get only price data (avoid detailed info that causes rate limits)
            hist = stock.history(period="1mo")
            
            if len(hist) < 5:
                print(f"  ❌ Not enough data for {ticker}")
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            # Calculate basic metrics
            current_volume = hist['Volume'].iloc[-1]
            avg_volume = hist['Volume'].tail(20).mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Simple confidence scoring
            confidence_score = 50
            
            # Price momentum (up to 30 points)
            if price_change_pct > 3:
                confidence_score += 25
            elif price_change_pct > 1:
                confidence_score += 15
            elif price_change_pct > 0:
                confidence_score += 8
            
            # Volume confirmation (up to 20 points)
            if volume_ratio > 2.0:
                confidence_score += 18
            elif volume_ratio > 1.5:
                confidence_score += 12
            elif volume_ratio > 1.2:
                confidence_score += 7
            
            # Trend strength (up to 10 points)
            if len(hist) >= 10:
                sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
                if current_price > sma_20:
                    confidence_score += 8
            
            confidence_score = min(max(confidence_score, 0), 100)
            
            stock_data = {
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_pct, 2),
                'volume': int(current_volume),
                'volume_ratio': round(volume_ratio, 2),
                'company_name': self.get_company_name(ticker),
                'confidence_score': confidence_score,
                'analysis': self.generate_analysis(confidence_score, price_change_pct, volume_ratio),
                'catalyst': "Price momentum and volume analysis"
            }
            
            print(f"  ✅ {ticker}: ${current_price:.2f} ({price_change_pct:+.2f}%) - Score: {confidence_score}/100")
            return stock_data
            
        except Exception as e:
            print(f"  ❌ Error with {ticker}: {str(e)[:100]}...")
            return None
    
    def get_company_name(self, ticker):
        """Get company name from a predefined mapping to avoid API calls"""
        name_map = {
            'AAPL': 'Apple Inc.',
            'MSFT': 'Microsoft Corporation',
            'TSLA': 'Tesla Inc.',
            'NVDA': 'NVIDIA Corporation',
            'GOOGL': 'Alphabet Inc.',
            'TSCO.L': 'Tesco PLC',
            'HSBA.L': 'HSBC Holdings',
            'LLOY.L': 'Lloyds Banking Group',
            'AIR.PA': 'Airbus SE',
            'SIE.DE': 'Siemens AG',
            'ASML.AS': 'ASML Holding NV'
        }
        return name_map.get(ticker, ticker)
    
    def generate_analysis(self, score, price_change_pct, volume_ratio):
        """Generate analysis based on metrics"""
        analysis_parts = []
        
        if score >= 75:
            analysis_parts.append("🚀 Strong bullish momentum")
        elif score >= 60:
            analysis_parts.append("📈 Positive trend developing")
        elif score >= 45:
            analysis_parts.append("⚡ Watch for confirmation")
        else:
            analysis_parts.append("🔄 Needs stronger signals")
        
        if price_change_pct > 2:
            analysis_parts.append("with significant price movement")
        elif price_change_pct > 0:
            analysis_parts.append("with positive price action")
        
        if volume_ratio > 1.5:
            analysis_parts.append("on high volume")
        elif volume_ratio > 1.0:
            analysis_parts.append("on average volume")
        
        return " ".join(analysis_parts)
    
    def update_all_stocks(self):
        """Update data for all stocks with rate limiting"""
        print("🚀 Starting stock analysis with rate limiting...")
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            print(f"\n🌍 Analyzing {region} stocks:")
            for i, ticker in enumerate(tickers):
                stock_data = self.get_stock_data_safe(ticker)
                if stock_data:
                    stock_data['region'] = region
                    all_stocks.append(stock_data)
                
                # Add delay between requests to avoid rate limiting
                if i < len(tickers) - 1:  # Don't delay after the last stock
                    print(f"    ⏳ Waiting 2 seconds...")
                    time.sleep(2)
        
        # Sort by confidence score (highest first)
        all_stocks.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Save results
        output = {
            'last_updated': datetime.now().isoformat(),
            'total_stocks_analyzed': len(all_stocks),
            'stocks': all_stocks
        }
        
        os.makedirs('data/processed', exist_ok=True)
        output_path = 'data/processed/latest_stocks.json'
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"\n🎉 SUCCESS: Analyzed {len(all_stocks)} stocks")
        print(f"💾 Data saved to: {output_path}")
        
        # Show top 5 stocks
        if all_stocks:
            print(f"\n🏆 Top 5 stocks by confidence:")
            for i, stock in enumerate(all_stocks[:5]):
                print(f"   {i+1}. {stock['ticker']}: {stock['confidence_score']}/100")
        
        return all_stocks

if __name__ == "__main__":
    analyzer = AdvancedStockAnalyzer()
    analyzer.update_all_stocks()
