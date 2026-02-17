"""PWA用アイコン生成スクリプト"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def create_icon(size):
    img = Image.new('RGBA', (size, size), (16, 185, 129, 255))  # emerald-500
    draw = ImageDraw.Draw(img)

    font_size = size // 2
    try:
        # Windows
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
    except OSError:
        try:
            # Linux
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "H", font=font)
    x = (size - (bbox[2] - bbox[0])) // 2
    y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), "H", fill="white", font=font)

    return img


if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "frontend" / "public"
    output_dir.mkdir(parents=True, exist_ok=True)

    for s in [192, 512]:
        img = create_icon(s)
        path = output_dir / f"icon-{s}.png"
        img.save(str(path))
        print(f"Generated {path}")
