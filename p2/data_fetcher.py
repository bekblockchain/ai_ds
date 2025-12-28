import pandas as pd
from datetime import datetime
import time
from config import TRADE_CONFIG, SUPPORTED_SYMBOLS, initialize_symbol_data

def get_ohlcv(exchange, symbol):
    """获取指定币种的5分钟K线数据（高频交易）"""
    try:
        # 获取最近150根5分钟K线用于计算技术指标
        ohlcv = exchange.fetch_ohlcv(symbol, TRADE_CONFIG['timeframe'], limit=150)

        # 转换为DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        current_data = df.iloc[-1]
        previous_data = df.iloc[-2] if len(df) > 1 else current_data

        # 计算价格变化（5分钟）
        price_change_5m = ((current_data['close'] - previous_data['close']) / previous_data['close']) * 100
        
        # 计算15分钟变化（最近3根K线）
        if len(df) >= 4:
            price_15m_ago = df.iloc[-4]['close']
            price_change_15m = ((current_data['close'] - price_15m_ago) / price_15m_ago) * 100
        else:
            price_change_15m = price_change_5m

        price_data = {
            'symbol': symbol,
            'price': current_data['close'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'high': current_data['high'],
            'low': current_data['low'],
            'volume': current_data['volume'],
            'timeframe': TRADE_CONFIG['timeframe'],
            'price_change': price_change_5m,
            'price_change_15m': price_change_15m,
            'kline_data': df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(8).to_dict('records'),  # 获取8根K线
            'full_data': df,
            'open': current_data['open'],
            'close': current_data['close']
        }
        
        # 初始化币种数据
        initialize_symbol_data(symbol)
        
        return price_data
    except Exception as e:
        print(f"获取{symbol}K线数据失败: {e}")
        return None

def get_current_price(exchange, symbol):
    """获取币种的当前最新价格（用于高频风险监控）"""
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"获取{symbol}最新价格失败: {e}")
        return None

def get_all_symbols_data(exchange):
    """获取所有启用币种的数据（高频版本）"""
    price_data_dict = {}
    current_price_dict = {}
    
    for symbol in TRADE_CONFIG['symbols']:
        if SUPPORTED_SYMBOLS[symbol]['enabled']:
            try:
                # 获取5分钟K线数据用于分析
                kline_data = get_ohlcv(exchange, symbol)
                if kline_data:
                    price_data_dict[symbol] = kline_data
                
                # 获取当前最新价格用于风险监控
                current_price = get_current_price(exchange, symbol)
                if current_price:
                    current_price_dict[symbol] = current_price
                
            except Exception as e:
                print(f"获取{symbol}数据失败: {e}")
                continue
            
            # 添加短暂延迟避免API限制
            time.sleep(0.05)  # 高频交易减少延迟
    
    return price_data_dict, current_price_dict

def build_kline_text(price_data):
    """构建K线数据文本（高频版本）"""
    symbol_name = SUPPORTED_SYMBOLS[price_data['symbol']]['name']
    
    text = f"【{symbol_name}({price_data['symbol']}) 最近8根{price_data['timeframe']}K线数据】\n"
    
    # 最近8根K线详细数据
    for i, kline in enumerate(price_data['kline_data']):
        trend = "阳线" if kline['close'] > kline['open'] else "阴线"
        change = ((kline['close'] - kline['open']) / kline['open']) * 100
        body_ratio = abs(kline['close'] - kline['open']) / (kline['high'] - kline['low']) if (kline['high'] - kline['low']) > 0 else 0
        
        # 添加K线形态判断
        if body_ratio > 0.7:
            candle_type = "实体大"
        elif body_ratio > 0.3:
            candle_type = "实体中"
        else:
            candle_type = "十字星"
        
        text += f"K线{i + 1}: {trend} {candle_type} 开:{kline['open']:.4f} 收:{kline['close']:.4f} 涨跌:{change:+.2f}%\n"
    
    # 添加汇总信息
    text += f"\n📊 价格变化汇总:\n"
    text += f"当前价格: ${price_data['price']:.4f}\n"
    text += f"5分钟变化: {price_data['price_change']:+.2f}%\n"
    text += f"15分钟变化: {price_data.get('price_change_15m', 0):+.2f}%\n"
    text += f"本K线范围: ${price_data['low']:.4f} - ${price_data['high']:.4f}\n"
    
    # 计算波动率
    if len(price_data['kline_data']) >= 3:
        prices = [k['close'] for k in price_data['kline_data'][-3:]]
        volatility = max(prices) - min(prices)
        volatility_percent = (volatility / price_data['price']) * 100
        text += f"近期波动率: {volatility_percent:.2f}%\n"
    
    return text

def get_market_status(exchange, symbol):
    """获取市场状态（用于判断是否适合高频交易）"""
    try:
        # 获取ticker数据
        ticker = exchange.fetch_ticker(symbol)
        
        # 计算买卖价差
        bid = ticker['bid']
        ask = ticker['ask']
        spread = (ask - bid) / bid * 100 if bid > 0 else 0
        
        # 获取最近成交
        trades = exchange.fetch_trades(symbol, limit=10)
        trade_volumes = [trade['amount'] for trade in trades]
        avg_trade_volume = sum(trade_volumes) / len(trade_volumes) if trade_volumes else 0
        
        market_status = {
            'symbol': symbol,
            'bid': bid,
            'ask': ask,
            'spread_percent': spread,
            'last_price': ticker['last'],
            'volume_24h': ticker['quoteVolume'],
            'avg_trade_volume': avg_trade_volume,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 判断市场流动性
        if spread < 0.01 and avg_trade_volume > 1000:
            market_status['liquidity'] = 'high'
        elif spread < 0.05 and avg_trade_volume > 100:
            market_status['liquidity'] = 'medium'
        else:
            market_status['liquidity'] = 'low'
        
        return market_status
        
    except Exception as e:
        print(f"获取{symbol}市场状态失败: {e}")
        return None

def validate_ohlcv_data(df, symbol):
    """验证K线数据完整性"""
    issues = []
    
    # 检查数据长度
    if len(df) < 50:
        issues.append(f"数据不足，只有{len(df)}根K线")
    
    # 检查NaN值
    nan_count = df.isna().sum().sum()
    if nan_count > 0:
        issues.append(f"发现{nan_count}个NaN值")
    
    # 检查价格合理性
    if 'close' in df.columns:
        if df['close'].iloc[-1] <= 0:
            issues.append("收盘价无效")
        
        # 检查价格突变
        price_changes = df['close'].pct_change().abs()
        large_jumps = (price_changes > 0.1).sum()  # 单次波动超过10%
        if large_jumps > 0:
            issues.append(f"发现{large_jumps}次异常价格波动")
    
    # 检查时间连续性
    if 'timestamp' in df.columns:
        time_diffs = df['timestamp'].diff().dt.total_seconds()
        expected_interval = 300  # 5分钟
        time_gaps = (time_diffs > expected_interval * 1.5).sum()
        if time_gaps > 0:
            issues.append(f"发现{time_gaps}处时间间隔异常")
    
    if issues:
        print(f"⚠️ {symbol}数据验证问题: {'; '.join(issues)}")
        return False
    
    return True