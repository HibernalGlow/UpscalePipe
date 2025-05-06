"""
进程监控模块 - 负责启动、监控和重启MangaJaNaiConverter进程
"""
import os
import re
import subprocess
import time
import threading
import queue
from loguru import logger
from .config import MANGA_COMMAND, ERROR_PATTERNS
from .file_checker import run_bad_zip_check

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

def run_manga_with_monitor(force_check=False):
    """运行MangaJaNaiConverter并实时监控输出错误"""
    logger.info("启动MangaJaNaiConverter并监控错误...")
    
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

    error_detected = False
    try:
        while process.poll() is None or not output_queue.empty():
            try:
                line = output_queue.get(block=False)
                if not line:
                    continue
                
                line = line.strip()
                print(line, flush=True)
                logger.info(f"{line}")
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
            return run_manga_with_monitor(force_check=force_check)
            
    except KeyboardInterrupt:
        logger.info("用户中断，正在终止进程...")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        raise
    
    except Exception as e:
        logger.error(f"监控过程中发生错误: {str(e)}")
        if process.poll() is None:
            process.terminate()
        return False
    
    return True