import os
import json
import logging
import sys
from datetime import datetime

import config
from modules.trends import collect_topics
from modules.script import generate_script
from modules.assets import generate_tts, download_images, download_music
from modules.render import render_video, render_from_clips
from modules.video_ai import generate_kling_clips
from modules.publish import generate_amazon_link, generate_shopee_link, save_publish_assets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _ensure_dirs():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.JOBS_DIR, exist_ok=True)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_topic(topic):
    slug = topic["slug"]
    job_dir = os.path.join(config.JOBS_DIR, slug)
    os.makedirs(job_dir, exist_ok=True)

    logger.info(f"--- Tópico: {topic['title']} | Score: {topic['score']} ---")

    # 1. Gerar roteiro
    script_data = generate_script(
        topic["title"],
        topic["top_keywords"],
        config.OLLAMA_BASE_URL,
        config.OLLAMA_MODEL,
    )
    if not script_data:
        logger.error(f"Roteiro falhou para '{topic['title']}'. Pulando.")
        return False

    job = {**topic, **script_data, "status": "script_ok", "created_at": datetime.now().isoformat()}
    job_path = os.path.join(job_dir, "job.json")
    _save_json(job_path, job)

    # 2. Gerar TTS
    tts_path = os.path.join(job_dir, "tts.mp3")
    if not generate_tts(script_data["tts_text"], tts_path, config.TTS_VOICE, config.TTS_RATE):
        logger.error(f"TTS falhou para '{topic['title']}'. Pulando.")
        return False

    # 3. Baixar imagens
    images_dir = os.path.join(job_dir, "images")
    image_paths = download_images(
        script_data.get("image_queries", [topic["title"]]),
        images_dir,
        config.UNSPLASH_ACCESS_KEY,
    )

    if not image_paths:
        logger.error(
            "Sem imagens. Adicione UNSPLASH_ACCESS_KEY no .env "
            "ou coloque imagens manualmente em: " + images_dir
        )
        return False

    # 4. Salvar SRT
    srt_path = os.path.join(job_dir, "legend.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(script_data.get("srt", ""))

    # 5. Música de fundo (opcional)
    music_path = os.path.join(job_dir, "bg.mp3")
    music_ok = download_music(music_path)

    # 6. Renderizar vídeo — tenta Kling AI, cai para slideshow se não configurado/falhar
    output_path = os.path.join(job_dir, "output.mp4")
    clips_dir   = os.path.join(job_dir, "clips")

    clip_paths = generate_kling_clips(
        script_data.get("video_prompts", []),
        clips_dir,
        config.KLING_ACCESS_KEY,
        config.KLING_SECRET_KEY,
    )

    if clip_paths:
        logger.info("Usando clipes Kling AI para o vídeo.")
        render_ok = render_from_clips(
            clip_paths=clip_paths,
            tts_path=tts_path,
            srt_path=srt_path,
            output_path=output_path,
            music_path=music_path if music_ok else None,
            total_duration=config.VIDEO_MAX_DURATION,
        )
    else:
        logger.info("Usando slideshow de imagens como vídeo base.")
        render_ok = render_video(
            image_paths=image_paths,
            tts_path=tts_path,
            srt_path=srt_path,
            output_path=output_path,
            music_path=music_path if music_ok else None,
            total_duration=config.VIDEO_MAX_DURATION,
        )

    # 7. Gerar assets de publicação (Amazon + Shopee)
    amazon_link = generate_amazon_link(topic["top_keywords"], config.AMAZON_AFFILIATE_TAG)
    shopee_link = generate_shopee_link(topic["top_keywords"], config.SHOPEE_AFFILIATE_ID)

    save_publish_assets(
        job_dir,
        topic["title"],
        slug,
        script_data["script_short"],
        amazon_link,
        shopee_link,
        topic["top_keywords"],
    )

    # Atualizar job com resultado final
    job["status"]       = "done" if render_ok else "render_failed"
    job["output_path"]  = output_path if render_ok else None
    job["amazon_link"]  = amazon_link
    job["shopee_link"]  = shopee_link
    job["used_kling"]   = bool(clip_paths)
    _save_json(job_path, job)

    if render_ok:
        logger.info(f"Vídeo pronto: {output_path}")

    return render_ok


def main():
    logger.info("=== Pipeline Shorts Afiliados ===")
    _ensure_dirs()

    # Fase 1: Coletar tópicos
    logger.info("Fase 1: Coletando tópicos em alta...")
    topics = collect_topics(config.SEED_KEYWORDS, config.MAX_TOPICS)
    _save_json(config.TOPICS_FILE, topics)

    # Fase 2: Processar os top N tópicos
    selected = topics[: config.MAX_VIDEOS]
    success = 0

    for topic in selected:
        if process_topic(topic):
            success += 1

    logger.info(f"=== Concluído: {success}/{len(selected)} vídeos gerados ===")
    logger.info(f"Vídeos em: {config.JOBS_DIR}")


if __name__ == "__main__":
    main()
