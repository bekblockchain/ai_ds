import time
from config import TRADE_CONFIG, SUPPORTED_SYMBOLS, get_trade_amount
from exchange_api import can_open_new_trade

def execute_trade(exchange, risk_manager, signal_data, price_data):
    """执行交易"""
    from exchange_api import get_current_position
    
    symbol = price_data['symbol']
    current_position = get_current_position(exchange, symbol)
    current_price = price_data['price']
    symbol_name = SUPPORTED_SYMBOLS[symbol]['name']

    print(f"\n🎯 {symbol_name}({symbol}) 交易分析:")
    print(f"📊 交易信号: {signal_data['signal']}")
    print(f"💪 信心程度: {signal_data['confidence']}")
    print(f"📝 理由: {signal_data['reason']}")
    
    # 显示风险摘要
    risk_summary = risk_manager.get_risk_summary(current_position, current_price)
    print(risk_summary)
    
    # 打印技术指标状态
    if 'technical_indicators' in signal_data:
        print("【技术指标状态】")
        tech_indicators = signal_data['technical_indicators']
        for indicator_name, indicator_data in tech_indicators.items():
            if 'signal' in indicator_data:
                print(f"  {indicator_name.upper()}: {indicator_data['signal']}")

    if TRADE_CONFIG['test_mode']:
        print("🧪 测试模式 - 仅模拟交易")
        return

    try:
        # 检查是否可以开新仓
        can_trade = can_open_new_trade(exchange)
        
        if signal_data['signal'] == 'BUY':
            if current_position and current_position['side'] == 'short':
                print("🔄 平空仓...")
                exchange.create_market_buy_order(
                    symbol,
                    current_position['size'],
                    {'posSide': 'short'}
                )
            elif not current_position and can_trade:
                # 开多仓
                trade_amount = get_trade_amount(symbol)
                print(f"📈 开多仓，数量: {trade_amount}...")
                exchange.create_market_buy_order(
                    symbol,
                    trade_amount,
                    {'posSide': 'long'}
                )
            elif current_position and current_position['side'] == 'long':
                print("✅ 已持有多仓，保持持仓")
            else:
                print("🚫 持仓已满，无法开新仓")

        elif signal_data['signal'] == 'SELL':
            if current_position and current_position['side'] == 'long':
                print("🔄 平多仓...")
                exchange.create_market_sell_order(
                    symbol,
                    current_position['size'],
                    {'posSide': 'long'}
                )
            elif not current_position and can_trade:
                # 开空仓
                trade_amount = get_trade_amount(symbol)
                print(f"📉 开空仓，数量: {trade_amount}...")
                exchange.create_market_sell_order(
                    symbol,
                    trade_amount,
                    {'posSide': 'short'}
                )
            elif current_position and current_position['side'] == 'short':
                print("✅ 已持有空仓，保持持仓")
            else:
                print("🚫 持仓已满，无法开新仓")

        elif signal_data['signal'] == 'HOLD':
            print("⏸️ 建议观望，不执行交易")
            return

        print("✅ 订单执行成功")
        time.sleep(2)
        position = get_current_position(exchange, symbol)
        print(f"📋 更新后持仓: {position}")

    except Exception as e:
        print(f"❌ {symbol}订单执行失败: {e}")