# 加密货币高频交易机器人

基于均线聚合 + 布林中轨突破策略的高频交易系统，专注于5分钟K线交易。

## 🚀 核心特性

### 高频交易策略
- **交易周期**: 5分钟K线
- **核心逻辑**: MA7/MA10/MA30均线聚合 + 布林带中轨突破
- **信号频率**: 每5分钟分析一次，每5秒监控风险
- **持仓时间**: 通常5-30分钟，最长60分钟

### 风险管理
- **快速止盈**: 0.3%-0.5%
- **快速止损**: 0.2%-0.3%
- **移动止损**: 盈利后启用
- **紧急止损**: 1%强制止损
- **反手交易**: 亏损超过0.5%时考虑反手

### 多币种支持
- BTC/USDT: 比特币（高波动）
- ETH/USDT: 以太坊（中波动）
- SOL/USDT: Solana（高波动）

## 📁 项目结构
trading_bot/
├── main.py # 主程序入口（高频版本）
├── config.py # 配置和初始化（高频参数）
├── exchange_api.py # 交易所相关功能（高频优化）
├── data_fetcher.py # 数据获取（5分钟K线）
├── technical_analyzer.py # 技术指标分析（均线聚合计算）
├── ai_analyzer.py # AI分析模块（高频策略提示）
├── executor.py # 交易执行（高频执行器）
├── risk_manager.py # 风险管理（高频风控）
├── hft_strategy.py # 高频策略核心逻辑（新增）
└── README.md


## ⚙️ 配置说明

### 交易参数 (`config.py`)
```python
TRADE_CONFIG = {
    'timeframe': '5m',           # 5分钟K线
    'execution_interval': 5,     # 5秒执行间隔
    'analysis_interval': 300,    # 5分钟分析间隔
    'max_concurrent_trades': 2,  # 最大同时交易数
    'max_trades_per_day': 100,   # 每日最大交易次数
    'leverage': 10,              # 10倍杠杆
}
```

## 风险管理 (config.py)
`
RISK_MANAGEMENT = {
    'quick_take_profit_percent': 0.3,  # 快速止盈0.3%
    'quick_stop_loss_percent': 0.2,    # 快速止损0.2%
    'hft_fixed_stop_loss': 0.3,        # 高频固定止损0.3%
    'hft_fixed_take_profit': 0.5,      # 高频固定止盈0.5%
}
`

## 🎯 策略逻辑

#### A级信号（强烈推荐）
均线高度聚合（聚合度<0.2%）

价格突破布林中轨0.1%以上

MA7和MA10同向排列

成交量放大确认


#### B级信号（推荐）
均线中度聚合（聚合度0.2%-0.5%）

价格突破布林中轨

均线同向排列

#### C级信号（谨慎）
均线聚合但未突破中轨

突破但量能不足

建议观望或轻仓试探


### 🔧 安装与运行

#### 环境设置
pip install ccxt pandas python-dotenv openai

#### 配置文件
创建 .env 文件：
DEEPSEEK_API_KEY=your_deepseek_api_key
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET=your_binance_secret

#### 运行程序
python main.py

## ⚠️ 风险提示
高频交易风险高：小止损可能被频繁触发

API限制：注意交易所API调用频率限制

滑点风险：市价单可能产生较大滑点

网络延迟：确保网络连接稳定

资金管理：建议使用小资金测试，单笔风险不超过2%

## 📊 性能监控
程序会实时显示：

今日交易次数

连续亏损次数

持仓状态

止损单状态

市场波动率

## v1.0 (2024)
实现高频交易框架

均线聚合策略

快速止盈止损

反手交易逻辑

多币种支持