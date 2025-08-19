"""
文件检查模块 - 负责检测和处理损坏的压缩文件
"""
import os
from datetime import datetime
from loguru import logger
from badzf import run_check

def run_bad_zip_check(force_check=False):
    """使用badzf模块执行损坏文件检测并获取返回码
    
    Args:
        force_check: 是否强制检查所有文件，忽略已处理记录
        
    Returns:
        bool: 检测是否成功完成
    """
    logger.info("开始执行损坏文件检测...")
    try:
        # 使用导入的badzf模块，调用run_check函数
        status_code = run_check(force_check=force_check, no_tui=True)
        
        # 根据状态码判断成功与否
        success = (status_code == 0)
        
        logger.info(f"文件检测完成，状态码: {status_code}, 结果: {'成功' if success else '失败'}")
        return success  # 返回成功与否
    except Exception as e:
        logger.error(f"执行损坏文件检测失败: {str(e)}")
        return False