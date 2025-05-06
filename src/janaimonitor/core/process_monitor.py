"""
进程监控模块 负责启动、监控和重启MangaJaNaiConverter进程
"""
import os
import re
import subprocess
import time
import threading
import queue
import sys
from pathlib import Path
from loguru import logger
from .config import MANGA_COMMAND, ERROR_PATTERNS
from .file_checker import run_bad_zip_check

# 添加日志分类的关键词模式
LOG_PATTERNS = {
    '#stats': [
        r'TOTALZIP=\d+',
        r'处理目录 \(\d+\/\d+\) \d+%',
        r'共处理'
    ],
    '#fileops': [
        r'(?:读取|保存)(?:文件|图像)',
        r'save image to zip:',
        r'read image',
        r'跳过已检查',
        r'复制文件',
        r'could not read as image',
        r'copying file'
    ],
    '#processing': [
        r'ModelFilePath',
        r'upscale',
        r'VipsForeignLoad'
    ],
    '#updating': [
        r'PROGRESS=',
        r'Matched Chain:',
        r'Auto adjusted levels',
    ]
}

def categorize_log(line):
    """根据关键词将日志分类到不同面板"""
    for category, patterns in LOG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return category
    return '#processing'  # 默认放到处理日志面板

def restart_manga_converter():
    """重启MangaJaNaiConverter程序，并将输出显示在当前终端"""
    logger.info("重启MangaJaNaiConverter...")
    try:
        # 修改为使用subprocess.Popen并将输出显示在当前终端
        process = subprocess.Popen(
            MANGA_COMMAND,
            stdout=None,  # 使用当前进程的stdout
            stderr=None,  # 使用当前进程的stderr
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True  # 使用shell执行，以确保输出正确显示
        )
        logger.info(f"MangaJaNaiConverter已重启，进程ID: {process.pid}")
    except Exception as e:
        logger.error(f"重启MangaJaNaiConverter失败: {str(e)}")

def setup_subprocess_logger(main_log_file):
    """设置子进程专用的logger"""
    # 从主日志文件路径提取目录
    # log_dir = os.path.dirname(main_log_file)
    # # 生成子进程专用日志文件名
    # subprocess_log_file = os.path.join(log_dir, "subprocess_output.log")
    
    # 创建子进程专用的logger处理器
    handler_id = logger.add(
        main_log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level.icon} {level: <8} | [{extra[category]}] {message}",
        filter=lambda record: "subprocess" in record["extra"]
    )
    
    logger.info(f"子进程日志将写入: {main_log_file}")
    return handler_id

def run_manga_with_monitor(force_check=False):
    """运行MangaJaNaiConverter并实时监控输出错误"""
    logger.info("启动MangaJaNaiConverter并监控错误...")
    
    # 尝试获取主日志文件路径
    main_log_file = None
    try:
        # 从主模块导入配置信息
        from ..__main__ import config_info
        if config_info and 'log_file' in config_info:
            main_log_file = config_info['log_file']
            logger.info(f"从主模块获取到日志文件路径: {main_log_file}")
    except (ImportError, AttributeError) as e:
        logger.warning(f"无法从主模块导入日志配置: {str(e)}")
    
    # 设置子进程专用logger
    subprocess_handler_id = setup_subprocess_logger(main_log_file) if main_log_file else None
    
    process = subprocess.Popen(
        MANGA_COMMAND,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace'
    )
    
    logger.info(f"MangaJaNaiConverter已启动，进程ID: {process.pid}")
    
    recent_output = []
    max_buffer_lines = 20
    output_queue = queue.Queue()

    def read_output(pipe, queue):
        for line in iter(pipe.readline, ''):
            queue.put(line)
        pipe.close()

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, output_queue), daemon=True)
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, output_queue), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    # 尝试导入TextualLoggerManager
    try:
        from textual_logger import TextualLoggerManager
        textual_logger_available = True
    except ImportError:
        textual_logger_available = False
        logger.warning("无法导入TextualLoggerManager，将使用标准日志记录")

    error_detected = False
    try:
        while process.poll() is None or not output_queue.empty():
            try:
                line = output_queue.get(block=False)
                if not line:
                    continue
                
                line = line.strip()
                
                # 不再直接打印到终端
                # print(line, flush=True)
                
                # 根据关键词分类日志并记录
                category = categorize_log(line)
                
                # 使用loguru的contextvars记录带分类的子进程日志
                subprocess_logger = logger.bind(subprocess=True, category=category)
                subprocess_logger.info(line)
                
                # 尝试使用TextualLoggerManager添加到分类面板
                
                recent_output.append(line)
                
                if len(recent_output) > max_buffer_lines:
                    recent_output.pop(0)
                    
                combined_output = '\n'.join(recent_output)
                for pattern in ERROR_PATTERNS:
                    if re.search(pattern, combined_output, re.IGNORECASE):
                        logger.warning(f"检测到错误模式: {pattern}")
                        error_detected = True
                        check_success = run_bad_zip_check(force_check=force_check)
                        
                        if check_success:
                            logger.info("损坏文件检查完成并成功")
                        else:
                            logger.warning("损坏文件检查失败或发现问题")
                        
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        
                        # 移除子进程logger处理器
                        if subprocess_handler_id:
                            logger.remove(subprocess_handler_id)
                        
                        # 重启进程
                        return run_manga_with_monitor(force_check=force_check)
                        
                output_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"处理输出时发生错误: {str(e)}")
            time.sleep(0.1)
                
        if process.returncode != 0 and not error_detected:
            logger.warning(f"进程异常退出，返回码: {process.returncode}，准备重启...")
            time.sleep(2)
            # 移除子进程logger处理器
            if subprocess_handler_id:
                logger.remove(subprocess_handler_id)
            return run_manga_with_monitor(force_check=force_check)
            
    except KeyboardInterrupt:
        logger.info("用户中断，正在终止进程...")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        # 移除子进程logger处理器
        if subprocess_handler_id:
            logger.remove(subprocess_handler_id)
        raise
    
    except Exception as e:
        logger.error(f"监控过程中发生错误: {str(e)}")
        if process.poll() is None:
            process.terminate()
        # 移除子进程logger处理器
        if subprocess_handler_id:
            logger.remove(subprocess_handler_id)
        return False
    
    # 移除子进程logger处理器
    if subprocess_handler_id:
        logger.remove(subprocess_handler_id)
    return True