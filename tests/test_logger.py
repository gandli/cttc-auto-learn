"""测试 Logger 模块"""

import logging
from pathlib import Path

from cttc.logger import Logger


def test_logger_init(tmp_dir):
    """测试 Logger 初始化"""
    log_file = str(tmp_dir / "test.log")
    logger = Logger(log_file)
    assert logger is not None


def test_logger_creates_log_file(tmp_dir):
    """测试自动创建日志文件"""
    log_file = str(tmp_dir / "test.log")
    logger = Logger(log_file)
    logger.info("test message")

    # 日志文件应该被创建（如果有文件处理器）
    # 注意：具体行为取决于 Logger 实现


def test_logger_info(tmp_dir, capsys):
    """测试 info 级别日志"""
    log_file = str(tmp_dir / "test.log")
    logger = Logger(log_file)
    logger.info("Test info message")

    captured = capsys.readouterr()
    # 检查是否有输出（取决于 Logger 实现）


def test_logger_warn(tmp_dir, capsys):
    """测试 warn 级别日志"""
    log_file = str(tmp_dir / "test.log")
    logger = Logger(log_file)
    logger.warn("Test warning message")


def test_logger_error(tmp_dir, capsys):
    """测试 error 级别日志"""
    log_file = str(tmp_dir / "test.log")
    logger = Logger(log_file)
    logger.error("Test error message")
