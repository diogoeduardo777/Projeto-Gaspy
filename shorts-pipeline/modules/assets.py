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


def download_images(queries, output_dir, unsplash_key, max_images=3):
    """
    Baixa imagens portrait do Unsplash para uso como base do slideshow.
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

    for i, query in enumerate(queries[:2]):
        try:
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 2, "orientation": "portrait"},
                headers={"Authorization": f"Client-ID {unsplash_key}"},
                timeout=15,
            )
            resp.raise_for_status()

            for j, photo in enumerate(resp.json().get("results", [])[:2]):
                img_url = photo["urls"]["regular"]
                img_path = os.path.join(output_dir, f"img_{i}_{j}.jpg")

                img_resp = requests.get(img_url, timeout=30, stream=True)
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
    Baixa trilha royalty-free curta para fundo do vídeo.
    Fonte: Free Music Archive (CC0).
    Retorna True se sucesso, False caso contrário (vídeo será gerado sem música).
    """
    # Trilha CC0 do Free Music Archive
    url = (
        "https://files.freemusicarchive.org/storage-freemusicarchive-org/"
        "music/no_curator/Tours/Enthusiast/Tours_-_01_-_Enthusiast.mp3"
    )

    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Música baixada: {output_path}")
        return True

    except Exception as e:
        logger.warning(f"Não foi possível baixar música de fundo: {e}")
        return False
