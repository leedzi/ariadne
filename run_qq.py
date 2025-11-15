"""
QQ Bot启动文件
基于NoneBot2和NapCat实现
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebot.log import logger, default_format
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def init_nonebot():
    """初始化NoneBot"""
    # 初始化NoneBot
    nonebot.init()
    
    # 注册适配器
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    
    # 配置日志
    logger.add(
        "logs/qq_bot_{time}.log",
        rotation="00:00",
        retention="7 days",
        format=default_format,
        level="INFO"
    )
    
    logger.info("=" * 50)
    logger.info("QQ Bot 启动中...")
    logger.info("=" * 50)


def load_plugins():
    """加载插件"""
    try:
        # 加载本地插件目录
        nonebot.load_plugins("plugins")
        logger.success("✅ 插件加载完成")
        
        # 显示已加载的插件
        plugins = nonebot.get_loaded_plugins()
        logger.info(f"已加载 {len(plugins)} 个插件:")
        for plugin in plugins:
            logger.info(f"  - {plugin.name}")
    except Exception as e:
        logger.error(f"❌ 插件加载失败: {e}")
        raise


def check_environment():
    """检查运行环境"""
    logger.info("正在检查运行环境...")
    
    # 检查必要的目录
    dirs = ['logs', 'data', 'temp', 'plugins']
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            logger.info(f"✅ 创建目录: {dir_name}")
    
    # 检查配置文件
    env_file = Path('.env.prod')
    if not env_file.exists():
        logger.warning("⚠️  .env.prod 文件不存在，使用默认配置")
        # 创建默认配置
        create_default_env()
    else:
        logger.success("✅ 找到配置文件: .env.prod")
    
    logger.success("✅ 环境检查完成")


def create_default_env():
    """创建默认环境配置"""
    default_env = """# NoneBot2 配置文件
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
DRIVER=~fastapi+~httpx+~websockets

# OneBot配置
ONEBOT_ACCESS_TOKEN=your_token_here

# 超级用户（管理员QQ号）
SUPERUSERS=["123456789"]

# 命令前缀
COMMAND_START=["/", ""]
COMMAND_SEP=["."]
"""
    
    with open('.env.prod', 'w', encoding='utf-8') as f:
        f.write(default_env)
    
    logger.info("✅ 已创建默认配置文件: .env.prod")
    logger.warning("⚠️  请修改 .env.prod 中的配置后重新启动")


def print_startup_info():
    """打印启动信息"""
    logger.info("")
    logger.info("=" * 50)
    logger.info("🤖 QQ Bot 启动成功！")
    logger.info("=" * 50)
    logger.info("📝 使用说明:")
    logger.info("  1. 确保 NapCat 已启动并登录QQ")
    logger.info("  2. 私聊Bot发送消息即可对话")
    logger.info("  3. 群聊中@Bot发送消息")
    logger.info("  4. 发送 /help 查看帮助")
    logger.info("=" * 50)
    logger.info("🔧 配置文件: .env.prod")
    logger.info("📂 插件目录: ./plugins")
    logger.info("📋 日志目录: ./logs")
    logger.info("=" * 50)
    logger.info("")


def main():
    """主函数"""
    try:
        # 检查环境
        check_environment()
        
        # 初始化NoneBot
        init_nonebot()
        
        # 加载插件
        load_plugins()
        
        # 打印启动信息
        print_startup_info()
        
        # 启动Bot
        nonebot.run()
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()