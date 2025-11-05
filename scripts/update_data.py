import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import requests
import ta  # Technical Analysis library

class AdvancedStockAnalyzer:
    def __init__(self):
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'META', 'AMD', 'AMZN', 'NFLX', 'JPM'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L', 'VOD.L', 'BARC.L', 'BP.L', 'GSK.L', 'RIO.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS', 'SAF.PA', 'BMW.DE', 'DB1.DE', 'ALV.DE', 'TTE.PA']
        }
    
    def get_technical_indicators(self, hist_data):
        """Calculate multiple technical indicators"""
        if len(hist_data) < 20:
            return {}
            
        # Convert to pandas Series for TA library
        closes = hist_data['Close']
        highs = hist_data['High']
        lows = hist_data['Low']
        volumes = hist_data['Volume']
        
        indicators = {}
        
        # Trend Indicators
        indicators['sma_20'] = ta.trend.SMAIndicator(closes, window=20).sma_indicator().iloc[-1]
        indicators['sma_50'] = ta.trend.SMAIndicator(closes, window=50).sma_indicator().iloc[-1]
        indicators['ema_12'] = ta.trend.EMAIndicator(closes, window=12).ema_indicator().iloc[-1]
        indicators['ema_26'] = ta.trend.EMAIndicator(closes, window=26).ema_indicator().iloc[-1]
        
        # Momentum Indicators
        indicators['rsi'] = ta.momentum.RSIIndicator(closes).rsi().iloc[-1]
        indicators['macd'] = ta.trend.MACD(closes).macd().iloc[-1]
        indicators['macd_signal'] = ta.trend.MACD(closes).macd_signal().iloc[-1]
        indicators['stoch_rsi'] = ta.momentum.StochRSIIndicator(closes).stochrsi().iloc[-1]
        
        # Volume Indicators
        indicators['volume_sma'] = volumes.rolling(20).mean().iloc[-1]
        indicators['obv'] = ta.volume.OnBalanceVolumeIndicator(closes, volumes).on_balance_volume().iloc[-1]
        
        # Volatility
        indicators['bb_upper'] = ta.volatility.BollingerBands(closes).bollinger_hband().iloc[-1]
        indicators['bb_lower'] = ta.volatility.BollingerBands(closes).bollinger_lband().iloc[-1]
        indicators['atr'] = ta.volatility.AverageTrueRange(highs, lows, closes).average_true_range().iloc[-1]
        
        return indicators
    
    def calculate_advanced_confidence(self, stock_data, indicators, hist_data):
        """Sophisticated multi-factor confidence scoring"""
        score_components = {}
        total_score = 0
        
        # 1. PRICE MOMENTUM (25 points max)
        price_score = 0
        current_price = stock_data['current_price']
        
        # Short-term momentum (5 days)
        if len(hist_data) >= 5:
            price_5d_ago = hist_data['Close'].iloc[-5]
            momentum_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
            
            if momentum_5d > 8:
                price_score += 10
            elif momentum_5d > 4:
                price_score += 7
            elif momentum_5d > 0:
                price_score += 3
        
        # Price vs Moving Averages
        if current_price > indicators.get('sma_20', 0):
            price_score += 5
        if current_price > indicators.get('sma_50', 0):
            price_score += 5
            
        # RSI Momentum (30-70 is healthy)
        rsi = indicators.get('rsi', 50)
        if 40 < rsi < 70:
            price_score += 5
        elif 30 < rsi < 80:
            price_score += 3
            
        score_components['price_momentum'] = min(price_score, 25)
        total_score += score_components['price_momentum']
        
        # 2. VOLUME ANALYSIS (20 points max)
        volume_score = 0
        current_volume = stock_data.get('volume', 0)
        avg_volume = indicators.get('volume_sma', current_volume)
        
        # Volume spike
        if avg_volume > 0:
            volume_ratio = current_volume / avg_volume
            if volume_ratio > 2.0:
                volume_score += 10
            elif volume_ratio > 1.5:
                volume_score += 7
            elif volume_ratio > 1.2:
                volume_score += 3
                
        # OBV trend
        obv = indicators.get('obv', 0)
        if obv > 0:
            volume_score += 5
            
        score_components['volume'] = min(volume_score, 20)
        total_score += score_components['volume']
        
        # 3. TREND STRENGTH (25 points max)
        trend_score = 0
        
        # MACD bullish
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 1)
        if macd > macd_signal:
            trend_score += 8
            
        # Moving average alignment
        if (indicators.get('ema_12', 0) > indicators.get('ema_26', 1) and 
            indicators.get('sma_20', 0) > indicators.get('sma_50', 1)):
            trend_score += 10
            
        # Bollinger Band position (not squeezed)
        bb_upper = indicators.get('bb_upper', current_price * 1.1)
        bb_lower = indicators.get('bb_lower', current_price * 0.9)
        bb_width = (bb_upper - bb_lower) / current_price
        
        if bb_width > 0.05:  # Not squeezed
            trend_score += 7
            
        score_components['trend'] = min(trend_score, 25)
        total_score += score_components['trend']
        
        # 4. VOLATILITY & RISK (15 points max)
        volatility_score = 0
        atr = indicators.get('atr', 0)
        atr_percentage = (atr / current_price) * 100 if current_price > 0 else 0
        
        # Lower volatility is better for confidence
        if atr_percentage < 2:
            volatility_score += 10
        elif atr_percentage < 4:
            volatility_score += 7
        elif atr_percentage < 6:
            volatility_score += 3
            
        # Price consistency
        if len(hist_data) >= 10:
            volatility = hist_data['Close'].pct_change().std() * np.sqrt(252)
            if volatility < 0.3:  # Annualized volatility < 30%
                volatility_score += 5
                
        score_components['volatility'] = min(volatility_score, 15)
        total_score += score_components['volatility']
        
        # 5. RELATIVE STRENGTH (15 points max)
        # This would compare to sector/index - simplified for now
        strength_score = 0
        
        # Stoch RSI
        stoch_rsi = indicators.get('stoch_rsi', 0.5)
        if 0.2 < stoch_rsi < 0.8:
            strength_score += 8
            
        # Recent performance consistency
        if len(hist_data) >= 10:
            positive_days = (hist_data['Close'].pct_change().tail(10) > 0).sum()
            if positive_days >= 6:
                strength_score += 7
                
        score_components['strength'] = min(strength_score, 15)
        total_score += score_components['strength']
        
        return {
            'total_score': min(max(total_score, 0), 100),
            'components': score_components,
            'indicators': {
                'rsi': round(rsi, 2),
                'macd': round(macd, 3),
                'volume_ratio': round(current_volume / avg_volume, 2) if avg_volume > 0 else 1,
                'above_sma_20': current_price > indicators.get('sma_20', 0),
                'above_sma_50': current_price > indicators.get('sma_50', 0)
            }
        }
    
    def generate_analysis_report(self, confidence_data, stock_data):
        """Generate detailed analysis based on confidence components"""
        components = confidence_data['components']
        indicators = confidence_data['indicators']
        
        report = []
        
        # Price momentum analysis
        if components['price_momentum'] >= 20:
            report.append("🚀 Strong bullish momentum with multiple confirmations")
        elif components['price_momentum'] >= 15:
            report.append("📈 Positive momentum with good technical alignment")
        else:
            report.append("⚡ Momentum needs improvement")
            
        # Volume analysis
        if components['volume'] >= 15:
            report.append("💧 High volume confirmation supporting the move")
        elif components['volume'] >= 10:
            report.append("💦 Moderate volume participation")
        else:
            report.append("🌵 Low volume - needs institutional confirmation")
            
        # Trend analysis
        if components['trend'] >= 20:
            report.append("🎯 Strong uptrend with multiple timeframe alignment")
        elif components['trend'] >= 15:
            report.append("📊 Healthy trend structure")
        else:
            report.append("🔄 Trend needs confirmation")
            
        # Risk assessment
        if components['volatility'] >= 12:
            report.append("🛡️ Low volatility setup with controlled risk")
        elif components['volatility'] >= 8:
            report.append("⚖️ Moderate risk profile")
        else:
            report.append("🎪 High volatility - position size carefully")
            
        # Technical levels
        if indicators['above_sma_20'] and indicators['above_sma_50']:
            report.append("🏔️ Trading above key moving averages")
        elif indicators['above_sma_20']:
            report.append("⛰️ Above short-term MA, watch 50-day SMA")
        else:
            report.append("🏞️ Below key moving averages - caution needed")
            
        return " | ".join(report)
    
    def get_stock_data(self, ticker):
        """Get comprehensive stock data with technical analysis"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get historical data for technical analysis
            hist = stock.history(period="2mo")  # 2 months for better indicators
            
            if len(hist) < 20:
                return None
                
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            # Calculate technical indicators
            indicators = self.get_technical_indicators(hist)
            
            stock_data = {
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_pct, 2),
                'volume': int(hist['Volume'].iloc[-1]),
                'company_name': info.get('longName', ticker),
                'market_cap': info.get('marketCap', 0),
                'previous_close': round(prev_close, 2)
            }
            
            # Calculate advanced confidence score
            confidence_data = self.calculate_advanced_confidence(stock_data, indicators, hist)
            
            stock_data.update({
                'confidence_score': confidence_data['total_score'],
                'analysis': self.generate_analysis_report(confidence_data, stock_data),
                'catalyst': "Multi-factor technical analysis with momentum confirmation",
                'technical_indicators': confidence_data['indicators'],
                'score_components': confidence_data['components']
            })
            
            return stock_data
            
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None
    
    def update_all_stocks(self):
        """Update data for all stocks in watchlist"""
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            print(f"Analyzing {region} stocks...")
            for ticker in tickers:
                stock_data = self.get_stock_data(ticker)
                
                if stock_data:
                    stock_data['region'] = region
                    all_stocks.append(stock_data)
                    print(f"✅ {ticker}: {stock_data['confidence_score']}/100")
                else:
                    print(f"❌ Failed to analyze {ticker}")
        
        # Sort by confidence score (highest first)
        all_stocks.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Save to JSON file
        output = {
            'last_updated': datetime.now().isoformat(),
            'update_type': 'advanced_technical_analysis',
            'stocks': all_stocks
        }
        
        os.makedirs('data/processed', exist_ok=True)
        with open('data/processed/latest_stocks.json', 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"✅ Updated {len(all_stocks)} stocks with advanced analysis")
        return all_stocks

if __name__ == "__main__":
    analyzer = AdvancedStockAnalyzer()
    analyzer.update_all_stocks()
