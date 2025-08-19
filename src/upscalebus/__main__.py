# d:\1VSCODE\Projects\ImageAll\UpscalePipe\src\upscalebus\__main__.py
import os
import sys
import traceback
from pathlib import Path
from datetime import datetime

# 从新模块导入功能
from upscalebus.core.operation import remove_temp_files
from upscalebus.core.process import process_corrupted_archives, compare_and_copy_archives, process_rename_cbz
from upscalebus.core.config import config
from loguru import logger

# Rich库导入
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.columns import Columns
    from rich.syntax import Syntax
    from rich.traceback import install
    # 安装Rich异常处理
    install(show_locals=True)
except ImportError:
    print("错误: 未安装Rich库，请运行 pip install rich 安装该库")
    sys.exit(1)

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
        enqueue=True,     )
    
    # 创建配置信息字典
    config_info = {
        'log_file': log_file,
    }
    
    logger.info(f"日志系统已初始化，应用名称: {app_name}")
    return logger, config_info


logger, config_info = setup_logger(app_name="upscale_bus", console_output=True)

# error_handler 模块似乎未使用，暂时注释掉
# from .error_handler import handle_file_operation

# 移除旧的函数定义和配置代码
# ... (移除 remove_empty_directories, remove_temp_files, count_files_in_zip)
# ... (移除 compare_and_copy_archives)
# ... (移除 check_archive, load_check_history, save_check_history, process_corrupted_archives)
# ... (移除 TEXTUAL_LAYOUT, config, logger, config_info, TextualLoggerManager setup)
from textual_logger import TextualLoggerManager

# Textual 布局配置
TEXTUAL_LAYOUT = {
    "stats": {
        "ratio": 2,
        "title": "📊 总体统计",
        "style": "lightyellow"
    },
    "fileops": {
        "ratio": 3,
        "title": "🔄 文件处理",
        "style": "lightcyan"
    },
    "processing": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightpink"
    },
    "updating": {
        "ratio": 1,
        "title": "ℹ️ 状态更新",
        "style": "lightgreen"
    }
}

# TextualLoggerManager.set_layout(TEXTUAL_LAYOUT,config_info['log_file'])

def main():
    """主执行函数"""
    # 使用Rich创建更好的UI
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.columns import Columns
    from rich.syntax import Syntax
    
    console = Console()
    
    # 显示欢迎信息
    console.print(Panel(
        "[bold green]UpscaleBus[/] - 压缩包文件处理工具\n\n"
        "该工具可以安全地处理压缩包文件，支持以下功能：\n"
        "• 按目录级别处理文件\n"
        "• 操作前预览和确认\n"
        "• 严格的安全性检查，避免数据损失\n"
        "• 文件备份和恢复机制",
        title="欢迎使用",
        border_style="blue"
    ))
      # 从配置文件获取默认目录对
    default_directory_pairs = []
    directory_pairs_config = config.get_value("directory_pairs", [])
    
    for pair in directory_pairs_config:
        if "source" in pair and "target" in pair:
            default_directory_pairs.append((pair["source"], pair["target"]))
    
    # 如果配置为空，使用默认值
    if not default_directory_pairs:
        default_directory_pairs = [
            ("D:\\3EHV", "E:\\7EHV"),
            ("E:\\7EHV", "E:\\999EHV"),
        ]
    
    # 让用户选择或输入目录对
    console.print("\n[bold]请选择要处理的目录对，或输入新的目录对:[/]")
    
    # 显示默认目录对
    table = Table(title="预设目录对")
    table.add_column("序号", style="dim")
    table.add_column("源目录", style="green")
    table.add_column("目标目录", style="yellow")
    
    for i, (source, target) in enumerate(default_directory_pairs, 1):
        table.add_row(str(i), source, target)
    
    console.print(table)
    console.print("输入 [cyan]0[/] 来手动输入目录对")
    
    # 获取用户选择
    choice = Prompt.ask("请选择", default="1")
    
    directory_pairs = []
    if choice == "0":
        # 手动输入目录对
        source_dir = Prompt.ask("请输入源目录路径")
        target_dir = Prompt.ask("请输入目标目录路径")
        directory_pairs.append((source_dir, target_dir))
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(default_directory_pairs):
                directory_pairs.append(default_directory_pairs[idx])
            else:
                console.print("[red]无效选择，将使用第一个目录对[/]")
                directory_pairs.append(default_directory_pairs[0])
        except ValueError:
            console.print("[red]无效输入，将使用第一个目录对[/]")
            directory_pairs.append(default_directory_pairs[0])
      # 选择操作类型（从配置获取默认值）
    default_mode = config.get_value("default_mode", "move") == "move"
    is_move = Confirm.ask("\n是否移动文件？（否则复制）", default=default_mode)
    operation_type = "移动" if is_move else "复制"
    
    # 依次处理每对目录
    for source_dir, target_dir in directory_pairs:
        console.print(f"\n[bold]开始处理目录对：[/]")
        console.print(f"源目录: [green]{source_dir}[/]")
        console.print(f"目标目录: [yellow]{target_dir}[/]")
        console.print(f"操作类型: [cyan]{operation_type}[/]")

        if not os.path.exists(source_dir):
            console.print("[red]源目录不存在！[/]")
            continue
          # 显示功能菜单
        console.print(Panel("\n[bold]请选择要执行的操作：[/]", border_style="cyan"))
        console.print("1. [green]检测损坏压缩包[/]")
        console.print("2. [green]清理临时文件[/]")
        console.print("3. [green]将CBZ重命名为ZIP[/]")
        console.print("4. [green]执行文件处理操作[/] (复制或移动)")
        console.print("5. [green]执行全部操作[/] (按顺序执行上述所有操作)")
        console.print("0. [red]跳过此目录对[/]")
        
        action = Prompt.ask("\n请选择操作", default="5")
        
        if action == "0":
            console.print("[yellow]已跳过此目录对[/]")
            continue
        
        # 检测损坏的压缩包
        if action in ["1", "5"]:
            console.print("\n[bold]开始检测损坏压缩包...[/]")
            process_corrupted_archives(source_dir)
        
        # 删除临时文件
        if action in ["2", "5"]:
            console.print("\n[bold]开始清理临时文件...[/]")
            temp_files_removed = remove_temp_files(source_dir)
            console.print(f"[green]已删除 {temp_files_removed} 个临时文件[/]")
            
        # CBZ重命名为ZIP
        if action in ["3", "5"]:
            console.print("\n[bold]开始将CBZ重命名为ZIP...[/]")
            renamed_count = process_rename_cbz(source_dir)
            console.print(f"[green]已重命名 {renamed_count} 个CBZ文件为ZIP[/]")
        
        # 执行文件移动/复制操作
        if action in ["4", "5"]:
            console.print(f"\n[bold]开始{operation_type}文件...[/]")
            compare_and_copy_archives(source_dir, target_dir, is_move)

if __name__ == "__main__":
    try:
        # 创建控制台对象
        console = Console()
        
        # 设置日志配置
        logger, config_info = setup_logger(app_name="upscale_bus", console_output=True)
        
        # 添加Rich控制台输出
        console.print(Panel(f"日志文件: [cyan]{config_info['log_file']}[/]", title="日志配置", border_style="blue"))
        
        # 运行主函数
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]操作已被用户中断[/]")
    except Exception as e:
        console.print(f"\n[red bold]发生错误: {str(e)}[/]")
        console.print_exception()
        logger.error(f"程序异常退出: {str(e)}\n{traceback.format_exc()}")