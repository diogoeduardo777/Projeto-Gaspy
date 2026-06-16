import json
import re
import logging
import requests

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """Você é um roteirista especialista em vídeos curtos para YouTube Shorts.
Crie um roteiro persuasivo em PT-BR coloquial para um Short de 30 segundos sobre: "{topic}".
Palavras-chave de referência: {keywords}.

Estrutura obrigatória:
- Gancho (0–3s): 1 frase impactante que prende atenção.
- Benefícios (3–20s): 2–3 frases sobre as principais features/vantagens.
- CTA (20–30s): 1 frase final pedindo para clicar no "link na descrição".

Retorne SOMENTE um JSON válido, sem texto adicional, neste formato exato:
{{
  "script_short": "texto completo com todas as frases separadas por espaço",
  "tts_text": "mesmo texto do script_short, limpo para narração",
  "srt": "1\\n00:00:00,000 --> 00:00:03,000\\nFrase de gancho\\n\\n2\\n00:00:03,000 --> 00:00:20,000\\nFrases de benefícios\\n\\n3\\n00:00:20,000 --> 00:00:30,000\\nFrase de CTA",
  "video_prompts": [
    "close-up of {topic} on a desk, dramatic studio lighting, cinematic 4K, 0-10s hook scene",
    "{topic} in action being used, hands interacting, clean background, product showcase shot",
    "person smiling holding {topic}, thumbs up, bright lighting, call to action scene"
  ],
  "thumbnail_prompt": "texto grande em destaque + imagem do produto {topic} em fundo escuro",
  "image_queries": ["{topic} product photo", "{topic} review setup"],
  "music_style": "eletrônica leve 100–110 BPM sem vocal"
}}"""


def _extract_json(text):
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def generate_script(topic, keywords, ollama_base_url, model):
    """
    Gera roteiro via Ollama local.
    Retorna dict com campos do roteiro ou None em caso de falha.
    """
    logger.info(f"Gerando roteiro para: {topic}")

    prompt = _PROMPT_TEMPLATE.format(
        topic=topic,
        keywords=", ".join(keywords),
    )

    try:
        response = requests.post(
            f"{ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9},
            },
            timeout=120,
        )
        response.raise_for_status()

        raw = response.json().get("response", "")
        data = _extract_json(raw)

        if not data:
            logger.error(f"LLM não retornou JSON válido para '{topic}'")
            return None

        required_fields = [
            "script_short", "tts_text", "srt",
            "thumbnail_prompt", "image_queries", "music_style", "video_prompts",
        ]
        list_fields = {"image_queries", "video_prompts"}
        for field in required_fields:
            if field not in data:
                logger.warning(f"Campo ausente na resposta do LLM: {field}")
                data[field] = [] if field in list_fields else ""

        return data

    except requests.exceptions.ConnectionError:
        logger.error("Ollama não está rodando. Execute: ollama serve")
        return None
    except requests.exceptions.Timeout:
        logger.error("Timeout ao chamar Ollama. Tente um modelo menor (ex: mistral).")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao gerar roteiro: {e}")
        return None
