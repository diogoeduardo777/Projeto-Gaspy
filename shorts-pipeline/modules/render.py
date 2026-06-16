import os
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

FPS = 25


def _check_ffmpeg():
    if not shutil.which("ffmpeg"):
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
    - Ken Burns (zoompan) em cada imagem
    - Concat das imagens
    - Legendas SRT embutidas
    - Mix de áudio (TTS + música opcional)
    """
    n = len(image_paths)
    per_img = total_duration / n
    frames = int(per_img * FPS)

    parts = []

    # Ken Burns por imagem
    for i in range(n):
        parts.append(
            f"[{i}:v]"
            f"scale=1920:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"zoompan=z='min(zoom+0.0008,1.3)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920,"
            f"fps={FPS}"
            f"[v{i}]"
        )

    # Concat de todos os segmentos
    concat_in = "".join(f"[v{i}]" for i in range(n))
    parts.append(f"{concat_in}concat=n={n}:v=1:a=0[vcat]")

    # Legendas
    srt_escaped = _escape_srt_path(srt_path)
    subtitle_style = (
        "FontName=Arial,FontSize=44,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=60"
    )
    parts.append(
        f"[vcat]subtitles='{srt_escaped}':force_style='{subtitle_style}'[vfinal]"
    )

    # Áudio
    tts_idx = n  # índice do input de TTS no comando FFmpeg
    if has_music:
        music_idx = n + 1
        parts.append(
            f"[{tts_idx}:a]volume=1.0[tts];"
            f"[{music_idx}:a]volume=0.12,atrim=0:{total_duration}[bg];"
            f"[tts][bg]amix=inputs=2:duration=first[aout]"
        )
        audio_map = "[aout]"
    else:
        audio_map = f"{tts_idx}:a"

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

    if not os.path.exists(srt_path):
        logger.error(f"SRT não encontrado: {srt_path}")
        return False

    has_music = bool(music_path and os.path.exists(music_path))
    n_images = len(image_paths)
    per_img = total_duration / n_images

    # Monta inputs
    cmd = ["ffmpeg", "-y"]

    for img in image_paths:
        cmd += ["-loop", "1", "-t", str(per_img), "-i", img]

    cmd += ["-i", tts_path]

    if has_music:
        cmd += ["-i", music_path]

    filter_graph, audio_map = _build_filter_complex(
        image_paths, srt_path, total_duration, has_music, n_images
    )

    cmd += ["-filter_complex", filter_graph]
    cmd += ["-map", "[vfinal]", "-map", audio_map]
    cmd += [
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        "-crf", "23",
        "-t", str(total_duration),
        "-r", str(FPS),
        "-ar", "44100",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Renderizando: {output_path}")
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
        "ffmpeg", "-y",
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
    srt_escaped    = _escape_srt_path(srt_path)
    subtitle_style = (
        "FontName=Arial,FontSize=44,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=60"
    )
    has_music = bool(music_path and os.path.exists(music_path))

    if has_music:
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"subtitles='{srt_escaped}':force_style='{subtitle_style}'[vfinal];"
            f"[1:a]volume=1.0[tts];"
            f"[2:a]volume=0.12,atrim=0:{total_duration}[bg];"
            f"[tts][bg]amix=inputs=2:duration=first[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_path, "-i", tts_path, "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "[vfinal]", "-map", "[aout]",
        ]
    else:
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"subtitles='{srt_escaped}':force_style='{subtitle_style}'[vfinal]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_path, "-i", tts_path,
            "-filter_complex", filter_complex,
            "-map", "[vfinal]", "-map", "1:a",
        ]

    cmd += [
        "-c:v", "libx264", "-c:a", "aac",
        "-preset", "fast", "-crf", "23",
        "-t", str(total_duration),
        "-r", str(FPS), "-ar", "44100",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Renderizando (Kling): {output_path}")
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
