# d:\1VSCODE\Projects\ImageAll\UpscalePipe\src\upsaclebus\upscale_bus.py
import os
# 从新模块导入功能
from .logger_config import logger # 导入配置好的 logger
from .file_utils import remove_temp_files
from .archive_processor import process_corrupted_archives, compare_and_copy_archives

# error_handler 模块似乎未使用，暂时注释掉
# from .error_handler import handle_file_operation

# 移除旧的函数定义和配置代码
# ... (移除 remove_empty_directories, remove_temp_files, count_files_in_zip)
# ... (移除 compare_and_copy_archives)
# ... (移除 check_archive, load_check_history, save_check_history, process_corrupted_archives)
# ... (移除 TEXTUAL_LAYOUT, config, logger, config_info, TextualLoggerManager setup)

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