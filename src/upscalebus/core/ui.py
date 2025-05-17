"""
UI 辅助模块 - 提供Rich UI界面的渲染功能
"""
import os
from typing import Dict, List, Tuple, Optional, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.prompt import Prompt, Confirm
from rich.progress import Progress
from rich.style import Style
from rich.text import Text

from .scan import ArchiveOperation
from .operation import format_size

# 创建一个全局控制台实例
console = Console()

def display_directory_tree(dir_info, level=0, show_files=False, max_depth=2):
    """
    在控制台显示目录树结构
    
    Args:
        dir_info: 目录信息字典
        level: 当前级别
        show_files: 是否显示文件
        max_depth: 最大显示深度
    """
    if level == 0:
        tree = Tree(
            f"[bold blue]{dir_info['name']}[/] ([green]{dir_info['archive_count']}[/] 压缩包, [yellow]{format_size(dir_info['total_size'])}[/])"
        )
        parent = tree
    else:
        if level >= max_depth:
            if dir_info["subdirs"] or dir_info["files"]:
                return f"[dim]... (包含 {len(dir_info['subdirs'])} 个子目录, {len(dir_info['files'])} 个文件)[/]"
            return None
        
        node_text = f"[bold cyan]{dir_info['name']}[/] ([green]{dir_info['archive_count']}[/] 压缩包, [yellow]{format_size(dir_info['total_size'])}[/])"
        return node_text

    # 递归处理子目录
    for subdir in sorted(dir_info["subdirs"], key=lambda x: x["name"]):
        child_text = display_directory_tree(subdir, level + 1, show_files, max_depth)
        if child_text:
            if level + 1 >= max_depth:
                parent.add(child_text)
            else:
                child_node = parent.add(child_text)
                # 递归添加子节点
                for sub_subdir in sorted(subdir["subdirs"], key=lambda x: x["name"]):
                    sub_child_text = display_directory_tree(sub_subdir, level + 2, show_files, max_depth)
                    if sub_child_text:
                        child_node.add(sub_child_text)
                
                # 如果需要显示文件
                if show_files:
                    for file in subdir["files"]:
                        file_text = f"[dim]{file['name']} ({format_size(file['size'])})[/]"
                        child_node.add(file_text)

    # 如果是顶层，直接打印树
    if level == 0:
        console.print(tree)
        return None
    
    return None

def generate_operations_preview(operations: List[ArchiveOperation]) -> Table:
    """
    生成操作预览表格
    
    Args:
        operations: 操作列表
        
    Returns:
        Table: Rich表格对象
    """
    table = Table(title="文件操作预览")
    
    table.add_column("序号", style="dim")
    table.add_column("操作", style="cyan")
    table.add_column("源文件", style="green")
    table.add_column("目标文件", style="yellow")
    table.add_column("源大小", style="blue")
    table.add_column("目标大小", style="magenta")
    table.add_column("源文件数", style="blue")
    table.add_column("目标文件数", style="magenta")
    table.add_column("安全性", style="bold")
    
    for i, op in enumerate(operations, 1):
        if not op.source_info:
            op.analyze()
        
        operation_type = "移动" if op.operation_type == "move" else "复制"
        source_path = os.path.basename(op.source_path)
        target_path = os.path.basename(op.target_path)
        
        source_size = format_size(op.source_info["size"]) if op.source_info else "N/A"
        target_size = format_size(op.target_info["size"]) if op.target_info and op.target_info.get("size") else "不存在"
        
        source_files = str(op.source_info.get("files", "N/A")) if op.source_info else "N/A"
        target_files = str(op.target_info.get("files", "N/A")) if op.target_info and op.target_info.get("files") else "不存在"
        
        safety = "[bold green]安全[/]" if op.is_safe else f"[bold red]不安全[/]\n{op.reason}"
        
        table.add_row(
            str(i),
            operation_type,
            source_path,
            target_path,
            source_size,
            target_size,
            source_files,
            target_files,
            safety
        )
    
    return table

def select_subdirectory(dir_structure: Dict, prompt_text="请选择要处理的子目录") -> Dict:
    """
    让用户选择要处理的子目录
    
    Args:
        dir_structure: 目录结构
        prompt_text: 提示文本
        
    Returns:
        dict: 选中的子目录结构
    """
    # 显示目录树
    console.print("\n[bold]目录结构：[/]")
    display_directory_tree(dir_structure)
    
    # 创建选择列表
    choices = []
    choice_map = {}
    
    # 添加当前目录作为选择
    current_dir_text = f"{dir_structure['name']} (当前目录, {dir_structure['archive_count']} 个压缩包)"
    choices.append(current_dir_text)
    choice_map[current_dir_text] = dir_structure
    
    # 添加一级子目录作为选择
    for i, subdir in enumerate(sorted(dir_structure["subdirs"], key=lambda x: x["name"]), 1):
        choice_text = f"{subdir['name']} ({subdir['archive_count']} 个压缩包, {format_size(subdir['total_size'])})"
        choices.append(choice_text)
        choice_map[choice_text] = subdir
    
    # 如果没有选择项，返回当前目录
    if len(choices) <= 1:
        console.print("[yellow]当前目录下没有子目录，将处理整个目录。[/]")
        return dir_structure
    
    # 让用户选择
    console.print(f"\n[bold]{prompt_text}[/] (输入编号或按Enter处理整个目录):")
    for i, choice in enumerate(choices):
        console.print(f"  [cyan]{i}[/]: {choice}")
    
    choice_input = Prompt.ask("请输入选择", default="0")
    
    try:
        choice_idx = int(choice_input)
        if 0 <= choice_idx < len(choices):
            selected = choice_map[choices[choice_idx]]
            console.print(f"[green]已选择：[/]{selected['name']}")
            return selected
        else:
            console.print("[yellow]无效选择，将处理整个目录。[/]")
            return dir_structure
    except ValueError:
        console.print("[yellow]无效输入，将处理整个目录。[/]")
        return dir_structure
