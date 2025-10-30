import time
from config import TRADE_CONFIG, RISK_MANAGEMENT, SUPPORTED_SYMBOLS
from exchange_api import get_current_position, calculate_position_metrics, check_stop_loss_condition, check_take_profit_condition, check_stop_orders_status

class RiskManager:
    def __init__(self, exchange):
        self.exchange = exchange
        self.last_check_time = 0
        self.check_interval = 5
        
    def monitor_positions(self, current_price_dict):
        """监控所有持仓并确保止损单有效"""
        current_time = time.time()
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
                    print(f"⚠️ {symbol}无有效止损单，立即设置...")
                    from exchange_api import create_stop_loss_order
                    create_stop_loss_order(self.exchange, symbol, position['side'], position['size'], position['entry_price'])
                    
                # 检查止盈止损条件（备用，主要依赖交易所止损单）
                if check_stop_loss_condition(position_metrics):
                    action = "STOP_LOSS"
                    reason = f"触发止损，当前亏损: {position_metrics['current_pnl_percent']:.2f}%"
                    
                elif check_take_profit_condition(position_metrics):
                    action = "TAKE_PROFIT" 
                    reason = f"触发止盈，当前盈利: {position_metrics['current_pnl_percent']:.2f}%"
                    
                elif self.check_trailing_stop(position, position_metrics, current_price):
                    action = "TRAILING_STOP"
                    reason = "触发移动止损"
                
                if action:
                    risk_signals.append({
                        'symbol': symbol,
                        'action': action,
                        'reason': reason,
                        'position': position,
                        'metrics': position_metrics
                    })
                    
        return risk_signals if risk_signals else None
    
    def check_trailing_stop(self, position, position_metrics, current_price):
        """检查移动止损条件"""
        if RISK_MANAGEMENT['trailing_stop_percent'] <= 0:
            return False
            
        if position_metrics['current_pnl_percent'] > 10:
            if position['side'] == 'long':
                trailing_stop_price = current_price * (1 - RISK_MANAGEMENT['trailing_stop_percent'] / 100 / TRADE_CONFIG['leverage'])
                if current_price <= trailing_stop_price:
                    return True
            else:
                trailing_stop_price = current_price * (1 + RISK_MANAGEMENT['trailing_stop_percent'] / 100 / TRADE_CONFIG['leverage'])
                if current_price >= trailing_stop_price:
                    return True
                    
        return False
    
    def execute_risk_management(self, risk_signals):
        """执行风险管理操作"""
        if not risk_signals:
            return
            
        for risk_signal in risk_signals:
            symbol = risk_signal['symbol']
            position = risk_signal['position']
            action = risk_signal['action']
            reason = risk_signal['reason']
            
            symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
            
            print(f"🚨 {symbol_name}({symbol}) 执行紧急风险管理: {action} - {reason}")
            
            try:
                # 先取消可能的止损单
                from exchange_api import cancel_stop_orders
                cancel_stop_orders(self.exchange, symbol)
                
                # 执行平仓
                if position['side'] == 'long':
                    self.exchange.create_market_sell_order(
                        symbol,
                        position['size'],
                        {'posSide': 'long'}
                    )
                    print(f"✅ 紧急平多仓，数量: {position['size']}")
                else:
                    self.exchange.create_market_buy_order(
                        symbol,
                        position['size'],
                        {'posSide': 'short'}
                    )
                    print(f"✅ 紧急平空仓，数量: {position['size']}")
                    
                self.record_risk_management_action(risk_signal)
                    
            except Exception as e:
                print(f"❌ {symbol}紧急风险管理失败: {e}")
    
    def record_risk_management_action(self, risk_signal):
        """记录风险管理操作"""
        log_entry = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': risk_signal['symbol'],
            'action': risk_signal['action'],
            'reason': risk_signal['reason'],
            'position': risk_signal['position'],
            'metrics': risk_signal['metrics']
        }
        print(f"📝 记录紧急风险管理: {log_entry}")
    
    def get_risk_summary(self, position, current_price):
        """获取风险摘要"""
        if not position:
            return "无持仓"
            
        metrics = calculate_position_metrics(position, current_price)
        if not metrics:
            return "无法计算风险指标"
            
        symbol_name = SUPPORTED_SYMBOLS[position['symbol']]['name']
        
        # 检查止损单状态
        stop_order_status = check_stop_orders_status(self.exchange, position['symbol'])
            
        summary = f"""
🔐 {symbol_name}风险监控摘要:
────────────────
持仓方向: {position['side']}
持仓数量: {position['size']}
入场价格: {position['entry_price']:.4f}
当前价格: {current_price:.4f}
当前盈亏: {metrics['current_pnl']:.2f} USDT ({metrics['current_pnl_percent']:.2f}%)
止损价格: {metrics['stop_loss_price']:.4f}
止盈价格: {metrics['take_profit_price']:.4f}
距止损: {metrics['stop_loss_distance_percent']:.2f}%
距止盈: {metrics['take_profit_distance_percent']:.2f}%
风险收益比: {metrics['risk_reward_ratio']:.2f}
止损单状态: {stop_order_status}
────────────────
"""
        return summary