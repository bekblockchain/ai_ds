import os
from openai import OpenAI
import ccxt
from dotenv import load_dotenv

load_dotenv()

# 支持的币种配置
SUPPORTED_SYMBOLS = {
    'BTC/USDT': {
        'name': '比特币',
        'amount': 0.001,
        'min_amount': 0.0001,
        'enabled': True
    },
    'ETH/USDT': {
        'name': '以太坊',
        'amount': 0.01,
        'min_amount': 0.001,
        'enabled': True
    },
    'SOL/USDT': {
        'name': 'Solana',
        'amount': 0.1,
        'min_amount': 0.01,
        'enabled': True
    },
    'DOGE/USDT': {
        'name': '狗狗币',
        'amount': 100,
        'min_amount': 10,
        'enabled': True
    },
    'BCH/USDT': {
        'name': '比特币现金',
        'amount': 0.01,
        'min_amount': 0.001,
        'enabled': True
    }
}

# 交易参数配置
TRADE_CONFIG = {
    'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'BCH/USDT'],
    'leverage': 10,
    'timeframe': '15m',  # 保持15分钟策略周期
    'test_mode': False,
    'max_concurrent_trades': 3,
    'execution_interval': 5,  # 执行间隔（秒）- 仅用于风险监控
    'analysis_interval': 900,  # 分析间隔（秒）- 15分钟，保持策略一致性
}

# 止盈止损配置
RISK_MANAGEMENT = {
    'stop_loss_percent': 20.0,
    'take_profit_percent': 30.0,
    'trailing_stop_percent': 10.0,
    'emergency_stop_loss': 25.0,
    'max_position_size': 0.01,
    'risk_per_trade': 0.02,
    'daily_loss_limit': 0.1,
}

# 技术指标插槽配置
TECHNICAL_INDICATORS = {
    'ma': {
        'enabled': True,
        'name': '移动平均线',
        'periods': [5, 10, 20],  # 基于15分钟K线的20周期 = 5小时趋势
        'description': '识别趋势方向和拐点'
    },
    'boll': {
        'enabled': True,
        'name': '布林带',
        'period': 20,  # 基于15分钟K线的20周期
        'std_dev': 2,
        'description': '识别突破和超买超卖'
    },
    'rsi': {
        'enabled': True,
        'name': '相对强弱指数',
        'period': 14,  # 基于15分钟K线的14周期
        'description': '识别超买超卖区域'
    },
    'macd': {
        'enabled': True,
        'name': 'MACD',
        'fast_period': 12,    # 基于15分钟K线
        'slow_period': 26,    # 基于15分钟K线
        'signal_period': 9,   # 基于15分钟K线
        'description': '识别趋势动量和转折'
    },
    'volume': {
        'enabled': True,
        'name': '成交量分析',
        'description': '分析成交量配合价格走势'
    }
}

# 全局变量
price_history = {}
signal_history = {}
technical_history = {}
position_history = {}
daily_performance = {}
last_analysis_time = {}  # 记录每个币种上次分析时间

def init_deepseek_client():
    """初始化DeepSeek客户端"""
    return OpenAI(
        api_key=os.getenv('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com"
    )

def init_exchange():
    """初始化交易所连接"""
    return ccxt.binance({
        'options': {'defaultType': 'future'},
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET'),
    })

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
            'net_profit': 0
        }
    if symbol not in last_analysis_time:
        last_analysis_time[symbol] = 0