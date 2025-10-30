import pandas as pd
from datetime import datetime
import time
from config import TRADE_CONFIG, SUPPORTED_SYMBOLS, initialize_symbol_data

def get_ohlcv(exchange, symbol):
    """获取指定币种的15分钟K线数据"""
    try:
        # 获取最近100根15分钟K线用于计算技术指标
        ohlcv = exchange.fetch_ohlcv(symbol, TRADE_CONFIG['timeframe'], limit=100)

        # 转换为DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        current_data = df.iloc[-1]
        previous_data = df.iloc[-2] if len(df) > 1 else current_data

        price_data = {
            'symbol': symbol,
            'price': current_data['close'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'high': current_data['high'],
            'low': current_data['low'],
            'volume': current_data['volume'],
            'timeframe': TRADE_CONFIG['timeframe'],
            'price_change': ((current_data['close'] - previous_data['close']) / previous_data['close']) * 100,
            'kline_data': df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_dict('records'),
            'full_data': df
        }
        
        # 初始化币种数据
        initialize_symbol_data(symbol)
        
        return price_data
    except Exception as e:
        print(f"获取{symbol}K线数据失败: {e}")
        return None

def get_current_price(exchange, symbol):
    """获取币种的当前最新价格（用于风险监控）"""
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"获取{symbol}最新价格失败: {e}")
        return None

def get_all_symbols_data(exchange):
    """获取所有启用币种的数据"""
    price_data_dict = {}
    current_price_dict = {}
    
    for symbol in TRADE_CONFIG['symbols']:
        if SUPPORTED_SYMBOLS[symbol]['enabled']:
            # 获取15分钟K线数据用于分析
            kline_data = get_ohlcv(exchange, symbol)
            if kline_data:
                price_data_dict[symbol] = kline_data
            
            # 获取当前最新价格用于风险监控
            current_price = get_current_price(exchange, symbol)
            if current_price:
                current_price_dict[symbol] = current_price
            
            # 添加延迟避免API限制
            time.sleep(0.1)
    
    return price_data_dict, current_price_dict

def build_kline_text(price_data):
    """构建K线数据文本"""
    symbol_name = SUPPORTED_SYMBOLS[price_data['symbol']]['name']
    kline_text = f"【{symbol_name}({price_data['symbol']}) 最近5根{price_data['timeframe']}K线数据】\n"
    for i, kline in enumerate(price_data['kline_data']):
        trend = "阳线" if kline['close'] > kline['open'] else "阴线"
        change = ((kline['close'] - kline['open']) / kline['open']) * 100
        kline_text += f"K线{i + 1}: {trend} 开盘:{kline['open']:.4f} 收盘:{kline['close']:.4f} 涨跌:{change:+.2f}%\n"
    
    return kline_text