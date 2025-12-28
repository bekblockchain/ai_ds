"""
高频策略核心逻辑 - 均线聚合 + 布林中轨突破
"""
import time
from datetime import datetime
from config import TRADE_CONFIG, SUPPORTED_SYMBOLS, HIGH_FREQUENCY_STATE

class HFTStrategy:
    """高频交易策略管理器"""
    
    def __init__(self):
        self.strategy_name = "均线聚合布林突破高频策略"
        self.version = "1.0"
        self.parameters = {
            'ma_periods': [7, 10, 30, 60],
            'boll_period': 20,
            'boll_std': 2,
            'convergence_threshold': 0.3,  # 聚合度阈值（%）
            'breakout_threshold': 0.1,     # 突破阈值（%）
            'volume_multiplier': 1.2,      # 成交量倍数
            'quick_tp_percent': 0.3,       # 快速止盈百分比
            'quick_sl_percent': 0.2,       # 快速止损百分比
            'max_holding_time': 3600,      # 最大持仓时间（秒）
            'min_holding_time': 300        # 最小持仓时间（秒）
        }
        self.signal_history = {}
        self.trade_log = []
        
    def analyze_ma_convergence(self, technical_indicators):
        """分析均线聚合情况"""
        try:
            # 获取MA值
            ma7 = technical_indicators.get('ma7', {}).get('value', 0)
            ma10 = technical_indicators.get('ma10', {}).get('value', 0)
            ma30 = technical_indicators.get('ma30', {}).get('value', 0)
            
            if ma7 == 0 or ma10 == 0 or ma30 == 0:
                return None
            
            # 计算聚合度
            max_ma = max(ma7, ma10, ma30)
            min_ma = min(ma7, ma10, ma30)
            spread = max_ma - min_ma
            spread_percent = (spread / ((ma7 + ma10 + ma30) / 3)) * 100
            
            # 判断聚合状态
            if spread_percent < self.parameters['convergence_threshold']:
                convergence_level = "高度聚合"
                signal_strength = "STRONG"
            elif spread_percent < self.parameters['convergence_threshold'] * 2:
                convergence_level = "中度聚合"
                signal_strength = "MEDIUM"
            else:
                convergence_level = "分散"
                signal_strength = "WEAK"
            
            # 判断均线排列
            if ma7 > ma10 > ma30:
                ma_alignment = "多头排列"
                alignment_signal = "BULLISH"
            elif ma7 < ma10 < ma30:
                ma_alignment = "空头排列"
                alignment_signal = "BEARISH"
            else:
                ma_alignment = "混乱排列"
                alignment_signal = "NEUTRAL"
            
            return {
                'spread_percent': spread_percent,
                'convergence_level': convergence_level,
                'signal_strength': signal_strength,
                'ma_alignment': ma_alignment,
                'alignment_signal': alignment_signal,
                'ma7': ma7,
                'ma10': ma10,
                'ma30': ma30
            }
            
        except Exception as e:
            print(f"均线聚合分析失败: {e}")
            return None
    
    def analyze_boll_breakout(self, technical_indicators, current_price):
        """分析布林带突破情况"""
        try:
            boll_data = technical_indicators.get('boll', {})
            if not boll_data:
                return None
            
            middle = boll_data.get('middle', current_price)
            price_vs_middle = ((current_price - middle) / middle) * 100
            
            # 判断突破状态
            if price_vs_middle > self.parameters['breakout_threshold']:
                breakout_status = "突破中轨向上"
                breakout_signal = "BULLISH_BREAKOUT"
                strength = abs(price_vs_middle) / self.parameters['breakout_threshold']
            elif price_vs_middle < -self.parameters['breakout_threshold']:
                breakout_status = "跌破中轨向下"
                breakout_signal = "BEARISH_BREAKOUT"
                strength = abs(price_vs_middle) / self.parameters['breakout_threshold']
            else:
                breakout_status = "在中轨附近"
                breakout_signal = "NO_BREAKOUT"
                strength = 0
            
            # 检查布林带宽度
            width_percent = boll_data.get('width_percent', 0)
            if width_percent < 1.0:
                volatility_status = "低波动"
            elif width_percent < 2.0:
                volatility_status = "正常波动"
            else:
                volatility_status = "高波动"
            
            return {
                'price_vs_middle': price_vs_middle,
                'breakout_status': breakout_status,
                'breakout_signal': breakout_signal,
                'breakout_strength': strength,
                'volatility_status': volatility_status,
                'boll_width': width_percent
            }
            
        except Exception as e:
            print(f"布林带突破分析失败: {e}")
            return None
    
    def analyze_volume_confirmation(self, technical_indicators):
        """分析成交量确认"""
        try:
            volume_data = technical_indicators.get('volume', {})
            if not volume_data:
                return None
            
            vs_average = volume_data.get('vs_average', 0)
            level = volume_data.get('level', '正常量能')
            
            # 判断成交量状态
            if vs_average > 50:
                volume_status = "明显放量"
                volume_signal = "HIGH_VOLUME"
                confirmation = True
            elif vs_average > 20:
                volume_status = "温和放量"
                volume_signal = "MEDIUM_VOLUME"
                confirmation = True
            elif vs_average < -50:
                volume_status = "明显缩量"
                volume_signal = "LOW_VOLUME"
                confirmation = False
            else:
                volume_status = "正常量能"
                volume_signal = "NORMAL_VOLUME"
                confirmation = True
            
            return {
                'volume_status': volume_status,
                'volume_signal': volume_signal,
                'vs_average': vs_average,
                'confirmation': confirmation
            }
            
        except Exception as e:
            print(f"成交量分析失败: {e}")
            return None
    
    def generate_trading_signal(self, symbol, current_price, technical_indicators):
        """生成高频交易信号"""
        try:
            symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
            
            # 分析各个组件
            ma_analysis = self.analyze_ma_convergence(technical_indicators)
            boll_analysis = self.analyze_boll_breakout(technical_indicators, current_price)
            volume_analysis = self.analyze_volume_confirmation(technical_indicators)
            
            if not ma_analysis or not boll_analysis:
                return None
            
            # 提取关键指标
            convergence_level = ma_analysis['convergence_level']
            ma_alignment = ma_analysis['ma_alignment']
            breakout_status = boll_analysis['breakout_status']
            breakout_signal = boll_analysis['breakout_signal']
            volume_confirmation = volume_analysis['confirmation'] if volume_analysis else True
            
            # 信号生成逻辑
            signal = None
            reason = ""
            confidence = "LOW"
            
            # 条件1：均线高度聚合 + 突破中轨向上 + 成交量确认
            if (convergence_level == "高度聚合" and 
                breakout_signal == "BULLISH_BREAKOUT" and
                volume_confirmation):
                
                signal = "BUY"
                reason = f"均线高度聚合({ma_analysis['spread_percent']:.2f}%) + {breakout_status} + 成交量确认"
                confidence = "HIGH"
            
            # 条件2：均线高度聚合 + 跌破中轨向下 + 成交量确认
            elif (convergence_level == "高度聚合" and 
                  breakout_signal == "BEARISH_BREAKOUT" and
                  volume_confirmation):
                
                signal = "SELL"
                reason = f"均线高度聚合({ma_analysis['spread_percent']:.2f}%) + {breakout_status} + 成交量确认"
                confidence = "HIGH"
            
            # 条件3：均线中度聚合 + 明确突破 + 均线同向排列
            elif (convergence_level == "中度聚合" and
                  breakout_signal in ["BULLISH_BREAKOUT", "BEARISH_BREAKOUT"] and
                  ma_alignment in ["多头排列", "空头排列"]):
                
                signal = "BUY" if breakout_signal == "BULLISH_BREAKOUT" else "SELL"
                reason = f"均线中度聚合({ma_analysis['spread_percent']:.2f}%) + {breakout_status} + {ma_alignment}"
                confidence = "MEDIUM"
            
            if signal:
                # 构建完整信号数据
                signal_data = {
                    'symbol': symbol,
                    'signal': signal,
                    'reason': reason,
                    'confidence': confidence,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'analysis': {
                        'ma': ma_analysis,
                        'boll': boll_analysis,
                        'volume': volume_analysis
                    },
                    'current_price': current_price,
                    'quick_signal': confidence == "HIGH"  # 高信心信号标记为快速信号
                }
                
                # 计算快速止盈止损价格
                if signal == "BUY":
                    sl_price = current_price * (1 - self.parameters['quick_sl_percent'] / 100)
                    tp_price = current_price * (1 + self.parameters['quick_tp_percent'] / 100)
                else:
                    sl_price = current_price * (1 + self.parameters['quick_sl_percent'] / 100)
                    tp_price = current_price * (1 - self.parameters['quick_tp_percent'] / 100)
                
                signal_data['quick_stop_loss'] = sl_price
                signal_data['quick_take_profit'] = tp_price
                
                # 记录信号历史
                self.record_signal(symbol, signal_data)
                
                print(f"✅ {symbol_name} 高频策略信号: {signal} ({confidence})")
                print(f"   理由: {reason}")
                print(f"   快速止损: {sl_price:.4f}")
                print(f"   快速止盈: {tp_price:.4f}")
                
                return signal_data
            
            return None
            
        except Exception as e:
            print(f"生成交易信号失败: {e}")
            return None
    
    def record_signal(self, symbol, signal_data):
        """记录信号历史"""
        if symbol not in self.signal_history:
            self.signal_history[symbol] = []
        
        self.signal_history[symbol].append(signal_data)
        
        # 保持最近20个信号
        if len(self.signal_history[symbol]) > 20:
            self.signal_history[symbol].pop(0)
    
    def get_signal_statistics(self, symbol=None):
        """获取信号统计"""
        if symbol:
            signals = self.signal_history.get(symbol, [])
        else:
            signals = []
            for sym_sigs in self.signal_history.values():
                signals.extend(sym_sigs)
        
        if not signals:
            return None
        
        total = len(signals)
        buy_signals = sum(1 for s in signals if s['signal'] == 'BUY')
        sell_signals = sum(1 for s in signals if s['signal'] == 'SELL')
        high_confidence = sum(1 for s in signals if s['confidence'] == 'HIGH')
        
        return {
            'total_signals': total,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'high_confidence_ratio': (high_confidence / total * 100) if total > 0 else 0
        }
    
    def should_reverse_position(self, position, technical_indicators, current_price):
        """判断是否应该反手"""
        try:
            if not position:
                return False
            
            symbol = position['symbol']
            side = position['side']
            entry_price = position['entry_price']
            
            # 分析当前市场状况
            ma_analysis = self.analyze_ma_convergence(technical_indicators)
            boll_analysis = self.analyze_boll_breakout(technical_indicators, current_price)
            
            if not ma_analysis or not boll_analysis:
                return False
            
            # 计算盈亏
            if side == 'long':
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
            
            # 反手条件1：亏损且市场反转
            if pnl_percent < -0.5:  # 亏损超过0.5%
                convergence_level = ma_analysis['convergence_level']
                breakout_signal = boll_analysis['breakout_signal']
                
                # 如果均线聚合且出现反向突破
                if convergence_level in ["高度聚合", "中度聚合"]:
                    if side == 'long' and breakout_signal == "BEARISH_BREAKOUT":
                        return True, "SELL"
                    elif side == 'short' and breakout_signal == "BULLISH_BREAKOUT":
                        return True, "BUY"
            
            return False, None
            
        except Exception as e:
            print(f"反手判断失败: {e}")
            return False, None

# 全局策略实例
hft_strategy = HFTStrategy()