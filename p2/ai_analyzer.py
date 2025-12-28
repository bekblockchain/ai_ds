import json
from config import price_history, signal_history, TECHNICAL_INDICATORS, SUPPORTED_SYMBOLS, initialize_symbol_data
from data_fetcher import build_kline_text
from technical_analyzer import build_technical_analysis_text
from exchange_api import get_current_position, can_open_new_trade

def analyze_with_deepseek(deepseek_client, exchange, price_data, technical_indicators):
    """使用DeepSeek分析市场并生成高频交易信号"""
    
    symbol = price_data['symbol']
    initialize_symbol_data(symbol)
    
    # 添加当前价格到历史记录
    price_history[symbol].append(price_data)
    if len(price_history[symbol]) > 10:  # 高频交易减少历史记录长度
        price_history[symbol].pop(0)

    # 构建K线数据文本
    kline_text = build_kline_text(price_data)

    # 构建技术指标文本
    indicator_text = build_technical_analysis_text(technical_indicators)

    # 使用高频策略增强分析
    from hft_strategy import hft_strategy
    hft_signal = hft_strategy.generate_trading_signal(
        symbol, 
        price_data['price'], 
        technical_indicators
    )
    
    # 添加高频策略分析结果
    hft_analysis = ""
    if hft_signal:
        hft_analysis = f"\n【高频策略信号】\n信号: {hft_signal['signal']}\n信心: {hft_signal['confidence']}\n理由: {hft_signal['reason']}"
        
        # 如果有快速止损止盈价格，也添加到分析中
        if 'quick_stop_loss' in hft_signal:
            hft_analysis += f"\n快速止损: {hft_signal['quick_stop_loss']:.4f}"
        if 'quick_take_profit' in hft_signal:
            hft_analysis += f"\n快速止盈: {hft_signal['quick_take_profit']:.4f}"

    # 添加上次交易信号
    signal_text = ""
    if signal_history[symbol]:
        last_signal = signal_history[symbol][-1]
        signal_text = f"\n【上次交易信号】\n信号: {last_signal.get('signal', 'N/A')}\n信心: {last_signal.get('confidence', 'N/A')}"
        if last_signal.get('timestamp'):
            signal_text += f"\n时间: {last_signal['timestamp']}"

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
    
    # 高频策略专用prompt - 修复：加入hft_analysis
    prompt = f"""
    你是一个高频加密货币交易分析师。请基于以下{symbol_name}({symbol}) 5分钟周期数据进行高频策略分析：

    {kline_text}

    {indicator_text}

    {hft_analysis}  # 这里加入了高频策略分析

    {signal_text}

    【当前行情】
    - 币种: {symbol_name}({symbol})
    - 当前价格: ${price_data['price']:,.4f}
    - 时间: {price_data['timestamp']}
    - 本K线最高: ${price_data['high']:,.4f}
    - 本K线最低: ${price_data['low']:,.4f}
    - 本K线成交量: {price_data['volume']:.2f}
    - 5分钟价格变化: {price_data['price_change']:+.2f}%
    - 当前持仓: {position_text}
    - 交易状态: {trade_status}
    - 启用的技术指标: {indicators_list}  # 新增：告诉AI启用了哪些技术指标

    【高频策略重点分析】
    请重点分析以下高频交易信号条件：
    1. 均线聚合度分析：MA7、MA10、MA30三条均线是否高度聚合（聚合度<0.3%为理想）
    2. 布林带中轨突破：价格是否突破布林带中轨，突破幅度至少0.1%
    3. 均线排列方向：MA7和MA10是否同向排列
    4. 成交量确认：突破时是否有放量支持
    
    【高频交易规则】
    A级信号（强烈推荐）：
    - 均线高度聚合（聚合度<0.2%）+ 突破布林中轨0.1%以上 + 均线同向排列 + 放量
    - 建议：立即执行，使用较大仓位
    
    B级信号（推荐）：
    - 均线中度聚合（聚合度0.2%-0.5%）+ 突破布林中轨 + 均线同向排列
    - 建议：执行交易，使用标准仓位
    
    C级信号（谨慎）：
    - 均线聚合但未突破中轨，或突破但量能不足
    - 建议：观望或轻仓试探
    
    【风险控制要求】
    高频交易必须设置快速止盈止损：
    - 快速止盈：0.3%-0.5%
    - 快速止损：0.2%-0.3%
    - 持仓时间：通常不超过30分钟

    【分析要求】
    1. 基于5分钟K线趋势和技术指标（{indicators_list}）给出交易信号: BUY(买入) / SELL(卖出) / HOLD(观望)
    2. 重点分析均线聚合情况和布林带突破信号
    3. 评估信号强度等级：STRONG（A级）/ MEDIUM（B级）/ WEAK（C级）
    4. 基于高频策略建议合理的快速止损价位（0.2%-0.3%）
    5. 基于高频策略建议合理的快速止盈价位（0.3%-0.5%）
    6. 评估信号信心程度
    7. 请参考高频策略信号的分析结果（如果有）

    【重要提醒】
    - 如果当前已有持仓且交易状态为"持仓已满"，只能给出HOLD或反向平仓信号
    - 高频交易追求小盈利、高胜率，避免持仓过夜
    - 考虑币种波动性：{symbol_name}的波动性为{SUPPORTED_SYMBOLS[symbol].get('volatility', 'medium')}

    【特殊场景处理】
    1. 如果均线高度聚合但价格在中轨附近震荡：建议HOLD，等待明确方向
    2. 如果突破但成交量萎缩：建议降低仓位或HOLD
    3. 如果当前持仓已有盈利超过0.5%：建议部分止盈，移动止损

    请用以下JSON格式回复：
    {{
        "signal": "BUY|SELL|HOLD",
        "signal_strength": "STRONG|MEDIUM|WEAK",
        "reason": "详细分析理由，重点说明均线聚合度、突破情况和成交量",
        "quick_stop_loss": 具体价格,
        "quick_take_profit": 具体价格,
        "confidence": "HIGH|MEDIUM|LOW",
        "suggested_position_size": "FULL|HALF|QUARTER",
        "expected_holding_time": "minutes",
        "risk_level": "LOW|MEDIUM|HIGH"
    }}
    """

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system",
                 "content": f"您是一位专业的加密货币高频交易员，专注于5分钟周期均线聚合突破策略。请严格按照高频交易规则分析，重点评估均线聚合度、布林带突破和成交量配合。"},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=0.3,  # 降低随机性，提高一致性
            max_tokens=800
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

        # 合并AI信号和高频策略信号
        if hft_signal:
            signal_data = merge_signals(signal_data, hft_signal)
        
        # 补充必要字段
        signal_data['timestamp'] = price_data['timestamp']
        signal_data['symbol'] = symbol
        signal_data['technical_indicators'] = technical_indicators
        signal_data['current_price'] = price_data['price']
        
        # 如果是快速信号，标记为quick_signal
        if signal_data.get('signal_strength') == 'STRONG':
            signal_data['quick_signal'] = True
        else:
            signal_data['quick_signal'] = False

        # 保存信号到历史记录
        signal_history[symbol].append(signal_data)
        if len(signal_history[symbol]) > 20:  # 高频交易减少历史记录长度
            signal_history[symbol].pop(0)

        print(f"✅ {symbol_name} AI分析完成:")
        print(f"   信号: {signal_data['signal']} ({signal_data['signal_strength']})")
        print(f"   信心: {signal_data['confidence']}")
        print(f"   建议仓位: {signal_data.get('suggested_position_size', '标准')}")
        
        return signal_data

    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        print(f"原始响应: {response.choices[0].message.content if 'response' in locals() else '无响应'}")
        return None
    except Exception as e:
        print(f"DeepSeek分析{symbol}失败: {e}")
        return None

def merge_signals(ai_signal, hft_signal):
    """合并AI信号和高频策略信号"""
    if not hft_signal or hft_signal['confidence'] != 'HIGH':
        return ai_signal
    
    # 如果高频策略给出高信心信号
    if hft_signal['confidence'] == 'HIGH':
        # 检查信号是否一致
        if ai_signal.get('signal') == hft_signal['signal']:
            # 信号一致，增强信心
            ai_signal['confidence'] = 'HIGH'
            ai_signal['quick_signal'] = True
            ai_signal['merged_reason'] = f"AI与高频策略一致: {hft_signal['reason']}"
        else:
            # 信号冲突，优先使用高频信号
            ai_signal = hft_signal.copy()
            ai_signal['merged_reason'] = "使用高频策略信号（高信心）"
            ai_signal['quick_signal'] = True
    
    return ai_signal

def analyze_quick_reversal(exchange, symbol, position_info, current_price, technical_indicators):
    """分析是否应该执行反手交易"""
    try:
        if not position_info:
            return None
        
        symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
        entry_price = position_info['entry_price']
        side = position_info['side']
        pnl_percent = position_info.get('pnl_percent', 0)
        
        # 检查均线聚合情况
        ma_convergence = technical_indicators.get('ma_convergence', {})
        spread_percent = ma_convergence.get('spread_percent', 100)
        
        # 检查布林带位置
        boll_data = technical_indicators.get('boll', {})
        price_vs_middle = boll_data.get('price_vs_middle', 0)
        
        # 反手交易条件
        reversal_conditions = []
        
        # 条件1：持仓亏损且均线开始反向聚合
        if pnl_percent < -0.2:  # 亏损超过0.2%
            if side == 'long' and price_vs_middle < -0.1:  # 多仓但价格低于中轨
                reversal_conditions.append(f"多仓亏损{pnl_percent:.2f}%且价格低于布林中轨")
                
            elif side == 'short' and price_vs_middle > 0.1:  # 空仓但价格高于中轨
                reversal_conditions.append(f"空仓亏损{pnl_percent:.2f}%且价格高于布林中轨")
        
        # 条件2：均线高度聚合且出现反向金叉/死叉
        if spread_percent < 0.3:  # 均线高度聚合
            cross_signal = ma_convergence.get('cross_signal', '')
            if side == 'long' and cross_signal == '死叉':
                reversal_conditions.append("均线高度聚合且出现死叉")
            elif side == 'short' and cross_signal == '金叉':
                reversal_conditions.append("均线高度聚合且出现金叉")
        
        # 条件3：价格反向突破关键位置
        if side == 'long' and current_price < entry_price * 0.995:  # 跌破入场价0.5%
            reversal_conditions.append("价格跌破入场价0.5%")
        elif side == 'short' and current_price > entry_price * 1.005:  # 涨破入场价0.5%
            reversal_conditions.append("价格涨破入场价0.5%")
        
        if reversal_conditions:
            # 确定反手方向
            if side == 'long':
                new_side = 'short'
                reason = f"多仓反手为空仓: {', '.join(reversal_conditions)}"
            else:
                new_side = 'long'
                reason = f"空仓反手为多仓: {', '.join(reversal_conditions)}"
            
            return {
                'signal': 'SELL' if new_side == 'short' else 'BUY',
                'side': new_side,
                'reason': reason,
                'confidence': 'HIGH' if len(reversal_conditions) >= 2 else 'MEDIUM',
                'is_reversal': True,
                'original_side': side,
                'original_pnl': pnl_percent
            }
        
        return None
        
    except Exception as e:
        print(f"反手交易分析失败: {e}")
        return None

def calculate_signal_score(technical_indicators, price_data):
    """计算信号强度评分（0-100）"""
    score = 50  # 基础分
    
    # 1. 均线聚合度评分 (0-30分)
    if 'ma_convergence' in technical_indicators:
        conv = technical_indicators['ma_convergence']
        spread = conv['spread_percent']
        if spread < 0.1:
            score += 30
        elif spread < 0.3:
            score += 15
        elif spread > 1.0:
            score -= 10
    
    # 2. 布林带突破评分 (0-25分)
    if 'boll' in technical_indicators:
        boll = technical_indicators['boll']
        price_vs_middle = abs(boll['price_vs_middle'])
        if price_vs_middle > 0.2:
            score += 25
        elif price_vs_middle > 0.1:
            score += 15
    
    # 3. 成交量确认评分 (0-20分)
    if 'volume' in technical_indicators:
        volume = technical_indicators['volume']
        if volume['confirmation_signal'] == 'CONFIRMED':
            score += 20
        elif volume['signal'] in ['HIGH_VOLUME', 'MEDIUM_VOLUME']:
            score += 10
    
    # 4. RSI位置评分 (0-15分)
    if 'rsi' in technical_indicators:
        rsi = technical_indicators['rsi']
        if rsi['signal'] in ['OVERSOLD', 'OVERBOUGHT']:
            score += 15  # 极端位置有反转潜力
    
    # 5. 波动率评分 (0-10分)
    if 'atr' in technical_indicators:
        atr = technical_indicators['atr']
        if atr['volatility'] == "正常波动":
            score += 10  # 正常波动最适合高频
    
    return max(0, min(100, score))

def get_signal_strength_from_score(score):
    """根据评分确定信号强度"""
    if score >= 80:
        return 'STRONG'
    elif score >= 60:
        return 'MEDIUM'
    else:
        return 'WEAK'