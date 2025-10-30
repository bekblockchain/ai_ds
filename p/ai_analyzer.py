import json
from config import price_history, signal_history, TECHNICAL_INDICATORS, SUPPORTED_SYMBOLS, initialize_symbol_data
from data_fetcher import build_kline_text
from technical_analyzer import build_technical_analysis_text
from exchange_api import get_current_position, can_open_new_trade

def analyze_with_deepseek(deepseek_client, exchange, price_data, technical_indicators):
    """使用DeepSeek分析市场并生成交易信号"""

    symbol = price_data['symbol']
    initialize_symbol_data(symbol)
    
    # 添加当前价格到历史记录
    price_history[symbol].append(price_data)
    if len(price_history[symbol]) > 20:
        price_history[symbol].pop(0)

    # 构建K线数据文本
    kline_text = build_kline_text(price_data)

    # 构建技术指标文本
    indicator_text = build_technical_analysis_text(technical_indicators)

    # 添加上次交易信号
    signal_text = ""
    if signal_history[symbol]:
        last_signal = signal_history[symbol][-1]
        signal_text = f"\n【上次交易信号】\n信号: {last_signal.get('signal', 'N/A')}\n信心: {last_signal.get('confidence', 'N/A')}"

    # 添加当前持仓信息
    current_pos = get_current_position(exchange, symbol)
    position_text = "无持仓" if not current_pos else f"{current_pos['side']}仓, 数量: {current_pos['size']}, 盈亏: {current_pos['unrealized_pnl']:.2f}USDT"

    # 检查是否可以开新仓
    can_trade = can_open_new_trade(exchange)
    trade_status = "可以开新仓" if can_trade else "持仓已满，只能平仓"

    # 构建启用的指标列表
    enabled_indicators = [indicator['name'] for indicator in TECHNICAL_INDICATORS.values() if indicator['enabled']]
    indicators_list = "、".join(enabled_indicators)

    symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
    
    prompt = f"""
    你是一个专业的加密货币交易分析师。请基于以下{symbol_name}({symbol}) {price_data['timeframe']}周期数据进行分析：

    {kline_text}

    {indicator_text}

    {signal_text}

    【当前行情】
    - 币种: {symbol_name}({symbol})
    - 当前价格: ${price_data['price']:,.4f}
    - 时间: {price_data['timestamp']}
    - 本K线最高: ${price_data['high']:,.4f}
    - 本K线最低: ${price_data['low']:,.4f}
    - 本K线成交量: {price_data['volume']:.2f}
    - 价格变化: {price_data['price_change']:+.2f}%
    - 当前持仓: {position_text}
    - 交易状态: {trade_status}

    【技术指标配置】
    当前启用的技术指标: {indicators_list}

    【分析要求】
    1. 基于{price_data['timeframe']}K线趋势和上述技术指标给出交易信号: BUY(买入) / SELL(卖出) / HOLD(观望)
    2. 简要分析理由（重点分析技术指标的协同或矛盾信号）
    3. 基于技术分析建议合理的止损价位
    4. 基于技术分析建议合理的止盈价位
    5. 评估信号信心程度

    【重要提醒】
    - 如果当前已有持仓且交易状态为"持仓已满"，只能给出HOLD或反向平仓信号
    - 考虑币种特性：{symbol_name}的波动性可能与其他币种不同

    请用以下JSON格式回复：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "分析理由",
        "stop_loss": 具体价格,
        "take_profit": 具体价格,
        "confidence": "HIGH|MEDIUM|LOW"
    }}
    """

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system",
                 "content": f"您是一位专业的加密货币交易员，专注于多币种{price_data['timeframe']}周期趋势分析。请结合K线形态和多种技术指标进行综合判断，注意不同币种的特性。"},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )

        # 安全解析JSON
        result = response.choices[0].message.content
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = result[start_idx:end_idx]
            signal_data = json.loads(json_str)
        else:
            print(f"无法解析JSON: {result}")
            return None

        # 保存信号到历史记录
        signal_data['timestamp'] = price_data['timestamp']
        signal_data['symbol'] = symbol
        signal_data['technical_indicators'] = technical_indicators
        signal_history[symbol].append(signal_data)
        if len(signal_history[symbol]) > 30:
            signal_history[symbol].pop(0)

        return signal_data

    except Exception as e:
        print(f"DeepSeek分析{symbol}失败: {e}")
        return None