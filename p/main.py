import time
import schedule
from datetime import datetime

from config import init_deepseek_client, init_exchange, TRADE_CONFIG, TECHNICAL_INDICATORS, SUPPORTED_SYMBOLS, last_analysis_time
from exchange_api import setup_exchange
from data_fetcher import get_all_symbols_data
from technical_analyzer import calculate_technical_indicators
from ai_analyzer import analyze_with_deepseek
from executor import execute_trade
from risk_manager import RiskManager

def should_analyze(symbol):
    """判断是否应该执行策略分析"""
    current_time = time.time()
    last_time = last_analysis_time.get(symbol, 0)
    
    # 如果距离上次分析超过15分钟，则执行分析
    if current_time - last_time >= TRADE_CONFIG['analysis_interval']:
        last_analysis_time[symbol] = current_time
        return True
    return False

def trading_bot(deepseek_client, exchange, risk_manager):
    """主交易机器人函数 - 分离的风险监控和策略分析"""
    print("\n" + "=" * 80)
    print(f"🏁 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 1. 获取所有币种数据
    print("📊 获取多币种市场数据...")
    price_data_dict, current_price_dict = get_all_symbols_data(exchange)
    
    if not price_data_dict or not current_price_dict:
        print("❌ 无法获取市场数据")
        return

    # 2. 实时监控所有持仓的止盈止损（每5秒执行）
    print("🔐 执行高频风险监控...")
    risk_signals = risk_manager.monitor_positions(current_price_dict)
    if risk_signals:
        risk_manager.execute_risk_management(risk_signals)
        print("✅ 风险管理执行完成")

    # 3. 为每个币种执行策略分析（每15分钟执行一次）
    print("\n🤖 检查策略分析条件...")
    for symbol, price_data in price_data_dict.items():
        if not SUPPORTED_SYMBOLS[symbol]['enabled']:
            continue
            
        symbol_name = SUPPORTED_SYMBOLS[symbol]['name']
        
        # 检查是否应该执行策略分析
        if not should_analyze(symbol):
            print(f"⏳ {symbol_name} 未到分析时间，跳过策略分析")
            continue
            
        print(f"\n{'='*50}")
        print(f"🔍 执行 {symbol_name}({symbol}) 15分钟策略分析")
        print(f"{'='*50}")
        
        print(f"💰 当前价格: ${price_data['price']:,.4f}")
        print(f"📈 15分钟价格变化: {price_data['price_change']:+.2f}%")

        # 计算技术指标（基于15分钟K线）
        technical_indicators = calculate_technical_indicators(price_data['full_data'])

        # 使用DeepSeek分析（15分钟策略）
        signal_data = analyze_with_deepseek(deepseek_client, exchange, price_data, technical_indicators)
        if not signal_data:
            print(f"❌ {symbol_name}分析失败，跳过")
            continue

        # 执行交易
        execute_trade(exchange, risk_manager, signal_data, price_data)
        
        # 添加延迟避免API限制
        time.sleep(1)

def main():
    """主函数"""
    print("🚀 多币种高频风险监控 + 15分钟策略交易机器人启动成功！")

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
    print(f"📊 策略分析频率: 每{TRADE_CONFIG['analysis_interval']}秒一次 (15分钟)")
    
    # 显示交易币种
    enabled_symbols = [f"{SUPPORTED_SYMBOLS[s]['name']}({s})" for s in TRADE_CONFIG['symbols'] if SUPPORTED_SYMBOLS[s]['enabled']]
    print(f"📈 交易币种: {', '.join(enabled_symbols)}")
    
    # 显示风险管理配置
    from config import RISK_MANAGEMENT
    print(f"🔐 风险管理配置:")
    print(f"   止损: {RISK_MANAGEMENT['stop_loss_percent']}%")
    print(f"   止盈: {RISK_MANAGEMENT['take_profit_percent']}%")

    # 设置交易所
    if not setup_exchange(exchange):
        print("❌ 交易所初始化失败，程序退出")
        return

    print("\n🔄 进入主循环...")
    
    # 立即执行一次
    print("🎯 执行首次分析...")
    trading_bot(deepseek_client, exchange, risk_manager)
    
    # 高频循环执行
    execution_count = 0
    while True:
        try:
            execution_count += 1
            print(f"\n🔄 第{execution_count}次风险监控...")
            trading_bot(deepseek_client, exchange, risk_manager)
            
            # 等待指定间隔
            print(f"⏳ 等待{TRADE_CONFIG['execution_interval']}秒后继续监控...")
            time.sleep(TRADE_CONFIG['execution_interval'])
            
        except KeyboardInterrupt:
            print("\n🛑 用户中断程序")
            break
        except Exception as e:
            print(f"❌ 主循环异常: {e}")
            print("🔄 5秒后重试...")
            time.sleep(5)

if __name__ == "__main__":
    main()