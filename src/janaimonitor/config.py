"""
配置常量模块
"""
import os

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

