# d:\1VSCODE\Projects\ImageAll\UpscalePipe\src\upsaclebus\upscale_bus.py
import os
# 从新模块导入功能
from .core.file_utils import remove_temp_files
from .core.archive_processor import process_corrupted_archives, compare_and_copy_archives
from loguru import logger
import os
import sys
from pathlib import Path
from datetime import datetime

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
        project_root = Path(__file__).parent.resolve()
    
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


logger, config_info = setup_logger(app_name="upscale_bus", console_output=False)

# error_handler 模块似乎未使用，暂时注释掉
# from .error_handler import handle_file_operation

# 移除旧的函数定义和配置代码
# ... (移除 remove_empty_directories, remove_temp_files, count_files_in_zip)
# ... (移除 compare_and_copy_archives)
# ... (移除 check_archive, load_check_history, save_check_history, process_corrupted_archives)
# ... (移除 TEXTUAL_LAYOUT, config, logger, config_info, TextualLoggerManager setup)
from textual_logger import TextualLoggerManager

# Textual 布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体统计",
        "style": "lightyellow"
    },
    "current_progress": {
        "ratio": 4,
        "title": "🔄 文件处理",
        "style": "lightcyan"
    },
    "process_log": {
        "ratio": 1,
        "title": "📝 处理日志",
        "style": "lightmagenta"
    },
    "update_log": {
        "ratio": 1,
        "title": "ℹ️ 状态更新",
        "style": "lightblue"
    }
}

TextualLoggerManager.set_layout(TEXTUAL_LAYOUT,config_info['log_file'])

def main():
    """主执行函数"""
    # 定义目录路径列表
    directory_pairs = [
        ("D:\\3EHV", "E:\\7EHV"),
        ("E:\\7EHV", "E:\\999EHV"),
    ]
    is_move = True  # 设置为True则移动文件，False则复制文件

    # 依次处理每对目录
    for source_dir, target_dir in directory_pairs:
        logger.info(f"[#current_stats]\n开始处理目录对：")
        logger.info(f"[#process_log]源目录: {source_dir}")
        logger.info(f"[#process_log]目标目录: {target_dir}")

        if not os.path.exists(source_dir):
            logger.info("[#process_log]源目录不存在！")
            continue
        # 目标目录不存在时，compare_and_copy_archives 会自动创建

        # 先检测损坏的压缩包
        logger.info("[#process_log]\n开始检测损坏压缩包...")
        process_corrupted_archives(source_dir) # 调用重构后的函数

        # 删除临时文件
        temp_files_removed = remove_temp_files(source_dir) # 调用重构后的函数
        logger.info(f"[#process_log]\n已删除 {temp_files_removed} 个临时文件")

        # 执行文件移动/复制操作
        compare_and_copy_archives(source_dir, target_dir, is_move) # 调用重构后的函数

if __name__ == "__main__":
    main()