from config import TRADE_CONFIG, RISK_MANAGEMENT, position_history, SUPPORTED_SYMBOLS, initialize_symbol_data
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
            # 获取指定币种的持仓
            symbols = [symbol]
        else:
            # 获取所有启用币种的持仓
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
                            
                            # 计算盈亏百分比
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
                            
                            # 记录持仓历史
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
    # 只保留最近100条记录
    if len(position_history[symbol]) > 100:
        position_history[symbol].pop(0)

def get_active_positions_count(exchange):
    """获取活跃持仓数量"""
    positions = get_current_position(exchange)
    return len(positions) if positions else 0

def can_open_new_trade(exchange):
    """检查是否可以开新仓"""
    active_positions = get_active_positions_count(exchange)
    return active_positions < TRADE_CONFIG['max_concurrent_trades']

def calculate_position_metrics(position_info, current_price):
    """计算持仓指标"""
    if not position_info:
        return None
        
    entry_price = position_info['entry_price']
    side = position_info['side']
    size = position_info['size']
    
    # 计算当前盈亏
    if side == 'long':
        pnl = (current_price - entry_price) * size
        pnl_percent = ((current_price - entry_price) / entry_price) * 100 * TRADE_CONFIG['leverage']
    else:  # short
        pnl = (entry_price - current_price) * size
        pnl_percent = ((entry_price - current_price) / entry_price) * 100 * TRADE_CONFIG['leverage']
    
    # 计算风险指标
    stop_loss_price = calculate_stop_loss_price(entry_price, side)
    take_profit_price = calculate_take_profit_price(entry_price, side)
    
    # 距离止损/止盈的百分比
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
    else:  # short
        return entry_price * (1 + RISK_MANAGEMENT['stop_loss_percent'] / 100 / TRADE_CONFIG['leverage'])

def calculate_take_profit_price(entry_price, side):
    """计算止盈价格"""
    if side == 'long':
        return entry_price * (1 + RISK_MANAGEMENT['take_profit_percent'] / 100 / TRADE_CONFIG['leverage'])
    else:  # short
        return entry_price * (1 - RISK_MANAGEMENT['take_profit_percent'] / 100 / TRADE_CONFIG['leverage'])

def check_stop_loss_condition(position_metrics):
    """检查止损条件"""
    if not position_metrics:
        return False
        
    # 检查是否触及止损
    if position_metrics['current_pnl_percent'] <= -RISK_MANAGEMENT['stop_loss_percent']:
        return True
    
    # 检查紧急止损
    if position_metrics['current_pnl_percent'] <= -RISK_MANAGEMENT['emergency_stop_loss']:
        return True
        
    return False

def check_take_profit_condition(position_metrics):
    """检查止盈条件"""
    if not position_metrics:
        return False
        
    # 检查是否触及止盈
    if position_metrics['current_pnl_percent'] >= RISK_MANAGEMENT['take_profit_percent']:
        return True
        
    return False