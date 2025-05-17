"""
文件操作模块 - 提供文件和目录操作的基础功能
"""
import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

from loguru import logger

from .config import config

def format_size(size_in_bytes):
    """将字节大小转换为人类可读的格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def remove_empty_directories(directory):
    """
    删除指定目录下的所有空文件夹
    
    Args:
        directory: 要处理的目录
    
    Returns:
        int: 删除的空文件夹数量
    """
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
    """
    删除指定目录下的所有临时文件（根据配置的扩展名）
    
    Args:
        directory: 要处理的目录
        
    Returns:
        int: 删除的文件数量
    """
    # 从配置获取临时文件扩展名
    temp_extensions = tuple(config.get_value('file_operations.temp_extensions', ['.tdel', '.bak']))
    
    removed_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(temp_extensions):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    removed_count += 1
                    logger.info(f"[#processing]已删除临时文件: {file_path}")
                except Exception as e:
                    logger.info(f"[#processing]删除临时文件失败 {file_path}: {e}")
    return removed_count

def count_files_in_zip(zip_path):
    """
    统计zip文件中的文件数量和总大小，忽略特定类型的文件
    
    Args:
        zip_path: zip文件路径
        
    Returns:
        tuple: (文件数量, 内容总大小)
    """
    # 从配置获取忽略的扩展名
    ignore_extensions = tuple(config.get_value('file_operations.ignored_extensions', 
                                              ['.md', '.yaml', '.yml', '.txt', '.json', '.db', '.ini']))
    
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            valid_files = [name for name in zip_file.namelist() 
                          if not name.lower().endswith(ignore_extensions)
                          and not name.endswith('/')
                          and zip_file.getinfo(name).file_size > 0]
            
            total_size = sum(zip_file.getinfo(name).file_size for name in valid_files)
            return len(valid_files), total_size
    except Exception as e:
        logger.info(f"[#processing]读取zip文件失败 {zip_path}: {str(e)}")
        return 0, 0

def is_safe_to_overwrite(source_path, target_path):
    """
    检查是否可以安全地覆盖目标文件
    
    Args:
        source_path: 源文件路径
        target_path: 目标文件路径
        
    Returns:
        tuple: (is_safe, reason, source_info, target_info)
            - is_safe: 布尔值，表示是否安全
            - reason: 如果不安全，给出原因
            - source_info: 源文件信息
            - target_info: 目标文件信息
    """    # 从配置获取安全阈值
    min_size = config.get_value('file_operations.min_valid_file_size', 1024 * 1024)  # 默认1MB
    size_threshold = config.get_value('file_operations.size_difference_threshold', 0.5)  # 默认50%
    file_count_threshold = config.get_value('file_operations.file_count_difference_threshold', 0.0)  # 默认0%，即要求完全相等
    
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
    if source_size < target_size * size_threshold:
        return False, f"源文件({format_size(source_size)})明显小于目标文件({format_size(target_size)})", source_info, target_info
      # 从配置获取压缩包扩展名
    archive_extensions = tuple(config.get_value('archive_extensions', 
                                               ['.zip', '.cbz', '.rar', '.7z']))
    
    # 如果是压缩包，比较内部文件数量
    if any(source_path.lower().endswith(ext) for ext in archive_extensions):
        source_files, source_content_size = count_files_in_zip(source_path)
        target_files, target_content_size = count_files_in_zip(target_path)
        
        source_info["files"] = source_files
        source_info["content_size"] = source_content_size
        target_info["files"] = target_files
        target_info["content_size"] = target_content_size
        if source_files < target_files * (1.0 - file_count_threshold):
            return False, f"源压缩包内文件数量({source_files})明显少于目标压缩包({target_files})", source_info, target_info
        if source_content_size < target_content_size * size_threshold:
            return False, f"源压缩包内容大小({format_size(source_content_size)})明显小于目标压缩包({format_size(target_content_size)})", source_info, target_info
    
    return True, "文件检查通过，可以安全覆盖", source_info, target_info

def backup_file(file_path, backup_dir=None):
    """
    创建文件备份
    
    Args:
        file_path: 要备份的文件路径
        backup_dir: 备份目录，如果为None，则在同一目录下创建备份
        
    Returns:
        str: 备份文件的路径
    """
    if backup_dir is None:
        # 尝试从配置获取备份目录
        backup_dir = config.get_value('directories.backup_dir')
    
    if not os.path.exists(file_path):
        logger.warning(f"要备份的文件不存在: {file_path}")
        return None
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_name = os.path.basename(file_path)
    backup_name = f"{file_name}.{timestamp}.upbak"
    
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

def rename_cbz_to_zip(directory):
    """
    将指定目录下的所有.cbz文件重命名为.zip文件
    
    Args:
        directory: 要处理的目录
    
    Returns:
        int: 重命名的文件数量
    """
    renamed_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.cbz'):
                source_path = os.path.join(root, file)
                target_path = os.path.join(root, file[:-4] + '.zip')
                
                # 检查目标文件是否已存在
                if os.path.exists(target_path):
                    logger.info(f"[#processing]目标文件已存在，跳过重命名: {source_path}")
                    continue
                    
                try:
                    os.rename(source_path, target_path)
                    renamed_count += 1
                    logger.info(f"[#processing]已重命名: {source_path} -> {target_path}")
                except Exception as e:
                    logger.info(f"[#processing]重命名失败 {source_path}: {e}")
    
    return renamed_count
