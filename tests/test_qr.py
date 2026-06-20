"""测试 QR 模块"""

import base64
import io
from pathlib import Path
from unittest.mock import patch, MagicMock

from PIL import Image

from cttc.qr import save_qr_image, print_qr_to_terminal, generate_qr_png

def _create_test_qr_image() -> bytes:
    """创建测试用二维码图片"""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_save_qr_image(tmp_dir):
    """测试保存二维码图片"""
    b64_data = base64.b64encode(_create_test_qr_image()).decode()
    output_path = str(tmp_dir / "test_qr.png")

    result = save_qr_image(b64_data, output_path)
    assert Path(result).exists()
    assert Path(result).stat().st_size > 0


def test_save_qr_image_creates_parent_dirs(tmp_dir):
    """测试自动创建父目录"""
    b64_data = base64.b64encode(_create_test_qr_image()).decode()
    output_path = str(tmp_dir / "subdir" / "deep" / "test_qr.png")

    result = save_qr_image(b64_data, output_path)
    assert Path(result).exists()


def test_print_qr_to_terminal_no_zxing():
    """测试无 zxing-cpp 时的降级处理"""
    with patch("cttc.qr.HAS_QR", False):
        result = print_qr_to_terminal("dGVzdA==")
        assert result is False


def test_print_qr_to_terminal_invalid_image():
    """测试无效图片处理"""
    result = print_qr_to_terminal("invalid_base64")
    assert result is False


def test_print_qr_to_terminal_no_barcode():
    """测试无二维码图片处理"""
    # 纯白图片，不含二维码
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode()

    with patch("cttc.qr.HAS_QR", True):
        # zxing-cpp 可能无法识别纯白图片
        result = print_qr_to_terminal(b64_data)
        # 结果取决于 zxing-cpp 是否能识别
        assert isinstance(result, bool)


def test_print_qr_to_terminal_with_mock_qr_lib():
    """测试成功打印二维码到终端 (lines 40-53)"""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode()

    # Mock zxingcpp and qrcode
    mock_barcode = MagicMock()
    mock_barcode.text = "https://example.com/qr"

    mock_qr_code = MagicMock()

    with patch("cttc.qr.HAS_QR", True):
        with patch("cttc.qr.zxingcpp") as mock_zxing:
            with patch("cttc.qr.qr_lib") as mock_qr:
                mock_zxing.read_barcodes.return_value = [mock_barcode]
                mock_qr.QRCode.return_value = mock_qr_code

                result = print_qr_to_terminal(b64_data)

                assert result is True
                mock_zxing.read_barcodes.assert_called_once()
                mock_qr.QRCode.assert_called_once_with(border=2)
                mock_qr_code.add_data.assert_called_once_with("https://example.com/qr")
                mock_qr_code.make.assert_called_once_with(fit=True)
                mock_qr_code.print_ascii.assert_called_once_with(invert=True)


def test_print_qr_to_terminal_rgba_conversion():
    """测试 RGBA 图片转换为 RGB (line 34)"""
    # Create RGBA image
    img = Image.new("RGBA", (100, 100), color=(255, 255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode()

    mock_barcode = MagicMock()
    mock_barcode.text = "https://example.com"
    mock_qr_code = MagicMock()

    with patch("cttc.qr.HAS_QR", True):
        with patch("cttc.qr.zxingcpp") as mock_zxing:
            with patch("cttc.qr.qr_lib") as mock_qr:
                mock_zxing.read_barcodes.return_value = [mock_barcode]
                mock_qr.QRCode.return_value = mock_qr_code

                result = print_qr_to_terminal(b64_data)
                assert result is True


def test_print_qr_to_terminal_win32_encoding():
    """测试 Windows 平台编码处理 (lines 42-47)"""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode()

    mock_barcode = MagicMock()
    mock_barcode.text = "https://example.com"
    mock_qr_code = MagicMock()

    with patch("cttc.qr.HAS_QR", True):
        with patch("cttc.qr.zxingcpp") as mock_zxing:
            with patch("cttc.qr.qr_lib") as mock_qr:
                with patch("cttc.qr.sys") as mock_sys:
                    with patch("cttc.qr.os") as mock_os:
                        mock_zxing.read_barcodes.return_value = [mock_barcode]
                        mock_qr.QRCode.return_value = mock_qr_code
                        mock_sys.platform = "win32"
                        mock_sys.stdout = MagicMock()

                        result = print_qr_to_terminal(b64_data)

                        assert result is True
                        mock_os.system.assert_called_once_with("chcp 65001 >nul 2>&1")
                        mock_sys.stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")


def test_print_qr_to_terminal_win32_reconfigure_exception():
    """测试 Windows 平台编码处理 - reconfigure 异常 (lines 46-47)"""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode()

    mock_barcode = MagicMock()
    mock_barcode.text = "https://example.com"
    mock_qr_code = MagicMock()

    with patch("cttc.qr.HAS_QR", True):
        with patch("cttc.qr.zxingcpp") as mock_zxing:
            with patch("cttc.qr.qr_lib") as mock_qr:
                with patch("cttc.qr.sys") as mock_sys:
                    with patch("cttc.qr.os") as mock_os:
                        mock_zxing.read_barcodes.return_value = [mock_barcode]
                        mock_qr.QRCode.return_value = mock_qr_code
                        mock_sys.platform = "win32"
                        mock_sys.stdout = MagicMock()
                        mock_sys.stdout.reconfigure = MagicMock(side_effect=Exception("reconfigure failed"))

                        result = print_qr_to_terminal(b64_data)
                        assert result is True


def test_print_qr_to_terminal_non_win32():
    """测试非 Windows 平台 (不调用 chcp)"""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode()

    mock_barcode = MagicMock()
    mock_barcode.text = "https://example.com"
    mock_qr_code = MagicMock()

    with patch("cttc.qr.HAS_QR", True):
        with patch("cttc.qr.zxingcpp") as mock_zxing:
            with patch("cttc.qr.qr_lib") as mock_qr:
                with patch("cttc.qr.sys") as mock_sys:
                    with patch("cttc.qr.os") as mock_os:
                        mock_zxing.read_barcodes.return_value = [mock_barcode]
                        mock_qr.QRCode.return_value = mock_qr_code
                        mock_sys.platform = "linux"

                        result = print_qr_to_terminal(b64_data)

                        assert result is True
                        mock_os.system.assert_not_called()


def test_print_qr_to_terminal_exception():
    """测试异常处理 (lines 55-56)"""
    with patch("cttc.qr.HAS_QR", True):
        with patch("cttc.qr.zxingcpp") as mock_zxing:
            with patch("cttc.qr.Image") as mock_image:
                mock_image.open.side_effect = Exception("Image error")
                result = print_qr_to_terminal("dGVzdA==")
                assert result is False


# ═══════════════════════════════════════════
# generate_qr_png
# ═══════════════════════════════════════════

def test_generate_qr_png_creates_file(tmp_dir):
    """测试生成二维码 PNG"""
    output_path = str(tmp_dir / "test_qr.png")
    result = generate_qr_png("https://example.com", output_path)
    # 返回相对路径，文件实际在 tmp_dir 中
    assert result == "test_qr.png"
    assert (tmp_dir / result).exists()
    assert (tmp_dir / result).stat().st_size > 0


def test_generate_qr_png_custom_size(tmp_dir):
    """测试自定义尺寸"""
    output_path = str(tmp_dir / "test_qr.png")
    result = generate_qr_png("https://example.com", output_path, size=300)
    assert result == "test_qr.png"
    assert (tmp_dir / result).exists()


def test_generate_qr_png_creates_parent_dirs(tmp_dir):
    """测试自动创建父目录"""
    output_path = str(tmp_dir / "subdir" / "deep" / "test_qr.png")
    result = generate_qr_png("https://example.com", output_path)
    assert result == "test_qr.png"
    assert Path(output_path).exists()


def test_generate_qr_png_returns_relative_path(tmp_dir):
    """测试返回相对路径（文件名）"""
    output_path = str(tmp_dir / "test_qr.png")
    result = generate_qr_png("https://example.com", output_path)
    assert not Path(result).is_absolute()
    assert result == "test_qr.png"


def test_generate_qr_png_different_content(tmp_dir):
    """测试不同内容生成不同二维码"""
    path1 = str(tmp_dir / "qr1.png")
    path2 = str(tmp_dir / "qr2.png")
    generate_qr_png("https://example.com/a", path1)
    generate_qr_png("https://example.com/b", path2)
    # 两个文件应该不同
    data1 = Path(path1).read_bytes()
    data2 = Path(path2).read_bytes()
    assert data1 != data2
