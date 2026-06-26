import json
import re
import logging
import requests

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """Você é um roteirista VIRAL de YouTube Shorts — especialista em fazer o dedo parar de rolar.
Crie um roteiro ALTAMENTE ENGAJANTE para um Short de 30 segundos sobre: "{topic}".
Nicho: {niche}. Palavras-chave: {keywords}.

ESTRUTURA OBRIGATÓRIA:
1. GANCHO VIRAL (0–3s): Frase que CHOCA ou INTRIGA. Hipérbole, situação relatable extrema, ou segredo revelado.
   Exemplos REAIS de ganchos que funcionam (adapte ao produto):
   - "Gastei R$2.000 em headset e esse de R$300 venceu no teste cego."
   - "Seis meses atrás eu não sabia que isso existia. Agora não consigo largar."
   - "Todo mundo tá comprando isso errado. Deixa eu te mostrar o correto."
   - "Isso aqui vai mudar o jeito que você [usa/joga/torce] pra sempre."
   - "Testei 7 produtos assim. Só esse sobreviveu."
2. BENEFÍCIOS COM PROVA (3–20s): 3 frases diretas com comparações e reações reais. Sem especificações inventadas.
   Use: "comparado com o anterior", "minha namorada/amigo/colega falou", "no dia a dia faz diferença".
3. CTA URGENTE (20–30s): Urgência real + prova social + "link na descrição".
   Ex: "Todo mundo que comprou voltou pra me agradecer. Link na descrição antes de acabar o estoque."

LINGUAGEM: gírias BR naturais ("cara", "mano", "galera", "pra caramba", "demais", "véi", "olha só").
Fale como quem testou de verdade, NÃO como vendedor. Varie frases curtas e longas.
O tts_text deve soar 100% natural falado em voz alta — sem emojis, sem pontuação estranha.

COMPLIANCE: não invente especificações técnicas. Benefícios gerais verificáveis apenas.

Retorne SOMENTE JSON válido, sem texto adicional:
{{
  "seo_title": "título YouTube SEO 2026 sem #Shorts — ex: 'Mouse Gamer Custo Benefício 2026: Testei e Esse SURPREENDEU'",
  "script_short": "roteiro completo com todas as frases, incluindo emojis para o texto de tela",
  "tts_text": "mesmo roteiro limpo para narração, SEM emojis, SEM markdown, fluido para TTS",
  "srt": "1\\n00:00:00,000 --> 00:00:03,000\\nGancho viral\\n\\n2\\n00:00:03,000 --> 00:00:10,000\\nBenefício 1\\n\\n3\\n00:00:10,000 --> 00:00:18,000\\nBenefício 2 e 3\\n\\n4\\n00:00:18,000 --> 00:00:25,000\\nProva social\\n\\n5\\n00:00:25,000 --> 00:00:30,000\\nCTA urgente",
  "video_prompts": [
    "extreme close-up of {topic}, dramatic studio lighting, cinematic 4K quality, dark premium background",
    "{topic} in hands being used, energetic action shot, bright vibrant colors, motion blur",
    "person reacting positively to {topic}, excited expression, clean minimal background",
    "{topic} detail shot showing premium quality, golden hour warm light, product photography",
    "side by side before after comparison, {topic} vs old product, clean white background, bold text"
  ],
  "thumbnail_prompt": "thumbnail viral: {topic} em destaque com texto impactante, fundo escuro com elementos de cor vibrante",
  "image_queries": [
    "{topic} product photo white background professional",
    "{topic} lifestyle hands-on review",
    "{topic} close up detail macro shot",
    "{topic} unboxing premium packaging",
    "{topic} action shot dynamic",
    "{topic} dark background dramatic lighting"
  ],
  "music_style": "eletrônica animada 115–125 BPM sem vocal, beat drop, energia máxima"
}}"""

_PRODUCT_VIRAL_TEMPLATE = """Você é um roteirista VIRAL de YouTube Shorts especializado em e-commerce.
Crie um roteiro ALTAMENTE ENGAJANTE para um Short de 30 segundos sobre o produto real:

Produto: {name}
Plataforma: {platform}
Preço: R$ {price}
Categoria: {category}
Avaliação: {rating}/5 ({rating_count} avaliações)
Vendas: {sold}+
Descrição do produto: {description}

ESTILO: VIRAL EXPLOSIVO — gancho que choca, números reais que impressionam, CTA urgente.

ESTRUTURA:
1. GANCHO (0–3s): Use os dados reais para chocar. Ex:
   - "Esse produto tem {sold} vendas na Shopee e eu nunca tinha ouvido falar"
   - "R$ {price} por isso? Fiquei em choque quando recebi"
   - "Todo mundo tá comprando e ninguém tá falando"
2. BENEFÍCIOS (3–20s): 3 benefícios reais e verificáveis, baseados na descrição. Sem inventar specs.
3. CTA (20–30s): Urgência + prova social + "link na descrição".

LINGUAGEM: gírias BR naturais, tom de quem testou de verdade, NÃO de vendedor.

Retorne SOMENTE JSON válido:
{{
  "seo_title": "título YouTube SEO sem #Shorts — ex: '{name} vale a pena? Testei e SURPREENDEU'",
  "script_short": "roteiro completo com emojis para texto de tela",
  "tts_text": "mesmo roteiro SEM emojis, SEM markdown, fluido para narração TTS",
  "srt": "1\\n00:00:00,000 --> 00:00:03,000\\nGancho\\n\\n2\\n00:00:03,000 --> 00:00:10,000\\nBenefício 1\\n\\n3\\n00:00:10,000 --> 00:00:18,000\\nBenefício 2 e 3\\n\\n4\\n00:00:18,000 --> 00:00:25,000\\nProva social\\n\\n5\\n00:00:25,000 --> 00:00:30,000\\nCTA urgente",
  "video_prompts": [
    "extreme close-up of {name}, dramatic studio lighting, cinematic 4K, dark premium background",
    "{name} product held in hands, energetic shot, vibrant colors, motion",
    "person reacting positively to {name}, excited expression, clean background",
    "{name} detail shot premium quality, golden hour light, product photography",
    "unboxing {name} packaging, satisfying reveal, bright clean background"
  ],
  "thumbnail_prompt": "thumbnail viral: {name} em destaque, texto impactante, fundo escuro vibrante",
  "image_queries": [
    "{name} product photo white background professional",
    "{name} lifestyle review hands-on",
    "{name} close up detail macro",
    "{name} unboxing packaging",
    "{name} in use action shot",
    "{name} dark background dramatic"
  ],
  "music_style": "eletrônica animada 115–125 BPM sem vocal, beat drop, energia máxima"
}}"""

_PRODUCT_UGC_TEMPLATE = """Você é um criador de conteúdo UGC (User Generated Content) autêntico brasileiro.
Crie um roteiro de YouTube Short de 30 segundos COMO SE FOSSE uma pessoa real
que acabou de comprar e está usando o produto:

Produto: {name}
Preço: R$ {price}
Plataforma: {platform}
Avaliação: {rating}/5 ({rating_count} avaliações)
Vendas: {sold}+
Descrição: {description}

ESTILO: UGC AUTÊNTICO — pessoa real, linguagem casual, mostrando o produto no dia a dia.
NÃO parece propaganda. Parece recomendação de amigo.

ESTRUTURA:
1. ABERTURA CASUAL (0–5s): "Olha o que chegou pra mim..." ou "Precisava te mostrar isso"
2. DEMONSTRAÇÃO (5–20s): Usando/testando o produto, reação genuína, mostra resultado real
3. RECOMENDAÇÃO (20–30s): "Valeu muito o preço, link na descrição"

LINGUAGEM: casual, gírias BR, tom de conversa, como TikTok de pessoa comum.
Mencione o preço real (R$ {price}) — preço acessível é prova social forte.

Retorne SOMENTE JSON válido:
{{
  "seo_title": "título YouTube SEO sem #Shorts — ex: 'Comprei {name} na {platform} — valeu a pena?'",
  "script_short": "roteiro completo com emojis para texto de tela",
  "tts_text": "mesmo roteiro SEM emojis, SEM markdown, fluido para narração TTS",
  "srt": "1\\n00:00:00,000 --> 00:00:05,000\\nAbertura casual\\n\\n2\\n00:00:05,000 --> 00:00:15,000\\nDemonstração\\n\\n3\\n00:00:15,000 --> 00:00:22,000\\nReação e resultado\\n\\n4\\n00:00:22,000 --> 00:00:30,000\\nRecomendação e CTA",
  "video_prompts": [
    "person unboxing {name} at home, natural light, authentic casual feel",
    "hands holding {name}, testing it, genuine reaction, warm home environment",
    "{name} in everyday use, person smiling, lifestyle shot, authentic",
    "close up {name} details, person pointing to features, casual vlog style",
    "person giving thumbs up with {name}, happy expression, natural light"
  ],
  "thumbnail_prompt": "pessoa segurando {name}, expressão surpresa positiva, fundo natural, texto 'VALE A PENA?'",
  "image_queries": [
    "{name} product review unboxing",
    "{name} in use lifestyle photo",
    "{name} hands on close up",
    "{name} everyday use home",
    "{name} user review authentic",
    "{name} product comparison"
  ],
  "music_style": "lo-fi relaxado 90 BPM, vibe casual autêntica, sem vocal"
}}"""

_REQUIRED_FIELDS = [
    "seo_title", "script_short", "tts_text", "srt",
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


def generate_product_script(product_data, style="viral", provider="ollama",
                            groq_api_key=None, groq_model=None,
                            ollama_base_url=None, ollama_model=None):
    """
    Gera roteiro focado em produto real.
    style: "viral" (gancho explosivo) ou "ugc" (pessoa autêntica usando o produto).
    """
    template = _PRODUCT_VIRAL_TEMPLATE if style == "viral" else _PRODUCT_UGC_TEMPLATE

    prompt = template.format(
        name=product_data.get("name", "produto"),
        platform=product_data.get("platform", "Shopee").capitalize(),
        price=product_data.get("price", 0),
        category=product_data.get("category", ""),
        rating=product_data.get("rating", 0),
        rating_count=product_data.get("rating_count", 0),
        sold=product_data.get("sold", 0),
        description=product_data.get("description", ""),
    )

    topic_label = f"{product_data.get('name', 'produto')} [{style}]"
    logger.info(f"Gerando roteiro de produto [{provider.upper()}]: {topic_label}")

    if provider == "groq":
        if not groq_api_key:
            logger.error("GROQ_API_KEY não configurado.")
            return None
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            completion = client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.75,
                max_tokens=1024,
            )
            raw = completion.choices[0].message.content
            data = _extract_json(raw)
            if not data:
                logger.error(f"Groq não retornou JSON válido para produto '{topic_label}'")
                return None
            return _validate_fields(data, topic_label)
        except Exception as e:
            logger.error(f"Erro Groq (produto): {e}")
            return None
    else:
        try:
            response = requests.post(
                f"{ollama_base_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.75, "top_p": 0.9},
                },
                timeout=120,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            data = _extract_json(raw)
            if not data:
                logger.error(f"Ollama não retornou JSON válido para produto '{topic_label}'")
                return None
            return _validate_fields(data, topic_label)
        except requests.exceptions.ConnectionError:
            logger.error("Ollama não está rodando. Execute: ollama serve")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao gerar roteiro de produto: {e}")
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
