"""给截图添加马赛克，遮盖个人信息（姓名、单位等）"""
from PIL import Image, ImageFilter
from pathlib import Path

SCREENSHOT_DIR = Path("docs/screenshots")


def add_mosaic(img_path: Path, regions: list[tuple[int, int, int, int]], block_size: int = 10):
    """给图片指定区域添加马赛克
    
    Args:
        img_path: 图片路径
        regions: 需要马赛克的区域列表 [(x1, y1, x2, y2), ...]
        block_size: 马赛克块大小
    """
    img = Image.open(img_path)
    
    for x1, y1, x2, y2 in regions:
        # 裁剪区域
        region = img.crop((x1, y1, x2, y2))
        
        # 缩小再放大实现马赛克效果
        w, h = region.size
        small = region.resize((max(1, w // block_size), max(1, h // block_size)), Image.NEAREST)
        mosaic = small.resize((w, h), Image.NEAREST)
        
        # 粘贴回原图
        img.paste(mosaic, (x1, y1))
    
    img.save(img_path)
    print(f"  ✅ 已处理: {img_path.name}")


def main():
    # 首页 - 右上角用户头像区域
    if (SCREENSHOT_DIR / "01-homepage.png").exists():
        add_mosaic(SCREENSHOT_DIR / "01-homepage.png", [
            (1050, 20, 1250, 60),  # 右上角用户信息区域
        ])
    
    # 学习中心 - 用户信息区域（姓名、单位）
    if (SCREENSHOT_DIR / "02-learning-center.png").exists():
        add_mosaic(SCREENSHOT_DIR / "02-learning-center.png", [
            (50, 100, 400, 250),  # 左侧用户姓名和单位区域
        ])
    
    # 任务页面 - 用户信息区域
    if (SCREENSHOT_DIR / "03-course-list.png").exists():
        add_mosaic(SCREENSHOT_DIR / "03-course-list.png", [
            (50, 100, 400, 250),  # 左侧用户姓名和单位区域
        ])
    
    # 个人中心 - 用户信息区域
    if (SCREENSHOT_DIR / "05-personal-center.png").exists():
        add_mosaic(SCREENSHOT_DIR / "05-personal-center.png", [
            (50, 100, 400, 250),  # 左侧用户姓名和单位区域
        ])
    
    print("\n📸 马赛克处理完成！")


if __name__ == "__main__":
    main()
