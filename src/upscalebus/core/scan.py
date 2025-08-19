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

def check_archive(file_path, timeout=None):
    """
    使用 7z 检测压缩包是否损坏，带超时防卡死机制
    
    Args:
        file_path: 压缩包文件路径
        timeout: 超时时间（秒），如果为None则从配置获取
        
    Returns:
        bool: 压缩包是否完好
    """
    try:
        logger.info(f"[#processing]正在检测: {file_path}")
        
        # 从配置获取超时相关设置
        if timeout is None:
            timeout = config.get_value('file_operations.archive_check_timeout', 300)
        min_timeout = config.get_value('file_operations.archive_check_min_timeout', 60)
        max_timeout = config.get_value('file_operations.archive_check_max_timeout', 1800)
        timeout_per_100mb = config.get_value('file_operations.archive_check_timeout_per_100mb', 60)
        
        # 获取文件大小用于超时计算
        try:
            file_size = os.path.getsize(file_path)
            # 根据文件大小动态调整超时时间：每100MB增加指定秒数
            dynamic_timeout = max(min_timeout, min(max_timeout, timeout + (file_size // (100 * 1024 * 1024)) * timeout_per_100mb))
            logger.debug(f"[#processing]文件大小: {format_size(file_size)}, 设置超时: {dynamic_timeout}秒")
        except Exception:
            dynamic_timeout = timeout
            logger.warning(f"[#processing]无法获取文件大小，使用默认超时: {timeout}秒")
        
        # 使用超时机制运行7z测试
        result = subprocess.run(
            ['7z', 't', file_path], 
            capture_output=True, 
            text=True, 
            check=False,
            timeout=dynamic_timeout
        )
        
        is_valid = result.returncode == 0
        
        if not is_valid:
            error_output = result.stderr.strip() or result.stdout.strip()
            logger.error(f"[#processing]文件损坏: {file_path}\n错误: {error_output}")
        else:
            logger.info(f"[#processing]检测完成: {file_path} - 完好")
        
        return is_valid
        
    except subprocess.TimeoutExpired:
        logger.error(f"[#processing]检测超时: {file_path} (超过 {dynamic_timeout} 秒)，视为损坏")
        return False
    except FileNotFoundError:
        logger.error("[#processing]错误: 未找到 7z 可执行文件。请确保 7z 已安装并添加到系统 PATH。")
        return False # Indicate failure if 7z is not found
    except PermissionError:
        logger.error(f"[#processing]权限错误: 无法访问文件 {file_path}")
        return False
    except OSError as e:
        logger.error(f"[#processing]系统错误: 检测文件 {file_path} 时发生 OSError: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"[#processing]检测文件 {file_path} 时发生未知错误: {str(e)}")
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
