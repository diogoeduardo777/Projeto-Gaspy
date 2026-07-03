import asyncio
import os
import time
import logging
import requests

logger = logging.getLogger(__name__)


def generate_tts(text, output_path, voice="pt-BR-FranciscaNeural", rate="+10%"):
    """
    Gera narração MP3 usando Edge-TTS (Microsoft, gratuito).
    Voz padrão: pt-BR-FranciscaNeural (feminina, natural).
    Alternativa masculina: pt-BR-AntonioNeural
    """
    try:
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(output_path)

        asyncio.run(_run())
        logger.info(f"TTS gerado: {output_path}")
        return True

    except ImportError:
        logger.error("edge-tts não instalado. Execute: pip install edge-tts")
        return False
    except Exception as e:
        logger.error(f"Erro ao gerar TTS: {e}")
        return False


def _fmt_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds * 1000) % 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _words_to_srt(words, words_per_block=5):
    if not words:
        return ""
    entries = []
    i = 0
    while i < len(words):
        block = words[i:i + words_per_block]
        start_s = block[0]["offset"] / 10_000_000
        last = block[-1]
        end_s = (last["offset"] + last["duration"]) / 10_000_000
        text = " ".join(w["word"] for w in block)
        entries.append((start_s, end_s, text))
        i += words_per_block
    lines = []
    for idx, (start, end, text) in enumerate(entries, 1):
        lines.append(str(idx))
        lines.append(f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _estimate_srt_from_text(text, words_per_block=5, words_per_second=2.6):
    """
    Fallback: gera SRT com tempos estimados quando o Edge-TTS não retorna
    eventos WordBoundary (falha intermitente conhecida). Estima ~2.6
    palavras/segundo para voz pt-BR. Legenda levemente fora de sincronia
    é melhor do que perder o vídeo inteiro.
    """
    tokens = [w for w in text.split() if w.strip()]
    if not tokens:
        return ""
    entries = []
    t = 0.0
    i = 0
    while i < len(tokens):
        block = tokens[i:i + words_per_block]
        dur = len(block) / words_per_second
        entries.append((t, t + dur, " ".join(block)))
        t += dur
        i += words_per_block
    lines = []
    for idx, (start, end, block_text) in enumerate(entries, 1):
        lines.append(str(idx))
        lines.append(f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}")
        lines.append(block_text)
        lines.append("")
    return "\n".join(lines)


def generate_tts_with_srt(text, audio_path, srt_path, voice="pt-BR-FranciscaNeural", rate="+10%", words_per_block=5):
    """
    Gera narração TTS e SRT sincronizado via eventos WordBoundary do Edge-TTS.
    As legendas mostram exatamente o que está sendo falado, em blocos de words_per_block palavras.
    """
    try:
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            words = []
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append({
                        "word": chunk["text"],
                        "offset": chunk["offset"],
                        "duration": chunk["duration"],
                    })
            with open(audio_path, "wb") as f:
                for data in audio_chunks:
                    f.write(data)
            return words

        # Retry: o Edge-TTS às vezes não emite WordBoundary (SRT sairia vazio)
        words = []
        for attempt in range(3):
            if attempt:
                logger.warning(f"Edge-TTS sem WordBoundary — nova tentativa {attempt + 1}/3...")
                time.sleep(2 * attempt)
            words = asyncio.run(_run())
            if words and os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                break

        if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 1000:
            logger.error("Edge-TTS não gerou áudio válido após 3 tentativas.")
            return False

        if words:
            srt_content = _words_to_srt(words, words_per_block)
        else:
            logger.warning("WordBoundary indisponível — usando SRT com tempos estimados (fallback).")
            srt_content = _estimate_srt_from_text(text, words_per_block)

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        logger.info(f"TTS gerado: {audio_path} | SRT: {srt_path} ({len(words)} palavras)")
        return True

    except ImportError:
        logger.error("edge-tts não instalado. Execute: pip install edge-tts")
        return False
    except Exception as e:
        logger.error(f"Erro ao gerar TTS+SRT: {e}")
        return False


def download_images(queries, output_dir, unsplash_key, max_images=12):
    """
    Baixa imagens portrait em alta resolução do Unsplash.
    Requer UNSPLASH_ACCESS_KEY (gratuito em unsplash.com/developers).
    Retorna lista de paths das imagens baixadas.
    """
    if not unsplash_key:
        logger.warning(
            "UNSPLASH_ACCESS_KEY não configurado. "
            "Cadastre-se em unsplash.com/developers e adicione ao .env"
        )
        return []

    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    # 8 sufixos variados: produto, lifestyle, ação, detalhe, estudio...
    style_suffixes = [
        "product photography clean white background",
        "close up macro detail cinematic",
        "tech gadget review hands on lifestyle",
        "unboxing premium packaging",
        "studio lighting product shot",
        "action shot dynamic movement",
        "dark background dramatic light",
        "flat lay minimal aesthetic",
    ]

    for i, query in enumerate(queries[:6]):  # até 6 queries para variedade máxima
        suffix = style_suffixes[i % len(style_suffixes)]
        enhanced_query = f"{query} {suffix}"

        try:
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": enhanced_query,
                    "per_page": 4,
                    "orientation": "portrait",
                    "order_by": "relevant",
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {unsplash_key}"},
                timeout=15,
            )
            resp.raise_for_status()

            for j, photo in enumerate(resp.json().get("results", [])[:4]):
                # "full" em vez de "regular" → resolução máxima para melhor qualidade de vídeo
                img_url = photo["urls"]["full"]
                img_path = os.path.join(output_dir, f"img_{i}_{j}.jpg")

                img_resp = requests.get(img_url, timeout=60, stream=True)
                img_resp.raise_for_status()

                with open(img_path, "wb") as f:
                    for chunk in img_resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                downloaded.append(img_path)
                logger.info(f"Imagem baixada: {img_path}")

                if len(downloaded) >= max_images:
                    return downloaded

        except requests.exceptions.HTTPError as e:
            logger.error(f"Unsplash API erro para '{query}': {e}")
        except Exception as e:
            logger.error(f"Erro ao baixar imagem '{query}': {e}")

    return downloaded


def download_product_images(image_urls, output_dir, max_images=8):
    """
    Baixa imagens diretamente de URLs (ex: CDN da Shopee).
    Retorna lista de paths baixados com sucesso.
    """
    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    for i, url in enumerate(image_urls[:max_images]):
        try:
            resp = requests.get(url, timeout=30, stream=True)
            resp.raise_for_status()
            img_path = os.path.join(output_dir, f"product_{i}.jpg")
            with open(img_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            if os.path.getsize(img_path) > 5000:  # ignora arquivos vazios
                downloaded.append(img_path)
                logger.info(f"Imagem produto baixada: {img_path}")
        except Exception as e:
            logger.warning(f"Falha ao baixar imagem produto {i}: {e}")

    return downloaded


def download_music(output_path):
    """
    Baixa trilha royalty-free CC0 animada para fundo do vídeo.
    Tenta múltiplas fontes — continua sem música se todas falharem.
    """
    _MUSIC_SOURCES = [
        # Free Music Archive — CC0
        (
            "https://files.freemusicarchive.org/storage-freemusicarchive-org/"
            "music/no_curator/Tours/Enthusiast/Tours_-_01_-_Enthusiast.mp3"
        ),
        # Pixabay royalty-free (backup)
        "https://cdn.pixabay.com/audio/2023/03/14/audio_fb7c4a4406.mp3",
        # ccMixter backup
        "https://dig.ccmixter.org/api/tags/hip_hop?format=mp3&order=random&limit=1",
    ]

    for url in _MUSIC_SOURCES:
        try:
            resp = requests.get(url, timeout=30, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "audio" not in content_type and "octet" not in content_type:
                continue

            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            if os.path.getsize(output_path) > 50_000:  # mínimo 50KB válido
                logger.info(f"Música baixada: {output_path}")
                return True

        except Exception as e:
            logger.debug(f"Fonte de música falhou ({url[:50]}): {e}")

    logger.warning("Não foi possível baixar música de fundo — vídeo sem trilha.")
    return False
