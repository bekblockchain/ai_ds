from config import (TRADE_CONFIG, RISK_MANAGEMENT, position_history, 
                   SUPPORTED_SYMBOLS, initialize_symbol_data, active_stop_orders)
from datetime import datetime

def setup_exchange(exchange):
    """设置交易所参数 - 高频版本"""
    try:
        # 为每个币种设置杠杆
        for symbol in TRADE_CONFIG['symbols']:
            if SUPPORTED_SYMBOLS[symbol]['enabled']:
                try:
                    symbol_config = SUPPORTED_SYMBOLS[symbol]
                    # 设置多仓杠杆
                    exchange.set_leverage(
                      symbol_config['leverage_long'],
                      symbol,
                      params={'marginMode': 'cross', 'positionSide': 'LONG'}
                    )
                    # 设置空仓杠杆
                    exchange.set_leverage(
                        symbol_config['leverage_short'],
                        symbol,
                        params={'marginMode': 'cross', 'positionSide': 'SHORT'}
                    )
                    print(f"设置{symbol}杠杆: 多仓{symbol_config['leverage_long']}x, 空仓{symbol_config['leverage_short']}x")
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
    """获取当前持仓情况 - 高频版本"""
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
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'holding_time': 0  # 持仓时间（秒）
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
    """记录持仓历史 - 高频版本"""
    symbol = position_info['symbol']
    initialize_symbol_data(symbol)
    
    # 计算持仓时间
    if position_history[symbol]:
        last_position = position_history[symbol][-1]
        if last_position['side'] == position_info['side']:
            # 同一方向持仓，更新持仓时间
            import time
            current_time = time.time()
            position_info['holding_time'] = last_position.get('holding_time', 0) + (TRADE_CONFIG['execution_interval'])
    
    position_history[symbol].append(position_info)
    if len(position_history[symbol]) > 50:  # 高频交易减少历史记录长度
        position_history[symbol].pop(0)

def create_quick_stop_loss(exchange, symbol, side, size, entry_price):
    """创建高频快速止损单（固定比例）"""
    try:
        # 使用高频固定止损比例
        if side == 'long':
            stop_loss_price = entry_price * (1 - RISK_MANAGEMENT['hft_fixed_stop_loss'] / 100)
        else:
            stop_loss_price = entry_price * (1 + RISK_MANAGEMENT['hft_fixed_stop_loss'] / 100)
        
        print(f"🚨 为{symbol}创建快速止损单:")
        print(f"   方向: {side}")
        print(f"   数量: {size}")
        print(f"   入场价: {entry_price:.4f}")
        print(f"   快速止损价: {stop_loss_price:.4f}")
        print(f"   止损幅度: {RISK_MANAGEMENT['hft_fixed_stop_loss']}%")
        
        if side == 'long':
            order = exchange.create_order(
                symbol,
                'STOP_MARKET',
                'sell',
                size,
                None,
                {
                    'stopPrice': stop_loss_price,
                    'reduceOnly': True,
                    'positionSide': 'LONG',
                    'priceProtect': 'TRUE'  # 价格保护
                }
            )
        else:
            order = exchange.create_order(
                symbol,
                'STOP_MARKET',
                'buy',
                size,
                None,
                {
                    'stopPrice': stop_loss_price,
                    'reduceOnly': True,
                    'positionSide': 'SHORT',
                    'priceProtect': 'TRUE'
                }
            )
        
        print(f"✅ 快速止损单创建成功，订单ID: {order['id']}")
        
        # 记录活跃止损单
        active_stop_orders[symbol] = {
            'order_id': order['id'],
            'symbol': symbol,
            'side': side,
            'size': size,
            'stop_price': stop_loss_price,
            'entry_price': entry_price,
            'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'quick_stop_loss'
        }
        
        return order
        
    except Exception as e:
        print(f"❌ 创建快速止损单失败: {e}")
        return None

def create_quick_take_profit(exchange, symbol, side, size, entry_price):
    """创建高频快速止盈单（固定比例）"""
    try:
        # 使用高频固定止盈比例
        if side == 'long':
            take_profit_price = entry_price * (1 + RISK_MANAGEMENT['hft_fixed_take_profit'] / 100)
        else:
            take_profit_price = entry_price * (1 - RISK_MANAGEMENT['hft_fixed_take_profit'] / 100)
        
        print(f"🎯 为{symbol}创建快速止盈单:")
        print(f"   方向: {side}")
        print(f"   数量: {size}")
        print(f"   入场价: {entry_price:.4f}")
        print(f"   快速止盈价: {take_profit_price:.4f}")
        print(f"   止盈幅度: {RISK_MANAGEMENT['hft_fixed_take_profit']}%")
        
        if side == 'long':
            order = exchange.create_order(
                symbol,
                'TAKE_PROFIT_MARKET',
                'sell',
                size,
                None,
                {
                    'stopPrice': take_profit_price,
                    'reduceOnly': True,
                    'positionSide': 'LONG',
                    'priceProtect': 'TRUE'
                }
            )
        else:
            order = exchange.create_order(
                symbol,
                'TAKE_PROFIT_MARKET',
                'buy',
                size,
                None,
                {
                    'stopPrice': take_profit_price,
                    'reduceOnly': True,
                    'positionSide': 'SHORT',
                    'priceProtect': 'TRUE'
                }
            )
        
        print(f"✅ 快速止盈单创建成功，订单ID: {order['id']}")
        return order
        
    except Exception as e:
        print(f"❌ 创建快速止盈单失败: {e}")
        return None

# 原有的create_stop_loss_order和create_take_profit_order保留，用于非高频交易
def create_stop_loss_order(exchange, symbol, side, size, entry_price):
    """创建常规止损单"""
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
            if side == 'long':
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
            if side == 'long':
                order = exchange.create_order(
                    symbol,
                    'STOP',
                    'sell',
                    size,
                    stop_loss_price * 0.995,
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
                    stop_loss_price * 1.005,
                    {
                        'stopPrice': stop_loss_price,
                        'reduceOnly': True,
                        'positionSide': 'SHORT'
                    }
                )
        
        print(f"✅ 止损单创建成功，订单ID: {order['id']}")
        
        active_stop_orders[symbol] = {
            'order_id': order['id'],
            'symbol': symbol,
            'side': side,
            'size': size,
            'stop_price': stop_loss_price,
            'entry_price': entry_price,
            'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'normal_stop_loss'
        }
        
        return order
        
    except Exception as e:
        print(f"❌ 创建止损单失败: {e}")
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

def can_open_new_trade(exchange):
    """检查是否可以开新仓（高频版本）"""
    try:
        # 获取当前所有持仓
        positions = get_current_position(exchange)
        
        # 检查持仓数量限制
        if len(positions) >= TRADE_CONFIG['max_concurrent_trades']:
            return False
            
        # 检查账户余额
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        
        # 高频交易要求有足够余额
        min_balance = 100  # 至少100USDT余额
        if usdt_balance < min_balance:
            print(f"⚠️ 余额不足: {usdt_balance:.2f} USDT < {min_balance} USDT")
            return False
            
        return True
        
    except Exception as e:
        print(f"检查开仓条件失败: {e}")
        return False

def get_order_status(exchange, order_id, symbol):
    """获取订单状态"""
    try:
        order = exchange.fetch_order(order_id, symbol)
        return order['status']
    except Exception as e:
        print(f"获取订单状态失败: {e}")
        return None

def calculate_position_value(position_info, current_price):
    """计算持仓价值"""
    if not position_info:
        return 0
        
    size = position_info['size']
    return size * current_price

def calculate_risk_amount(position_info, current_price):
    """计算风险金额"""
    if not position_info:
        return 0
        
    position_value = calculate_position_value(position_info, current_price)
    risk_percent = RISK_MANAGEMENT['risk_per_trade']
    return position_value * risk_percent

def safe_exchange_call(func, max_retries=3, delay=1):
    """安全的交易所API调用装饰器"""
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ccxt.NetworkError as e:
                last_exception = e
                print(f"⚠️ 网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
            except ccxt.ExchangeError as e:
                last_exception = e
                print(f"⚠️ 交易所错误: {e}")
                break  # 交易所错误通常不需要重试
            except Exception as e:
                last_exception = e
                print(f"⚠️ 未知错误: {e}")
                break
        
        raise last_exception if last_exception else Exception("API调用失败")
    return wrapper

# 应用到关键函数
@safe_exchange_call
def get_current_position_safe(exchange, symbol=None):
    return get_current_position(exchange, symbol)