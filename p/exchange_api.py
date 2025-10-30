from config import TRADE_CONFIG, RISK_MANAGEMENT, position_history, SUPPORTED_SYMBOLS, initialize_symbol_data, active_stop_orders
from datetime import datetime

def setup_exchange(exchange):
    """设置交易所参数"""
    try:
        # 为每个币种设置杠杆
        for symbol in TRADE_CONFIG['symbols']:
            if SUPPORTED_SYMBOLS[symbol]['enabled']:
                try:
                    exchange.set_leverage(TRADE_CONFIG['leverage'], symbol)
                    print(f"设置{symbol}杠杆倍数: {TRADE_CONFIG['leverage']}x")
                except Exception as e:
                    print(f"设置{symbol}杠杆失败: {e}")
        
        # 获取余额
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        print(f"当前USDT余额: {usdt_balance:.2f}")

        return True
    except Exception as e:
        print(f"交易所设置失败: {e}")
        return False

def get_current_position(exchange, symbol=None):
    """获取当前持仓情况"""
    try:
        if symbol:
            symbols = [symbol]
        else:
            symbols = [s for s in TRADE_CONFIG['symbols'] if SUPPORTED_SYMBOLS[s]['enabled']]
        
        all_positions = []
        
        for sym in symbols:
            try:
                positions = exchange.fetch_positions([sym])
                config_symbol_normalized = f"{sym.split('/')[0]}/USDT:USDT"
                
                for pos in positions:
                    if pos['symbol'] == config_symbol_normalized:
                        position_amt = 0
                        if 'positionAmt' in pos.get('info', {}):
                            position_amt = float(pos['info']['positionAmt'])
                        elif 'contracts' in pos:
                            contracts = float(pos['contracts'])
                            if pos.get('side') == 'short':
                                position_amt = -contracts
                            else:
                                position_amt = contracts

                        if position_amt != 0:
                            side = 'long' if position_amt > 0 else 'short'
                            entry_price = float(pos.get('entryPrice', 0))
                            unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                            position_value = abs(position_amt) * entry_price
                            
                            if entry_price > 0:
                                pnl_percent = (unrealized_pnl / (position_value / TRADE_CONFIG['leverage'])) * 100
                            else:
                                pnl_percent = 0
                            
                            position_info = {
                                'symbol': sym,
                                'side': side,
                                'size': abs(position_amt),
                                'entry_price': entry_price,
                                'unrealized_pnl': unrealized_pnl,
                                'pnl_percent': pnl_percent,
                                'position_amt': position_amt,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            record_position_history(position_info)
                            all_positions.append(position_info)
                            
            except Exception as e:
                print(f"获取{sym}持仓失败: {e}")
                continue
        
        if symbol:
            return all_positions[0] if all_positions else None
        else:
            return all_positions

    except Exception as e:
        print(f"获取持仓失败: {e}")
        return None if symbol else []

def record_position_history(position_info):
    """记录持仓历史"""
    symbol = position_info['symbol']
    initialize_symbol_data(symbol)
    position_history[symbol].append(position_info)
    if len(position_history[symbol]) > 100:
        position_history[symbol].pop(0)

def create_stop_loss_order(exchange, symbol, side, size, entry_price):
    """创建止损单"""
    try:
        if not RISK_MANAGEMENT['immediate_stop_loss']:
            return None
            
        stop_loss_price = calculate_stop_loss_price(entry_price, side)
        
        print(f"🚨 为{symbol}创建止损单:")
        print(f"   方向: {side}")
        print(f"   数量: {size}")
        print(f"   入场价: {entry_price:.4f}")
        print(f"   止损价: {stop_loss_price:.4f}")
        
        if RISK_MANAGEMENT['stop_loss_type'] == 'market':
            # 市价止损单
            if side == 'long':
                # 多仓止损：当价格跌到止损价时市价卖出
                order = exchange.create_order(
                    symbol,
                    'STOP_MARKET',
                    'sell',
                    size,
                    None,
                    {
                        'stopPrice': stop_loss_price,
                        'reduceOnly': True,
                        'positionSide': 'LONG'
                    }
                )
            else:
                # 空仓止损：当价格涨到止损价时市价买入
                order = exchange.create_order(
                    symbol,
                    'STOP_MARKET',
                    'buy',
                    size,
                    None,
                    {
                        'stopPrice': stop_loss_price,
                        'reduceOnly': True,
                        'positionSide': 'SHORT'
                    }
                )
        else:
            # 限价止损单
            if side == 'long':
                order = exchange.create_order(
                    symbol,
                    'STOP',
                    'sell',
                    size,
                    stop_loss_price * 0.995,  # 略低于止损价确保成交
                    {
                        'stopPrice': stop_loss_price,
                        'reduceOnly': True,
                        'positionSide': 'LONG'
                    }
                )
            else:
                order = exchange.create_order(
                    symbol,
                    'STOP',
                    'buy',
                    size,
                    stop_loss_price * 1.005,  # 略高于止损价确保成交
                    {
                        'stopPrice': stop_loss_price,
                        'reduceOnly': True,
                        'positionSide': 'SHORT'
                    }
                )
        
        print(f"✅ 止损单创建成功，订单ID: {order['id']}")
        
        # 记录活跃止损单
        active_stop_orders[symbol] = {
            'order_id': order['id'],
            'symbol': symbol,
            'side': side,
            'size': size,
            'stop_price': stop_loss_price,
            'entry_price': entry_price,
            'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return order
        
    except Exception as e:
        print(f"❌ 创建止损单失败: {e}")
        return None

def create_take_profit_order(exchange, symbol, side, size, entry_price):
    """创建止盈单"""
    try:
        take_profit_price = calculate_take_profit_price(entry_price, side)
        
        print(f"🎯 为{symbol}创建止盈单:")
        print(f"   方向: {side}")
        print(f"   数量: {size}")
        print(f"   入场价: {entry_price:.4f}")
        print(f"   止盈价: {take_profit_price:.4f}")
        
        if side == 'long':
            # 多仓止盈：当价格涨到止盈价时市价卖出
            order = exchange.create_order(
                symbol,
                'TAKE_PROFIT_MARKET',
                'sell',
                size,
                None,
                {
                    'stopPrice': take_profit_price,
                    'reduceOnly': True,
                    'positionSide': 'LONG'
                }
            )
        else:
            # 空仓止盈：当价格跌到止盈价时市价买入
            order = exchange.create_order(
                symbol,
                'TAKE_PROFIT_MARKET',
                'buy',
                size,
                None,
                {
                    'stopPrice': take_profit_price,
                    'reduceOnly': True,
                    'positionSide': 'SHORT'
                }
            )
        
        print(f"✅ 止盈单创建成功，订单ID: {order['id']}")
        return order
        
    except Exception as e:
        print(f"❌ 创建止盈单失败: {e}")
        return None

def cancel_stop_orders(exchange, symbol):
    """取消指定币种的所有止损止盈单"""
    try:
        if symbol in active_stop_orders and active_stop_orders[symbol]:
            order_id = active_stop_orders[symbol]['order_id']
            try:
                exchange.cancel_order(order_id, symbol)
                print(f"✅ 取消{symbol}止损单: {order_id}")
            except Exception as e:
                print(f"⚠️ 取消止损单失败（可能已触发）: {e}")
            
            active_stop_orders[symbol] = None
            
        # 同时取消所有开仓方向的止损止盈单
        open_orders = exchange.fetch_open_orders(symbol)
        for order in open_orders:
            if order['type'] in ['STOP_MARKET', 'STOP', 'TAKE_PROFIT_MARKET']:
                try:
                    exchange.cancel_order(order['id'], symbol)
                    print(f"✅ 取消{symbol}条件单: {order['id']}")
                except Exception as e:
                    print(f"⚠️ 取消条件单失败: {e}")
                    
    except Exception as e:
        print(f"❌ 取消{symbol}止损单失败: {e}")

def check_stop_orders_status(exchange, symbol):
    """检查止损单状态"""
    try:
        if symbol not in active_stop_orders or not active_stop_orders[symbol]:
            return "无活跃止损单"
            
        order_info = active_stop_orders[symbol]
        try:
            order = exchange.fetch_order(order_info['order_id'], symbol)
            return f"状态: {order['status']}, 止损价: {order_info['stop_price']:.4f}"
        except Exception as e:
            # 订单可能已成交或取消
            return f"订单可能已触发: {str(e)}"
            
    except Exception as e:
        return f"检查失败: {str(e)}"

# 原有的计算函数保持不变
def calculate_position_metrics(position_info, current_price):
    """计算持仓指标"""
    if not position_info:
        return None
        
    entry_price = position_info['entry_price']
    side = position_info['side']
    size = position_info['size']
    
    if side == 'long':
        pnl = (current_price - entry_price) * size
        pnl_percent = ((current_price - entry_price) / entry_price) * 100 * TRADE_CONFIG['leverage']
    else:
        pnl = (entry_price - current_price) * size
        pnl_percent = ((entry_price - current_price) / entry_price) * 100 * TRADE_CONFIG['leverage']
    
    stop_loss_price = calculate_stop_loss_price(entry_price, side)
    take_profit_price = calculate_take_profit_price(entry_price, side)
    
    if side == 'long':
        stop_loss_distance = ((current_price - stop_loss_price) / current_price) * 100
        take_profit_distance = ((take_profit_price - current_price) / current_price) * 100
    else:
        stop_loss_distance = ((stop_loss_price - current_price) / current_price) * 100
        take_profit_distance = ((current_price - take_profit_price) / current_price) * 100
    
    return {
        'current_pnl': pnl,
        'current_pnl_percent': pnl_percent,
        'stop_loss_price': stop_loss_price,
        'take_profit_price': take_profit_price,
        'stop_loss_distance_percent': stop_loss_distance,
        'take_profit_distance_percent': take_profit_distance,
        'risk_reward_ratio': take_profit_distance / abs(stop_loss_distance) if stop_loss_distance != 0 else 0
    }

def calculate_stop_loss_price(entry_price, side):
    """计算止损价格"""
    if side == 'long':
        return entry_price * (1 - RISK_MANAGEMENT['stop_loss_percent'] / 100 / TRADE_CONFIG['leverage'])
    else:
        return entry_price * (1 + RISK_MANAGEMENT['stop_loss_percent'] / 100 / TRADE_CONFIG['leverage'])

def calculate_take_profit_price(entry_price, side):
    """计算止盈价格"""
    if side == 'long':
        return entry_price * (1 + RISK_MANAGEMENT['take_profit_percent'] / 100 / TRADE_CONFIG['leverage'])
    else:
        return entry_price * (1 - RISK_MANAGEMENT['take_profit_percent'] / 100 / TRADE_CONFIG['leverage'])

def check_stop_loss_condition(position_metrics):
    """检查止损条件"""
    if not position_metrics:
        return False
    return position_metrics['current_pnl_percent'] <= -RISK_MANAGEMENT['stop_loss_percent']

def check_take_profit_condition(position_metrics):
    """检查止盈条件"""
    if not position_metrics:
        return False
    return position_metrics['current_pnl_percent'] >= RISK_MANAGEMENT['take_profit_percent']