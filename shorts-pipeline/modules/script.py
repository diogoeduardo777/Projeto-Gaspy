import json
import re
import logging
import requests

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """Você é um roteirista criativo de YouTube Shorts com estilo bem-humorado e linguagem jovem PT-BR.
Crie um roteiro ENGAJANTE e ENGRAÇADO para um Short de 30 segundos sobre: "{topic}".
Nicho: {niche}. Palavras-chave: {keywords}.

REGRAS DE OURO:
1. Gancho (0–3s): situação relatable, hipérbole leve ou pergunta provocativa. Deve fazer o espectador parar de rolar o feed.
   Exemplos de estilo (adapte para o produto):
   - "Minha mão recusou usar outro mouse depois desse."
   - "Eu testei e minha torcida nunca mais foi igual."
   - "Você tá perdendo dinheiro se ainda não tem isso."
2. Benefícios (3–20s): 2–3 frases diretas, empolgadas, linguagem de quem usa no dia a dia. PROIBIDO inventar especificações técnicas exatas — mencione apenas benefícios gerais verificáveis (ex: "som incrível", "bateria dura o dia todo", "leve pra caramba").
3. CTA (20–30s): urgência leve + "link na descrição". Ex: "Corre lá, tá baratinho agora."

COMPLIANCE OBRIGATÓRIO: não afirme nada que não possa ser verificado. Sem especificações inventadas.

Retorne SOMENTE um JSON válido, sem texto adicional, neste formato exato:
{{
  "script_short": "texto completo do roteiro com todas as frases",
  "tts_text": "mesmo texto limpo para narração em voz alta, sem emojis",
  "srt": "1\\n00:00:00,000 --> 00:00:03,000\\nFrase gancho\\n\\n2\\n00:00:03,000 --> 00:00:20,000\\nFrases benefícios\\n\\n3\\n00:00:20,000 --> 00:00:30,000\\nFrase CTA",
  "video_prompts": [
    "close-up of {topic} with dramatic lighting, cinematic 4K, exciting hook scene",
    "{topic} being used in action, energetic movement, clean colorful background",
    "happy person giving thumbs up with {topic}, bright studio, call to action vibe"
  ],
  "thumbnail_prompt": "thumbnail impactante: texto grande e legível + {topic} em destaque, fundo escuro ou vibrante",
  "image_queries": ["{topic} product photo white background", "{topic} lifestyle action"],
  "music_style": "eletrônica animada 110–125 BPM sem vocal, energia alta"
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


def _generate_groq(topic, keywords, api_key, model, niche="tecnologia"):
    """Gera roteiro via Groq API (Llama 3.3 70B na nuvem, grátis)."""
    try:
        from groq import Groq
    except ImportError:
        logger.error("groq não instalado. Execute: pip install groq")
        return None

    if not api_key:
        logger.error("GROQ_API_KEY não configurado. Cadastre-se em console.groq.com")
        return None

    prompt = _PROMPT_TEMPLATE.format(topic=topic, keywords=", ".join(keywords), niche=niche)

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


def _generate_ollama(topic, keywords, base_url, model, niche="tecnologia"):
    """Gera roteiro via Ollama local."""
    prompt = _PROMPT_TEMPLATE.format(topic=topic, keywords=", ".join(keywords), niche=niche)

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
                    ollama_base_url=None, ollama_model=None,
                    niche="tecnologia"):
    """
    Gera roteiro via Groq (nuvem, recomendado) ou Ollama (local).
    Controlado por LLM_PROVIDER no .env.
    """
    logger.info(f"Gerando roteiro [{provider.upper()}]: {topic}")

    if provider == "groq":
        return _generate_groq(topic, keywords, groq_api_key, groq_model, niche)
    else:
        return _generate_ollama(topic, keywords, ollama_base_url, ollama_model, niche)
