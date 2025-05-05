import os
import re
import subprocess
import time
import sys
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
# 加载环境变量
from dotenv import load_dotenv
import argparse

# 自动在当前目录及其父目录中查找 .env 文件
load_dotenv(override=True)
python_path = os.getenv('PYTHON_PATH')

# 设置日志记录
from loguru import logger
import os
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(app_name="app", project_root=None, console_output=True):
    """配置 Loguru 日志系统
    
    Args:
        app_name: 应用名称，用于日志目录
        project_root: 项目根目录，默认为当前文件所在目录
        console_output: 是否输出到控制台，默认为True
        
    Returns:
        tuple: (logger, config_info)
            - logger: 配置好的 logger 实例
            - config_info: 包含日志配置信息的字典
    """
    # 获取项目根目录
    if project_root is None:
        project_root = Path(__file__).parent.resolve()
    
    # 清除默认处理器
    logger.remove()
    
    # 有条件地添加控制台处理器（简洁版格式）
    if console_output:
        logger.add(
            sys.stdout,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <blue>{elapsed}</blue> | <level>{level.icon} {level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
        )
    
    # 使用 datetime 构建日志路径
    current_time = datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")
    hour_str = current_time.strftime("%H")
    minute_str = current_time.strftime("%M%S")
    
    # 构建日志目录和文件路径
    log_dir = os.path.join(project_root, "logs", app_name, date_str, hour_str)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{minute_str}.log")
    
    # 添加文件处理器
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {elapsed} | {level.icon} {level: <8} | {name}:{function}:{line} - {message}",
    )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info

logger, config_info = setup_logger(app_name="janai_monitor", console_output=True)


# 定义要监视的错误模式 - 更精确的模式
ERROR_PATTERNS = [
    r'\^\^\^+',
    r'BadZipFile',
    r'Error',
    r'Traceback',
    ]

# 定义不应被视为错误的模式
NORMAL_PATTERNS = [
    r'跳过已检查且完好的文件',
    r'跳过处理',
    r'跳过已存在的',
    r'跳过空文件夹'
]

APPSTATE_PATH = r'C:\Users\30902\AppData\Roaming\MangaJaNaiConverterGui\appstate2.json'
# MangaJaNaiConverter命令
MANGA_COMMAND = [
    r'C:\Users\30902\AppData\Roaming\MangaJaNaiConverterGui\python\python\python.exe',
    r'C:\Users\30902\AppData\Local\MangaJaNaiConverterGui\current\backend\src\run_upscale.py',
    '--settings',
    APPSTATE_PATH
]

# bad_zip_tdel.py 脚本路径
BAD_ZIP_SCRIPT = os.path.join(os.getenv("PROJECT_ROOT"), 'src', 'scripts', 'folder', 'bad_zip_tdel.py')

def run_bad_zip_check(force_check=False):
    """使用.env中PYTHON_PATH执行bad_zip_tdel模块并获取返回码
    
    Args:
        force_check: 是否强制检查所有文件，忽略已处理记录
    """
    logger.info("开始执行损坏文件检测...")
    try:
        # 使用.env中定义的Python路径
        venv_python = python_path
        if not os.path.exists(venv_python):
            logger.warning(f"未找到.env中指定的Python路径: {venv_python}，将使用系统Python")
            venv_python = "python"
            
        # 准备命令参数
        cmd = [venv_python, BAD_ZIP_SCRIPT, "--no_tui"]
        
        # # 添加强制检查参数
        # if force_check:
        #     cmd.append("--force_check")
        logger.info("启用强制检查模式：将检查所有文件")
            
        # 直接执行脚本文件
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        
        # 记录输出
        if process.stdout:
            for line in process.stdout.splitlines():
                logger.info(f"检测输出: {line}")
        if process.stderr:
            for line in process.stderr.splitlines():
                # 检查是否匹配正常模式
                is_normal_message = any(re.search(pattern, line) for pattern in NORMAL_PATTERNS)
                if is_normal_message:
                    logger.info(f"检测信息: {line}")
                else:
                    logger.warning(f"检测错误: {line}")
        
        logger.info(f"文件检测完成，返回码: {process.returncode}")
        return process.returncode == 0  # 返回成功与否
    except Exception as e:
        logger.error(f"执行损坏文件检测失败: {str(e)}")
        return False

def restart_manga_converter():
    """重启MangaJaNaiConverter程序，并将输出显示在当前终端"""
    logger.info("重启MangaJaNaiConverter...")
    try:
        # 修改为使用subprocess.Popen并将输出显示在当前终端
        process = subprocess.Popen(
            MANGA_COMMAND,
            # 不捕获输出，而是将输出直接显示在当前终端
            stdout=None,  # None表示使用当前进程的stdout
            stderr=None,  # None表示使用当前进程的stderr
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True  # 使用shell执行，以确保输出正确显示
        )
        logger.info(f"MangaJaNaiConverter已重启，进程ID: {process.pid}")
    except Exception as e:
        logger.error(f"重启MangaJaNaiConverter失败: {str(e)}")

def run_manga_with_monitor():
    """运行MangaJaNaiConverter并实时监控输出错误"""
    # 获取force_check参数的状态
    force_check = getattr(run_manga_with_monitor, 'force_check', False)
    
    logger.info("启动MangaJaNaiConverter并监控错误...")
    
    # 启动进程，但保持管道打开以便我们可以读取输出
    process = subprocess.Popen(
        MANGA_COMMAND,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,  # 不需要输入
        text=True,
        bufsize=1,  # 行缓冲
        universal_newlines=True,
        encoding='utf-8',
        errors='replace'  # 处理无法解码的字符
    )
    
    logger.info(f"MangaJaNaiConverter已启动，进程ID: {process.pid}")
    
    # 初始化缓冲区，用于保存最近的输出行
    recent_output = []
    max_buffer_lines = 20  # 保存最近20行
    
    # 使用非阻塞读取
    import select
    import threading
    import queue
    
    # 创建队列存储输出
    output_queue = queue.Queue()
    
    # 定义读取输出的函数
    def read_output(pipe, queue):
        for line in iter(pipe.readline, ''):
            queue.put(line)
        pipe.close()
    
    # 创建读取线程
    stdout_thread = threading.Thread(
        target=read_output, 
        args=(process.stdout, output_queue),
        daemon=True
    )
    stderr_thread = threading.Thread(
        target=read_output, 
        args=(process.stderr, output_queue),
        daemon=True
    )
    
    stdout_thread.start()
    stderr_thread.start()
    
    # 主循环
    error_detected = False
    try:
        while process.poll() is None or not output_queue.empty():
            try:
                # 非阻塞方式获取队列中的行
                try:
                    line = output_queue.get(block=False)
                    if not line:
                        continue
                    
                    line = line.strip()
                    # 直接打印到控制台
                    print(line, flush=True)
                    # 同时记录到日志
                    logger.info(f"{line}")
                    # 添加到最近输出
                    recent_output.append(line)
                    
                    # 保持缓冲区大小
                    if len(recent_output) > max_buffer_lines:
                        recent_output.pop(0)
                        
                    # 检查错误模式
                    combined_output = '\n'.join(recent_output)
                    for pattern in ERROR_PATTERNS:
                        if re.search(pattern, combined_output, re.IGNORECASE):
                            logger.warning(f"检测到错误模式: {pattern}")
                            error_detected = True
                            # 执行损坏文件检查并获取结果，传递force_check参数
                            check_success = run_bad_zip_check(force_check=force_check)
                            
                            if check_success:
                                logger.info("损坏文件检查完成并成功")
                            else:
                                logger.warning("损坏文件检查失败或发现问题")
                            
                            # 终止当前进程
                            process.terminate()
                            # 等待进程结束
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                            
                            # 重启进程
                            return run_manga_with_monitor()
                            
                    output_queue.task_done()
                except queue.Empty:
                    pass
                
                # 间隔性检查
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"处理输出时发生错误: {str(e)}")
                time.sleep(1)
                
        # 进程已结束，检查是否是错误退出
        if process.returncode != 0 and not error_detected:
            logger.warning(f"进程异常退出，返回码: {process.returncode}，准备重启...")
            time.sleep(2)
            return run_manga_with_monitor()
            
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

def main():
    """主函数"""
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='MangaJaNaiConverter监控工具')
    parser.add_argument('--force_check', action='store_true', help='强制检查所有压缩包文件，忽略已处理记录')
    args = parser.parse_args()
    
    logger.info("启动终端监控程序...")
    
    # 确保脚本存在
    if not Path(BAD_ZIP_SCRIPT).exists():
        logger.error(f"找不到脚本: {BAD_ZIP_SCRIPT}")
        return
    
    # 启动时先执行一次文件检查，传递force_check参数
    logger.info("执行初始文件检查...")
    initial_check = run_bad_zip_check(force_check=args.force_check)
    if initial_check:
        logger.info("初始文件检查完成并成功")
    else:
        logger.warning("初始文件检查失败或发现问题")
        
    # 存储force_check参数，以便在后续检查中使用
    run_manga_with_monitor.force_check = args.force_check
        
    # 使用新函数启动并监控MangaJaNaiConverter
    try:
        run_manga_with_monitor()
    except KeyboardInterrupt:
        logger.info("监控程序被用户中断")
    except Exception as e:
        logger.error(f"监控程序发生错误: {str(e)}")

if __name__ == "__main__":
    main()
