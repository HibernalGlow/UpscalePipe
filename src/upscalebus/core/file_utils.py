"""
文件系统工具模块 - 提供文件和目录操作的辅助函数
"""
import os
import zipfile
from loguru import logger

def remove_empty_directories(directory):
    """删除指定目录下的所有空文件夹"""
    removed_count = 0
    for root, dirs, _ in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查文件夹是否为空
                    os.rmdir(dir_path)
                    removed_count += 1
                    logger.info(f"[#process_log]已删除空文件夹: {dir_path}")
            except Exception as e:
                logger.info(f"[#process_log]删除空文件夹失败 {dir_path}: {e}")
    return removed_count

def remove_temp_files(directory):
    """删除指定目录下的所有 .tdel 和 .bak 文件"""
    removed_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.tdel', '.bak')):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    removed_count += 1
                    logger.info(f"[#process_log]已删除临时文件: {file_path}")
                except Exception as e:
                    logger.info(f"[#process_log]删除临时文件失败 {file_path}: {e}")
    return removed_count

def count_files_in_zip(zip_path):
    """统计zip文件中的文件数量，忽略特定类型的文件"""
    ignore_extensions = ('.md', '.yaml', '.yml', '.txt', '.json', '.db', '.ini')
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            valid_files = [name for name in zip_file.namelist() 
                         if not name.lower().endswith(ignore_extensions)
                         and not name.endswith('/')
                         and zip_file.getinfo(name).file_size > 0]
            return len(valid_files)
    except Exception as e:
        logger.info(f"[#process_log]读取zip文件失败 {zip_path}: {str(e)}")
        return 0