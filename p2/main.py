import time
import schedule
from datetime import datetime
from datetime import datetime, timedelta
from exchange_api import get_current_position

from config import (init_deepseek_client, init_exchange, TRADE_CONFIG, 
                   TECHNICAL_INDICATORS, SUPPORTED_SYMBOLS, last_analysis_time,
                   update_hft_state, can_trade_hft, HIGH_FREQUENCY_STATE)
from exchange_api import setup_exchange
from data_fetcher import get_all_symbols_data
from technical_analyzer import calculate_technical_indicators
from ai_analyzer import analyze_with_deepseek
from executor import execute_trade
from risk_manager import RiskManager


def get_next_analysis_time():
    """计算下次分析时间（精确对齐5分钟）"""
    now = datetime.now()
    
    # 计算下一个5分钟整点
    minutes = now.minute
    next_minute = ((minutes // 5) + 1) * 5
    if next_minute >= 60:
        next_minute = 0
        now = now.replace(hour=now.hour + 1)
    
    next_time = now.replace(minute=next_minute, second=0, microsecond=0)
    
    # 如果已经过了这个时间，等待到下一个5分钟
    if next_time <= datetime.now():
        next_time = next_time + timedelta(minutes=5)
    
    return next_time

def safe_sleep_until(target_time):
    """安全休眠直到指定时间"""
    current_time = datetime.now()
    if target_time > current_time:
        sleep_seconds = (target_time - current_time).total_seconds()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

def health_check(exchange, deepseek_client):
    """系统健康检查"""
    checks = []
    
    # 1. 检查交易所连接
    try:
        exchange.fetch_time()
        checks.append(("交易所连接", "✅"))
    except Exception as e:
        checks.append(("交易所连接", f"❌ {str(e)}"))
    
    # 2. 检查DeepSeek API
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        checks.append(("DeepSeek API", "✅"))
    except Exception as e:
        checks.append(("DeepSeek API", f"❌ {str(e)}"))
    
    # 3. 检查账户余额
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        checks.append(("账户余额", f"✅ {usdt_balance:.2f} USDT"))
    except Exception as e:
        checks.append(("账户余额", f"❌ {str(e)}"))
    
    # 4. 检查持仓状态
    try:
        positions = get_current_position(exchange)
        if positions:
            checks.append(("持仓状态", f"✅ {len(positions)}个持仓"))
        else:
            checks.append(("持仓状态", "✅ 无持仓"))
    except Exception as e:
        checks.append(("持仓状态", f"❌ {str(e)}"))
    
    # 打印检查结果
    print("\n🔍 系统健康检查:")
    for check_name, status in checks:
        print(f"  {check_name}: {status}")
    
    # 如果有严重错误，返回False
    return all("✅" in status or "无持仓" in status for _, status in checks)
            
def should_analyze(symbol):
    """判断是否应该执行策略分析"""
    current_time = time.time()
    last_time = last_analysis_time.get(symbol, 0)
    
    # 高频模式下，每5分钟执行一次策略分析
    if current_time - last_time >= TRADE_CONFIG['analysis_interval']:
        last_analysis_time[symbol] = current_time
        return True
    return False

def check_quick_signal(symbol, price_data, technical_indicators):
    """检查快速交易信号（基于均线聚合）"""
    try:
        # 检查是否有均线数据
        if 'ma7' not in technical_indicators or 'ma10' not in technical_indicators:
            return None
        
        ma7 = technical_indicators['ma7']['value']
        ma10 = technical_indicators['ma10']['value']
        ma30 = technical_indicators.get('ma30', {}).get('value', ma10)
        current_price = price_data['price']
        
        # 计算均线聚合度
        max_ma = max(ma7, ma10, ma30)
        min_ma = min(ma7, ma10, ma30)
        spread_ratio = (max_ma - min_ma) / current_price
        
        # 检查布林带中轨突破
        boll_middle = technical_indicators.get('boll', {}).get('middle', current_price)
        
        # 快速信号条件：均线高度聚合 + 突破布林中轨
        if spread_ratio < 0.002:  # 均线聚合度小于0.2%
            if current_price > boll_middle * 1.001:  # 突破中轨0.1%
                # 检查MA7和MA10趋势
                ma7_trend = technical_indicators['ma7']['trend']
                ma10_trend = technical_indicators['ma10']['trend']
                
                if ma7_trend == "上升" and ma10_trend == "上升":
                    return {
                        'signal': 'BUY',
                        'reason': f'快速做多信号：均线聚合度{spread_ratio*100:.2f}% + 突破布林中轨',
                        'confidence': 'HIGH',
                        'quick_signal': True
                    }
            
            elif current_price < boll_middle * 0.999:  # 跌破中轨0.1%
                ma7_trend = technical_indicators['ma7']['trend']
                ma10_trend = technical_indicators['ma10']['trend']
                
                if ma7_trend == "下降" and ma10_trend == "下降":
                    return {
                        'signal': 'SELL',
                        'reason': f'快速做空信号：均线聚合度{spread_ratio*100:.2f}% + 跌破布林中轨',
                        'confidence': 'HIGH',
                        'quick_signal': True
                    }
        
        return None
    except Exception as e:
        print(f"检查快速信号失败: {e}")
        return None

def trading_bot(deepseek_client, exchange, risk_manager):
    """主交易机器人函数 - 高频版本"""
    print("\n" + "=" * 80)
    print(f"🏁 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 今日交易次数: {HIGH_FREQUENCY_STATE['daily_trades']}")
    print(f"🔴 连续亏损: {HIGH_FREQUENCY_STATE['consecutive_losses']}")
    print("=" * 80)

    try:
        print("包裹下方代码")
    except Exception as e:
        print(f"❌ 交易机器人异常: {e}")
        import traceback
        traceback.print_exc()  # 打印详细堆栈信息
        
    # 1. 检查高频交易条件
    if not can_trade_hft():
        print("⏸️ 高频交易条件不满足，跳过本轮交易")
        return

    # 2. 获取所有币种数据（5分钟K线）
    print("📊 获取多币种5分钟K线数据...")
    price_data_dict, current_price_dict = get_all_symbols_data(exchange)
    
    if not price_data_dict or not current_price_dict:
        print("❌ 无法获取市场数据")
        return

    # 3. 实时监控所有持仓的止盈止损（每5秒执行）
    print("🔐 执行高频风险监控...")
    risk_signals = risk_manager.monitor_positions(current_price_dict)
    if risk_signals:
        risk_manager.execute_risk_management(risk_signals)
        print("✅ 风险管理执行完成")

    # 4. 为每个币种执行策略分析（每5分钟执行一次）
    print("\n🤖 检查5分钟策略分析条件...")
    for symbol, price_data in price_data_dict.items():
        if not SUPPORTED_SYMBOLS[symbol]['enabled']:
            continue
            
        symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
        
        # 检查是否应该执行策略分析
        if not should_analyze(symbol):
            # 即使不是策略分析时间，也检查快速信号
            try:
                # 计算技术指标用于快速信号检测
                technical_indicators = calculate_technical_indicators(price_data['full_data'])
                
                # 检查快速交易信号
                quick_signal = check_quick_signal(symbol, price_data, technical_indicators)
                if quick_signal:
                    print(f"🚨 {symbol_name} 检测到快速交易信号！")
                    print(f"   信号: {quick_signal['signal']}")
                    print(f"   理由: {quick_signal['reason']}")
                    
                    # 合并信号数据
                    signal_data = quick_signal
                    signal_data['symbol'] = symbol
                    
                    # 执行快速交易
                    execute_trade(exchange, risk_manager, signal_data, price_data)
            except Exception as e:
                print(f"快速信号检查失败: {e}")
            
            continue
            
        print(f"\n{'='*50}")
        print(f"🔍 执行 {symbol_name}({symbol}) 5分钟策略分析")
        print(f"{'='*50}")
        
        print(f"💰 当前价格: ${price_data['price']:,.4f}")
        print(f"📈 5分钟价格变化: {price_data['price_change']:+.2f}%")

        # 计算技术指标（基于5分钟K线）
        technical_indicators = calculate_technical_indicators(price_data['full_data'])

        # 使用DeepSeek分析（5分钟策略）
        signal_data = analyze_with_deepseek(deepseek_client, exchange, price_data, technical_indicators)
        if not signal_data:
            print(f"❌ {symbol_name}分析失败，跳过")
            continue

        # 执行交易
        execute_trade(exchange, risk_manager, signal_data, price_data)
        
        # 添加延迟避免API限制
        time.sleep(0.5)


def main():
    """主函数"""
    print("🚀 多币种高频交易机器人启动成功！")
    print("⚡ 交易模式: 高频策略 (5分钟K线)")
    print("🎯 策略: 均线聚合 + 布林中轨突破")

    # 初始化客户端
    deepseek_client = init_deepseek_client()
    exchange = init_exchange()
    
    # 初始化风险管理器
    risk_manager = RiskManager(exchange)

    if TRADE_CONFIG['test_mode']:
        print("🧪 当前为模拟模式，不会真实下单")
    else:
        print("⚠️ 实盘交易模式，请谨慎操作！")

    print(f"⏰ 风险监控频率: 每{TRADE_CONFIG['execution_interval']}秒一次")
    print(f"📊 策略分析频率: 每{TRADE_CONFIG['analysis_interval']}秒一次 (5分钟)")
    print(f"📈 每日最大交易次数: {TRADE_CONFIG['max_trades_per_day']}")
    
    # 显示交易币种
    enabled_symbols = [f"{SUPPORTED_SYMBOLS[s]['name']}({s})" for s in TRADE_CONFIG['symbols'] if SUPPORTED_SYMBOLS[s]['enabled']]
    print(f"📈 交易币种: {', '.join(enabled_symbols)}")
    
    # 显示风险管理配置
    from config import RISK_MANAGEMENT
    print(f"🔐 高频风险管理配置:")
    print(f"   快速止损: {RISK_MANAGEMENT['quick_stop_loss_percent']}%")
    print(f"   快速止盈: {RISK_MANAGEMENT['quick_take_profit_percent']}%")
    print(f"   固定止损: {RISK_MANAGEMENT['hft_fixed_stop_loss']}%")
    print(f"   固定止盈: {RISK_MANAGEMENT['hft_fixed_take_profit']}%")

    # 设置交易所
    if not setup_exchange(exchange):
        print("❌ 交易所初始化失败，程序退出")
        return

    print("\n🔄 进入高频交易主循环...")
    
    # 立即执行一次
    print("🎯 执行首次分析...")
    trading_bot(deepseek_client, exchange, risk_manager)
    
    # 高频循环执行
    execution_count = 0
    last_full_analysis = time.time()
    
    while True:
        try:
            execution_count += 1
            current_time = time.time()
            
            # 每5秒执行一次风险监控和快速信号检查
            print(f"\n🔄 第{execution_count}次高频监控...")
            
            # 执行交易逻辑
            trading_bot(deepseek_client, exchange, risk_manager)
            
            # 重置每日交易计数（假设一天开始）
            if datetime.now().hour == 0 and datetime.now().minute == 0:
                from config import trade_count_today, consecutive_losses
                trade_count_today = 0
                consecutive_losses = 0
                HIGH_FREQUENCY_STATE['daily_trades'] = 0
                HIGH_FREQUENCY_STATE['consecutive_losses'] = 0
                print("🔄 新的一天，重置交易计数")
            
            # 等待指定间隔
            print(f"⏳ 等待{TRADE_CONFIG['execution_interval']}秒后继续监控...")
            time.sleep(TRADE_CONFIG['execution_interval'])
            
        except KeyboardInterrupt:
            print("\n🛑 用户中断程序")
            break
        except Exception as e:
            print(f"❌ 主循环异常: {e}")
            print("🔄 3秒后重试...")
            time.sleep(3)

if __name__ == "__main__":
    main()