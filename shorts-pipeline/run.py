import os
import json
import logging
import sys
from datetime import datetime

import config
from modules.trends import collect_topics
from modules.script import generate_script, generate_product_script
from modules.assets import generate_tts, generate_tts_with_srt, download_images, download_music, download_product_images
from modules.render import render_video, render_from_clips
from modules.video_ai import generate_kling_clips
from modules.publish import (
    generate_amazon_link, generate_shopee_link, generate_mercadolivre_link,
    generate_shopee_product_direct_link, generate_amazon_product_link,
    save_publish_assets,
)
from modules.thumbnail import generate_thumbnail
from modules.tracker import JobTracker
from modules.youtube import upload_video, upload_thumbnail, post_affiliate_comment

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


# Rotação dos horários de pico: cada vídeo do dia sai em um horário diferente
_publish_slot = 0


def _next_publish_hour():
    global _publish_slot
    hours = config.YOUTUBE_PUBLISH_HOURS
    if not hours or config.YOUTUBE_PRIVACY != "scheduled":
        return None
    hour = hours[_publish_slot % len(hours)]
    _publish_slot += 1
    return hour


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def process_topic(topic, tracker):
    slug    = topic["slug"]
    job_dir = os.path.join(config.JOBS_DIR, slug)
    os.makedirs(job_dir, exist_ok=True)

    logger.info(f"--- Tópico: {topic['title']} | Score: {topic['score']}"
                f"{' [intenção comercial]' if topic.get('has_commercial_intent') else ''} ---")

    # 1. Gerar roteiro (Groq ou Ollama conforme LLM_PROVIDER no .env)
    script_data = generate_script(
        topic["title"],
        topic["top_keywords"],
        provider=config.LLM_PROVIDER,
        groq_api_key=config.GROQ_API_KEY,
        groq_model=config.GROQ_MODEL,
        ollama_base_url=config.OLLAMA_BASE_URL,
        ollama_model=config.OLLAMA_MODEL,
        niche=config.NICHO,
    )
    if not script_data:
        logger.error(f"Roteiro falhou para '{topic['title']}'. Pulando.")
        tracker.upsert(slug, title=topic["title"], score=topic["score"], status="script_failed",
                       created_at=datetime.now().isoformat())
        return False

    job = {**topic, **script_data, "status": "script_ok", "created_at": datetime.now().isoformat()}
    job_path = os.path.join(job_dir, "job.json")
    _save_json(job_path, job)

    # 2. Gerar TTS + SRT sincronizado automaticamente via WordBoundary
    tts_path = os.path.join(job_dir, "tts.mp3")
    srt_path = os.path.join(job_dir, "legend.srt")
    if not generate_tts_with_srt(script_data["tts_text"], tts_path, srt_path, config.TTS_VOICE, config.TTS_RATE):
        logger.error(f"TTS falhou para '{topic['title']}'. Pulando.")
        return False

    # 3. Baixar imagens
    images_dir  = os.path.join(job_dir, "images")
    image_paths = download_images(
        script_data.get("image_queries", [topic["title"]]),
        images_dir,
        config.UNSPLASH_ACCESS_KEY,
    )
    if not image_paths:
        logger.error("Sem imagens. Adicione UNSPLASH_ACCESS_KEY no .env ou coloque imagens em: " + images_dir)
        return False

    # 4. Gerar thumbnail (usa primeira imagem baixada)
    thumbnail_path = os.path.join(job_dir, "thumbnail.jpg")
    generate_thumbnail(image_paths[0], topic["title"], thumbnail_path)

    # 6. Música de fundo (opcional)
    music_path = os.path.join(job_dir, "bg.mp3")
    music_ok   = download_music(music_path)

    # 7. Renderizar vídeo — tenta Kling AI, cai para slideshow se não configurado/falhar
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
            clip_paths=clip_paths, tts_path=tts_path, srt_path=srt_path,
            output_path=output_path, music_path=music_path if music_ok else None,
            total_duration=config.VIDEO_MAX_DURATION,
        )
    else:
        logger.info("Usando slideshow de imagens como vídeo base.")
        render_ok = render_video(
            image_paths=image_paths, tts_path=tts_path, srt_path=srt_path,
            output_path=output_path, music_path=music_path if music_ok else None,
            total_duration=config.VIDEO_MAX_DURATION,
        )

    # 8. Gerar links de afiliado (Amazon + Shopee + Mercado Livre)
    amazon_link = generate_amazon_link(topic["top_keywords"], config.AMAZON_AFFILIATE_TAG)
    shopee_link = generate_shopee_link(topic["top_keywords"], config.SHOPEE_AFFILIATE_ID)
    ml_link     = generate_mercadolivre_link(topic["top_keywords"], config.MERCADOLIVRE_AFFILIATE_ID)
    save_publish_assets(job_dir, topic["title"], slug, script_data["script_short"],
                        amazon_link, shopee_link, topic["top_keywords"],
                        telegram_channel=config.TELEGRAM_CHANNEL,
                        mercadolivre_link=ml_link)

    # 9. Upload automático YouTube (se YOUTUBE_AUTO_UPLOAD=true)
    youtube_id  = None
    youtube_url = None

    if render_ok and config.YOUTUBE_AUTO_UPLOAD:
        with open(os.path.join(job_dir, "description.txt"), encoding="utf-8") as f:
            description_text = f.read()

        yt_title   = script_data.get("seo_title") or f"{topic['title']} - Vale a pena? #Shorts"
        extra_tags = ["review", "vale a pena", "gadgets", "2026", "Shorts"]
        youtube_id = upload_video(
            video_path=output_path, title=yt_title, description=description_text,
            tags=topic["top_keywords"] + extra_tags, credentials_file=config.YOUTUBE_CREDENTIALS_FILE,
            token_file=config.YOUTUBE_TOKEN_FILE, privacy=config.YOUTUBE_PRIVACY,
            publish_hour=_next_publish_hour(),
        )

        if youtube_id:
            youtube_url = f"https://youtube.com/shorts/{youtube_id}"

            # 9a. Upload da thumbnail
            upload_thumbnail(
                youtube_id, thumbnail_path,
                config.YOUTUBE_CREDENTIALS_FILE, config.YOUTUBE_TOKEN_FILE,
            )

            # 9b. Comentário com links de afiliado (Amazon + Shopee + ML)
            post_affiliate_comment(
                youtube_id, amazon_link, shopee_link,
                config.YOUTUBE_CREDENTIALS_FILE, config.YOUTUBE_TOKEN_FILE,
                mercadolivre_link=ml_link,
            )

    # 10. Registrar no SQLite
    tracker.upsert(
        slug,
        title=topic["title"],
        score=topic["score"],
        status="done" if render_ok else "render_failed",
        used_kling=int(bool(clip_paths)),
        created_at=job.get("created_at"),
        output_path=output_path if render_ok else None,
        thumbnail_path=thumbnail_path if os.path.exists(thumbnail_path) else None,
        amazon_link=amazon_link,
        shopee_link=shopee_link,
        youtube_id=youtube_id,
        youtube_url=youtube_url,
    )

    # Atualizar job.json
    job.update({
        "status":      "done" if render_ok else "render_failed",
        "output_path": output_path if render_ok else None,
        "amazon_link": amazon_link,
        "shopee_link": shopee_link,
        "used_kling":  bool(clip_paths),
        "youtube_id":  youtube_id,
        "youtube_url": youtube_url,
    })
    _save_json(job_path, job)

    if render_ok:
        logger.info(f"Vídeo pronto: {output_path}")
    if youtube_url:
        logger.info(f"YouTube: {youtube_url}")

    return render_ok


def process_product(product, style, tracker):
    """
    Processa um produto real gerando um vídeo no estilo indicado.
    style: "viral" ou "ugc"
    """
    from modules.product_scorer import score_product

    item_id  = product.get("item_id") or product.get("asin") or "unknown"
    platform = product.get("platform", "shopee")
    slug     = f"product_{platform}_{item_id}_{style}"
    job_dir  = os.path.join(config.JOBS_DIR, slug)
    os.makedirs(job_dir, exist_ok=True)

    viral_score = score_product(product)
    logger.info(
        f"--- Produto: {product['name'][:50]} | Score: {viral_score} "
        f"| Plataforma: {platform.upper()} | Estilo: {style.upper()} ---"
    )

    # 1. Gerar roteiro focado no produto
    script_data = generate_product_script(
        product_data=product,
        style=style,
        provider=config.LLM_PROVIDER,
        groq_api_key=config.GROQ_API_KEY,
        groq_model=config.GROQ_MODEL,
        ollama_base_url=config.OLLAMA_BASE_URL,
        ollama_model=config.OLLAMA_MODEL,
    )
    if not script_data:
        logger.error(f"Roteiro falhou para produto '{product['name'][:40]}'. Pulando.")
        tracker.upsert(slug, title=product["name"], score=viral_score,
                       status="script_failed", created_at=datetime.now().isoformat())
        return False

    job = {**product, **script_data, "style": style, "viral_score": viral_score,
           "status": "script_ok", "created_at": datetime.now().isoformat()}
    _save_json(os.path.join(job_dir, "job.json"), job)

    # 2. TTS + SRT sincronizado automaticamente via WordBoundary
    tts_path = os.path.join(job_dir, "tts.mp3")
    srt_path = os.path.join(job_dir, "legend.srt")
    if not generate_tts_with_srt(script_data["tts_text"], tts_path, srt_path, config.TTS_VOICE, config.TTS_RATE):
        logger.error(f"TTS falhou para produto '{product['name'][:40]}'.")
        return False

    # 3. Imagens — tenta CDN do produto primeiro, cai para Unsplash
    images_dir  = os.path.join(job_dir, "images")
    image_paths = download_product_images(product.get("images", []), images_dir)
    if len(image_paths) < 3:
        logger.info("Poucas imagens do produto — complementando com Unsplash.")
        extra = download_images(
            script_data.get("image_queries", [product["name"]]),
            images_dir,
            config.UNSPLASH_ACCESS_KEY,
            max_images=max(4, 8 - len(image_paths)),
        )
        image_paths = image_paths + extra

    if not image_paths:
        logger.error("Sem imagens disponíveis para o produto. Pulando.")
        return False

    # 4. Thumbnail
    thumbnail_path = os.path.join(job_dir, "thumbnail.jpg")
    generate_thumbnail(image_paths[0], product["name"], thumbnail_path)

    # 6. Música
    music_path = os.path.join(job_dir, "bg.mp3")
    music_ok   = download_music(music_path)

    # 7. Renderizar vídeo
    output_path = os.path.join(job_dir, "output.mp4")
    clips_dir   = os.path.join(job_dir, "clips")

    clip_paths = generate_kling_clips(
        script_data.get("video_prompts", []),
        clips_dir,
        config.KLING_ACCESS_KEY,
        config.KLING_SECRET_KEY,
    )

    if clip_paths:
        logger.info("Usando clipes Kling AI.")
        render_ok = render_from_clips(
            clip_paths=clip_paths, tts_path=tts_path, srt_path=srt_path,
            output_path=output_path, music_path=music_path if music_ok else None,
            total_duration=config.VIDEO_MAX_DURATION,
        )
    else:
        logger.info("Usando slideshow de imagens do produto.")
        render_ok = render_video(
            image_paths=image_paths, tts_path=tts_path, srt_path=srt_path,
            output_path=output_path, music_path=music_path if music_ok else None,
            total_duration=config.VIDEO_MAX_DURATION,
        )

    # 8. Links de afiliado diretos por produto
    # affiliate_override: link manual do products.json tem prioridade
    affiliate_override = product.get("affiliate_override")

    if platform == "shopee":
        shopee_link = affiliate_override or generate_shopee_product_direct_link(
            product.get("item_id"), product.get("shop_id"),
            product["name"], config.SHOPEE_AFFILIATE_ID,
        )
        amazon_link = generate_amazon_link(product["name"].split()[:3], config.AMAZON_AFFILIATE_TAG)
    else:  # amazon
        asin        = product.get("asin", "")
        amazon_link = affiliate_override or (
            generate_amazon_product_link(asin, config.AMAZON_AFFILIATE_TAG) if asin
            else generate_amazon_link(product["name"].split()[:3], config.AMAZON_AFFILIATE_TAG)
        )
        shopee_link = generate_shopee_link(product["name"].split()[:3], config.SHOPEE_AFFILIATE_ID)

    ml_link = generate_mercadolivre_link(product["name"].split()[:3], config.MERCADOLIVRE_AFFILIATE_ID)

    top_keywords = product["name"].lower().split()[:5]
    save_publish_assets(job_dir, product["name"], slug, script_data["script_short"],
                        amazon_link, shopee_link, top_keywords,
                        telegram_channel=config.TELEGRAM_CHANNEL,
                        mercadolivre_link=ml_link,
                        platform=platform)

    # 9. Upload YouTube
    youtube_id  = None
    youtube_url = None

    if render_ok and config.YOUTUBE_AUTO_UPLOAD:
        with open(os.path.join(job_dir, "description.txt"), encoding="utf-8") as f:
            description_text = f.read()

        yt_title   = script_data.get("seo_title") or f"{product['name'][:50]} - Vale a pena? #Shorts"
        extra_tags = ["review", "vale a pena", "shopee", "amazon", "2026", "Shorts"]
        youtube_id = upload_video(
            video_path=output_path, title=yt_title, description=description_text,
            tags=top_keywords + extra_tags, credentials_file=config.YOUTUBE_CREDENTIALS_FILE,
            token_file=config.YOUTUBE_TOKEN_FILE, privacy=config.YOUTUBE_PRIVACY,
            publish_hour=_next_publish_hour(),
        )
        if youtube_id:
            youtube_url = f"https://youtube.com/shorts/{youtube_id}"
            upload_thumbnail(youtube_id, thumbnail_path,
                             config.YOUTUBE_CREDENTIALS_FILE, config.YOUTUBE_TOKEN_FILE)
            post_affiliate_comment(youtube_id, amazon_link, shopee_link,
                                   config.YOUTUBE_CREDENTIALS_FILE, config.YOUTUBE_TOKEN_FILE,
                                   mercadolivre_link=ml_link)

    # 10. Registrar no SQLite
    tracker.upsert(
        slug,
        title=product["name"],
        score=viral_score,
        status="done" if render_ok else "render_failed",
        used_kling=int(bool(clip_paths)),
        created_at=job.get("created_at"),
        output_path=output_path if render_ok else None,
        thumbnail_path=thumbnail_path if os.path.exists(thumbnail_path) else None,
        amazon_link=amazon_link,
        shopee_link=shopee_link,
        youtube_id=youtube_id,
        youtube_url=youtube_url,
    )

    job.update({
        "status":      "done" if render_ok else "render_failed",
        "output_path": output_path if render_ok else None,
        "amazon_link": amazon_link,
        "shopee_link": shopee_link,
        "youtube_id":  youtube_id,
        "youtube_url": youtube_url,
    })
    _save_json(os.path.join(job_dir, "job.json"), job)

    if render_ok:
        logger.info(f"Vídeo produto pronto: {output_path}")
    if youtube_url:
        logger.info(f"YouTube: {youtube_url}")

    return render_ok


def run_product_mode(tracker):
    """
    Modo produto: descobre automaticamente produtos em alta na Shopee,
    ranqueia por score viral e gera vídeos viral+ugc para os top N.
    Se existir data/products.json, usa os produtos manuais em vez do auto-discovery.
    """
    from modules.product_fetcher import discover_shopee_products, load_manual_products
    from modules.product_scorer import score_product

    logger.info("=== Modo Produto: buscando produtos em alta na Shopee ===")

    # Prioridade 1: products.json manual (mais confiável)
    manual_file = os.path.join(config.DATA_DIR, "products.json")
    candidates = load_manual_products(manual_file)

    # Prioridade 2: auto-discovery via API Shopee
    if not candidates:
        logger.info("products.json não encontrado — tentando auto-discovery Shopee...")
        candidates = discover_shopee_products(
            config.PRODUCT_KEYWORDS,
            max_per_keyword=5,
        )

    if not candidates:
        logger.warning(
            "Nenhum produto encontrado. Crie o arquivo data/products.json com produtos manuais "
            "ou verifique a conexão com a Shopee."
        )
        return 0

    # Ranquear por score viral
    for p in candidates:
        p["_score"] = score_product(p)

    # Rotação diária: prioriza produtos não usados nos últimos 7 dias
    recent_ids = tracker.get_recent_product_ids(days=7)
    for p in candidates:
        p_id = str(p.get("item_id") or p.get("asin") or "")
        p["_used_recently"] = p_id in recent_ids

    # Ordena: não usados recentemente primeiro (por score), depois os usados (mais antigos primeiro)
    candidates.sort(key=lambda x: (x["_used_recently"], -x["_score"]))

    selected = candidates[: config.MAX_PRODUCTS_PER_PLATFORM]
    recently_used_count = sum(1 for p in selected if p["_used_recently"])
    logger.info(
        f"Produtos selecionados: {[(p['name'][:30], p['_score'], '(recente)' if p['_used_recently'] else '') for p in selected]}"
    )
    if recently_used_count:
        logger.info(f"Aviso: {recently_used_count} produto(s) repetido(s) — pool pequeno, considere adicionar mais produtos ao products.json")

    styles  = ["viral", "ugc"][: config.VIDEOS_PER_PRODUCT]
    success = 0

    for product in selected:
        for style in styles:
            if process_product(product, style, tracker):
                success += 1

    total = len(selected) * len(styles)
    logger.info(f"=== Modo Produto concluído: {success}/{total} vídeos gerados ===")
    return success


def main():
    logger.info("=== Pipeline Shorts Afiliados ===")
    _ensure_dirs()

    tracker = JobTracker(config.DB_PATH)
    success = 0

    if config.PRODUCT_MODE:
        logger.info("Modo: PRODUTO (Shopee/Amazon — produtos reais)")
        success = run_product_mode(tracker)
    else:
        # Modo padrão: tópicos em alta (comportamento original)
        logger.info("Modo: TÓPICOS (Google Trends + YouTube)")
        logger.info("Fase 1: Coletando tópicos em alta...")
        topics = collect_topics(config.SEED_KEYWORDS, config.MAX_TOPICS)
        _save_json(config.TOPICS_FILE, topics)

        selected = topics[: config.MAX_VIDEOS]
        success  = 0
        for topic in selected:
            if process_topic(topic, tracker):
                success += 1

        logger.info(f"=== Concluído: {success}/{len(selected)} vídeos gerados ===")
        logger.info(f"Vídeos em: {config.JOBS_DIR}")

    tracker.print_summary()

    # 0 vídeos gerados = falha real — exit 1 faz o GitHub Actions ficar vermelho
    # e disparar notificação, em vez de falhar em silêncio com status verde
    if success == 0:
        logger.error("Nenhum vídeo foi gerado nesta execução — saindo com erro.")
        sys.exit(1)


if __name__ == "__main__":
    main()
