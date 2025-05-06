"""
压缩包处理模块 - 包含比较、复制/移动和检查压缩包的核心逻辑
"""
import os
import shutil
import subprocess
import json
from datetime import datetime
import concurrent.futures
import send2trash
from loguru import logger
from .file_utils import count_files_in_zip, remove_empty_directories

def compare_and_copy_archives(source_dir, target_dir, is_move=False):
    """比较并复制/移动压缩包文件"""
    total_files = sum(
        len([f for f in files if f.endswith(('.cbz', '.zip'))])
        for root, _, files in os.walk(source_dir)
    )
    processed_files = 0
    success_count = 0
    skip_count = 0
    error_files = []
    
    logger.info(f"[#stats]开始处理目录对：{source_dir} -> {target_dir}")
    
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.endswith(('.cbz', '.zip')):
                source_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, source_dir)
                
                source_file = file.replace('.cbz', '.zip') if file.endswith('.cbz') else file
                target_file = source_file
                
                temp_source = os.path.join(root, source_file)
                target_path = os.path.join(target_dir, rel_path, target_file)
                
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                logger.info(f"[#updating]正在处理: {source_path} -> {target_path}")
                if file.endswith('.cbz'):
                    try:
                        if source_path != temp_source: # Avoid renaming if names are already the same
                            os.rename(source_path, temp_source)
                    except OSError as e:
                        logger.info(f"[#updating]重命名失败,跳过处理: {source_path} -> {temp_source}")
                        logger.info(f"[#processing]错误信息: {str(e)}")
                        skip_count += 1
                        processed_files += 1 # Count skipped file as processed
                        continue
                
                try:
                    processed_files += 1
                    progress = (processed_files / total_files) * 100 if total_files > 0 else 0
                    logger.info(f"[@fileops]处理中 ({processed_files}/{total_files}) {progress:.1f}%")
                    
                    operation_type = "移动" if is_move else "复制"
                    action_func = shutil.move if is_move else shutil.copy2

                    if not os.path.exists(target_path):
                        try:
                            action_func(temp_source, target_path)
                            logger.info(f"[#processing]{operation_type}新文件: {file} -> {target_file}")
                            success_count += 1
                        except OSError as e:
                            logger.info(f"[#updating]文件操作失败,跳过: {temp_source} -> {target_path}")
                            logger.info(f"[#processing]错误信息: {str(e)}")
                            skip_count += 1
                            continue
                    else:
                        source_count = count_files_in_zip(temp_source)
                        target_count = count_files_in_zip(target_path)
                            
                        if source_count == target_count:
                            try:
                                send2trash.send2trash(target_path)
                                logger.info(f"[#processing]已将原文件移动到回收站: {target_path}")
                                action_func(temp_source, target_path)
                                logger.info(f"[#processing]{operation_type}并覆盖: {file} -> {target_file}")
                                success_count += 1
                                logger.info(f"[#processing]有效文件数量: {source_count}")
                            except Exception as e:
                                logger.info(f"[#updating]文件操作或移至回收站失败: {str(e)}")
                                skip_count += 1
                                continue
                        else:
                            skip_count += 1
                            error_msg = f"[#processing]跳过: {file} - 文件数量不一致 (源:{source_count}, 目标:{target_count})"
                            error_files.append(error_msg)
                            logger.info(error_msg)

                    if success_count % 10 == 0: # Update progress periodically
                        logger.info(f"[@fileops]已处理 ({processed_files}/{total_files}) {progress:.1f}%")
                        
                except Exception as e:
                    logger.info(f"[@fileops]❌ 错误 ({processed_files}/{total_files}) {progress:.1f}%")
                    skip_count += 1
                    error_msg = f"[#updating]错误: {file} - {str(e)}"
                    error_files.append(error_msg)
                    logger.info(error_msg)
    
    if is_move:
        removed_count = remove_empty_directories(source_dir)
        logger.info(f"[#processing]\n已删除 {removed_count} 个空文件夹")
    
    logger.info(f"[@fileops]✅ 完成 ({processed_files}/{total_files}) 100%")
    logger.info("[#processing]\n处理完成！")
    logger.info(f"[#stats]成功处理: {success_count} 个文件")
    logger.info(f"[#stats]跳过处理: {skip_count} 个文件")
    if error_files:
        logger.info("[#processing]\n详细错误列表:")
        for error in error_files:
            logger.info(error)

def check_archive(file_path):
    """使用 7z 检测压缩包是否损坏"""
    try:
        result = subprocess.run(['7z', 't', file_path], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        logger.error("[#processing]错误: 未找到 7z 可执行文件。请确保 7z 已安装并添加到系统 PATH。")
        return False # Indicate failure if 7z is not found
    except Exception as e:
        logger.info(f"[#processing]检测文件 {file_path} 时发生错误: {str(e)}")
        return False

def load_check_history(history_file):
    """加载检测历史记录"""
    history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        file_path = entry.get('path')
                        if file_path:
                            # Store the latest entry for each path
                            history[file_path] = {
                                'timestamp': entry.get('timestamp'),
                                'valid': entry.get('valid')
                            }
                    except json.JSONDecodeError:
                        logger.warning(f"[#processing]跳过无效的历史记录行: {line}")
                        continue
        except Exception as e:
             logger.error(f"[#processing]加载历史记录文件失败 {history_file}: {e}")
    return history

def save_check_history(history_file, new_entry):
    """追加方式保存检测记录"""
    try:
        new_entry['timestamp'] = datetime.now().isoformat()
        if 'time' in new_entry: # Ensure old 'time' key is removed if present
            del new_entry['time']
        with open(history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.info(f"[#processing]保存检查记录失败: {str(e)}")

def process_corrupted_archives(directory, skip_checked=True, max_workers=4):
    """检测并处理指定目录下的损坏压缩包"""
    archive_extensions = ('.zip', '.rar', '.7z', '.cbz')
    history_file = os.path.join(directory, 'archive_check_history.json')
    check_history = load_check_history(history_file)
    
    # 删除 temp_ 开头的文件夹
    for root, dirs, _ in os.walk(directory, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith('temp_')] # Efficiently modify dirs in-place
        # for dir_name in list(dirs): # Iterate over a copy
        #     if dir_name.startswith('temp_'):
        #         try:
        #             dir_path = os.path.join(root, dir_name)
        #             logger.info(f"[#processing]正在删除临时文件夹: {dir_path}")
        #             shutil.rmtree(dir_path)
        #             dirs.remove(dir_name) # Remove from list to prevent descending
        #         except Exception as e:
        #             logger.info(f"[#processing]删除文件夹 {dir_path} 时发生错误: {str(e)}")

    files_to_process = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(archive_extensions):
                file_path = os.path.join(root, filename)
                if file_path.endswith('.tdel'):
                    continue
                # Check history: skip if checked and valid
                if skip_checked and file_path in check_history and check_history[file_path].get('valid') is True:
                    # logger.info(f"[#processing]跳过已检查且完好的文件: {file_path}")
                    continue
                files_to_process.append(file_path)

    total = len(files_to_process)
    processed = 0
    
    if total == 0:
        logger.info("[#processing]没有需要处理的文件")
        return

    def process_single_file(file_path):
        nonlocal processed
        try:
            logger.info(f"[#fileops]正在检测: {os.path.basename(file_path)}")
            is_valid = check_archive(file_path)
            return {
                'path': file_path,
                'valid': is_valid,
                'timestamp': datetime.now().isoformat(),
                'error': None
            }
        except Exception as e:
            logger.info(f"[#updating]检测过程中发生异常: {str(e)}")
            return {
                'path': file_path,
                'valid': False,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
        finally:
            processed += 1
            progress = (processed / total) * 100 if total > 0 else 0
            logger.info(f"[@fileops]检测中 ({processed}/{total}) {progress:.1f}%")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_file, file_path): file_path for file_path in files_to_process}
        
        for future in concurrent.futures.as_completed(futures):
            file_path = futures[future]
            try:
                result = future.result()
            except Exception as e:
                logger.info(f"[#updating]任务执行失败 for {os.path.basename(file_path)}: {str(e)}")
                continue
            
            is_valid = result['valid']
            current_time = result['timestamp'] # Use timestamp from result for consistency
            
            # Update history in memory
            check_history[file_path] = {
                'timestamp': current_time,
                'valid': is_valid
            }
            
            # Save entry to history file
            save_check_history(history_file, {
                'path': file_path,
                'valid': is_valid,
                # 'timestamp' will be added by save_check_history
            })
            
            if not is_valid:
                new_path = file_path + '.tdel'
                try:
                    if os.path.exists(new_path):
                        os.remove(new_path)
                        logger.info(f"[#processing]删除已存在的tdel文件: {os.path.basename(new_path)}")
                    os.rename(file_path, new_path)
                    logger.info(f"[#processing]文件损坏,已重命名为: {os.path.basename(new_path)}")
                except Exception as e:
                    logger.info(f"[#updating]重命名文件 {os.path.basename(file_path)} 时发生错误: {str(e)}")
            # else:
                # logger.info(f"[#processing]文件 {os.path.basename(file_path)} 完好")

    logger.info(f"[@fileops]✅ 完成检测 ({processed}/{total}) 100%")