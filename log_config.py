#!/usr/bin/env python3
"""
IndexTTS API 日志配置模块
支持日志轮转和不同级别的日志记录
"""

import logging
import logging.handlers
import os
from datetime import datetime


def setup_advanced_logging(log_file="logs/indextts_api.log", log_level="INFO", max_bytes=50*1024*1024, backup_count=10):
    """
    设置高级日志配置，支持日志轮转
    
    Args:
        log_file (str): 日志文件路径
        log_level (str): 日志级别
        max_bytes (int): 单个日志文件最大大小（字节）
        backup_count (int): 保留的备份文件数量
    """
    # 创建日志目录
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 创建格式化器
    formatter = logging.Formatter(log_format, date_format)
    
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 文件处理器（支持轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, 
        maxBytes=max_bytes, 
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)  # 控制台只显示INFO及以上级别
    
    # 错误日志文件处理器
    error_log_file = log_file.replace('.log', '_error.log')
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_handler)
    
    # 创建API专用日志器
    api_logger = logging.getLogger("IndexTTS-API")
    
    return api_logger


def log_request_summary(logger, request_id, method, path, status_code, duration, client_ip=None, user_agent=None):
    """记录请求摘要信息"""
    summary = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration": f"{duration:.3f}s",
        "client_ip": client_ip,
        "user_agent": user_agent,
        "timestamp": datetime.now().isoformat()
    }
    
    if status_code >= 400:
        logger.error(f"请求失败摘要: {summary}")
    else:
        logger.info(f"请求成功摘要: {summary}")


def log_tts_request(logger, request_id, text_length, infer_mode, prompt_url, duration, success=True, error_msg=None):
    """记录TTS请求详细信息"""
    tts_info = {
        "request_id": request_id,
        "text_length": text_length,
        "infer_mode": infer_mode,
        "prompt_url": prompt_url,
        "duration": f"{duration:.3f}s",
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    
    if error_msg:
        tts_info["error"] = error_msg
        logger.error(f"TTS请求失败: {tts_info}")
    else:
        logger.info(f"TTS请求成功: {tts_info}")


if __name__ == "__main__":
    # 测试日志配置
    logger = setup_advanced_logging()
    logger.info("日志配置测试 - INFO级别")
    logger.warning("日志配置测试 - WARNING级别")
    logger.error("日志配置测试 - ERROR级别")
    logger.debug("日志配置测试 - DEBUG级别")
