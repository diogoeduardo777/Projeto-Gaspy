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
    "close-up of {topic} on a desk, dramatic studio lighting, cinematic 4K, hook scene",
    "{topic} in action being used, hands interacting, clean background, product showcase",
    "person smiling holding {topic}, bright lighting, thumbs up, call to action scene"
  ],
  "thumbnail_prompt": "texto grande em destaque + imagem do produto {topic} em fundo escuro",
  "image_queries": ["{topic} product photo", "{topic} review setup"],
  "music_style": "eletrônica leve 100–110 BPM sem vocal"
}}"""

_REQUIRED_FIELDS = [
    "script_short", "tts_text", "srt",
    "thumbnail_prompt", "image_queries", "music_style", "video_prompts",
]
_LIST_FIELDS = {"image_queries", "video_prompts"}


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


def _validate_fields(data, topic):
    for field in _REQUIRED_FIELDS:
        if field not in data:
            logger.warning(f"Campo ausente na resposta do LLM: {field}")
            data[field] = [] if field in _LIST_FIELDS else ""
    return data


def _generate_groq(topic, keywords, api_key, model):
    """Gera roteiro via Groq API (Llama 3.3 70B na nuvem, grátis)."""
    try:
        from groq import Groq
    except ImportError:
        logger.error("groq não instalado. Execute: pip install groq")
        return None

    if not api_key:
        logger.error("GROQ_API_KEY não configurado. Cadastre-se em console.groq.com")
        return None

    prompt = _PROMPT_TEMPLATE.format(topic=topic, keywords=", ".join(keywords))

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )
        raw = completion.choices[0].message.content
        data = _extract_json(raw)

        if not data:
            logger.error(f"Groq não retornou JSON válido para '{topic}'")
            return None

        return _validate_fields(data, topic)

    except Exception as e:
        logger.error(f"Erro ao chamar Groq API: {e}")
        return None


def _generate_ollama(topic, keywords, base_url, model):
    """Gera roteiro via Ollama local."""
    prompt = _PROMPT_TEMPLATE.format(topic=topic, keywords=", ".join(keywords))

    try:
        response = requests.post(
            f"{base_url}/api/generate",
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
            logger.error(f"Ollama não retornou JSON válido para '{topic}'")
            return None

        return _validate_fields(data, topic)

    except requests.exceptions.ConnectionError:
        logger.error("Ollama não está rodando. Execute: ollama serve")
        return None
    except requests.exceptions.Timeout:
        logger.error("Timeout ao chamar Ollama. Tente um modelo menor (ex: mistral).")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao gerar roteiro: {e}")
        return None


def generate_script(topic, keywords, provider="ollama",
                    groq_api_key=None, groq_model=None,
                    ollama_base_url=None, ollama_model=None):
    """
    Gera roteiro via Groq (nuvem, recomendado) ou Ollama (local).
    Controlado por LLM_PROVIDER no .env.
    """
    logger.info(f"Gerando roteiro [{provider.upper()}]: {topic}")

    if provider == "groq":
        return _generate_groq(topic, keywords, groq_api_key, groq_model)
    else:
        return _generate_ollama(topic, keywords, ollama_base_url, ollama_model)
