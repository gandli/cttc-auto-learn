"""测试 Config 模块"""

from pathlib import Path

from cttc.config import Config


def test_config_default_values():
    """测试默认配置值"""
    config = Config()
    assert config.base_url == "https://mooc.ctt.cn"
    assert config.headless is False
    assert config.viewport_width == 1280
    assert config.viewport_height == 800
    assert config.qr_refresh_cooldown == 15
    assert config.page_timeout == 30000


def test_config_creates_directories(tmp_dir):
    """测试自动创建目录"""
    config = Config(
        output_dir=str(tmp_dir / "output"),
        screenshot_dir=str(tmp_dir / "output" / "screenshots"),
    )
    assert Path(tmp_dir / "output").exists()
    assert Path(tmp_dir / "output" / "screenshots").exists()


def test_config_auto_populates_paths(tmp_dir):
    """测试自动填充路径"""
    config = Config(
        output_dir=str(tmp_dir / "output"),
        progress_file=str(tmp_dir / "data" / "progress.json"),
        log_file=str(tmp_dir / "logs" / "cttc.log"),
    )
    assert config.output_dir == str(Path(tmp_dir / "output"))
    assert config.progress_file == str(Path(tmp_dir / "data" / "progress.json"))
    assert config.log_file == str(Path(tmp_dir / "logs" / "cttc.log"))


def test_config_custom_values(tmp_dir):
    """测试自定义配置值"""
    config = Config(
        headless=True,
        viewport_width=1920,
        viewport_height=1080,
        qr_refresh_cooldown=30,
    )
    assert config.headless is True
    assert config.viewport_width == 1920
    assert config.viewport_height == 1080
    assert config.qr_refresh_cooldown == 30
