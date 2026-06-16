import os
import logging

logger = logging.getLogger(__name__)

_W, _H = 1280, 720

_FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size):
    try:
        from PIL import ImageFont
        for path in _FONT_PATHS:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()
    except ImportError:
        return None


def generate_thumbnail(image_path, title, output_path):
    """
    Gera thumbnail YouTube 1280x720:
    - Imagem do produto como fundo
    - Overlay escuro na metade inferior
    - Título em branco com sombra
    - Badge vermelho "VALE A PENA?"
    Requer: pip install Pillow
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow não instalado. Execute: pip install Pillow")
        return None

    # Fundo
    try:
        img = Image.open(image_path).convert("RGB").resize((_W, _H), Image.LANCZOS)
    except Exception:
        img = Image.new("RGB", (_W, _H), (15, 15, 15))

    # Overlay escuro gradiente na metade inferior (melhora legibilidade do texto)
    overlay = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    half = _H // 2
    for y in range(half, _H):
        alpha = int(200 * (y - half) / half)
        draw_ov.rectangle([0, y, _W, y + 1], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_title = _load_font(70)
    font_badge = _load_font(36)

    # Título com sombra
    text = title.upper()
    tx, ty = 30, _H - 185
    if font_title:
        draw.text((tx + 3, ty + 3), text, font=font_title, fill=(0, 0, 0))
        draw.text((tx, ty), text, font=font_title, fill=(255, 255, 255))
    else:
        draw.text((tx, ty), text, fill=(255, 255, 255))

    # Badge vermelho
    bx, by = 30, _H - 85
    badge = "VALE A PENA?"
    if font_badge:
        bbox = draw.textbbox((bx, by), badge, font=font_badge)
        pad = 10
        draw.rounded_rectangle(
            [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
            radius=6, fill=(210, 30, 30),
        )
        draw.text((bx, by), badge, font=font_badge, fill=(255, 255, 255))

    img.save(output_path, "JPEG", quality=95)
    logger.info(f"Thumbnail gerada: {output_path}")
    return output_path
