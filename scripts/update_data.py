import os
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import yfinance as yf

class AdvancedStockAnalyzer:
    def __init__(self):
        # Expanded watchlist with verified symbols
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'META', 'AMZN', 'NFLX'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L', 'VOD.L', 'BARC.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS', 'SAF.PA', 'BMW.DE']
        }
    
    def get_stock_data_safe(self, ticker):
        """Get stock data with proper date handling for weekends"""
        try:
            print(f"📊 Fetching {ticker}...")
            stock = yf.Ticker(ticker)
            
            # Get longer historical data to ensure we have recent trading days
            hist = stock.history(period="2mo")  # 2 months of data
            
            if len(hist) < 5:
                print(f"  ❌ Not enough historical data for {ticker}")
                return None
            
            # Find the most recent trading day (skip weekends/holidays)
            today = datetime.now().date()
            days_back = 0
            max_days_back = 10  # Don't go back more than 2 weeks
            
            while days_back < max_days_back:
                check_date = today - timedelta(days=days_back)
                if check_date in hist.index:
                    # Found a trading day
                    recent_data = hist.loc[check_date:]
                    if len(recent_data) >= 2:
                        break
                days_back += 1
            else:
                print(f"  ❌ No recent trading data found for {ticker}")
                return None
            
            # Use the most recent available data
            current_price = recent_data['Close'].iloc[-1]
            prev_close = recent_data['Close'].iloc[-2] if len(recent_data) >= 2 else current_price
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            # Calculate basic metrics
            current_volume = recent_data['Volume'].iloc[-1]
            avg_volume = recent_data['Volume'].tail(20).mean() if len(recent_data) >= 20 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Enhanced confidence scoring
            confidence_score = 50
            
            # Price momentum (up to 30 points)
            if price_change_pct > 3:
                confidence_score += 25
            elif price_change_pct > 1:
                confidence_score += 15
            elif price_change_pct > 0:
                confidence_score += 8
            elif price_change_pct < -2:
                confidence_score -= 10
            
            # Volume confirmation (up to 20 points)
            if volume_ratio > 2.0:
                confidence_score += 18
            elif volume_ratio > 1.5:
                confidence_score += 12
            elif volume_ratio > 1.2:
                confidence_score += 7
            elif volume_ratio < 0.8:
                confidence_score -= 5
            
            # Trend strength (up to 15 points)
            if len(recent_data) >= 20:
                sma_20 = recent_data['Close'].rolling(20).mean().iloc[-1]
                if current_price > sma_20:
                    confidence_score += 10
                else:
                    confidence_score -= 5
            
            # RSI-like momentum (up to 10 points)
            if len(recent_data) >= 14:
                price_changes = recent_data['Close'].pct_change().dropna()
                if len(price_changes) >= 5:
                    recent_momentum = price_changes.tail(5).mean() * 100
                    if recent_momentum > 0.5:
                        confidence_score += 8
                    elif recent_momentum > 0.1:
                        confidence_score += 4
            
            confidence_score = min(max(confidence_score, 0), 100)
            
            # Determine market status
            latest_date = recent_data.index[-1].date()
            days_since_update = (today - latest_date).days
            market_status = "LIVE" if days_since_update <= 1 else f"DATA FROM {latest_date}"
            
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
                'catalyst': f"Technical analysis | {market_status}",
                'last_trading_day': latest_date.isoformat()
            }
            
            print(f"  ✅ {ticker}: ${current_price:.2f} ({price_change_pct:+.2f}%) - Score: {confidence_score}/100 - {market_status}")
            return stock_data
            
        except Exception as e:
            print(f"  ❌ Error with {ticker}: {str(e)[:100]}...")
            return None
    
    def get_company_name(self, ticker):
        """Get company name from mapping"""
        name_map = {
            'AAPL': 'Apple Inc.',
            'MSFT': 'Microsoft Corporation',
            'TSLA': 'Tesla Inc.',
            'NVDA': 'NVIDIA Corporation',
            'GOOGL': 'Alphabet Inc.',
            'META': 'Meta Platforms Inc.',
            'AMZN': 'Amazon.com Inc.',
            'NFLX': 'Netflix Inc.',
            'TSCO.L': 'Tesco PLC',
            'HSBA.L': 'HSBC Holdings PLC',
            'LLOY.L': 'Lloyds Banking Group PLC',
            'VOD.L': 'Vodafone Group PLC',
            'BARC.L': 'Barclays PLC',
            'AIR.PA': 'Airbus SE',
            'SIE.DE': 'Siemens AG',
            'ASML.AS': 'ASML Holding NV',
            'SAF.PA': 'Safran SA',
            'BMW.DE': 'BMW AG'
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
        elif price_change_pct < -2:
            analysis_parts.append("with recent pressure")
        
        if volume_ratio > 1.5:
            analysis_parts.append("on high volume")
        elif volume_ratio > 1.0:
            analysis_parts.append("on average volume")
        else:
            analysis_parts.append("volume below average")
        
        return " ".join(analysis_parts)
    
    def update_all_stocks(self):
        """Update data for all stocks with proper error handling"""
        print("🚀 Starting stock analysis...")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            print(f"\n🌍 Analyzing {region} stocks:")
            for i, ticker in enumerate(tickers):
                stock_data = self.get_stock_data_safe(ticker)
                if stock_data:
                    stock_data['region'] = region
                    all_stocks.append(stock_data)
                
                # Add delay between requests to avoid rate limiting
                if i < len(tickers) - 1:
                    print(f"    ⏳ Waiting 3 seconds...")
                    time.sleep(3)
        
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
        
        # Show summary
        if all_stocks:
            print(f"\n🏆 Top stocks by confidence:")
            for i, stock in enumerate(all_stocks[:8]):
                print(f"   {i+1}. {stock['ticker']}: {stock['confidence_score']}/100")
            
            avg_score = sum(s['confidence_score'] for s in all_stocks) / len(all_stocks)
            print(f"\n📊 Average confidence score: {avg_score:.1f}/100")
        else:
            print("❌ No stocks were successfully analyzed")
            print("💡 This often happens on weekends when markets are closed")
            print("💡 The script will work when markets are open (Monday-Friday)")
        
        return all_stocks

if __name__ == "__main__":
    analyzer = AdvancedStockAnalyzer()
    analyzer.update_all_stocks()
