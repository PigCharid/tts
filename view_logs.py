#!/usr/bin/env python3
"""
IndexTTS API 日志查看工具
支持实时查看、过滤和分析日志
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
import re


def tail_log(log_file, lines=50, follow=False):
    """查看日志文件的最后几行"""
    if not os.path.exists(log_file):
        print(f"日志文件不存在: {log_file}")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            if follow:
                # 实时跟踪日志
                f.seek(0, 2)  # 移动到文件末尾
                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip())
                    else:
                        time.sleep(0.1)
            else:
                # 显示最后几行
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line.rstrip())
    except KeyboardInterrupt:
        print("\n停止查看日志")
    except Exception as e:
        print(f"读取日志文件失败: {e}")


def filter_logs(log_file, level=None, keyword=None, hours=24):
    """过滤日志"""
    if not os.path.exists(log_file):
        print(f"日志文件不存在: {log_file}")
        return
    
    # 计算时间范围
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 解析时间戳
                try:
                    timestamp_str = line.split(' - ')[0]
                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # 时间过滤
                    if log_time < cutoff_time:
                        continue
                    
                    # 级别过滤
                    if level and level.upper() not in line:
                        continue
                    
                    # 关键词过滤
                    if keyword and keyword.lower() not in line.lower():
                        continue
                    
                    print(line.rstrip())
                except:
                    # 如果解析失败，跳过这行
                    continue
    except Exception as e:
        print(f"过滤日志失败: {e}")


def analyze_logs(log_file, hours=24):
    """分析日志统计信息"""
    if not os.path.exists(log_file):
        print(f"日志文件不存在: {log_file}")
        return
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    stats = {
        'total_requests': 0,
        'successful_requests': 0,
        'failed_requests': 0,
        'tts_requests': 0,
        'error_count': 0,
        'warning_count': 0,
        'info_count': 0,
        'total_duration': 0,
        'avg_duration': 0
    }
    
    durations = []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    timestamp_str = line.split(' - ')[0]
                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    if log_time < cutoff_time:
                        continue
                    
                    # 统计日志级别
                    if 'ERROR' in line:
                        stats['error_count'] += 1
                    elif 'WARNING' in line:
                        stats['warning_count'] += 1
                    elif 'INFO' in line:
                        stats['info_count'] += 1
                    
                    # 统计请求
                    if '请求开始' in line:
                        stats['total_requests'] += 1
                    elif '请求成功摘要' in line:
                        stats['successful_requests'] += 1
                        # 提取处理时间
                        duration_match = re.search(r'duration.*?(\d+\.\d+)s', line)
                        if duration_match:
                            duration = float(duration_match.group(1))
                            durations.append(duration)
                            stats['total_duration'] += duration
                    elif '请求失败摘要' in line:
                        stats['failed_requests'] += 1
                    elif 'TTS请求' in line:
                        stats['tts_requests'] += 1
                        
                except:
                    continue
        
        # 计算平均处理时间
        if durations:
            stats['avg_duration'] = sum(durations) / len(durations)
        
        # 打印统计信息
        print(f"\n=== 日志分析报告 (最近 {hours} 小时) ===")
        print(f"总请求数: {stats['total_requests']}")
        print(f"成功请求: {stats['successful_requests']}")
        print(f"失败请求: {stats['failed_requests']}")
        print(f"TTS请求: {stats['tts_requests']}")
        print(f"平均处理时间: {stats['avg_duration']:.3f}秒")
        print(f"\n日志级别统计:")
        print(f"  INFO: {stats['info_count']}")
        print(f"  WARNING: {stats['warning_count']}")
        print(f"  ERROR: {stats['error_count']}")
        
    except Exception as e:
        print(f"分析日志失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="IndexTTS API 日志查看工具")
    parser.add_argument("--log-file", default="logs/indextts_api.log", help="日志文件路径")
    parser.add_argument("--lines", type=int, default=50, help="显示最后几行")
    parser.add_argument("--follow", "-f", action="store_true", help="实时跟踪日志")
    parser.add_argument("--level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="过滤日志级别")
    parser.add_argument("--keyword", help="过滤关键词")
    parser.add_argument("--hours", type=int, default=24, help="分析最近几小时的日志")
    parser.add_argument("--analyze", action="store_true", help="分析日志统计")
    
    args = parser.parse_args()
    
    if args.analyze:
        analyze_logs(args.log_file, args.hours)
    elif args.follow:
        tail_log(args.log_file, args.lines, follow=True)
    elif args.level or args.keyword:
        filter_logs(args.log_file, args.level, args.keyword, args.hours)
    else:
        tail_log(args.log_file, args.lines)


if __name__ == "__main__":
    main()

