import pandas as pd
import numpy as np
from datetime import datetime
from config import TECHNICAL_INDICATORS, technical_history

def calculate_ma_indicators(df, periods):
    """计算移动平均线指标"""
    indicators = {}
    
    for period in periods:
        if len(df) >= period:
            ma_key = f'MA{period}'
            df[ma_key] = df['close'].rolling(window=period).mean()
            
            current_ma = df[ma_key].iloc[-1]
            prev_ma = df[ma_key].iloc[-2] if len(df) >= period + 1 else current_ma
            
            if current_ma > prev_ma:
                trend = "上升"
                trend_signal = "BULLISH"
            else:
                trend = "下降"
                trend_signal = "BEARISH"
            
            change_pct = ((current_ma - prev_ma) / prev_ma) * 100 if prev_ma != 0 else 0
            
            indicators[f'ma{period}'] = {
                'value': current_ma,
                'trend': trend,
                'signal': trend_signal,
                'change_percent': change_pct,
                'price_vs_ma': ((df['close'].iloc[-1] - current_ma) / current_ma) * 100
            }
    
    return indicators

def calculate_boll_indicators(df, period=20, std_dev=2):
    """计算布林带指标"""
    if len(df) < period:
        return {}
        
    df['BOLL_MID'] = df['close'].rolling(window=period).mean()
    df['BOLL_STD'] = df['close'].rolling(window=period).std()
    df['BOLL_UPPER'] = df['BOLL_MID'] + std_dev * df['BOLL_STD']
    df['BOLL_LOWER'] = df['BOLL_MID'] - std_dev * df['BOLL_STD']
    
    current_close = df['close'].iloc[-1]
    current_mid = df['BOLL_MID'].iloc[-1]
    prev_close = df['close'].iloc[-2]
    prev_mid = df['BOLL_MID'].iloc[-2]
    
    if prev_close <= prev_mid and current_close > current_mid:
        signal = "突破中轨向上"
        direction = "BULLISH_BREAK"
    elif prev_close >= prev_mid and current_close < current_mid:
        signal = "跌破中轨向下"
        direction = "BEARISH_BREAK"
    else:
        if current_close > current_mid:
            signal = "在中轨上方"
            direction = "ABOVE_MID"
        else:
            signal = "在中轨下方"
            direction = "BELOW_MID"
    
    boll_width = ((df['BOLL_UPPER'].iloc[-1] - df['BOLL_LOWER'].iloc[-1]) / df['BOLL_MID'].iloc[-1]) * 100
    boll_position = ((current_close - df['BOLL_LOWER'].iloc[-1]) / (df['BOLL_UPPER'].iloc[-1] - df['BOLL_LOWER'].iloc[-1])) * 100
    
    return {
        'boll': {
            'upper': df['BOLL_UPPER'].iloc[-1],
            'middle': current_mid,
            'lower': df['BOLL_LOWER'].iloc[-1],
            'signal': signal,
            'direction': direction,
            'width_percent': boll_width,
            'position_percent': boll_position,
            'price_vs_middle': ((current_close - current_mid) / current_mid) * 100
        }
    }

def calculate_rsi_indicators(df, period=14):
    """计算RSI指标"""
    if len(df) < period + 1:
        return {}
        
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    current_rsi = df['RSI'].iloc[-1]
    prev_rsi = df['RSI'].iloc[-2]
    
    if current_rsi < 30:
        level = "超卖区域"
        signal = "OVERSOLD"
    elif current_rsi > 70:
        level = "超买区域"
        signal = "OVERBOUGHT"
    else:
        level = "正常区域"
        signal = "NEUTRAL"
    
    if current_rsi > prev_rsi:
        trend = "上升"
        trend_signal = "BULLISH"
    else:
        trend = "下降"
        trend_signal = "BEARISH"
    
    return {
        'rsi': {
            'value': current_rsi,
            'level': level,
            'signal': signal,
            'trend': trend,
            'trend_signal': trend_signal,
            'change': current_rsi - prev_rsi
        }
    }

def calculate_macd_indicators(df, fast_period=12, slow_period=26, signal_period=9):
    """计算MACD指标"""
    if len(df) < slow_period + signal_period:
        return {}
        
    exp1 = df['close'].ewm(span=fast_period, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow_period, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_SIGNAL'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
    df['MACD_HISTOGRAM'] = df['MACD'] - df['MACD_SIGNAL']
    
    current_macd = df['MACD'].iloc[-1]
    current_signal = df['MACD_SIGNAL'].iloc[-1]
    current_hist = df['MACD_HISTOGRAM'].iloc[-1]
    prev_macd = df['MACD'].iloc[-2]
    prev_signal = df['MACD_SIGNAL'].iloc[-2]
    prev_hist = df['MACD_HISTOGRAM'].iloc[-2]
    
    if current_macd > current_signal and prev_macd <= prev_signal:
        signal = "金叉看涨"
        direction = "BULLISH_CROSS"
    elif current_macd < current_signal and prev_macd >= prev_signal:
        signal = "死叉看跌"
        direction = "BEARISH_CROSS"
    else:
        if current_macd > current_signal:
            signal = "多头排列"
            direction = "BULLISH"
        else:
            signal = "空头排列"
            direction = "BEARISH"
    
    hist_trend = "放大" if abs(current_hist) > abs(prev_hist) else "缩小"
    
    return {
        'macd': {
            'macd_line': current_macd,
            'signal_line': current_signal,
            'histogram': current_hist,
            'signal': signal,
            'direction': direction,
            'histogram_trend': hist_trend,
            'above_zero': current_macd > 0
        }
    }

def calculate_volume_indicators(df):
    """计算成交量指标"""
    if len(df) < 2:
        return {}
        
    current_volume = df['volume'].iloc[-1]
    prev_volume = df['volume'].iloc[-2]
    avg_volume = df['volume'].tail(20).mean() if len(df) >= 20 else current_volume
    
    volume_change = ((current_volume - prev_volume) / prev_volume) * 100 if prev_volume != 0 else 0
    volume_vs_avg = ((current_volume - avg_volume) / avg_volume) * 100 if avg_volume != 0 else 0
    
    if volume_vs_avg > 50:
        level = "放量明显"
        signal = "HIGH_VOLUME"
    elif volume_vs_avg < -50:
        level = "缩量明显"
        signal = "LOW_VOLUME"
    else:
        level = "正常量能"
        signal = "NORMAL_VOLUME"
    
    return {
        'volume': {
            'current': current_volume,
            'change_percent': volume_change,
            'vs_average': volume_vs_avg,
            'level': level,
            'signal': signal
        }
    }

def calculate_technical_indicators(df):
    """计算所有启用的技术指标"""
    all_indicators = {}
    
    try:
        # MA移动平均线
        if TECHNICAL_INDICATORS['ma']['enabled']:
            ma_indicators = calculate_ma_indicators(df, TECHNICAL_INDICATORS['ma']['periods'])
            all_indicators.update(ma_indicators)
        
        # 布林带
        if TECHNICAL_INDICATORS['boll']['enabled']:
            boll_indicators = calculate_boll_indicators(
                df, 
                TECHNICAL_INDICATORS['boll']['period'],
                TECHNICAL_INDICATORS['boll']['std_dev']
            )
            all_indicators.update(boll_indicators)
        
        # RSI
        if TECHNICAL_INDICATORS['rsi']['enabled']:
            rsi_indicators = calculate_rsi_indicators(df, TECHNICAL_INDICATORS['rsi']['period'])
            all_indicators.update(rsi_indicators)
        
        # MACD
        if TECHNICAL_INDICATORS['macd']['enabled']:
            macd_indicators = calculate_macd_indicators(
                df,
                TECHNICAL_INDICATORS['macd']['fast_period'],
                TECHNICAL_INDICATORS['macd']['slow_period'],
                TECHNICAL_INDICATORS['macd']['signal_period']
            )
            all_indicators.update(macd_indicators)
        
        # 成交量
        if TECHNICAL_INDICATORS['volume']['enabled']:
            volume_indicators = calculate_volume_indicators(df)
            all_indicators.update(volume_indicators)
        
        # 保存技术指标历史
        if all_indicators:
            tech_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'price': df['close'].iloc[-1],
                'indicators': all_indicators
            }
            technical_history.append(tech_data)
            if len(technical_history) > 50:
                technical_history.pop(0)
                
        return all_indicators
        
    except Exception as e:
        print(f"计算技术指标失败: {e}")
        return {}

def build_technical_analysis_text(indicators):
    """构建技术指标分析文本"""
    if not indicators:
        return "【技术指标】数据不足计算技术指标\n"
    
    text = "【技术指标分析】\n"
    
    # MA移动平均线
    ma_indicators = {k: v for k, v in indicators.items() if k.startswith('ma')}
    if ma_indicators:
        text += "\n📈 【移动平均线分析】\n"
        for key, ma_data in sorted(ma_indicators.items()):
            period = key[2:]
            text += f"MA{period}: {ma_data['value']:.2f} ({ma_data['trend']} {ma_data['change_percent']:+.3f}%)\n"
            text += f"   价格相对MA{period}: {ma_data['price_vs_ma']:+.2f}%\n"
    
    # 布林带
    if 'boll' in indicators:
        boll_data = indicators['boll']
        text += "\n🎯 【布林带分析】\n"
        text += f"上轨: {boll_data['upper']:.2f} | 中轨: {boll_data['middle']:.2f} | 下轨: {boll_data['lower']:.2f}\n"
        text += f"信号: {boll_data['signal']} | 带宽: {boll_data['width_percent']:.2f}%\n"
        text += f"位置: {boll_data['position_percent']:.1f}% | 相对中轨: {boll_data['price_vs_middle']:+.2f}%\n"
    
    # RSI
    if 'rsi' in indicators:
        rsi_data = indicators['rsi']
        text += "\n⚖️ 【RSI分析】\n"
        text += f"RSI: {rsi_data['value']:.1f} ({rsi_data['level']}) | 趋势: {rsi_data['trend']}\n"
        text += f"变化: {rsi_data['change']:+.2f}\n"
    
    # MACD
    if 'macd' in indicators:
        macd_data = indicators['macd']
        text += "\n📊 【MACD分析】\n"
        text += f"信号: {macd_data['signal']} | 柱状图: {macd_data['histogram']:.4f} ({macd_data['histogram_trend']})\n"
        text += f"MACD线: {macd_data['macd_line']:.4f} | 信号线: {macd_data['signal_line']:.4f}\n"
        text += f"零轴上方: {'是' if macd_data['above_zero'] else '否'}\n"
    
    # 成交量
    if 'volume' in indicators:
        volume_data = indicators['volume']
        text += "\n📦 【成交量分析】\n"
        text += f"成交量: {volume_data['current']:.2f} | 变化: {volume_data['change_percent']:+.1f}%\n"
        text += f"相对均量: {volume_data['vs_average']:+.1f}% | 状态: {volume_data['level']}\n"
    
    return text