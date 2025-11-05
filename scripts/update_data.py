import os
import json
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime, timedelta
import yfinance as yf
import requests

class RobustStockAnalyzer:
    def __init__(self):
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'META', 'AMZN', 'NFLX'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L', 'VOD.L', 'BARC.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS', 'SAF.PA', 'BMW.DE']
        }
        
        # User agents to rotate to avoid blocking
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]
    
    def get_stock_data_alternative(self, ticker):
        """Try alternative methods to get stock data"""
        try:
            print(f"📊 Attempting to fetch {ticker}...")
            
            # Method 1: Try yfinance with different parameters
            try:
                stock = yf.Ticker(ticker)
                # Try different period parameters
                for period in ["1mo", "2mo", "3mo", "6mo"]:
                    try:
                        hist = stock.history(period=period)
                        if len(hist) > 5:
                            print(f"  ✅ Success with period={period}")
                            return self.process_yfinance_data(ticker, hist)
                    except:
                        continue
            except Exception as e:
                print(f"  ❌ yfinance failed: {str(e)[:50]}")
            
            # Method 2: Try Alpha Vantage fallback (if API key available)
            alpha_data = self.try_alpha_vantage(ticker)
            if alpha_data:
                return alpha_data
                
            # Method 3: Use static sample data as last resort
            return self.generate_sample_data(ticker)
            
        except Exception as e:
            print(f"  ❌ All methods failed for {ticker}: {str(e)[:50]}")
            return self.generate_sample_data(ticker)
    
    def process_yfinance_data(self, ticker, hist):
        """Process successful yfinance data"""
        if len(hist) < 5:
            return None
            
        # Get the most recent valid data
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100
        
        current_volume = hist['Volume'].iloc[-1]
        avg_volume = hist['Volume'].tail(20).mean() if len(hist) >= 20 else current_volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Calculate confidence score
        confidence_score = self.calculate_confidence_score(price_change_pct, volume_ratio, hist)
        
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
            'catalyst': "Live market data analysis",
            'data_source': 'yfinance',
            'last_updated': datetime.now().isoformat()
        }
        
        print(f"  ✅ {ticker}: ${current_price:.2f} ({price_change_pct:+.2f}%) - Score: {confidence_score}/100")
        return stock_data
    
    def try_alpha_vantage(self, ticker):
        """Try Alpha Vantage as fallback"""
        alpha_key = os.getenv('ALPHA_VANTAGE_KEY', 'demo')
        if alpha_key == 'demo':
            return None
            
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={alpha_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if 'Global Quote' in data:
                quote = data['Global Quote']
                current_price = float(quote['05. price'])
                prev_close = float(quote['08. previous close'])
                price_change = current_price - prev_close
                price_change_pct = (price_change / prev_close) * 100
                volume = int(quote['06. volume'])
                
                confidence_score = self.calculate_confidence_score(price_change_pct, 1.0, None)
                
                return {
                    'ticker': ticker,
                    'current_price': round(current_price, 2),
                    'price_change': round(price_change, 2),
                    'price_change_percent': round(price_change_pct, 2),
                    'volume': volume,
                    'volume_ratio': 1.0,
                    'company_name': self.get_company_name(ticker),
                    'confidence_score': confidence_score,
                    'analysis': self.generate_analysis(confidence_score, price_change_pct, 1.0),
                    'catalyst': "Alpha Vantage API data",
                    'data_source': 'alphavantage',
                    'last_updated': datetime.now().isoformat()
                }
        except:
            pass
            
        return None
    
    def generate_sample_data(self, ticker):
        """Generate realistic sample data when APIs fail"""
        # Realistic price ranges for each stock
        price_ranges = {
            'AAPL': (150, 200), 'MSFT': (300, 400), 'TSLA': (150, 300), 
            'NVDA': (400, 800), 'GOOGL': (120, 150), 'META': (300, 400),
            'AMZN': (120, 180), 'NFLX': (500, 700), 'TSCO.L': (2.5, 3.5),
            'HSBA.L': (6, 8), 'LLOY.L': (0.4, 0.6), 'VOD.L': (0.6, 0.9),
            'BARC.L': (1.5, 2.0), 'AIR.PA': (120, 160), 'SIE.DE': (140, 180),
            'ASML.AS': (600, 800), 'SAF.PA': (180, 220), 'BMW.DE': (80, 110)
        }
        
        base_price = random.uniform(*price_ranges.get(ticker, (50, 100)))
        price_change_pct = random.uniform(-3, 5)
        price_change = base_price * (price_change_pct / 100)
        current_price = base_price + price_change
        
        volume_ratio = random.uniform(0.8, 2.5)
        confidence_score = random.randint(40, 85)
        
        stock_data = {
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'price_change': round(price_change, 2),
            'price_change_percent': round(price_change_pct, 2),
            'volume': random.randint(1000000, 50000000),
            'volume_ratio': round(volume_ratio, 2),
            'company_name': self.get_company_name(ticker),
            'confidence_score': confidence_score,
            'analysis': self.generate_analysis(confidence_score, price_change_pct, volume_ratio),
            'catalyst': "Sample data - API limited",
            'data_source': 'sample',
            'last_updated': datetime.now().isoformat()
        }
        
        print(f"  📝 {ticker}: ${current_price:.2f} ({price_change_pct:+.2f}%) - Score: {confidence_score}/100 [SAMPLE]")
        return stock_data
    
    def calculate_confidence_score(self, price_change_pct, volume_ratio, hist_data):
        """Calculate confidence score based on available data"""
        score = 50
        
        # Price momentum
        if price_change_pct > 3:
            score += 20
        elif price_change_pct > 1:
            score += 12
        elif price_change_pct > 0:
            score += 6
        elif price_change_pct < -2:
            score -= 10
        
        # Volume confirmation
        if volume_ratio > 2.0:
            score += 15
        elif volume_ratio > 1.5:
            score += 10
        elif volume_ratio > 1.2:
            score += 5
        elif volume_ratio < 0.8:
            score -= 5
        
        return min(max(score, 0), 100)
    
    def get_company_name(self, ticker):
        """Get company names"""
        name_map = {
            'AAPL': 'Apple Inc.', 'MSFT': 'Microsoft Corporation', 
            'TSLA': 'Tesla Inc.', 'NVDA': 'NVIDIA Corporation',
            'GOOGL': 'Alphabet Inc.', 'META': 'Meta Platforms Inc.',
            'AMZN': 'Amazon.com Inc.', 'NFLX': 'Netflix Inc.',
            'TSCO.L': 'Tesco PLC', 'HSBA.L': 'HSBC Holdings PLC',
            'LLOY.L': 'Lloyds Banking Group', 'VOD.L': 'Vodafone Group PLC',
            'BARC.L': 'Barclays PLC', 'AIR.PA': 'Airbus SE',
            'SIE.DE': 'Siemens AG', 'ASML.AS': 'ASML Holding NV',
            'SAF.PA': 'Safran SA', 'BMW.DE': 'BMW AG'
        }
        return name_map.get(ticker, ticker)
    
    def generate_analysis(self, score, price_change_pct, volume_ratio):
        """Generate analysis text"""
        if score >= 75:
            base = "🚀 Strong bullish momentum"
        elif score >= 60:
            base = "📈 Positive trend developing"
        elif score >= 45:
            base = "⚡ Watch for confirmation"
        else:
            base = "🔄 Needs stronger signals"
        
        if price_change_pct > 2:
            trend = "with significant price movement"
        elif price_change_pct > 0:
            trend = "with positive price action"
        else:
            trend = "consolidating at current levels"
        
        if volume_ratio > 1.5:
            volume = "on high volume"
        elif volume_ratio > 1.0:
            volume = "on average volume"
        else:
            volume = "volume below average"
        
        return f"{base} {trend} {volume}"
    
    def update_all_stocks(self):
        """Update all stocks with robust error handling"""
        print("🚀 Starting robust stock analysis...")
        print("💡 Using multiple data sources with fallbacks")
        
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            print(f"\n🌍 Analyzing {region} stocks:")
            for i, ticker in enumerate(tickers):
                stock_data = self.get_stock_data_alternative(ticker)
                if stock_data:
                    stock_data['region'] = region
                    all_stocks.append(stock_data)
                
                # Random delay to avoid detection
                if i < len(tickers) - 1:
                    delay = random.uniform(2, 5)
                    print(f"    ⏳ Waiting {delay:.1f} seconds...")
                    time.sleep(delay)
        
        # Sort by confidence score
        all_stocks.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Count data sources
        sources = {}
        for stock in all_stocks:
            source = stock.get('data_source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        # Save results
        output = {
            'last_updated': datetime.now().isoformat(),
            'total_stocks_analyzed': len(all_stocks),
            'data_sources': sources,
            'stocks': all_stocks
        }
        
        os.makedirs('data/processed', exist_ok=True)
        output_path = 'data/processed/latest_stocks.json'
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"\n🎉 SUCCESS: Analyzed {len(all_stocks)} stocks")
        print(f"📊 Data sources: {sources}")
        print(f"💾 Data saved to: {output_path}")
        
        if all_stocks:
            print(f"\n🏆 Top stocks by confidence:")
            for i, stock in enumerate(all_stocks[:8]):
                source = stock.get('data_source', 'unknown')
                print(f"   {i+1}. {stock['ticker']}: {stock['confidence_score']}/100 [{source}]")
        
        return all_stocks

if __name__ == "__main__":
    analyzer = RobustStockAnalyzer()
    analyzer.update_all_stocks()
