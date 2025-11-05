import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf

class StockAnalyzer:
    def __init__(self):
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'META', 'AMD', 'AMZN', 'NFLX'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L', 'VOD.L', 'BARC.L', 'BP.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS', 'SAF.PA', 'BMW.DE', 'DB1.DE']
        }
    
    def calculate_sma(self, data, window):
        """Simple Moving Average"""
        return data.rolling(window=window).mean()
    
    def calculate_rsi(self, data, window=14):
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_confidence(self, hist_data, current_price):
        """Calculate confidence score using basic technical analysis"""
        if len(hist_data) < 20:
            return 50
        
        closes = hist_data['Close']
        volumes = hist_data['Volume']
        
        score = 50  # Base score
        
        # 1. Price vs Moving Averages (25 points)
        sma_20 = self.calculate_sma(closes, 20).iloc[-1]
        sma_50 = self.calculate_sma(closes, 50).iloc[-1]
        
        if current_price > sma_20:
            score += 10
        if current_price > sma_50:
            score += 10
        if sma_20 > sma_50:
            score += 5
        
        # 2. RSI Momentum (25 points)
        try:
            rsi = self.calculate_rsi(closes).iloc[-1]
            if 40 < rsi < 70:  # Healthy RSI range
                score += 15
            elif 30 < rsi < 80:  # Acceptable range
                score += 8
        except:
            pass
        
        # 3. Volume Analysis (20 points)
        current_volume = volumes.iloc[-1]
        avg_volume = volumes.tail(20).mean()
        
        if current_volume > avg_volume * 1.5:
            score += 15
        elif current_volume > avg_volume:
            score += 8
        
        # 4. Recent Performance (15 points)
        price_5d_ago = closes.iloc[-5] if len(closes) >= 5 else closes.iloc[0]
        performance_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
        
        if performance_5d > 5:
            score += 10
        elif performance_5d > 0:
            score += 5
        
        # 5. Volatility (15 points) - lower is better
        volatility = closes.pct_change().std() * np.sqrt(252)  # Annualized
        if volatility < 0.3:
            score += 10
        elif volatility < 0.5:
            score += 5
        
        return min(max(score, 0), 100)
    
    def generate_analysis(self, score, price_change_pct, volume_ratio):
        """Generate analysis based on metrics"""
        analysis_parts = []
        
        if score >= 70:
            analysis_parts.append("🚀 Strong bullish setup")
        elif score >= 50:
            analysis_parts.append("📈 Positive momentum")
        else:
            analysis_parts.append("⚡ Needs confirmation")
        
        if price_change_pct > 2:
            analysis_parts.append("with strong price momentum")
        elif price_change_pct > 0:
            analysis_parts.append("with positive price action")
        else:
            analysis_parts.append("watching for reversal")
        
        if volume_ratio > 1.5:
            analysis_parts.append("on high volume")
        elif volume_ratio > 1.0:
            analysis_parts.append("on average volume")
        else:
            analysis_parts.append("volume below average")
        
        return " ".join(analysis_parts)
    
    def get_stock_data(self, ticker):
        """Get stock data and analysis"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get historical data
            hist = stock.history(period="2mo")
            
            if len(hist) < 5:
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            # Calculate metrics
            current_volume = hist['Volume'].iloc[-1]
            avg_volume = hist['Volume'].tail(20).mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            confidence_score = self.calculate_confidence(hist, current_price)
            analysis = self.generate_analysis(confidence_score, price_change_pct, volume_ratio)
            
            return {
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_pct, 2),
                'volume': int(current_volume),
                'volume_ratio': round(volume_ratio, 2),
                'company_name': info.get('longName', ticker),
                'confidence_score': confidence_score,
                'analysis': analysis,
                'catalyst': "Technical analysis with price & volume momentum"
            }
            
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None
    
    def update_all_stocks(self):
        """Update data for all stocks"""
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            print(f"Analyzing {region} stocks...")
            for ticker in tickers:
                stock_data = self.get_stock_data(ticker)
                if stock_data:
                    stock_data['region'] = region
                    all_stocks.append(stock_data)
                    print(f"✅ {ticker}: {stock_data['confidence_score']}/100")
        
        # Sort by confidence score
        all_stocks.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Save results
        output = {
            'last_updated': datetime.now().isoformat(),
            'stocks': all_stocks
        }
        
        os.makedirs('data/processed', exist_ok=True)
        with open('data/processed/latest_stocks.json', 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"✅ Updated {len(all_stocks)} stocks")
        return all_stocks

if __name__ == "__main__":
    analyzer = StockAnalyzer()
    analyzer.update_all_stocks()
