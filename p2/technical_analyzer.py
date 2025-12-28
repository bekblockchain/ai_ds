import pandas as pd
import numpy as np
from datetime import datetime
from config import TECHNICAL_INDICATORS, technical_history

def calculate_atr_indicators(df, period=20):
    """计算平均真实波幅(ATR) - 高频交易重要指标"""
    if len(df) < period + 1:
        return {}
    
    # 计算TR（真实波幅）
    high_low = df['high'] - df['low']
    high_close_prev = abs(df['high'] - df['close'].shift())
    low_close_prev = abs(df['low'] - df['close'].shift())
    
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    
    # 计算ATR
    df['ATR'] = tr.rolling(window=period).mean()
    
    current_atr = df['ATR'].iloc[-1]
    prev_atr = df['ATR'].iloc[-2] if len(df) > period else current_atr
    atr_percent = (current_atr / df['close'].iloc[-1]) * 100
    
    # 判断波动率水平
    if atr_percent > 1.5:
        volatility = "高波动"
        signal = "HIGH_VOLATILITY"
    elif atr_percent < 0.5:
        volatility = "低波动"
        signal = "LOW_VOLATILITY"
    else:
        volatility = "正常波动"
        signal = "NORMAL_VOLATILITY"
    
    return {
        'atr': {
            'value': current_atr,
            'percent': atr_percent,
            'volatility': volatility,
            'signal': signal,
            'change': current_atr - prev_atr,
            'change_percent': ((current_atr - prev_atr) / prev_atr) * 100 if prev_atr != 0 else 0
        }
    }

def calculate_ma_convergence(df, periods=[7, 10, 30]):
    """计算均线聚合度 - 高频策略核心指标"""
    if len(df) < max(periods):
        return {}
    
    ma_values = {}
    for period in periods:
        ma_key = f'MA{period}'
        if ma_key not in df.columns:
            df[ma_key] = df['close'].rolling(window=period).mean()
        ma_values[period] = df[ma_key].iloc[-1]
    
    # 计算聚合度
    max_ma = max(ma_values.values())
    min_ma = min(ma_values.values())
    spread = max_ma - min_ma
    spread_percent = (spread / df['close'].iloc[-1]) * 100
    
    # 判断聚合状态
    if spread_percent < 0.1:
        convergence = "高度聚合"
        signal = "STRONG_CONVERGENCE"
    elif spread_percent < 0.3:
        convergence = "中度聚合"
        signal = "MEDIUM_CONVERGENCE"
    else:
        convergence = "分散"
        signal = "DIVERGENCE"
    
    # 计算MA7和MA10的金叉死叉
    ma7 = df['MA7'].iloc[-1] if 'MA7' in df.columns else ma_values[7]
    ma10 = df['MA10'].iloc[-1] if 'MA10' in df.columns else ma_values[10]
    ma7_prev = df['MA7'].iloc[-2] if len(df) > 7 and 'MA7' in df.columns else ma7
    ma10_prev = df['MA10'].iloc[-2] if len(df) > 10 and 'MA10' in df.columns else ma10
    
    if ma7 > ma10 and ma7_prev <= ma10_prev:
        cross_signal = "金叉"
        cross_direction = "GOLDEN_CROSS"
    elif ma7 < ma10 and ma7_prev >= ma10_prev:
        cross_signal = "死叉"
        cross_direction = "DEAD_CROSS"
    else:
        cross_signal = "无交叉"
        cross_direction = "NO_CROSS"
    
    return {
        'ma_convergence': {
            'spread': spread,
            'spread_percent': spread_percent,
            'convergence': convergence,
            'signal': signal,
            'cross_signal': cross_signal,
            'cross_direction': cross_direction,
            'ma7': ma7,
            'ma10': ma10,
            'ma30': ma_values[30] if 30 in ma_values else None
        }
    }

# 辅助函数定义
def _calculate_ma_momentum(df, period, lookback=3):
    """计算均线动量"""
    if len(df) < period + lookback:
        return "数据不足"
    
    ma_key = f'MA{period}'
    current_ma = df[ma_key].iloc[-1]
    past_ma = df[ma_key].iloc[-(lookback + 1)]
    
    momentum = ((current_ma - past_ma) / past_ma) * 100 if past_ma != 0 else 0
    
    if momentum > 0.5:
        return "强势上升"
    elif momentum > 0.1:
        return "温和上升"
    elif momentum < -0.5:
        return "强势下降"
    elif momentum < -0.1:
        return "温和下降"
    else:
        return "无动量"

def _check_trend_confirmation(df, period):
    """检查趋势确认"""
    ma_key = f'MA{period}'
    
    # 检查最近3根K线的MA方向是否一致
    if len(df) >= period + 3:
        ma_values = df[ma_key].tail(3).values
        increasing = all(ma_values[i] < ma_values[i+1] for i in range(len(ma_values)-1))
        decreasing = all(ma_values[i] > ma_values[i+1] for i in range(len(ma_values)-1))
        
        if increasing:
            return "趋势确认上升"
        elif decreasing:
            return "趋势确认下降"
    
    return "趋势未确认"

def _calculate_trend_strength(df, period):
    """计算趋势强度"""
    ma_key = f'MA{period}'
    
    # 计算斜率
    if len(df) >= period + 5:
        recent_ma = df[ma_key].tail(5).values
        x = np.arange(len(recent_ma))
        slope, _ = np.polyfit(x, recent_ma, 1)
        
        slope_percent = (slope / recent_ma[0]) * 100 * 100  # 放大显示
        
        if abs(slope_percent) > 0.5:
            return "趋势强劲"
        elif abs(slope_percent) > 0.2:
            return "趋势中等"
        else:
            return "趋势疲弱"
    
    return "数据不足"

def _check_support_resistance(df, ma_value):
    """检查是否起到支撑/阻力作用"""
    current_price = df['close'].iloc[-1]
    price_distance = abs((current_price - ma_value) / ma_value) * 100
    
    if price_distance < 0.3:  # 价格接近MA
        if current_price > ma_value:
            return "支撑位"
        else:
            return "阻力位"
    
    return "无"

def _get_market_context(df, ma60_value):
    """获取市场背景"""
    current_price = df['close'].iloc[-1]
    price_vs_ma60 = ((current_price - ma60_value) / ma60_value) * 100
    
    if price_vs_ma60 > 10:
        return "强势牛市"
    elif price_vs_ma60 > 5:
        return "温和牛市"
    elif price_vs_ma60 < -10:
        return "强势熊市"
    elif price_vs_ma60 < -5:
        return "温和熊市"
    else:
        return "震荡市"

def _calculate_alignment_strength(ma_values, reverse=False):
    """计算均线排列强度"""
    if reverse:
        ma_values = ma_values[::-1]
    
    # 检查间距是否均匀
    spacings = []
    for i in range(len(ma_values)-1):
        spacing = ((ma_values[i+1] - ma_values[i]) / ma_values[i]) * 100
        spacings.append(spacing)
    
    if len(spacings) == 0:
        return "未知"
    
    avg_spacing = np.mean(spacings)
    spacing_std = np.std(spacings)
    
    # 间距均匀且适中为最强
    if spacing_std < avg_spacing * 0.3 and 0.1 < avg_spacing < 0.5:
        return "强"
    elif spacing_std < avg_spacing * 0.5:
        return "中"
    else:
        return "弱"

def _analyze_ma_relationships(df, periods):
    """分析均线间的关系（高频策略核心）"""
    relationships = {}
    
    # 检查是否有所需的均线
    required_ma = [7, 10, 30, 60]
    available_ma = [p for p in required_ma if f'MA{p}' in df.columns and p in periods]
    
    if len(available_ma) < 2:
        return relationships
    
    # 1. 检查均线排列（多头/空头）
    ma_values = {}
    for period in available_ma:
        ma_key = f'MA{period}'
        ma_values[period] = df[ma_key].iloc[-1]
    
    # 按周期排序
    sorted_periods = sorted(available_ma)
    sorted_values = [ma_values[p] for p in sorted_periods]
    
    # 检查是否全部递增（多头排列）或全部递减（空头排列）
    is_bullish = all(sorted_values[i] < sorted_values[i+1] for i in range(len(sorted_values)-1))
    is_bearish = all(sorted_values[i] > sorted_values[i+1] for i in range(len(sorted_values)-1))
    
    if is_bullish:
        relationships['ma_alignment'] = {
            'type': '多头排列',
            'signal': 'BULLISH_ALIGNMENT',
            'strength': _calculate_alignment_strength(sorted_values)
        }
    elif is_bearish:
        relationships['ma_alignment'] = {
            'type': '空头排列',
            'signal': 'BEARISH_ALIGNMENT',
            'strength': _calculate_alignment_strength(sorted_values, reverse=True)
        }
    else:
        relationships['ma_alignment'] = {
            'type': '混乱排列',
            'signal': 'MIXED_ALIGNMENT',
            'strength': '弱'
        }
    
    # 2. 检查MA7和MA10的关系（短期趋势）
    if 7 in ma_values and 10 in ma_values:
        ma7_ma10_spread = ((ma_values[10] - ma_values[7]) / ma_values[7]) * 100
        relationships['ma7_ma10'] = {
            'spread_percent': ma7_ma10_spread,
            'ma7_above_ma10': ma_values[7] > ma_values[10],
            'short_term_signal': 'BULLISH' if ma_values[7] > ma_values[10] else 'BEARISH'
        }
    
    # 3. 检查MA7、MA10、MA30的聚合情况
    if {7, 10, 30}.issubset(set(ma_values.keys())):
        ma7 = ma_values[7]
        ma10 = ma_values[10]
        ma30 = ma_values[30]
        
        max_ma = max(ma7, ma10, ma30)
        min_ma = min(ma7, ma10, ma30)
        spread_percent = ((max_ma - min_ma) / ((ma7 + ma10 + ma30) / 3)) * 100
        
        relationships['ma_convergence_trio'] = {
            'spread_percent': spread_percent,
            'convergence_level': '高度聚合' if spread_percent < 0.3 else '中度聚合' if spread_percent < 0.5 else '分散',
            'avg_value': (ma7 + ma10 + ma30) / 3
        }
    
    # 4. 检查价格与关键均线的关系
    current_price = df['close'].iloc[-1]
    for period in [7, 10, 30]:
        if period in ma_values:
            key = f'price_vs_ma{period}'
            price_vs_ma = ((current_price - ma_values[period]) / ma_values[period]) * 100
            
            relationships[key] = {
                'percent': price_vs_ma,
                'position': '上方' if price_vs_ma > 0 else '下方',
                'distance': abs(price_vs_ma)
            }
    
    return relationships

def calculate_ma_indicators(df, periods):
    """计算移动平均线指标（支持MA7, MA10, MA30, MA60等高频策略所需均线）"""
    indicators = {}
    
    # 高频策略特别关注的均线周期
    hft_focus_periods = [7, 10, 30, 60]
    
    for period in periods:
        if len(df) >= period:
            ma_key = f'MA{period}'
            
            # 确保有计算MA值
            if ma_key not in df.columns:
                df[ma_key] = df['close'].rolling(window=period, min_periods=1).mean()
            
            current_ma = df[ma_key].iloc[-1]
            prev_ma = df[ma_key].iloc[-2] if len(df) >= period + 1 else current_ma
            
            # 判断趋势
            if current_ma > prev_ma:
                trend = "上升"
                trend_signal = "BULLISH"
            elif current_ma < prev_ma:
                trend = "下降"
                trend_signal = "BEARISH"
            else:
                trend = "持平"
                trend_signal = "NEUTRAL"
            
            # 计算变化百分比
            change_pct = ((current_ma - prev_ma) / prev_ma) * 100 if prev_ma != 0 else 0
            
            # 计算价格相对MA的位置
            current_price = df['close'].iloc[-1]
            price_vs_ma = ((current_price - current_ma) / current_ma) * 100
            
            # 基础指标信息
            ma_data = {
                'value': current_ma,
                'trend': trend,
                'signal': trend_signal,
                'change_percent': change_pct,
                'price_vs_ma': price_vs_ma,
                'period': period
            }
            
            # 针对高频策略所需均线添加额外分析
            if period in hft_focus_periods:
                # 1. MA7和MA10的短期动能分析
                if period == 7:
                    # 计算短期动量
                    ma7_momentum = _calculate_ma_momentum(df, period, lookback=3)
                    ma_data.update({
                        'momentum': ma7_momentum,
                        'is_short_term': True,
                        'role': "微观趋势指标"
                    })
                    
                # 2. MA10的趋势确认分析
                elif period == 10:
                    # 检查MA10是否在MA7和MA30之间（趋势过渡）
                    ma7_value = df['MA7'].iloc[-1] if 'MA7' in df.columns else None
                    ma30_value = df['MA30'].iloc[-1] if 'MA30' in df.columns else None
                    
                    if ma7_value and ma30_value:
                        between_7_30 = ma7_value < current_ma < ma30_value or ma30_value < current_ma < ma7_value
                        ma_data.update({
                            'between_7_30': between_7_30,
                            'role': "次级趋势指标",
                            'trend_confirmation': _check_trend_confirmation(df, period)
                        })
                
                # 3. MA30的主趋势分析
                elif period == 30:
                    # 判断主要趋势强度
                    trend_strength = _calculate_trend_strength(df, period)
                    ma_data.update({
                        'trend_strength': trend_strength,
                        'role': "主趋势指标",
                        'is_long_term': True,
                        'support_resistance': _check_support_resistance(df, current_ma)
                    })
                
                # 4. MA60的长期趋势参考
                elif period == 60:
                    ma_data.update({
                        'role': "长期趋势参考",
                        'is_very_long_term': True,
                        'market_context': _get_market_context(df, current_ma)
                    })
            
            indicators[f'ma{period}'] = ma_data
    
    # 添加均线关系分析（特别针对高频策略）
    relationships = _analyze_ma_relationships(df, periods)
    indicators.update(relationships)
    
    return indicators

def calculate_technical_indicators(df):
    """计算所有启用的技术指标 - 高频版本"""
    all_indicators = {}
    
    try:
        # 确保计算高频策略所需的所有MA
        ma_periods = TECHNICAL_INDICATORS['ma']['periods']
        
        # 强制包含高频策略所需的关键MA
        hft_required_periods = [7, 10, 30, 60]
        for period in hft_required_periods:
            if period not in ma_periods:
                ma_periods.append(period)
        
        df = df.copy()
        
        # 计算所有MA
        for period in ma_periods:
            ma_key = f'MA{period}'
            df[ma_key] = df['close'].rolling(window=period, min_periods=1).mean()
        
        # 使用修复后的calculate_ma_indicators函数
        ma_indicators = calculate_ma_indicators(df, ma_periods)
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
        
        # ATR（高频交易重要指标）
        if TECHNICAL_INDICATORS['atr']['enabled']:
            atr_indicators = calculate_atr_indicators(df, TECHNICAL_INDICATORS['atr']['period'])
            all_indicators.update(atr_indicators)
        
        # 计算均线聚合度
        convergence_indicators = calculate_ma_convergence(df, [7, 10, 30])
        all_indicators.update(convergence_indicators)
        
        # 保存技术指标历史
        if all_indicators:
            tech_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'price': df['close'].iloc[-1],
                'indicators': all_indicators
            }
            technical_history.append(tech_data)
            if len(technical_history) > 30:  # 高频交易减少历史记录长度
                technical_history.pop(0)
                
        return all_indicators
        
    except Exception as e:
        print(f"计算技术指标失败: {e}")
        return {}

def build_technical_analysis_text(indicators):
    """构建技术指标分析文本 - 高频版本"""
    if not indicators:
        return "【技术指标】数据不足计算技术指标\n"
    
    text = "【高频技术指标分析】\n"
    
    # 均线聚合度分析
    if 'ma_convergence' in indicators:
        conv_data = indicators['ma_convergence']
        text += "\n⚡ 【均线聚合度分析】\n"
        text += f"聚合度: {conv_data['spread_percent']:.3f}% ({conv_data['convergence']})\n"
        text += f"交叉信号: {conv_data['cross_signal']}\n"
        if conv_data['ma30']:
            text += f"MA7: {conv_data['ma7']:.2f} | MA10: {conv_data['ma10']:.2f} | MA30: {conv_data['ma30']:.2f}\n"
    
    # MA移动平均线
    ma_indicators = {k: v for k, v in indicators.items() if k.startswith('ma') and not k.startswith('ma_convergence')}
    if ma_indicators:
        text += "\n📈 【移动平均线分析】\n"
        for key, ma_data in sorted(ma_indicators.items()):
            if isinstance(ma_data, dict) and 'value' in ma_data:
                period = key[2:]
                text += f"MA{period}: {ma_data['value']:.2f} ({ma_data['trend']} {ma_data['change_percent']:+.3f}%)\n"
    
    # 布林带
    if 'boll' in indicators:
        boll_data = indicators['boll']
        text += "\n🎯 【布林带分析】\n"
        text += f"信号: {boll_data['signal']} | 带宽: {boll_data['width_percent']:.2f}%\n"
        text += f"位置: {boll_data['position_percent']:.1f}% | 相对中轨: {boll_data['price_vs_middle']:+.2f}%\n"
    
    # RSI
    if 'rsi' in indicators:
        rsi_data = indicators['rsi']
        text += "\n⚖️ 【RSI分析】\n"
        text += f"RSI: {rsi_data['value']:.1f} ({rsi_data['level']}) | 趋势: {rsi_data['trend']}\n"
    
    # ATR波动率
    if 'atr' in indicators:
        atr_data = indicators['atr']
        text += "\n🌊 【波动率分析(ATR)】\n"
        text += f"ATR: {atr_data['value']:.4f} | 波动率: {atr_data['percent']:.2f}% ({atr_data['volatility']})\n"
    
    # 成交量
    if 'volume' in indicators:
        volume_data = indicators['volume']
        text += "\n📦 【成交量分析】\n"
        text += f"成交量状态: {volume_data['level']} | 相对均量: {volume_data['vs_average']:+.1f}%\n"
    
    return text

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
    prev_rsi = df['RSI'].iloc[-2] if len(df) > period + 1 else current_rsi
    
    # 判断超买超卖
    if current_rsi >= 70:
        level = "超买"
        signal = "OVERBOUGHT"
    elif current_rsi <= 30:
        level = "超卖"
        signal = "OVERSOLD"
    else:
        level = "正常"
        signal = "NEUTRAL"
    
    # 判断趋势
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
            'prev_value': prev_rsi,
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
    
    prev_macd = df['MACD'].iloc[-2] if len(df) > slow_period + signal_period else current_macd
    prev_signal = df['MACD_SIGNAL'].iloc[-2] if len(df) > slow_period + signal_period else current_signal
    
    # 判断金叉死叉
    if current_macd > current_signal and prev_macd <= prev_signal:
        cross_signal = "金叉"
        cross_direction = "GOLDEN_CROSS"
    elif current_macd < current_signal and prev_macd >= prev_signal:
        cross_signal = "死叉"
        cross_direction = "DEAD_CROSS"
    else:
        cross_signal = "无交叉"
        cross_direction = "NO_CROSS"
    
    # 判断趋势
    if current_hist > 0:
        trend = "多头"
        trend_signal = "BULLISH"
    else:
        trend = "空头"
        trend_signal = "BEARISH"
    
    return {
        'macd': {
            'macd': current_macd,
            'signal': current_signal,
            'histogram': current_hist,
            'cross_signal': cross_signal,
            'cross_direction': cross_direction,
            'trend': trend,
            'trend_signal': trend_signal
        }
    }

def calculate_volume_indicators(df, period=20):
    """计算成交量指标"""
    if len(df) < period:
        return {}
    
    current_volume = df['volume'].iloc[-1]
    avg_volume = df['volume'].rolling(window=period).mean().iloc[-1]
    
    vs_average = ((current_volume - avg_volume) / avg_volume) * 100 if avg_volume > 0 else 0
    
    # 判断成交量水平
    if vs_average > 50:
        level = "巨量"
        signal = "HIGH_VOLUME"
    elif vs_average > 20:
        level = "放量"
        signal = "MEDIUM_VOLUME"
    elif vs_average < -50:
        level = "极度缩量"
        signal = "EXTREME_LOW_VOLUME"
    elif vs_average < -20:
        level = "缩量"
        signal = "LOW_VOLUME"
    else:
        level = "正常量能"
        signal = "NORMAL_VOLUME"
    
    # 检查价量配合
    price_change = ((df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]) * 100
    if (price_change > 0 and vs_average > 0) or (price_change < 0 and vs_average > 20):
        price_volume_confirmation = "价量配合良好"
        confirmation_signal = "CONFIRMED"
    else:
        price_volume_confirmation = "价量背离"
        confirmation_signal = "DIVERGENCE"
    
    return {
        'volume': {
            'current': current_volume,
            'average': avg_volume,
            'vs_average': vs_average,
            'level': level,
            'signal': signal,
            'price_volume_confirmation': price_volume_confirmation,
            'confirmation_signal': confirmation_signal
        }
    }