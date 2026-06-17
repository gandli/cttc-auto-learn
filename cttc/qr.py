"""二维码工具模块"""

import base64
import io
import os
import sys
from pathlib import Path

from PIL import Image

try:
    import zxingcpp
    import qrcode as qr_lib
    HAS_QR = True
except ImportError:
    HAS_QR = False


def save_qr_image(b64_data: str, output_path: str) -> str:
    """保存 base64 二维码图片"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(b64_data))
    return str(path)


def generate_qr_png(text: str, output_path: str, size: int = 200) -> str:
    """生成二维码 PNG（从文本内容）"""
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path))
    return str(path.resolve())


def print_qr_to_terminal(b64_data: str) -> bool:
    """zxing-cpp 解码 → qrcode 库终端渲染"""
    if not HAS_QR:
        return False
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64_data)))
        if img.mode != "RGB":
            img = img.convert("RGB")

        results = zxingcpp.read_barcodes(img)
        if not results:
            return False

        content = results[0].text

        if sys.platform == "win32":
            os.system("chcp 65001 >nul 2>&1")
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        qr = qr_lib.QRCode(border=2)
        qr.add_data(content)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        return True

    except Exception:
        return False
