import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

_KLING_BASE = "https://api.klingai.com"


def _generate_jwt(access_key, secret_key):
    try:
        import jwt
    except ImportError:
        raise ImportError("PyJWT não instalado. Execute: pip install PyJWT")
    now = int(time.time())
    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
    return jwt.encode(payload, secret_key, algorithm="HS256")


def _submit_task(prompt, access_key, secret_key, duration="10"):
    token = _generate_jwt(access_key, secret_key)
    resp = requests.post(
        f"{_KLING_BASE}/v1/videos/text2video",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "model": "kling-v1",
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, watermark, text overlay, distorted",
            "aspect_ratio": "9:16",
            "duration": duration,
            "mode": "std",
            "cfg_scale": 0.5,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]["task_id"]


def _poll_task(task_id, access_key, secret_key, max_wait=300):
    """Aguarda conclusão do task Kling. Retorna URL do vídeo ou None."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(10)
        token = _generate_jwt(access_key, secret_key)
        resp = requests.get(
            f"{_KLING_BASE}/v1/videos/text2video/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["task_status"]

        if status == "succeed":
            return data["task_result"]["videos"][0]["url"]
        if status == "failed":
            logger.error(f"Kling task falhou: {data.get('task_status_msg', '')}")
            return None

    logger.error("Kling timeout — task não concluiu em 5 minutos.")
    return None


def _download_clip(url, output_path):
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def generate_kling_clips(video_prompts, output_dir, access_key, secret_key):
    """
    Gera clipes de vídeo via Kling AI (text-to-video) para cada cena.
    Plano gratuito: 66 créditos/dia (~22 vídeos completos de 3 cenas cada).
    Retorna lista de paths dos clipes ou [] para acionar fallback slideshow.
    """
    if not access_key or not secret_key:
        logger.info("Kling não configurado — usando slideshow como vídeo base.")
        return []

    os.makedirs(output_dir, exist_ok=True)
    clip_paths = []

    for i, prompt in enumerate(video_prompts[:3]):
        logger.info(f"Kling: gerando clipe {i+1}/3...")

        try:
            task_id  = _submit_task(prompt, access_key, secret_key, duration="10")
            video_url = _poll_task(task_id, access_key, secret_key)

            if not video_url:
                logger.warning("Clipe Kling falhou — ativando fallback para slideshow.")
                return []

            clip_path = os.path.join(output_dir, f"clip_{i}.mp4")
            _download_clip(video_url, clip_path)
            clip_paths.append(clip_path)
            logger.info(f"Clipe {i+1} salvo: {clip_path}")

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning("Créditos Kling esgotados hoje — usando slideshow.")
            else:
                logger.error(f"Kling API erro: {e}")
            return []
        except Exception as e:
            logger.error(f"Erro inesperado no clipe {i+1}: {e}")
            return []

    return clip_paths
