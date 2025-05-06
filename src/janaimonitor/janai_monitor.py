"""
主监控脚本 - 负责启动和协调监控流程
"""
import argparse
from loguru import logger
from .logger import setup_logger
from .file_checker import run_bad_zip_check
from .process_monitor import run_manga_with_monitor

# 初始化日志
logger, config_info = setup_logger(app_name="janai_monitor", console_output=True)

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
