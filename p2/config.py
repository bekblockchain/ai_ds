import os
# 导入time模块
import time
from openai import OpenAI
import ccxt
from dotenv import load_dotenv

load_dotenv()

# 支持的币种配置 - 高频交易减少币种数量
SUPPORTED_SYMBOLS = {
    'BTC/USDT': {
        'name': '比特币',
        'amount': 0.001,
        'min_amount': 0.0001,
        'enabled': True,
        'volatility': 'high',  # 波动性标签
        'atr_multiplier': 1.0,  # ATR乘数用于计算止损
        'leverage_long': 10,      # 🆕 做多杠杆倍数
        'leverage_short': 10,    # 🆕 做空杠杆倍数
    },
    'ETH/USDT': {
        'name': '以太坊',
        'amount': 0.01,
        'min_amount': 0.001,
        'enabled': True,
        'volatility': 'medium',
        'atr_multiplier': 1.2,
        'leverage_long': 10,      # 🆕 做多杠杆倍数
        'leverage_short': 10,    # 🆕 做空杠杆倍数
    },
    'SOL/USDT': {
        'name': 'Solana',
        'amount': 0.1,
        'min_amount': 0.01,
        'enabled': True,
        'volatility': 'high',
        'atr_multiplier': 1.0,
        'leverage_long': 5,      # 🆕 做多杠杆倍数
        'leverage_short': 5,    # 🆕 做空杠杆倍数
    }
}

# 高频交易参数配置
TRADE_CONFIG = {
    'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],  # 减少币种数量以专注
    'leverage': 10,
    'timeframe': '5m',  # 改为5分钟K线
    'test_mode': False,
    'max_concurrent_trades': 2,  # 减少同时交易数量
    'execution_interval': 5,  # 风险监控频率5秒
    'analysis_interval': 300,  # 策略分析频率300秒（5分钟）
    'hft_enabled': True,  # 启用高频交易模式
    'max_trades_per_day': 100,  # 每日最大交易次数限制
}

# 高频止盈止损配置 - 使用固定比例
RISK_MANAGEMENT = {
    'stop_loss_percent': 0.5,  # 固定0.5%止损
    'take_profit_percent': 0.8,  # 固定0.8%止盈
    'trailing_stop_percent': 0.3,  # 移动止损0.3%
    'emergency_stop_loss': 1.0,  # 紧急止损1%
    'max_position_size': 0.01,
    'risk_per_trade': 0.02,
    'daily_loss_limit': 0.05,  # 每日亏损限制5%
    'immediate_stop_loss': True,
    'stop_loss_type': 'market',
    'hft_fixed_stop_loss': 0.3,  # 高频固定止损0.3%
    'hft_fixed_take_profit': 0.5,  # 高频固定止盈0.5%
    'quick_take_profit_percent': 0.3,  # 快速止盈0.3%
    'quick_stop_loss_percent': 0.2,  # 快速止损0.2%
}

# 高频技术指标配置
TECHNICAL_INDICATORS = {
    'ma': {
        'enabled': True,
        'name': '移动平均线',
        'periods': [7, 10, 30, 60],  # 高频策略所需均线
        'description': '识别趋势方向和聚合点'
    },
    'boll': {
        'enabled': True,
        'name': '布林带',
        'period': 20,
        'std_dev': 2,
        'description': '识别突破和波动率压缩'
    },
    'rsi': {
        'enabled': True,
        'name': '相对强弱指数',
        'period': 14,
        'description': '识别超买超卖区域'
    },
    'macd': {
        'enabled': False,  # 高频交易中MACD响应较慢，可选禁用
        'name': 'MACD',
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9,
        'description': '识别趋势动量和转折'
    },
    'volume': {
        'enabled': True,
        'name': '成交量分析',
        'description': '分析成交量配合价格走势'
    },
    'atr': {
        'enabled': True,  # 新增ATR用于计算止损
        'name': '平均真实波幅',
        'period': 20,
        'description': '计算市场波动率和止损距离'
    }
}

# 高频策略状态跟踪
HIGH_FREQUENCY_STATE = {
    'daily_trades': 0,
    'consecutive_losses': 0,
    'last_trade_time': None,
    'market_volatility': 'normal',  # normal, high, low
    'position_reverse_count': 0,  # 反手交易次数
    'quick_profit_trades': 0,  # 快速止盈交易次数
}

# 全局变量
price_history = {}
signal_history = {}
technical_history = {}
position_history = {}
daily_performance = {}
last_analysis_time = {}
active_stop_orders = {}
trade_count_today = 0  # 今日交易次数
consecutive_losses = 0  # 连续亏损次数
last_trade_result = None  # 上次交易结果

def init_deepseek_client():
    """初始化DeepSeek客户端"""
    return OpenAI(
        api_key=os.getenv('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com"
    )

def init_exchange():
    """初始化交易所连接"""
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET'),
        'enableRateLimit': True,
    })
    # 设置高频参数
    exchange.options.update({
        'defaultType': 'future',
        'adjustForTimeDifference': True,
        'recvWindow': 10000,
    })
    return exchange

def get_symbol_config(symbol):
    """获取币种配置"""
    return SUPPORTED_SYMBOLS.get(symbol, SUPPORTED_SYMBOLS['BTC/USDT'])

def get_trade_amount(symbol):
    """获取交易数量"""
    config = get_symbol_config(symbol)
    return config['amount']

def initialize_symbol_data(symbol):
    """初始化币种数据"""
    if symbol not in price_history:
        price_history[symbol] = []
    if symbol not in signal_history:
        signal_history[symbol] = []
    if symbol not in technical_history:
        technical_history[symbol] = []
    if symbol not in position_history:
        position_history[symbol] = []
    if symbol not in daily_performance:
        daily_performance[symbol] = {
            'trades': 0,
            'profit': 0,
            'loss': 0,
            'net_profit': 0,
            'quick_profits': 0,  # 快速止盈次数
            'reversal_trades': 0,  # 反手交易次数
        }
    if symbol not in last_analysis_time:
        last_analysis_time[symbol] = 0
    if symbol not in active_stop_orders:
        active_stop_orders[symbol] = None

def update_hft_state(trade_result):
    """更新高频交易状态"""
    global trade_count_today, consecutive_losses, last_trade_result
    
    trade_count_today += 1
    last_trade_result = trade_result
    
    if trade_result == 'loss':
        consecutive_losses += 1
    else:
        consecutive_losses = 0
    
    # 更新HIGH_FREQUENCY_STATE
    HIGH_FREQUENCY_STATE['daily_trades'] = trade_count_today
    HIGH_FREQUENCY_STATE['consecutive_losses'] = consecutive_losses
    HIGH_FREQUENCY_STATE['last_trade_time'] = time.time()

def get_dynamic_position_size(symbol, signal_strength):
    """根据信号强度动态计算仓位大小"""
    base_amount = get_symbol_config(symbol)['amount']
    
    # 根据信号强度调整仓位
    if signal_strength == 'STRONG':
        return base_amount * 1.5
    elif signal_strength == 'WEAK':
        return base_amount * 0.5
    else:
        return base_amount

def can_trade_hft():
    """检查是否可以执行高频交易"""
    global trade_count_today, consecutive_losses
    
    # 检查每日交易次数限制
    if trade_count_today >= TRADE_CONFIG['max_trades_per_day']:
        print(f"⚠️ 达到每日交易次数限制: {trade_count_today}/{TRADE_CONFIG['max_trades_per_day']}")
        return False
    
    # 检查连续亏损
    if consecutive_losses >= 5:
        print(f"⚠️ 连续亏损{consecutive_losses}次，暂停交易30分钟")
        return False
    
    # 检查市场波动率
    if HIGH_FREQUENCY_STATE['market_volatility'] == 'high':
        print("⚠️ 市场波动率过高，降低交易频率")
        return True  # 仍然允许但会降低仓位
    
    return True

def validate_environment():
    """验证环境变量"""
    required_vars = ['DEEPSEEK_API_KEY', 'BINANCE_API_KEY', 'BINANCE_SECRET']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise EnvironmentError(f"缺少必要环境变量: {', '.join(missing_vars)}")
    
    # 验证API密钥格式
    binance_key = os.getenv('BINANCE_API_KEY')
    if len(binance_key) < 10:
        raise ValueError("Binance API密钥格式不正确")
    
    print("✅ 环境变量验证通过")
    return True

def cleanup_old_data(max_history=1000):
    """清理旧数据防止内存泄漏"""
    global price_history, signal_history, technical_history
    
    for symbol in list(price_history.keys()):
        if len(price_history[symbol]) > max_history:
            price_history[symbol] = price_history[symbol][-max_history:]
    
    for symbol in list(signal_history.keys()):
        if len(signal_history[symbol]) > max_history:
            signal_history[symbol] = signal_history[symbol][-max_history:]
    
    if len(technical_history) > max_history:
        technical_history = technical_history[-max_history:]
    
    print(f"🧹 清理历史数据完成，当前内存使用: {get_memory_usage()}MB")

def get_memory_usage():
    """获取内存使用情况"""
    import psutil
    import os
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB