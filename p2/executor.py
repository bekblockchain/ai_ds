import time
from exchange_api import (get_current_position, can_open_new_trade, 
                         create_stop_loss_order, create_take_profit_order, 
                         cancel_stop_orders, check_stop_orders_status, 
                         create_quick_stop_loss, create_quick_take_profit)

# 然后移除函数内部的 from exchange_api import get_current_position
from config import (TRADE_CONFIG, SUPPORTED_SYMBOLS, get_trade_amount, 
                   get_dynamic_position_size, update_hft_state, can_trade_hft,
                   RISK_MANAGEMENT)
from exchange_api import (can_open_new_trade, create_stop_loss_order, 
                         create_take_profit_order, cancel_stop_orders, 
                         check_stop_orders_status, create_quick_stop_loss,
                         create_quick_take_profit)

def execute_trade(exchange, risk_manager, signal_data, price_data):
    """执行高频交易并设置快速止损单"""
    from exchange_api import get_current_position
    
    symbol = price_data['symbol']
    current_position = get_current_position(exchange, symbol)
    current_price = price_data['price']
    symbol_name = SUPPORTED_SYMBOLS[symbol]['name']

    print(f"\n🎯 {symbol_name}({symbol}) 高频交易执行:")
    print(f"📊 交易信号: {signal_data['signal']}")
    print(f"💪 信心程度: {signal_data['confidence']}")
    print(f"📝 理由: {signal_data['reason']}")
    
    # 检查是否为快速信号
    is_quick_signal = signal_data.get('quick_signal', False)
    
    if is_quick_signal:
        print("⚡ 检测到快速交易信号，使用高频参数")
    
    # 显示止损单状态
    stop_order_status = check_stop_orders_status(exchange, symbol)
    print(f"🛡️ 止损单状态: {stop_order_status}")
    
    # 显示风险摘要
    risk_summary = risk_manager.get_risk_summary(current_position, current_price)
    print(risk_summary)

    if TRADE_CONFIG['test_mode']:
        print("🧪 测试模式 - 仅模拟交易")
        return

    try:
        # 检查是否可以开新仓
        can_trade = can_open_new_trade(exchange)
        
        if signal_data['signal'] == 'BUY':
            if current_position and current_position['side'] == 'short':
                print("🔄 平空仓...")
                # 先取消空仓的止损单
                cancel_stop_orders(exchange, symbol)
                # 执行平仓
                exchange.create_market_buy_order(
                    symbol,
                    current_position['size'],
                    {'posSide': 'short'}
                )
                print("✅ 空仓已平")
                update_hft_state('close_short')
                
            elif not current_position and can_trade:
                # 高频交易：检查是否超过每日限制
                if not can_trade_hft():
                    print("🚫 高频交易限制，无法开新仓")
                    return
                
                # 动态计算仓位大小
                signal_strength = signal_data.get('confidence', 'MEDIUM')
                trade_amount = get_dynamic_position_size(symbol, signal_strength)
                
                print(f"📈 开多仓，数量: {trade_amount}...")
                order = exchange.create_market_buy_order(
                    symbol,
                    trade_amount,
                    {'posSide': 'long'}
                )
                print("✅ 多仓已开")
                
                # 获取实际成交价格
                entry_price = current_price
                if order and 'average' in order and order['average']:
                    entry_price = order['average']
                
                # 高频交易：立即设置快速止损单
                if is_quick_signal:
                    # 使用高频固定止损止盈
                    create_quick_stop_loss(exchange, symbol, 'long', trade_amount, entry_price)
                    create_quick_take_profit(exchange, symbol, 'long', trade_amount, entry_price)
                else:
                    # 常规止损单
                    create_stop_loss_order(exchange, symbol, 'long', trade_amount, entry_price)
                
                update_hft_state('open_long')
                
            elif current_position and current_position['side'] == 'long':
                print("✅ 已持有多仓，保持持仓")
                # 检查止损单是否仍然有效
                stop_order_status = check_stop_orders_status(exchange, symbol)
                if "无活跃止损单" in stop_order_status or "已触发" in stop_order_status:
                    print("🔄 重新设置止损单...")
                    if is_quick_signal:
                        create_quick_stop_loss(exchange, symbol, 'long', current_position['size'], current_position['entry_price'])
                    else:
                        create_stop_loss_order(exchange, symbol, 'long', current_position['size'], current_position['entry_price'])
            else:
                print("🚫 持仓已满，无法开新仓")

        elif signal_data['signal'] == 'SELL':
            if current_position and current_position['side'] == 'long':
                print("🔄 平多仓...")
                # 先取消多仓的止损单
                cancel_stop_orders(exchange, symbol)
                # 执行平仓
                exchange.create_market_sell_order(
                    symbol,
                    current_position['size'],
                    {'posSide': 'long'}
                )
                print("✅ 多仓已平")
                update_hft_state('close_long')
                
            elif not current_position and can_trade:
                # 高频交易：检查是否超过每日限制
                if not can_trade_hft():
                    print("🚫 高频交易限制，无法开新仓")
                    return
                
                # 动态计算仓位大小
                signal_strength = signal_data.get('confidence', 'MEDIUM')
                trade_amount = get_dynamic_position_size(symbol, signal_strength)
                
                print(f"📉 开空仓，数量: {trade_amount}...")
                order = exchange.create_market_sell_order(
                    symbol,
                    trade_amount,
                    {'posSide': 'short'}
                )
                print("✅ 空仓已开")
                
                # 获取实际成交价格
                entry_price = current_price
                if order and 'average' in order and order['average']:
                    entry_price = order['average']
                
                # 高频交易：立即设置快速止损单
                if is_quick_signal:
                    # 使用高频固定止损止盈
                    create_quick_stop_loss(exchange, symbol, 'short', trade_amount, entry_price)
                    create_quick_take_profit(exchange, symbol, 'short', trade_amount, entry_price)
                else:
                    # 常规止损单
                    create_stop_loss_order(exchange, symbol, 'short', trade_amount, entry_price)
                
                update_hft_state('open_short')
                
            elif current_position and current_position['side'] == 'short':
                print("✅ 已持有空仓，保持持仓")
                # 检查止损单是否仍然有效
                stop_order_status = check_stop_orders_status(exchange, symbol)
                if "无活跃止损单" in stop_order_status or "已触发" in stop_order_status:
                    print("🔄 重新设置止损单...")
                    if is_quick_signal:
                        create_quick_stop_loss(exchange, symbol, 'short', current_position['size'], current_position['entry_price'])
                    else:
                        create_stop_loss_order(exchange, symbol, 'short', current_position['size'], current_position['entry_price'])
            else:
                print("🚫 持仓已满，无法开新仓")

        elif signal_data['signal'] == 'HOLD':
            print("⏸️ 建议观望，不执行交易")
            # 高频交易中，如果有持仓且信号不明确，可以考虑部分止盈
            if current_position:
                # 检查是否达到快速止盈条件
                unrealized_pnl_percent = current_position.get('pnl_percent', 0)
                if unrealized_pnl_percent > RISK_MANAGEMENT['quick_take_profit_percent']:
                    print(f"🎯 达到快速止盈条件({unrealized_pnl_percent:.2f}%)，建议部分止盈")
                    
                # 确保止损单有效
                stop_order_status = check_stop_orders_status(exchange, symbol)
                if "无活跃止损单" in stop_order_status or "已触发" in stop_order_status:
                    print("🔄 重新设置止损单...")
                    if is_quick_signal:
                        create_quick_stop_loss(exchange, symbol, current_position['side'], current_position['size'], current_position['entry_price'])
                    else:
                        create_stop_loss_order(exchange, symbol, current_position['side'], current_position['size'], current_position['entry_price'])
            return

        print("✅ 交易执行完成")
        time.sleep(1)  # 高频交易中减少等待时间
        
        # 验证持仓和止损单状态
        position = get_current_position(exchange, symbol)
        stop_order_status = check_stop_orders_status(exchange, symbol)
        print(f"📋 更新后持仓: {position}")
        print(f"🛡️ 止损单状态: {stop_order_status}")

    except Exception as e:
        print(f"❌ {symbol}高频交易执行失败: {e}")
        update_hft_state('error')
        # 交易失败时取消可能已创建的止损单
        cancel_stop_orders(exchange, symbol)

def execute_reversal_trade(exchange, risk_manager, symbol, side, reason):
    """执行反手交易（平仓后立即反向开仓）"""
    print(f"\n🔄 执行反手交易: {symbol} {side}")
    print(f"📝 理由: {reason}")
    
    from exchange_api import get_current_position
    
    try:
        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        # 获取当前持仓
        current_position = get_current_position(exchange, symbol)
        
        if not current_position:
            print("❌ 没有持仓，无法执行反手交易")
            return False
        
        # 计算反手数量（使用原持仓的80%）
        reversal_amount = current_position['size'] * 0.8
        
        # 先平仓
        print(f"📊 平仓: {current_position['side']}仓，数量: {current_position['size']}")
        if current_position['side'] == 'long':
            exchange.create_market_sell_order(
                symbol,
                current_position['size'],
                {'posSide': 'long'}
            )
        else:
            exchange.create_market_buy_order(
                symbol,
                current_position['size'],
                {'posSide': 'short'}
            )
        
        print("✅ 原仓位已平")
        
        # 反向开仓
        time.sleep(0.5)  # 短暂等待
        
        print(f"📊 反向开{side}仓，数量: {reversal_amount}")
        if side == 'long':
            order = exchange.create_market_buy_order(
                symbol,
                reversal_amount,
                {'posSide': 'long'}
            )
        else:
            order = exchange.create_market_sell_order(
                symbol,
                reversal_amount,
                {'posSide': 'short'}
            )
        
        print("✅ 反手仓位已开")
        
        # 获取实际成交价格
        entry_price = current_price
        if order and 'average' in order and order['average']:
            entry_price = order['average']
        
        # 设置快速止损单
        create_quick_stop_loss(exchange, symbol, side, reversal_amount, entry_price)
        create_quick_take_profit(exchange, symbol, side, reversal_amount, entry_price)
        
        update_hft_state('reversal')
        
        return True
        
    except Exception as e:
        print(f"❌ 反手交易失败: {e}")
        return False