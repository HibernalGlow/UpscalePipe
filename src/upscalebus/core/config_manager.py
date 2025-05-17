"""
配置管理模块 - 处理配置文件的加载和保存
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

class ConfigManager:
    """配置管理类，负责加载、保存和访问配置"""
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None，则使用默认路径（模块同级目录）
        """
        if config_path is None:
            # 默认配置文件在模块同级目录下
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(current_dir, "config.json")
        else:
            self.config_path = config_path
            
        # 确保配置目录存在
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # 加载配置
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件，如果不存在则创建默认配置
        
        Returns:
            dict: 配置字典
        """        # 默认配置
        default_config = {
            "file_operations": {
                "min_valid_file_size": 1048576,  # 1MB
                "size_difference_threshold": 0.5,
                "ignored_extensions": [".md", ".yaml", ".yml", ".txt", ".json", ".db", ".ini"],
                "rename_cbz_to_zip": True,
                "auto_cleanup": True
            },
            "archive_extensions": [".zip", ".cbz", ".rar", ".7z"],
            "temp_extensions": [".tdel", ".bak"],
            "directory_pairs": [
                {"source": "D:\\3EHV", "target": "E:\\7EHV"},
                {"source": "E:\\7EHV", "target": "E:\\999EHV"}
            ],
            "scan": {
                "max_workers": 4,
                "skip_checked": True
            },
            "ui": {
                "table_style": "rounded",
                "success_color": "green",
                "error_color": "red",
                "warning_color": "yellow",
                "info_color": "blue"
            },
            "auto_operations": {
                "check_corrupted": True,
                "clean_temp_files": True,
                "rename_cbz_to_zip": True,
                "remove_empty_dirs": True
            },
            "default_mode": "move"
        }
        
        # 检查配置文件是否存在
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # 更新默认配置（这样可以确保新版本添加的配置项也存在）
                self._update_nested_dict(default_config, loaded_config)
                logger.info(f"已加载配置文件: {self.config_path}")
                return default_config
            except Exception as e:
                logger.error(f"加载配置文件失败: {str(e)}，将使用默认配置")
                return default_config
        else:
            # 创建默认配置文件
            self.save_config(default_config)
            logger.info(f"已创建默认配置文件: {self.config_path}")
            return default_config
    
    def _update_nested_dict(self, base_dict: Dict, update_dict: Dict) -> None:
        """
        递归更新嵌套字典
        
        Args:
            base_dict: 要更新的基础字典
            update_dict: 包含更新内容的字典
        """
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._update_nested_dict(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def save_config(self, config: Optional[Dict] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置，如果为None则保存当前配置
            
        Returns:
            bool: 是否成功保存
        """
        if config is None:
            config = self.config
            
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存配置文件: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值，支持使用点号访问嵌套配置
        
        Args:
            key_path: 配置键路径，如 "file_operations.min_valid_file_size"
            default: 默认值，当路径不存在时返回
            
        Returns:
            Any: 配置值或默认值
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set_value(self, key_path: str, value: Any) -> bool:
        """
        设置配置值，支持使用点号访问嵌套配置
        
        Args:
            key_path: 配置键路径，如 "file_operations.min_valid_file_size"
            value: 要设置的值
            
        Returns:
            bool: 是否成功设置
        """
        keys = key_path.split('.')
        config = self.config
        
        # 导航到最后一个键的父级
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        
        # 设置值
        config[keys[-1]] = value
        return True
    
    def save(self) -> bool:
        """保存当前配置"""
        return self.save_config()

# 创建全局配置管理器实例
config = ConfigManager()
