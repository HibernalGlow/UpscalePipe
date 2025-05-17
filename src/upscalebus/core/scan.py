"""
压缩包扫描模块 - 提供目录扫描和压缩包分析功能
"""
import os
import subprocess
import json
from datetime import datetime
import concurrent.futures
from typing import Dict, List, Tuple, Optional, Any

from loguru import logger

from .config import config
from .operation import format_size

def scan_directory_structure(root_dir: str) -> Dict:
    """
    扫描目录结构，返回层次化的目录信息
    
    Args:
        root_dir: 要扫描的根目录
        
    Returns:
        dict: 包含目录结构和文件信息的嵌套字典
    """
    # 从配置获取压缩包扩展名
    archive_extensions = tuple(config.get_value('file_operations.archive_extensions', 
                                               ['.zip', '.cbz', '.rar', '.7z']))
    
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
                    "is_archive": any(item.lower().endswith(ext) for ext in archive_extensions)
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

def check_archive(file_path):
    """
    使用 7z 检测压缩包是否损坏
    
    Args:
        file_path: 压缩包文件路径
        
    Returns:
        bool: 压缩包是否完好
    """
    try:
        logger.info(f"[#processing]正在检测: {file_path}")
        result = subprocess.run(['7z', 't', file_path], capture_output=True, text=True, check=False)
        is_valid = result.returncode == 0
        
        if not is_valid:
            error_output = result.stderr.strip() or result.stdout.strip()
            logger.error(f"[#processing]文件损坏: {file_path}\n错误: {error_output}")
        
        return is_valid
    except FileNotFoundError:
        logger.error("[#processing]错误: 未找到 7z 可执行文件。请确保 7z 已安装并添加到系统 PATH。")
        return False # Indicate failure if 7z is not found
    except Exception as e:
        logger.error(f"[#processing]检测文件 {file_path} 时发生错误: {str(e)}")
        return False

def load_check_history(history_file):
    """
    加载检测历史记录
    
    Args:
        history_file: 历史记录文件路径
        
    Returns:
        dict: 历史记录字典
    """
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        file_path = entry.get('path')
                        if file_path:
                            # Store the latest entry for each path
                            history[file_path] = {
                                'timestamp': entry.get('timestamp'),
                                'valid': entry.get('valid')
                            }
                    except json.JSONDecodeError:
                        logger.warning(f"[#processing]跳过无效的历史记录行: {line}")
                        continue
        except Exception as e:
             logger.error(f"[#processing]加载历史记录文件失败 {history_file}: {e}")
    return history

def save_check_history(history_file, new_entry):
    """
    追加方式保存检测记录
    
    Args:
        history_file: 历史记录文件路径
        new_entry: 新的检测记录
    """
    try:
        new_entry['timestamp'] = datetime.now().isoformat()
        if 'time' in new_entry: # Ensure old 'time' key is removed if present
            del new_entry['time']
        with open(history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"[#processing]保存检查记录失败: {str(e)}")

class ArchiveOperation:
    """
    表示一个压缩包操作的类
    """
    def __init__(self, source_path, target_path, operation_type="copy"):
        self.source_path = source_path
        self.target_path = target_path
        self.operation_type = operation_type  # "copy" 或 "move"
        self.source_info = None
        self.target_info = None
        self.is_safe = None
        self.reason = None
        self.status = "pending"  # pending, success, skipped, error
        self.error_message = None
        self.backup_path = None
