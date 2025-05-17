"""
文件系统工具模块 - 提供文件和目录操作的辅助函数
"""
import os
import zipfile
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track
from rich.prompt import Confirm

from .config_manager import config

# 创建Rich控制台对象
console = Console()

# 从配置文件加载安全操作设置
MIN_VALID_FILE_SIZE = config.get_value("file_operations.min_valid_file_size", 1024 * 1024)  # 默认1MB
SIZE_DIFFERENCE_THRESHOLD = config.get_value("file_operations.size_difference_threshold", 0.5)  # 默认50%

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
                    logger.info(f"[#processing]已删除空文件夹: {dir_path}")
            except Exception as e:
                logger.info(f"[#processing]删除空文件夹失败 {dir_path}: {e}")
    return removed_count

def remove_temp_files(directory):
    """删除指定目录下的临时文件（根据配置的扩展名）"""
    # 从配置文件获取临时文件扩展名
    temp_extensions = tuple(config.get_value("temp_extensions", ['.tdel', '.bak']))
    
    removed_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(temp_extensions):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    removed_count += 1
                    logger.info(f"[#processing]已删除临时文件: {file_path}")
                except Exception as e:
                    logger.info(f"[#processing]删除临时文件失败 {file_path}: {e}")
    return removed_count

def count_files_in_zip(zip_path):
    """统计zip文件中的文件数量，忽略特定类型的文件"""
    # 从配置文件获取要忽略的扩展名
    ignore_extensions = tuple(config.get_value("file_operations.ignored_extensions", 
                                             ['.md', '.yaml', '.yml', '.txt', '.json', '.db', '.ini']))
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            valid_files = [name for name in zip_file.namelist() 
                         if not name.lower().endswith(ignore_extensions)
                         and not name.endswith('/')
                         and zip_file.getinfo(name).file_size > 0]
            return len(valid_files), sum(zip_file.getinfo(name).file_size for name in valid_files)
    except Exception as e:
        logger.info(f"[#processing]读取zip文件失败 {zip_path}: {str(e)}")
        return 0, 0

def format_size(size_in_bytes):
    """将字节大小转换为人类可读的格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def is_safe_to_overwrite(source_path, target_path, min_size=MIN_VALID_FILE_SIZE):
    """
    检查是否可以安全地覆盖目标文件
    
    Args:
        source_path: 源文件路径
        target_path: 目标文件路径
        min_size: 最小有效文件大小（字节）
        
    Returns:
        tuple: (is_safe, reason, source_info, target_info)
            - is_safe: 布尔值，表示是否安全
            - reason: 如果不安全，给出原因
            - source_info: 源文件信息
            - target_info: 目标文件信息
    """
    if not os.path.exists(source_path):
        return False, "源文件不存在", None, None
    
    if not os.path.exists(target_path):
        # 目标文件不存在，直接复制
        source_size = os.path.getsize(source_path)
        if source_size < min_size:
            return False, f"源文件过小 ({format_size(source_size)})", {"size": source_size}, None
        return True, "目标文件不存在，可以安全复制", {"size": source_size}, None
    
    source_size = os.path.getsize(source_path)
    target_size = os.path.getsize(target_path)
    
    source_info = {"size": source_size}
    target_info = {"size": target_size}
    
    # 文件过小检查
    if source_size < min_size:
        return False, f"源文件过小 ({format_size(source_size)})", source_info, target_info
    
    # 源文件明显小于目标文件
    if source_size < target_size * SIZE_DIFFERENCE_THRESHOLD:
        return False, f"源文件({format_size(source_size)})明显小于目标文件({format_size(target_size)})", source_info, target_info
    
    # 如果是压缩包，比较内部文件数量
    if source_path.lower().endswith(('.zip', '.cbz')):
        source_files, source_content_size = count_files_in_zip(source_path)
        target_files, target_content_size = count_files_in_zip(target_path)
        
        source_info["files"] = source_files
        source_info["content_size"] = source_content_size
        target_info["files"] = target_files
        target_info["content_size"] = target_content_size
        
        if source_files < target_files * SIZE_DIFFERENCE_THRESHOLD:
            return False, f"源压缩包内文件数量({source_files})明显少于目标压缩包({target_files})", source_info, target_info
        
        if source_content_size < target_content_size * SIZE_DIFFERENCE_THRESHOLD:
            return False, f"源压缩包内容大小({format_size(source_content_size)})明显小于目标压缩包({format_size(target_content_size)})", source_info, target_info
    
    return True, "文件检查通过，可以安全覆盖", source_info, target_info

def scan_directory_structure(root_dir: str) -> Dict:
    """
    扫描目录结构，返回层次化的目录信息
    
    Args:
        root_dir: 要扫描的根目录
        
    Returns:
        dict: 包含目录结构和文件信息的嵌套字典
    """
    result = {
        "path": root_dir,
        "name": os.path.basename(root_dir) or root_dir,
        "type": "directory",
        "subdirs": [],
        "files": [],
        "archive_count": 0,
        "total_size": 0
    }
    
    try:
        items = os.listdir(root_dir)
        
        dirs = []
        files = []
        
        for item in items:
            full_path = os.path.join(root_dir, item)
            
            if os.path.isdir(full_path):
                dirs.append(item)
            else:
                file_size = os.path.getsize(full_path)
                file_info = {
                    "name": item,
                    "path": full_path,
                    "size": file_size,
                    "is_archive": item.lower().endswith(('.zip', '.cbz', '.rar', '.7z'))
                }
                files.append(file_info)
                result["total_size"] += file_size
                if file_info["is_archive"]:
                    result["archive_count"] += 1
        
        # 处理子目录
        for dir_name in dirs:
            subdir_path = os.path.join(root_dir, dir_name)
            subdir_info = scan_directory_structure(subdir_path)
            result["subdirs"].append(subdir_info)
            result["archive_count"] += subdir_info["archive_count"]
            result["total_size"] += subdir_info["total_size"]
        
        # 添加文件信息
        result["files"] = files
        
    except Exception as e:
        logger.error(f"扫描目录 {root_dir} 时出错: {str(e)}")
    
    return result

def backup_file(file_path, backup_dir=None):
    """
    创建文件备份
    
    Args:
        file_path: 要备份的文件路径
        backup_dir: 备份目录，如果为None，则在同一目录下创建备份
        
    Returns:
        str: 备份文件的路径
    """
    if not os.path.exists(file_path):
        logger.warning(f"要备份的文件不存在: {file_path}")
        return None
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_name = os.path.basename(file_path)
    backup_name = f"{file_name}.{timestamp}.bak"
    
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, backup_name)
    else:
        backup_path = os.path.join(os.path.dirname(file_path), backup_name)
    
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"[#processing]已创建文件备份: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"创建文件备份失败: {str(e)}")
        return None