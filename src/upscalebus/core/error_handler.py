import functools
import traceback
from typing import Callable, Any
from loguru import logger

# 获取logger实例
class FileProcessError(Exception):
    """文件处理相关的自定义异常"""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

def handle_file_operation(skip_errors: bool = True) -> Callable:
    """
    文件操作错误处理装饰器
    
    Args:
        skip_errors: 是否跳过错误继续执行,默认True
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"文件操作错误: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                
                if not skip_errors:
                    raise FileProcessError(error_msg, e)
                else:
                    logger.info(f"[#updating]跳过错误,继续执行: {str(e)}")
                    return None
        return wrapper
    return decorator 