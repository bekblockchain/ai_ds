import time
from datetime import datetime
from config import (TRADE_CONFIG, RISK_MANAGEMENT, SUPPORTED_SYMBOLS, 
                   HIGH_FREQUENCY_STATE, can_trade_hft, update_hft_state)
from exchange_api import (get_current_position, calculate_position_metrics, 
                         check_stop_loss_condition, check_take_profit_condition, 
                         check_stop_orders_status, cancel_stop_orders)

class RiskManager:
    def __init__(self, exchange):
        self.exchange = exchange
        self.last_check_time = 0
        self.check_interval = 5  # 5秒检查一次
        self.daily_loss = 0
        self.consecutive_losses = 0
        self.trade_history = []
        self.quick_profit_targets = {}  # 快速止盈目标记录

    def monitor_positions(self, current_price_dict):
        """监控所有持仓并确保止损单有效（高频版本）"""
        current_time = time.time()
        
        # 高频监控：每5秒执行一次
        if current_time - self.last_check_time < self.check_interval:
            return None
            
        self.last_check_time = current_time
        
        risk_signals = []
        
        # 获取所有持仓
        all_positions = get_current_position(self.exchange)
        if not all_positions:
            return None
            
        for position in all_positions:
            symbol = position['symbol']
            if symbol in current_price_dict:
                current_price = current_price_dict[symbol]
                
                # 计算持仓指标
                position_metrics = calculate_position_metrics(position, current_price)
                if not position_metrics:
                    continue
                
                # 检查止损单状态
                stop_order_status = check_stop_orders_status(self.exchange, symbol)
                if "无活跃止损单" in stop_order_status or "已触发" in stop_order_status:
                    print(f"⚠️ {symbol}无有效止损单，立即设置快速止损...")
                    from exchange_api import create_quick_stop_loss
                    create_quick_stop_loss(self.exchange, symbol, position['side'], 
                                          position['size'], position['entry_price'])
                
                # 高频特有：检查快速止盈条件
                quick_tp_signal = self.check_quick_take_profit(position, position_metrics, current_price)
                if quick_tp_signal:
                    risk_signals.append(quick_tp_signal)
                    continue
                
                # 检查移动止损条件（高频优化版）
                trailing_stop_signal = self.check_hft_trailing_stop(position, position_metrics, current_price)
                if trailing_stop_signal:
                    risk_signals.append(trailing_stop_signal)
                    continue
                
                # 检查紧急止损条件
                emergency_stop_signal = self.check_emergency_stop_loss(position, position_metrics)
                if emergency_stop_signal:
                    risk_signals.append(emergency_stop_signal)
                    continue
                    
                # 检查持仓时间（高频交易不宜持仓过久）
                time_stop_signal = self.check_holding_time(position)
                if time_stop_signal:
                    risk_signals.append(time_stop_signal)
                    continue
                
                # 检查反手交易条件
                reversal_signal = self.check_reversal_condition(position, position_metrics, current_price)
                if reversal_signal:
                    risk_signals.append(reversal_signal)
        
        return risk_signals if risk_signals else None
    
    def check_quick_take_profit(self, position, position_metrics, current_price):
        """检查快速止盈条件（高频交易特有）"""
        try:
            symbol = position['symbol']
            pnl_percent = position_metrics['current_pnl_percent']
            
            # 快速止盈条件1：达到0.3%盈利
            if pnl_percent >= RISK_MANAGEMENT['quick_take_profit_percent']:
                return {
                    'symbol': symbol,
                    'action': 'QUICK_TAKE_PROFIT',
                    'reason': f'达到快速止盈条件: {pnl_percent:.2f}% ≥ {RISK_MANAGEMENT["quick_take_profit_percent"]}%',
                    'position': position,
                    'metrics': position_metrics,
                    'urgency': 'HIGH'
                }
            
            # 快速止盈条件2：价格触及快速止盈价
            quick_tp_price = self.calculate_quick_take_profit_price(position['entry_price'], position['side'])
            if (position['side'] == 'long' and current_price >= quick_tp_price) or \
               (position['side'] == 'short' and current_price <= quick_tp_price):
                return {
                    'symbol': symbol,
                    'action': 'QUICK_TAKE_PROFIT',
                    'reason': f'价格触及快速止盈价: {current_price:.4f}',
                    'position': position,
                    'metrics': position_metrics,
                    'urgency': 'HIGH'
                }
            
            return None
            
        except Exception as e:
            print(f"检查快速止盈条件失败: {e}")
            return None
    
    def check_hft_trailing_stop(self, position, position_metrics, current_price):
        """检查高频移动止损条件"""
        if RISK_MANAGEMENT['trailing_stop_percent'] <= 0:
            return None
        
        symbol = position['symbol']
        entry_price = position['entry_price']
        side = position['side']
        pnl_percent = position_metrics['current_pnl_percent']
        
        # 只有盈利超过一定比例才启用移动止损
        if pnl_percent >= 0.2:  # 盈利超过0.2%
            if side == 'long':
                # 计算移动止损价（基于最高价）
                if not hasattr(self, f'trailing_high_{symbol}'):
                    setattr(self, f'trailing_high_{symbol}', current_price)
                else:
                    current_high = getattr(self, f'trailing_high_{symbol}')
                    if current_price > current_high:
                        setattr(self, f'trailing_high_{symbol}', current_price)
                    
                    trailing_stop_price = getattr(self, f'trailing_high_{symbol}') * \
                                         (1 - RISK_MANAGEMENT['trailing_stop_percent'] / 100 / TRADE_CONFIG['leverage'])
                    
                    if current_price <= trailing_stop_price:
                        return {
                            'symbol': symbol,
                            'action': 'TRAILING_STOP',
                            'reason': f'触发移动止损，从最高点回撤{RISK_MANAGEMENT["trailing_stop_percent"]}%',
                            'position': position,
                            'metrics': position_metrics,
                            'urgency': 'MEDIUM'
                        }
            
            else:  # short
                if not hasattr(self, f'trailing_low_{symbol}'):
                    setattr(self, f'trailing_low_{symbol}', current_price)
                else:
                    current_low = getattr(self, f'trailing_low_{symbol}')
                    if current_price < current_low:
                        setattr(self, f'trailing_low_{symbol}', current_price)
                    
                    trailing_stop_price = getattr(self, f'trailing_low_{symbol}') * \
                                         (1 + RISK_MANAGEMENT['trailing_stop_percent'] / 100 / TRADE_CONFIG['leverage'])
                    
                    if current_price >= trailing_stop_price:
                        return {
                            'symbol': symbol,
                            'action': 'TRAILING_STOP',
                            'reason': f'触发移动止损，从最低点反弹{RISK_MANAGEMENT["trailing_stop_percent"]}%',
                            'position': position,
                            'metrics': position_metrics,
                            'urgency': 'MEDIUM'
                        }
        
        return None
    
    def check_emergency_stop_loss(self, position, position_metrics):
        """检查紧急止损条件"""
        pnl_percent = position_metrics['current_pnl_percent']
        
        if pnl_percent <= -RISK_MANAGEMENT['emergency_stop_loss']:
            return {
                'symbol': position['symbol'],
                'action': 'EMERGENCY_STOP',
                'reason': f'触发紧急止损: {pnl_percent:.2f}% ≤ -{RISK_MANAGEMENT["emergency_stop_loss"]}%',
                'position': position,
                'metrics': position_metrics,
                'urgency': 'CRITICAL'
            }
        
        return None
    
    def check_holding_time(self, position):
        """检查持仓时间（高频交易不宜持仓过久）"""
        try:
            symbol = position['symbol']
            holding_time = position.get('holding_time', 0)
            
            # 高频交易最大持仓时间：60分钟
            if holding_time > 3600:  # 3600秒 = 60分钟
                return {
                    'symbol': symbol,
                    'action': 'TIME_STOP',
                    'reason': f'持仓时间过长: {holding_time//60}分钟 ≥ 60分钟',
                    'position': position,
                    'metrics': None,
                    'urgency': 'MEDIUM'
                }
            
            return None
            
        except Exception as e:
            print(f"检查持仓时间失败: {e}")
            return None
    
    def check_reversal_condition(self, position, position_metrics, current_price):
        """检查反手交易条件"""
        try:
            symbol = position['symbol']
            pnl_percent = position_metrics['current_pnl_percent']
            side = position['side']
            
            # 反手条件1：亏损超过0.5%且价格反向突破关键位置
            if pnl_percent < -0.5:
                # 获取技术指标数据
                from data_fetcher import get_ohlcv
                from technical_analyzer import calculate_technical_indicators
                
                price_data = get_ohlcv(self.exchange, symbol)
                if price_data:
                    technical_indicators = calculate_technical_indicators(price_data['full_data'])
                    
                    # 检查均线聚合和布林带
                    ma_convergence = technical_indicators.get('ma_convergence', {})
                    boll_data = technical_indicators.get('boll', {})
                    
                    spread_percent = ma_convergence.get('spread_percent', 100)
                    price_vs_middle = boll_data.get('price_vs_middle', 0)
                    
                    # 如果均线高度聚合且价格反向突破中轨，考虑反手
                    if spread_percent < 0.3:
                        if side == 'long' and price_vs_middle < -0.2:  # 多仓但价格低于中轨0.2%
                            return {
                                'symbol': symbol,
                                'action': 'REVERSAL_SELL',
                                'reason': f'亏损{pnl_percent:.2f}% + 均线聚合 + 价格低于布林中轨，建议反手做空',
                                'position': position,
                                'metrics': position_metrics,
                                'urgency': 'HIGH',
                                'new_side': 'short'
                            }
                        elif side == 'short' and price_vs_middle > 0.2:  # 空仓但价格高于中轨0.2%
                            return {
                                'symbol': symbol,
                                'action': 'REVERSAL_BUY',
                                'reason': f'亏损{pnl_percent:.2f}% + 均线聚合 + 价格高于布林中轨，建议反手做多',
                                'position': position,
                                'metrics': position_metrics,
                                'urgency': 'HIGH',
                                'new_side': 'long'
                            }
            
            return None
            
        except Exception as e:
            print(f"检查反手条件失败: {e}")
            return None
    
    def execute_risk_management(self, risk_signals):
        """执行风险管理操作（高频版本）"""
        if not risk_signals:
            return
        
        for risk_signal in risk_signals:
            symbol = risk_signal['symbol']
            position = risk_signal['position']
            action = risk_signal['action']
            reason = risk_signal['reason']
            urgency = risk_signal.get('urgency', 'MEDIUM')
            
            symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
            
            print(f"🚨 {symbol_name}({symbol}) {urgency}紧急风险管理: {action} - {reason}")
            
            try:
                # 先取消可能的止损单
                cancel_stop_orders(self.exchange, symbol)
                
                # 根据不同action执行不同操作
                if action in ['QUICK_TAKE_PROFIT', 'TRAILING_STOP', 'EMERGENCY_STOP', 'TIME_STOP']:
                    # 平仓操作
                    if position['side'] == 'long':
                        self.exchange.create_market_sell_order(
                            symbol,
                            position['size'],
                            {'posSide': 'long', 'reduceOnly': True}
                        )
                        result = 'profit' if 'TAKE_PROFIT' in action else 'loss'
                    else:
                        self.exchange.create_market_buy_order(
                            symbol,
                            position['size'],
                            {'posSide': 'short', 'reduceOnly': True}
                        )
                        result = 'profit' if 'TAKE_PROFIT' in action else 'loss'
                    
                    print(f"✅ 执行{action}，数量: {position['size']}")
                    update_hft_state(result)
                    
                elif action in ['REVERSAL_BUY', 'REVERSAL_SELL']:
                    # 反手交易
                    new_side = risk_signal['new_side']
                    
                    # 先平仓
                    if position['side'] == 'long':
                        self.exchange.create_market_sell_order(
                            symbol,
                            position['size'],
                            {'posSide': 'long', 'reduceOnly': True}
                        )
                    else:
                        self.exchange.create_market_buy_order(
                            symbol,
                            position['size'],
                            {'posSide': 'short', 'reduceOnly': True}
                        )
                    
                    print(f"✅ 平仓完成，准备反手开{new_side}仓")
                    
                    # 短暂等待后反向开仓（使用原仓位的60%）
                    time.sleep(0.5)
                    reversal_amount = position['size'] * 0.6
                    
                    if new_side == 'long':
                        order = self.exchange.create_market_buy_order(
                            symbol,
                            reversal_amount,
                            {'posSide': 'long'}
                        )
                    else:
                        order = self.exchange.create_market_sell_order(
                            symbol,
                            reversal_amount,
                            {'posSide': 'short'}
                        )
                    
                    print(f"✅ 反手{new_side}仓已开，数量: {reversal_amount}")
                    
                    # 设置快速止损止盈
                    if order and 'average' in order and order['average']:
                        entry_price = order['average']
                        from exchange_api import create_quick_stop_loss, create_quick_take_profit
                        create_quick_stop_loss(self.exchange, symbol, new_side, reversal_amount, entry_price)
                        create_quick_take_profit(self.exchange, symbol, new_side, reversal_amount, entry_price)
                    
                    update_hft_state('reversal')
                
                # 记录风险管理操作
                self.record_risk_management_action(risk_signal)
                    
            except Exception as e:
                print(f"❌ {symbol}紧急风险管理失败: {e}")
                update_hft_state('error')
    
    def calculate_quick_take_profit_price(self, entry_price, side):
        """计算快速止盈价格"""
        if side == 'long':
            return entry_price * (1 + RISK_MANAGEMENT['quick_take_profit_percent'] / 100 / TRADE_CONFIG['leverage'])
        else:
            return entry_price * (1 - RISK_MANAGEMENT['quick_take_profit_percent'] / 100 / TRADE_CONFIG['leverage'])
    
    def record_risk_management_action(self, risk_signal):
        """记录风险管理操作"""
        log_entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': risk_signal['symbol'],
            'action': risk_signal['action'],
            'reason': risk_signal['reason'],
            'position': risk_signal['position'],
            'metrics': risk_signal.get('metrics'),
            'urgency': risk_signal.get('urgency', 'MEDIUM')
        }
        
        self.trade_history.append(log_entry)
        if len(self.trade_history) > 100:
            self.trade_history.pop(0)
        
        print(f"📝 记录风险管理: {log_entry}")
    
    def get_risk_summary(self, position, current_price):
        """获取风险摘要（高频版本）"""
        if not position:
            return "无持仓"
            
        metrics = calculate_position_metrics(position, current_price)
        if not metrics:
            return "无法计算风险指标"
            
        symbol_name = SUPPORTED_SYMBOLS[position['symbol']]['name']
        
        # 检查止损单状态
        stop_order_status = check_stop_orders_status(self.exchange, position['symbol'])
        
        # 计算快速止盈价
        quick_tp_price = self.calculate_quick_take_profit_price(position['entry_price'], position['side'])
        quick_tp_distance = abs((current_price - quick_tp_price) / current_price * 100)
        
        # 计算持仓时间
        holding_time = position.get('holding_time', 0)
        holding_time_min = holding_time // 60
        holding_time_sec = holding_time % 60
        
        summary = f"""
🔐 {symbol_name}高频风险监控摘要:
────────────────
持仓方向: {position['side']}
持仓数量: {position['size']}
入场价格: {position['entry_price']:.4f}
当前价格: {current_price:.4f}
持仓时间: {holding_time_min}分{holding_time_sec}秒
当前盈亏: {metrics['current_pnl']:.2f} USDT ({metrics['current_pnl_percent']:.2f}%)
快速止盈价: {quick_tp_price:.4f} (距离: {quick_tp_distance:.2f}%)
止损价格: {metrics['stop_loss_price']:.4f}
距止损: {metrics['stop_loss_distance_percent']:.2f}%
风险收益比: {metrics['risk_reward_ratio']:.2f}
止损单状态: {stop_order_status}
────────────────
【高频交易提示】
快速止盈目标: {RISK_MANAGEMENT['quick_take_profit_percent']}%
快速止损保护: {RISK_MANAGEMENT['quick_stop_loss_percent']}%
建议最大持仓: 60分钟
────────────────
"""
        return summary
    
    def get_daily_performance(self):
        """获取当日绩效统计"""
        profitable_trades = sum(1 for trade in self.trade_history 
                              if trade['action'] in ['QUICK_TAKE_PROFIT', 'TRAILING_STOP'])
        total_trades = len(self.trade_history)
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'win_rate': win_rate,
            'consecutive_losses': self.consecutive_losses,
            'daily_loss': self.daily_loss
        }