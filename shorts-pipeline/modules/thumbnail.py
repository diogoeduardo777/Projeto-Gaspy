import os
import logging

logger = logging.getLogger(__name__)

_W, _H = 1280, 720

_FONT_PATHS_LARGE = [
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

_FONT_PATHS_MEDIUM = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size, prefer_impact=True):
    try:
        from PIL import ImageFont
        paths = _FONT_PATHS_LARGE if prefer_impact else _FONT_PATHS_MEDIUM
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()
    except ImportError:
        return None


def _draw_outlined_text(draw, pos, text, font, fill, outline_color, outline=5):
    """Desenha texto com outline espesso — estilo YouTube viral."""
    x, y = pos
    for dx in range(-outline, outline + 1):
        for dy in range(-outline, outline + 1):
            if abs(dx) + abs(dy) <= outline + 1:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(text, font, max_width, draw):
    """Quebra o texto em linhas que cabem em max_width."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        try:
            w = draw.textlength(test, font=font)
        except Exception:
            w = len(test) * 20
        if w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def generate_thumbnail(image_path, title, output_path):
    """
    Gera thumbnail YouTube 1280x720 estilo viral:
    - Imagem com saturation/contraste aumentados
    - Gradiente laranja/vermelho vibrante no rodapé
    - Título amarelo Impact com outline espesso
    - Badge vermelho com sombra
    """
    try:
        from PIL import Image, ImageDraw, ImageEnhance
    except ImportError:
        logger.error("Pillow não instalado. Execute: pip install Pillow")
        return None

    # Fundo com enhancement de cor
    try:
        img = Image.open(image_path).convert("RGB").resize((_W, _H), Image.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Color(img).enhance(1.45)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.05)
    except Exception:
        img = Image.new("RGB", (_W, _H), (20, 20, 40))

    # Gradiente laranja/vermelho vibrante no terço inferior
    overlay = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    start_y = int(_H * 0.42)
    for y in range(start_y, _H):
        t = (y - start_y) / (_H - start_y)
        # Gradiente: laranja vibrante no início → vermelho escuro no rodapé
        r = int(220 - 80 * t)
        g = int(80 - 70 * t)
        b = int(10 * (1 - t))
        alpha = int(240 * t)
        draw_ov.rectangle(
            [0, y, _W, y + 1],
            fill=(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), alpha)
        )

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_title = _load_font(76, prefer_impact=True)
    font_badge = _load_font(42, prefer_impact=False)
    font_sub   = _load_font(32, prefer_impact=False)

    # Título em amarelo vibrante com outline espesso
    text = title.upper()
    max_w = _W - 60
    lines = _wrap_text(text, font_title, max_w, draw)

    total_lines = len(lines)
    line_h = 85
    start_ty = _H - 210 - (total_lines - 1) * line_h

    for i, line in enumerate(lines):
        ty = start_ty + i * line_h
        _draw_outlined_text(draw, (30, ty), line, font_title,
                            fill=(255, 230, 0), outline_color=(0, 0, 0), outline=5)

    # Badge "VALE A PENA?" — vermelho com sombra
    bx, by = 30, _H - 80
    badge = "VALE A PENA?"
    if font_badge:
        try:
            bbox = draw.textbbox((bx, by), badge, font=font_badge)
        except Exception:
            bbox = (bx, by, bx + 280, by + 44)
        pad = 14
        # Sombra
        draw.rounded_rectangle(
            [bbox[0] - pad + 4, bbox[1] - pad + 4, bbox[2] + pad + 4, bbox[3] + pad + 4],
            radius=8, fill=(80, 0, 0),
        )
        # Badge principal
        draw.rounded_rectangle(
            [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
            radius=8, fill=(210, 25, 25),
        )
        _draw_outlined_text(draw, (bx, by), badge, font_badge,
                            fill=(255, 255, 255), outline_color=(100, 0, 0), outline=2)

    # Linha decorativa laranja no topo do gradiente
    draw.rectangle([0, start_y - 4, _W, start_y], fill=(255, 140, 0))

    # Badge "🔥 EM ALTA" no canto superior direito
    badge_em_alta = "EM ALTA"
    font_top = _load_font(34, prefer_impact=False)
    if font_top:
        try:
            top_bbox = draw.textbbox((0, 0), badge_em_alta, font=font_top)
            bw = top_bbox[2] - top_bbox[0]
            bx_top = _W - bw - 44
            by_top = 18
            pad_top = 10
            # Sombra
            draw.rounded_rectangle(
                [bx_top - pad_top + 3, by_top - pad_top + 3,
                 bx_top + bw + pad_top + 3, by_top + (top_bbox[3] - top_bbox[1]) + pad_top + 3],
                radius=6, fill=(60, 0, 120),
            )
            # Fundo roxo vibrante
            draw.rounded_rectangle(
                [bx_top - pad_top, by_top - pad_top,
                 bx_top + bw + pad_top, by_top + (top_bbox[3] - top_bbox[1]) + pad_top],
                radius=6, fill=(140, 20, 220),
            )
            _draw_outlined_text(draw, (bx_top, by_top), badge_em_alta, font_top,
                                fill=(255, 255, 255), outline_color=(80, 0, 130), outline=2)
            # "🔥" antes do badge (texto simples pois Pillow sem emoji)
            fire_font = _load_font(28, prefer_impact=True)
            if fire_font:
                draw.text((bx_top - 38, by_top + 2), ">>", font=fire_font, fill=(255, 220, 0))
        except Exception:
            pass

    img.save(output_path, "JPEG", quality=95)
    logger.info(f"Thumbnail gerada: {output_path}")
    return output_path
