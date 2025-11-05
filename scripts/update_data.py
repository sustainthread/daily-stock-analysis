import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
from technical_analysis_library import calculate_rsi, calculate_macd, calculate_bollinger_bands

class AdvancedStockAnalyzer:
    def __init__(self):
        self.watchlist = {
            'US': ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'META', 'AMD', 'AMZN', 'NFLX', 'JPM'],
            'UK': ['TSCO.L', 'HSBA.L', 'LLOY.L', 'VOD.L', 'BARC.L', 'BP.L', 'GSK.L', 'RIO.L'],
            'EU': ['AIR.PA', 'SIE.DE', 'ASML.AS', 'SAF.PA', 'BMW.DE', 'DB1.DE', 'ALV.DE', 'TTE.PA']
        }
    
    def calculate_technical_indicators(self, closes, volumes, highs, lows):
        """Calculate advanced technical indicators manually"""
        indicators = {}
        
        # Moving Averages
        indicators['sma_20'] = closes.rolling(window=20).mean().iloc[-1]
        indicators['sma_50'] = closes.rolling(window=50).mean().iloc[-1]
        indicators['ema_12'] = closes.ewm(span=12).mean().iloc[-1]
        indicators['ema_26'] = closes.ewm(span=26).mean().iloc[-1]
        
        # RSI
        try:
            indicators['rsi'] = calculate_rsi(closes).iloc[-1]
        except:
            # Manual RSI calculation
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD
        try:
            macd_line, macd_signal = calculate_macd(closes)
            indicators['macd'] = macd_line.iloc[-1]
            indicators['macd_signal'] = macd_signal.iloc[-1]
        except:
            ema_12 = closes.ewm(span=12).mean()
            ema_26 = closes.ewm(span=26).mean()
            indicators['macd'] = (ema_12 - ema_26).iloc[-1]
            indicators['macd_signal'] = (ema_12 - ema_26).ewm(span=9).mean().iloc[-1]
        
        # Bollinger Bands
        try:
            bb_upper, bb_lower = calculate_bollinger_bands(closes)
            indicators['bb_upper'] = bb_upper.iloc[-1]
            indicators['bb_lower'] = bb_lower.iloc[-1]
        except:
            sma_20 = closes.rolling(window=20).mean()
            bb_std = closes.rolling(window=20).std()
            indicators['bb_upper'] = (sma_20 + (bb_std * 2)).iloc[-1]
            indicators['bb_lower'] = (sma_20 - (bb_std * 2)).iloc[-1]
        
        # Volume indicators
        indicators['volume_sma'] = volumes.rolling(20).mean().iloc[-1]
        
        # ATR (Average True Range)
        try:
            tr1 = highs - lows
            tr2 = abs(highs - closes.shift())
            tr3 = abs(lows - closes.shift())
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            indicators['atr'] = true_range.rolling(14).mean().iloc[-1]
        except:
            indicators['atr'] = (highs - lows).rolling(14).mean().iloc[-1]
        
        return indicators
    
    def calculate_advanced_confidence(self, stock_data, indicators, hist_data):
        """SOPHISTICATED multi-factor confidence scoring"""
        score_components = {}
        total_score = 0
        
        current_price = stock_data['current_price']
        current_volume = stock_data['volume']
        
        # 1. PRICE MOMENTUM (30 points)
        price_score = 0
        
        # Multi-timeframe momentum
        for days, weight in [(5, 10), (10, 8), (20, 7)]:
            if len(hist_data) >= days:
                past_price = hist_data['Close'].iloc[-days]
                momentum = ((current_price - past_price) / past_price) * 100
                if momentum > 8:
                    price_score += weight
                elif momentum > 4:
                    price_score += weight * 0.7
                elif momentum > 0:
                    price_score += weight * 0.4
        
        # Moving average alignment
        ma_bonus = 0
        if current_price > indicators['sma_20']:
            ma_bonus += 3
        if current_price > indicators['sma_50']:
            ma_bonus += 3
        if indicators['sma_20'] > indicators['sma_50']:
            ma_bonus += 4
        price_score += ma_bonus
        
        score_components['price_momentum'] = min(price_score, 30)
        total_score += score_components['price_momentum']
        
        # 2. TECHNICAL STRENGTH (25 points)
        tech_score = 0
        
        # RSI strength (optimal 40-70)
        rsi = indicators.get('rsi', 50)
        if 45 < rsi < 65:  # Strong bullish zone
            tech_score += 10
        elif 40 < rsi < 70:  # Good zone
            tech_score += 7
        elif 35 < rsi < 75:  # Acceptable
            tech_score += 4
        
        # MACD bullish crossover
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 1)
        if macd > macd_signal and macd > 0:
            tech_score += 8
        elif macd > macd_signal:
            tech_score += 5
        
        # Bollinger Band position
        bb_position = (current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
        if 0.5 < bb_position < 0.8:  # Upper band strength but not overbought
            tech_score += 7
        
        score_components['technical_strength'] = min(tech_score, 25)
        total_score += score_components['technical_strength']
        
        # 3. VOLUME CONFIRMATION (20 points)
        volume_score = 0
        volume_ratio = current_volume / indicators['volume_sma'] if indicators['volume_sma'] > 0 else 1
        
        if volume_ratio > 2.0:
            volume_score += 12
        elif volume_ratio > 1.5:
            volume_score += 8
        elif volume_ratio > 1.2:
            volume_score += 5
        
        # Volume trend (last 5 days)
        if len(hist_data) >= 5:
            recent_volumes = hist_data['Volume'].tail(5)
            if recent_volumes.is_monotonic_increasing:
                volume_score += 5
            elif recent_volumes.iloc[-1] > recent_volumes.iloc[-5]:
                volume_score += 3
        
        score_components['volume_confirmation'] = min(volume_score, 20)
        total_score += score_components['volume_confirmation']
        
        # 4. TREND QUALITY (15 points)
        trend_score = 0
        
        # Price consistency (recent higher highs/lows)
        if len(hist_data) >= 10:
            recent_highs = hist_data['High'].tail(10)
            recent_lows = hist_data['Low'].tail(10)
            
            if (recent_highs.iloc[-1] > recent_highs.iloc[-5] and 
                recent_lows.iloc[-1] > recent_lows.iloc[-5]):
                trend_score += 8
        
        # Low volatility trend
        atr_percentage = (indicators['atr'] / current_price) * 100
        if atr_percentage < 2.5:
            trend_score += 4
        elif atr_percentage < 4:
            trend_score += 2
        
        # EMA alignment
        if (indicators['ema_12'] > indicators['ema_26'] and 
            indicators['ema_12'] > indicators['sma_50']):
            trend_score += 3
        
        score_components['trend_quality'] = min(trend_score, 15)
        total_score += score_components['trend_quality']
        
        # 5. RISK ADJUSTMENT (10 points) - Lower risk = higher score
        risk_score = 10
        
        # High volatility penalty
        if atr_percentage > 6:
            risk_score -= 6
        elif atr_percentage > 4:
            risk_score -= 3
        
        # Overbought RSI penalty
        if rsi > 75:
            risk_score -= 3
        elif rsi > 70:
            risk_score -= 1
        
        # Oversold RSI bonus (less risk)
        if rsi < 30:
            risk_score += 2
        
        score_components['risk_adjustment'] = max(risk_score, 0)
        total_score += score_components['risk_adjustment']
        
        return {
            'total_score': min(max(total_score, 0), 100),
            'components': score_components,
            'indicators': {
                'rsi': round(rsi, 1),
                'macd': round(macd, 3),
                'volume_ratio': round(volume_ratio, 2),
                'atr_percentage': round(atr_percentage, 2),
                'bb_position': round(bb_position, 2),
                'above_sma_20': current_price > indicators['sma_20'],
                'above_sma_50': current_price > indicators['sma_50']
            }
        }
    
    def generate_detailed_analysis(self, confidence_data, stock_data):
        """Generate professional-level analysis"""
        components = confidence_data['components']
        indicators = confidence_data['indicators']
        
        analysis_parts = []
        
        # Overall assessment
        total_score = confidence_data['total_score']
        if total_score >= 80:
            analysis_parts.append("🎯 **HIGH CONVICTION** - Strong multi-timeframe alignment")
        elif total_score >= 65:
            analysis_parts.append("📈 **BULLISH** - Solid technical foundation")
        elif total_score >= 50:
            analysis_parts.append("⚡ **NEUTRAL-BULLISH** - Needs confirmation")
        else:
            analysis_parts.append("🔄 **WATCH** - Requires stronger signals")
        
        # Technical breakdown
        if components['price_momentum'] >= 25:
            analysis_parts.append("Momentum accelerating across timeframes")
        elif components['price_momentum'] >= 18:
            analysis_parts.append("Positive momentum with MA support")
        
        if components['technical_strength'] >= 20:
            analysis_parts.append("RSI/MACD in optimal bullish configuration")
        elif components['technical_strength'] >= 15:
            analysis_parts.append("Technical indicators supportive")
        
        if components['volume_confirmation'] >= 15:
            analysis_parts.append("Strong volume confirmation")
        elif components['volume_confirmation'] >= 10:
            analysis_parts.append("Adequate volume participation")
        
        # Risk assessment
        if indicators['rsi'] > 70:
            analysis_parts.append("⚠️ RSI approaching overbought")
        elif indicators['rsi'] < 35:
            analysis_parts.append("📉 RSI shows oversold potential")
        
        if indicators['atr_percentage'] > 5:
            analysis_parts.append("⚡ High volatility - size positions carefully")
        
        return " | ".join(analysis_parts)
    
    def get_stock_data(self, ticker):
        """Get comprehensive stock analysis"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get sufficient historical data
            hist = stock.history(period="3mo")
            
            if len(hist) < 50:  # Need enough data for reliable indicators
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            # Calculate advanced technical indicators
            indicators = self.calculate_technical_indicators(
                hist['Close'], hist['Volume'], hist['High'], hist['Low']
            )
            
            stock_data = {
                'ticker': ticker,
                'current_price': round(current_price, 2),
                'price_change': round(price_change, 2),
                'price_change_percent': round(price_change_pct, 2),
                'volume': int(hist['Volume'].iloc[-1]),
                'company_name': info.get('longName', ticker),
                'market_cap': info.get('marketCap', 0)
            }
            
            # Advanced confidence scoring
            confidence_data = self.calculate_advanced_confidence(stock_data, indicators, hist)
            
            stock_data.update({
                'confidence_score': confidence_data['total_score'],
                'analysis': self.generate_detailed_analysis(confidence_data, stock_data),
                'catalyst': "Multi-timeframe technical analysis with volume confirmation",
                'technical_indicators': confidence_data['indicators'],
                'score_components': confidence_data['components']
            })
            
            return stock_data
            
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None
    
    def update_all_stocks(self):
        """Update all stock analyses"""
        all_stocks = []
        
        for region, tickers in self.watchlist.items():
            print(f"🔍 Analyzing {region} stocks...")
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
            'analysis_type': 'advanced_technical_v2',
            'stocks': all_stocks
        }
        
        os.makedirs('data/processed', exist_ok=True)
        with open('data/processed/latest_stocks.json', 'w') as f:
            json.dump(output, f, indent=2)
            
        print(f"🎉 Successfully updated {len(all_stocks)} stocks with advanced analysis")
        return all_stocks

if __name__ == "__main__":
    analyzer = AdvancedStockAnalyzer()
    analyzer.update_all_stocks()
