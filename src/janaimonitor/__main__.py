"""
主监控脚本 - 负责启动和协调监控流程
"""
import argparse
from .core.file_checker import run_bad_zip_check
from .core.process_monitor import run_manga_with_monitor
import os
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

def setup_logger(app_name="app", project_root=None, console_output=True):
    """配置 Loguru 日志系统
    
    Args:
        app_name: 应用名称，用于日志目录
        project_root: 项目根目录，默认为当前文件所在目录
        console_output: 是否输出到控制台，默认为True
        
    Returns:
        tuple: (logger, config_info)
            - logger: 配置好的 logger 实例
            - config_info: 包含日志配置信息的字典
    """
    # 获取项目根目录
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent.resolve()
    
    # 清除默认处理器
    logger.remove()
    
    # 有条件地添加控制台处理器（简洁版格式）
    if console_output:
        logger.add(
            sys.stdout,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{elapsed}</blue> | <level>{level.icon} {level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
        )
    
    # 使用 datetime 构建日志路径
    current_time = datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")
    hour_str = current_time.strftime("%H")
    minute_str = current_time.strftime("%M%S")
    
    # 构建日志目录和文件路径
    log_dir = os.path.join(project_root, "logs", app_name, date_str, hour_str)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{minute_str}.log")
    
    # 添加文件处理器
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {elapsed} | {level.icon} {level: <8} | {name}:{function}:{line} - {message}",
    )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info
# 初始化日志
logger, config_info = setup_logger(app_name="janai_monitor", console_output=True)

from textual_logger import TextualLoggerManager

# Textual 布局配置
TEXTUAL_LAYOUT = {
    "stats": {
        "ratio": 2,
        "title": "📊 总体统计",
        "style": "lightyellow"
    },
    "fileops": {
        "ratio": 3,
        "title": "🔄 文件处理",
        "style": "lightcyan"
    },
    "processing": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightpink"
    },
    "updating": {
        "ratio": 1,
        "title": "ℹ️ 状态更新",
        "style": "lightgreen"
    }
}

TextualLoggerManager.set_layout(TEXTUAL_LAYOUT,config_info['log_file'])

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MangaJaNaiConverter监控工具')
    parser.add_argument('--force_check', action='store_true', help='强制检查所有压缩包文件，忽略已处理记录')
    args = parser.parse_args()
    
    logger.info("启动终端监控程序...")
    
    # 启动时先执行一次文件检查
    logger.info("执行初始文件检查...")
    initial_check = run_bad_zip_check(force_check=args.force_check)
    if initial_check:
        logger.info("初始文件检查完成并成功")
    else:
        logger.warning("初始文件检查失败或发现问题")
        
    # 启动并监控MangaJaNaiConverter
    try:
        run_manga_with_monitor(force_check=args.force_check)
    except KeyboardInterrupt:
        logger.info("监控程序被用户中断")
    except Exception as e:
        logger.error(f"监控程序发生错误: {str(e)}")

if __name__ == "__main__":
    main()
