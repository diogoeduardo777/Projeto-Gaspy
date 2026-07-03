import os
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

FPS = 30  # padrão YouTube Shorts
_encoder_cache = None
_FFMPEG_FALLBACK = r"C:\ffmpeg\bin\ffmpeg.exe"

# 8 Ken Burns directions: zoom-in e zoom-out alternados para dinamismo máximo
_ZOOM_CONFIGS = [
    ("min(zoom+0.0018,1.5)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),           # in centro
    ("if(eq(on,1),1.5,max(1,zoom-0.002))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # out centro
    ("min(zoom+0.002,1.6)",  "0",                  "0"),                          # in topo-esq
    ("min(zoom+0.002,1.6)",  "iw-(iw/zoom)",        "ih-(ih/zoom)"),              # in baixo-dir
    ("if(eq(on,1),1.6,max(1,zoom-0.0022))", "iw-(iw/zoom)", "0"),               # out topo-dir
    ("min(zoom+0.0015,1.5)", "iw/2-(iw/zoom/2)",   "0"),                         # in topo-centro
    ("if(eq(on,1),1.5,max(1,zoom-0.0018))", "0",   "ih-(ih/zoom)"),             # out baixo-esq
    ("min(zoom+0.0015,1.5)", "iw-(iw/zoom)",        "ih/2-(ih/zoom/2)"),         # in direita
]
_XFADE_DURATION = 0.25  # segundos de transição dissolve entre cenas


def _ffmpeg_exe():
    """Retorna o executável ffmpeg: PATH primeiro, depois caminho fixo."""
    return shutil.which("ffmpeg") or _FFMPEG_FALLBACK


def _detect_best_encoder():
    """
    Detecta o encoder H.264 a usar:
    - Se VIDEO_ENCODER=cpu no .env, força libx264 (CPU).
    - Caso contrário testa AMD AMF e NVENC e cai em libx264 se falharem.
    Resultado é cacheado — a detecção roda só uma vez por sessão.
    """
    global _encoder_cache
    if _encoder_cache:
        return _encoder_cache

    env_encoder = os.getenv("VIDEO_ENCODER", "auto").lower()
    if env_encoder == "cpu":
        _encoder_cache = "libx264"
        logger.info(f"Encoder fixado por VIDEO_ENCODER=cpu: {_encoder_cache}")
        return _encoder_cache

    try:
        result = subprocess.run(
            [_ffmpeg_exe(), "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout
        if "h264_nvenc" in out:
            _encoder_cache = "h264_nvenc"
        else:
            _encoder_cache = "libx264"
    except Exception:
        _encoder_cache = "libx264"
    logger.info(f"Encoder detectado: {_encoder_cache}")
    return _encoder_cache


def _encoder_flags(encoder):
    """Retorna os flags FFmpeg corretos para cada encoder."""
    if encoder == "h264_amf":
        # AMD RX 580 — hardware encoding via AMF
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "22", "-qp_p", "24"]
    if encoder == "h264_nvenc":
        # NVIDIA — hardware encoding via NVENC
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"]
    # CPU fallback
    return ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]


def _check_ffmpeg():
    exe = _ffmpeg_exe()
    if not os.path.isfile(exe) and not shutil.which("ffmpeg"):
        logger.error(
            "FFmpeg não encontrado. Baixe em https://ffmpeg.org e adicione ao PATH do sistema."
        )
        return False
    return True


def _escape_srt_path(path):
    """
    Escapa path para uso no filtro subtitles= do FFmpeg.
    No Windows: converte backslashes e escapa o ':' do drive (ex: C: -> C\\:).
    """
    path = path.replace("\\", "/")
    # Escapa apenas o ':' que vem após a letra do drive (C:/ -> C\:/)
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    return path


def _build_filter_complex(image_paths, srt_path, total_duration, has_music, n_extra_inputs):
    """
    Monta o filtergraph FFmpeg:
    - Ken Burns 8 direções (zoom-in e zoom-out alternados)
    - Transições xfade dissolve entre cenas
    - Legendas SRT embutidas
    - Color grade cinematográfico + vignette
    - Mix de áudio (TTS + música opcional)
    """
    n = len(image_paths)

    # Ajusta duração por imagem para manter total_duration com o overlap do xfade
    if n > 1:
        per_img = (total_duration + (n - 1) * _XFADE_DURATION) / n
    else:
        per_img = total_duration
    frames = int(per_img * FPS)

    parts = []

    # Ken Burns por imagem — 8 direções alternadas incluindo zoom-out
    for i in range(n):
        z_expr, x_expr, y_expr = _ZOOM_CONFIGS[i % len(_ZOOM_CONFIGS)]
        parts.append(
            f"[{i}:v]"
            f"scale=1920:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"zoompan=z='{z_expr}':d={frames}:"
            f"x='{x_expr}':y='{y_expr}':s=1080x1920,"
            f"fps={FPS},"
            f"setsar=1"
            f"[v{i}]"
        )

    # Encadeia transições xfade dissolve entre cada par de cenas
    if n == 1:
        last_label = "v0"
    else:
        offset = per_img - _XFADE_DURATION
        parts.append(
            f"[v0][v1]xfade=transition=dissolve:"
            f"duration={_XFADE_DURATION:.2f}:offset={offset:.2f}[xf1]"
        )
        last_label = "xf1"
        for i in range(2, n):
            offset += per_img - _XFADE_DURATION
            new_label = f"xf{i}"
            parts.append(
                f"[{last_label}][v{i}]xfade=transition=dissolve:"
                f"duration={_XFADE_DURATION:.2f}:offset={offset:.2f}[{new_label}]"
            )
            last_label = new_label

    # Legendas + color grade: saturação vibrante, nitidez, vignette cinematográfico
    # srt_path=None → renderiza sem legendas (SRT ausente/vazio não derruba o vídeo)
    if srt_path:
        srt_escaped = _escape_srt_path(srt_path)
        # FontSize 24 + MarginV 60: legenda maior e acima da área de botões do Shorts
        subtitle_style = (
            "FontName=Arial,FontSize=24,Bold=1,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "Outline=2,Shadow=1,"
            "Alignment=2,MarginV=60"
        )
        subtitle_filter = f"subtitles='{srt_escaped}':force_style='{subtitle_style}',"
    else:
        subtitle_filter = ""
    parts.append(
        f"[{last_label}]"
        f"{subtitle_filter}"
        f"eq=saturation=1.6:contrast=1.1:brightness=0.02,"
        f"unsharp=5:5:0.6:3:3:0.0,"
        f"vignette=angle=0.8[vfinal]"
    )

    # Áudio — loudnorm -14 LUFS (padrão YouTube) para volume consistente entre vídeos
    tts_idx = n  # índice do input TTS no comando FFmpeg
    if has_music:
        music_idx = n + 1
        parts.append(
            f"[{tts_idx}:a]volume=1.0[tts];"
            f"[{music_idx}:a]volume=0.12,atrim=0:{total_duration}[bg];"
            f"[tts][bg]amix=inputs=2:duration=first,"
            f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        )
    else:
        parts.append(f"[{tts_idx}:a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    audio_map = "[aout]"

    return ";".join(parts), audio_map


def render_video(image_paths, tts_path, srt_path, output_path, music_path=None, total_duration=30):
    """
    Renderiza o vídeo final: slideshow Ken Burns + narração TTS + legendas SRT.
    Saída: 1080x1920, H.264, AAC, ≤30s.
    Requer FFmpeg com libass (para subtitles=) instalado.
    """
    if not _check_ffmpeg():
        return False

    if not image_paths:
        logger.error("Nenhuma imagem para renderização.")
        return False

    if not os.path.exists(tts_path):
        logger.error(f"TTS não encontrado: {tts_path}")
        return False

    # SRT ausente ou vazio não impede o vídeo — renderiza sem legendas
    if not os.path.exists(srt_path) or os.path.getsize(srt_path) == 0:
        logger.warning(f"SRT ausente ou vazio ({srt_path}) — renderizando sem legendas.")
        srt_path = None

    has_music = bool(music_path and os.path.exists(music_path))
    n_images = len(image_paths)

    # per_img deve incluir o overlap do xfade — mesma lógica de _build_filter_complex
    if n_images > 1:
        per_img = (total_duration + (n_images - 1) * _XFADE_DURATION) / n_images
    else:
        per_img = float(total_duration)

    # Monta inputs — cada imagem precisa durar per_img completo para o zoompan
    cmd = [_ffmpeg_exe(), "-y"]

    for img in image_paths:
        cmd += ["-loop", "1", "-t", str(per_img), "-i", img]

    cmd += ["-i", tts_path]

    if has_music:
        cmd += ["-i", music_path]

    filter_graph, audio_map = _build_filter_complex(
        image_paths, srt_path, total_duration, has_music, n_images
    )

    encoder = _detect_best_encoder()
    cmd += ["-filter_complex", filter_graph]
    cmd += ["-map", "[vfinal]", "-map", audio_map]
    cmd += _encoder_flags(encoder)
    cmd += [
        "-c:a", "aac",
        "-t", str(total_duration),
        "-r", str(FPS),
        "-ar", "44100",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Renderizando [{encoder}]: {output_path}")
    logger.debug("Comando: " + " ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.error(f"FFmpeg falhou (código {result.returncode}):\n{result.stderr[-2000:]}")
            return False

        logger.info(f"Vídeo gerado: {output_path}")
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout (5 min). Verifique as imagens ou reduza a duração.")
        return False
    except Exception as e:
        logger.error(f"Erro ao executar FFmpeg: {e}")
        return False


def render_from_clips(clip_paths, tts_path, srt_path, output_path, music_path=None, total_duration=30):
    """
    Monta vídeo final a partir de clipes Kling AI pré-gerados.
    Concatena os clipes e sobrepõe narração TTS + legendas SRT via FFmpeg.
    """
    if not _check_ffmpeg():
        return False

    if not clip_paths:
        logger.error("Nenhum clipe Kling para montar.")
        return False

    work_dir = os.path.dirname(output_path)
    filelist_path = os.path.join(work_dir, "_filelist.txt")
    concat_path   = os.path.join(work_dir, "_concat.mp4")

    # Passo 1: concatenar clipes
    with open(filelist_path, "w", encoding="utf-8") as f:
        for clip in clip_paths:
            f.write(f"file '{clip.replace(chr(39), '')}'\n")

    concat_cmd = [
        _ffmpeg_exe(), "-y",
        "-f", "concat", "-safe", "0",
        "-i", filelist_path,
        "-c", "copy",
        concat_path,
    ]
    result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        logger.error(f"FFmpeg concat falhou:\n{result.stderr[-1000:]}")
        return False

    # Passo 2: escalar para 1080x1920, adicionar áudio + legendas
    # SRT ausente ou vazio não impede o vídeo — renderiza sem legendas
    if not os.path.exists(srt_path) or os.path.getsize(srt_path) == 0:
        logger.warning(f"SRT ausente ou vazio ({srt_path}) — renderizando sem legendas.")
        subtitle_filter = ""
    else:
        srt_escaped    = _escape_srt_path(srt_path)
        # FontSize 24 + MarginV 60: legenda maior e acima da área de botões do Shorts
        subtitle_style = (
            "FontName=Arial,FontSize=24,Bold=1,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "Outline=2,Shadow=1,"
            "Alignment=2,MarginV=60"
        )
        subtitle_filter = f",subtitles='{srt_escaped}':force_style='{subtitle_style}'"
    has_music = bool(music_path and os.path.exists(music_path))

    if has_music:
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"eq=saturation=1.5:contrast=1.1:brightness=0.02,unsharp=5:5:0.5:3:3:0.0,"
            f"vignette=angle=0.8"
            f"{subtitle_filter}[vfinal];"
            f"[1:a]volume=1.0[tts];"
            f"[2:a]volume=0.12,atrim=0:{total_duration}[bg];"
            f"[tts][bg]amix=inputs=2:duration=first,"
            f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        )
        cmd = [
            _ffmpeg_exe(), "-y",
            "-i", concat_path, "-i", tts_path, "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "[vfinal]", "-map", "[aout]",
        ]
    else:
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"eq=saturation=1.5:contrast=1.1:brightness=0.02,unsharp=5:5:0.5:3:3:0.0,"
            f"vignette=angle=0.8"
            f"{subtitle_filter}[vfinal];"
            f"[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        )
        cmd = [
            _ffmpeg_exe(), "-y",
            "-i", concat_path, "-i", tts_path,
            "-filter_complex", filter_complex,
            "-map", "[vfinal]", "-map", "[aout]",
        ]

    encoder = _detect_best_encoder()
    cmd += _encoder_flags(encoder)
    cmd += [
        "-c:a", "aac",
        "-t", str(total_duration),
        "-r", str(FPS), "-ar", "44100",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Renderizando Kling [{encoder}]: {output_path}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # limpeza de arquivos temporários
        for tmp in (filelist_path, concat_path):
            try:
                os.remove(tmp)
            except Exception:
                pass

        if result.returncode != 0:
            logger.error(f"FFmpeg render falhou:\n{result.stderr[-2000:]}")
            return False

        logger.info(f"Vídeo Kling gerado: {output_path}")
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout na renderização Kling.")
        return False
    except Exception as e:
        logger.error(f"Erro ao renderizar clipes Kling: {e}")
        return False
