"""
压缩包处理模块 - 包含压缩包复制、移动和检查的核心逻辑
"""
import os
import shutil
import send2trash
import concurrent.futures
from typing import Dict, List, Tuple, Optional, Any

from loguru import logger
from rich.progress import Progress

from .config import config
from .operation import (
    remove_empty_directories, 
    remove_temp_files, 
    is_safe_to_overwrite, 
    backup_file,
    format_size
)
from .scan import (
    scan_directory_structure, 
    check_archive, 
    load_check_history, 
    save_check_history,
    ArchiveOperation
)
from .ui import (
    console, 
    display_directory_tree, 
    generate_operations_preview, 
    select_subdirectory
)
from rich.panel import Panel
from rich.prompt import Confirm

def prepare_operations(source_structure: Dict, target_structure: Dict, 
                       source_base: str, target_base: str, is_move: bool) -> List[ArchiveOperation]:
    """
    准备文件操作列表
    
    Args:
        source_structure: 源目录结构
        target_structure: 目标目录结构
        source_base: 源基础路径
        target_base: 目标基础路径
        is_move: 是否为移动操作
        
    Returns:
        list: ArchiveOperation对象列表
    """
    operations = []
    
    # 处理当前目录中的文件
    for file_info in source_structure["files"]:
        if file_info["is_archive"]:
            rel_path = os.path.relpath(os.path.dirname(file_info["path"]), source_base)
            if rel_path == ".":
                rel_path = ""
            
            target_dir = os.path.join(target_base, rel_path)
            target_path = os.path.join(target_dir, file_info["name"])
            
            operation = ArchiveOperation(
                file_info["path"], 
                target_path,
                "move" if is_move else "copy"
            )
            operations.append(operation)
    
    # 递归处理子目录
    for subdir in source_structure["subdirs"]:
        # 找到目标中对应的子目录
        target_subdir = next(
            (d for d in target_structure["subdirs"] if d["name"] == subdir["name"]), 
            {"path": os.path.join(target_structure["path"], subdir["name"]), "subdirs": [], "files": []}
        )
        
        # 递归处理
        subdir_operations = prepare_operations(
            subdir, 
            target_subdir, 
            source_base, 
            target_base,
            is_move
        )
        
        operations.extend(subdir_operations)
    
    return operations

def filter_operations(operations: List[ArchiveOperation], 
                     only_safe=True, 
                     skip_existing=False) -> List[ArchiveOperation]:
    """
    过滤操作列表
    
    Args:
        operations: 操作列表
        only_safe: 是否只包含安全操作
        skip_existing: 是否跳过已存在的文件
        
    Returns:
        list: 过滤后的操作列表
    """
    # 确保所有操作已分析
    for op in operations:
        if op.is_safe is None:
            op.analyze()
    
    filtered = []
    for op in operations:
        # 如果只要安全操作，跳过不安全的
        if only_safe and not op.is_safe:
            continue
        
        # 如果跳过已存在的，检查目标是否存在
        if skip_existing and os.path.exists(op.target_path):
            continue
        
        filtered.append(op)
    
    return filtered

def scan_directory_pair(source_dir: str, target_dir: str) -> Tuple[Dict, Dict]:
    """
    扫描源目录和目标目录结构
    
    Args:
        source_dir: 源目录
        target_dir: 目标目录
        
    Returns:
        tuple: (源目录结构, 目标目录结构)
    """
    console.print(f"[bold blue]正在扫描源目录：[/][yellow]{source_dir}[/]")
    with Progress() as progress:
        task = progress.add_task("扫描中...", total=None)
        source_structure = scan_directory_structure(source_dir)
        progress.update(task, completed=100)
    
    console.print(f"[bold blue]正在扫描目标目录：[/][yellow]{target_dir}[/]")
    with Progress() as progress:
        task = progress.add_task("扫描中...", total=None)
        if os.path.exists(target_dir):
            target_structure = scan_directory_structure(target_dir)
        else:
            target_structure = {
                "path": target_dir,
                "name": os.path.basename(target_dir) or target_dir,
                "type": "directory",
                "subdirs": [],
                "files": [],
                "archive_count": 0,
                "total_size": 0
            }
        progress.update(task, completed=100)
    
    return source_structure, target_structure

def compare_and_copy_archives(source_dir: str, target_dir: str, is_move: bool = False):
    """
    比较并复制/移动压缩包文件（按目录处理）
    
    Args:
        source_dir: 源目录
        target_dir: 目标目录
        is_move: 是否移动（True）而不是复制（False）
    """
    console.print(Panel(f"[bold]开始处理目录对[/]\n\n源目录: [green]{source_dir}[/]\n目标目录: [yellow]{target_dir}[/]", 
                       title="文件处理任务", border_style="blue"))
    
    # 扫描目录结构
    source_structure, target_structure = scan_directory_pair(source_dir, target_dir)
    
    # 显示目录统计
    console.print(f"\n[bold]源目录统计：[/]")
    console.print(f"总压缩包数: [green]{source_structure['archive_count']}[/]")
    console.print(f"总大小: [green]{format_size(source_structure['total_size'])}[/]")
    
    # 让用户选择要处理的子目录
    selected_source = select_subdirectory(source_structure, "请选择要处理的源子目录")
    
    # 根据选择构建对应的目标结构
    if selected_source is source_structure:
        selected_target = target_structure
    else:
        # 查找相匹配的目标子目录，或创建新结构
        rel_path = os.path.relpath(selected_source["path"], source_structure["path"])
        target_path = os.path.normpath(os.path.join(target_structure["path"], rel_path))
        
        if os.path.exists(target_path):
            for subdir in target_structure["subdirs"]:
                if os.path.normpath(subdir["path"]) == target_path:
                    selected_target = subdir
                    break
            else:
                # 目录存在但不在结构中，重新扫描
                selected_target = scan_directory_structure(target_path)
        else:
            # 目标子目录不存在，创建空结构
            selected_target = {
                "path": target_path,
                "name": os.path.basename(target_path),
                "type": "directory",
                "subdirs": [],
                "files": [],
                "archive_count": 0,
                "total_size": 0
            }
    
    # 准备操作列表
    operations = prepare_operations(
        selected_source, 
        selected_target, 
        selected_source["path"], 
        target_structure["path"] if selected_source is source_structure else selected_target["path"],
        is_move
    )
    
    if not operations:
        console.print("[yellow]没有找到需要处理的压缩包文件。[/]")
        return
    
    # 分析操作安全性
    with Progress() as progress:
        task = progress.add_task("分析文件安全性...", total=len(operations))
        
        def analyze_operation(op):
            op.is_safe, op.reason, op.source_info, op.target_info = is_safe_to_overwrite(
                op.source_path, op.target_path
            )
            return op
            
        for op in operations:
            analyze_operation(op)
            progress.update(task, advance=1)
    
    # 计算安全和不安全操作数量
    safe_ops = [op for op in operations if op.is_safe]
    unsafe_ops = [op for op in operations if not op.is_safe]
    
    # 生成并显示预览
    console.print(f"\n[bold]找到 [green]{len(operations)}[/] 个文件操作：[/]")
    console.print(f"安全操作: [green]{len(safe_ops)}[/]")
    console.print(f"不安全操作: [red]{len(unsafe_ops)}[/]")
    
    # 显示操作预览
    preview_table = generate_operations_preview(operations)
    console.print(preview_table)
    
    # 询问用户是否继续
    if not Confirm.ask("\n是否继续执行这些操作？",default=True):
        console.print("[yellow]操作已取消。[/]")
        return
    
    # 询问是否只执行安全操作
    only_safe = True
    if unsafe_ops and Confirm.ask("\n是否跳过不安全的操作？", default=True):
        operations = safe_ops
        console.print(f"[yellow]将只执行 {len(operations)} 个安全操作[/]")
    
    # 执行操作
    success_count = 0
    skip_count = 0
    error_count = 0
    
    with Progress() as progress:
        task = progress.add_task("执行文件操作...", total=len(operations))
        
        for i, operation in enumerate(operations, 1):
            op_type = "移动" if operation.operation_type == "move" else "复制"
            progress.update(task, description=f"正在{op_type} {i}/{len(operations)}: {os.path.basename(operation.source_path)}")
            
            # 执行操作
            try:
                # 如果目标已存在，先备份
                if os.path.exists(operation.target_path):
                    backup_dir = config.get_value('directories.backup_dir')
                    operation.backup_path = backup_file(operation.target_path, backup_dir)
                
                target_dir = os.path.dirname(operation.target_path)
                os.makedirs(target_dir, exist_ok=True)
                
                if operation.operation_type == "move":
                    shutil.move(operation.source_path, operation.target_path)
                else:
                    shutil.copy2(operation.source_path, operation.target_path)
                
                operation.status = "success"
                success_count += 1
            except Exception as e:
                operation.status = "error"
                operation.error_message = str(e)
                logger.error(f"执行文件操作失败: {operation.source_path} -> {operation.target_path}, 错误: {str(e)}")
                
                # 如果有备份，尝试恢复
                if operation.backup_path and os.path.exists(operation.backup_path):
                    try:
                        shutil.copy2(operation.backup_path, operation.target_path)
                        logger.info(f"已从备份恢复文件: {operation.target_path}")
                    except Exception as restore_error:
                        logger.error(f"恢复备份失败: {str(restore_error)}")
                
                error_count += 1
            
            progress.update(task, advance=1)
    
    # 如果是移动操作且配置允许，删除空文件夹
    if is_move and selected_source is source_structure and config.get_value('processing.auto_remove_empty_dirs', True):
        console.print("\n[bold]清理空文件夹...[/]")
        removed_count = remove_empty_directories(source_dir)
        console.print(f"已删除 [green]{removed_count}[/] 个空文件夹")
    
    # 显示结果统计
    console.print(Panel(
        f"成功: [green]{success_count}[/] 个文件\n"
        f"错误: [red]{error_count}[/] 个文件\n"
        f"总计: [blue]{len(operations)}[/] 个文件",
        title="处理完成", 
        border_style="green"
    ))

    logger.info(f"[#stats]成功处理: {success_count} 个文件")
    logger.info(f"[#stats]跳过处理: {skip_count} 个文件")
    logger.info(f"[#stats]错误处理: {error_count} 个文件")

def process_corrupted_archives(directory, skip_checked=True):
    """
    检测并处理指定目录下的损坏压缩包
    
    Args:
        directory: 要检测的目录
        skip_checked: 是否跳过已检查过的文件
    """
    # 从配置获取参数
    max_workers = config.get_value('processing.max_workers', 4)
    
    console.print(Panel(f"[bold]开始检测目录中的损坏压缩包[/]\n\n目录: [green]{directory}[/]", 
                       title="压缩包检测", border_style="blue"))
    
    # 扫描目录结构
    dir_structure = scan_directory_structure(directory)
    
    # 显示目录统计
    console.print(f"\n[bold]目录统计：[/]")
    console.print(f"总压缩包数: [green]{dir_structure['archive_count']}[/]")
    console.print(f"总大小: [green]{format_size(dir_structure['total_size'])}[/]")
    
    # 让用户选择要处理的子目录
    # selected_dir = select_subdirectory(dir_structure, "请选择要检测的子目录")
    selected_dir = dir_structure
    # 从配置获取压缩包扩展名
    archive_extensions = tuple(config.get_value('file_operations.archive_extensions', 
                                              ['.zip', '.cbz', '.rar', '.7z']))
    
    # 加载历史记录
    history_file = os.path.join(directory, 'archive_check_history.json')
    check_history = load_check_history(history_file)
    
    # 删除 temp_ 开头的文件夹
    for root, dirs, _ in os.walk(selected_dir["path"], topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith('temp_')]
    
    # 收集要处理的文件
    console.print("\n[bold]正在扫描需要检测的文件...[/]")
    
    files_to_process = []
    
    def collect_files_from_structure(structure):
        result = []
        for file_info in structure["files"]:
            if file_info["name"].lower().endswith(archive_extensions) and not file_info["path"].endswith('.tdel'):
                # 检查历史记录
                if skip_checked and file_info["path"] in check_history and check_history[file_info["path"]].get('valid') is True:
                    continue
                result.append(file_info["path"])
        
        for subdir in structure["subdirs"]:
            result.extend(collect_files_from_structure(subdir))
        
        return result
    
    files_to_process = collect_files_from_structure(selected_dir)
    
    total = len(files_to_process)
    
    if total == 0:
        console.print("[yellow]没有需要检测的文件。[/]")
        return
    
    console.print(f"[green]找到 {total} 个需要检测的压缩包文件。[/]")
    
    # 预览并询问是否继续
    if not Confirm.ask("\n是否继续检测这些文件？", default=True):
        console.print("[yellow]操作已取消。[/]")
        return
    
    # 执行检测
    processed = 0
    valid_count = 0
    invalid_count = 0
    
    def process_single_file(file_path):
        """处理单个文件"""
        try:
            is_valid = check_archive(file_path)
            return {
                'path': file_path,
                'valid': is_valid,
                'timestamp': None,  # 会在save_check_history中添加
                'error': None
            }
        except Exception as e:
            logger.error(f"[#updating]检测过程中发生异常: {str(e)}")
            return {
                'path': file_path,
                'valid': False,
                'timestamp': None,  # 会在save_check_history中添加
                'error': str(e)
                        }

    with Progress() as progress:
        task = progress.add_task("检测压缩包...", total=total)
        
        # 从配置获取超时设置
        single_file_timeout = config.get_value('file_operations.archive_check_timeout', 300) + 30  # 为单个文件处理留30秒余量
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_file, file_path): file_path for file_path in files_to_process}
            
            try:
                for future in concurrent.futures.as_completed(futures, timeout=single_file_timeout):
                    file_path = futures[future]
                    try:
                        # 为每个future设置超时
                        result = future.result(timeout=single_file_timeout)
                    except concurrent.futures.TimeoutError:
                        logger.error(f"[#updating]文件检测任务超时: {os.path.basename(file_path)}")
                        invalid_count += 1
                        
                        # 保存超时记录
                        save_check_history(history_file, {
                            'path': file_path,
                            'valid': False,
                            'error': 'Timeout'
                        })
                        
                        processed += 1
                        progress.update(task, completed=processed)
                        continue
                    except Exception as e:
                        logger.error(f"[#updating]任务执行失败: {os.path.basename(file_path)}: {str(e)}")
                        invalid_count += 1
                        
                        # 保存错误记录
                        save_check_history(history_file, {
                            'path': file_path,
                            'valid': False,
                            'error': str(e)
                        })
                        
                        processed += 1
                        progress.update(task, completed=processed)
                        continue
                    
                    is_valid = result['valid']
                    
                    # 更新历史记录
                    check_history[file_path] = {
                        'timestamp': None,  # 会在save_check_history中添加
                        'valid': is_valid
                    }
                    
                    # 保存记录
                    save_check_history(history_file, {
                        'path': file_path,
                        'valid': is_valid,
                    })
                    
                    # 处理无效文件
                    if is_valid:
                        valid_count += 1
                    else:
                        invalid_count += 1
                        new_path = file_path + '.tdel'
                        
                        # 预览标记
                        console.print(f"[red]发现损坏文件:[/] {os.path.basename(file_path)}")
                        
                        if Confirm.ask(f"是否将文件标记为 .tdel?", default=True):
                            try:
                                if os.path.exists(new_path):
                                    os.remove(new_path)
                                    logger.info(f"[#processing]删除已存在的tdel文件: {os.path.basename(new_path)}")
                                os.rename(file_path, new_path)
                                console.print(f"[green]已将文件标记为: {os.path.basename(new_path)}[/]")
                            except Exception as e:
                                logger.error(f"[#updating]重命名文件失败: {str(e)}")
                            processed += 1
                    progress.update(task, completed=processed)
                    
            except concurrent.futures.TimeoutError:
                logger.error(f"[#updating]整体检测任务超时，正在取消剩余任务...")
                # 取消所有未完成的任务
                for future in futures:
                    if not future.done():
                        future.cancel()
                        file_path = futures[future]
                        logger.warning(f"[#updating]已取消超时任务: {os.path.basename(file_path)}")
                        invalid_count += 1
                        processed += 1
                        progress.update(task, completed=processed)
                    
                    if Confirm.ask(f"是否将文件标记为 .tdel?", default=True):
                        try:
                            if os.path.exists(new_path):
                                os.remove(new_path)
                                logger.info(f"[#processing]删除已存在的tdel文件: {os.path.basename(new_path)}")
                            os.rename(file_path, new_path)
                            console.print(f"[green]已将文件标记为: {os.path.basename(new_path)}[/]")
                        except Exception as e:
                            logger.error(f"[#updating]重命名文件失败: {str(e)}")
                
                processed += 1
                progress.update(task, completed=processed)
    
    # 显示结果
    console.print(Panel(
        f"检测完成: [green]{processed}[/] 个文件\n"
        f"完好文件: [green]{valid_count}[/] 个\n"
        f"损坏文件: [red]{invalid_count}[/] 个",
        title="检测完成", 
        border_style="green"
    ))

def process_rename_cbz(directory):
    """
    处理指定目录下的CBZ文件，将其重命名为ZIP文件
    
    Args:
        directory: 要处理的目录
    """
    from .operation import rename_cbz_to_zip
    
    console.print(Panel(f"[bold]开始处理目录中的CBZ文件[/]\n\n目录: [green]{directory}[/]", 
                       title="CBZ重命名", border_style="blue"))
    
    # 扫描目录结构
    dir_structure = scan_directory_structure(directory)
    
    # 显示目录统计
    console.print(f"\n[bold]目录统计：[/]")
    console.print(f"总压缩包数: [green]{dir_structure['archive_count']}[/]")
    
    # 让用户选择要处理的子目录
    # selected_dir = select_subdirectory(dir_structure, "请选择要处理的子目录")
    selected_dir = dir_structure
    # 处理CBZ文件
    console.print("\n[bold]开始处理CBZ文件...[/]")
    renamed_count = rename_cbz_to_zip(selected_dir["path"])
    
    # 显示结果
    console.print(f"\n[bold]处理完成：[/]")
    console.print(f"已重命名 [green]{renamed_count}[/] 个CBZ文件为ZIP文件")
    
    return renamed_count
