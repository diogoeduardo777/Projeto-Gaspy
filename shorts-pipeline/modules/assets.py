import asyncio
import os
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
