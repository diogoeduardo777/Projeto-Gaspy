import logging
from groq import Groq

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """Você é um assistente de marketing de afiliados brasileiro.
Crie uma mensagem curta e atraente para um canal de Telegram de ofertas de {niche}.

Produto/tema: {keyword}

Regras:
- Máximo 5 linhas de texto
- Tom animado e informal, como se fosse uma dica de amigo
- Inclua 1 ou 2 emojis relevantes
- Termine com uma chamada para ação (ex: "Veja o link abaixo 👇")
- NÃO invente preços ou especificações técnicas exatas
- NÃO use hashtags em excesso (máximo 2)
- O texto deve parecer natural, não robótico

Retorne APENAS o texto da mensagem, sem introdução nem explicação."""


def generate_deal_message(keyword, niche, groq_api_key, groq_model):
    """Gera mensagem de oferta via Groq. Retorna string ou None."""
    if not groq_api_key:
        logger.warning("GROQ_API_KEY não configurada. Usando mensagem padrão.")
        return _default_message(keyword)

    try:
        client   = Groq(api_key=groq_api_key)
        prompt   = _PROMPT_TEMPLATE.format(keyword=keyword, niche=niche)
        response = client.chat.completions.create(
            model=groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        logger.info(f"Mensagem gerada via Groq para '{keyword}'")
        return text
    except Exception as e:
        logger.error(f"Erro ao gerar mensagem Groq: {e}")
        return _default_message(keyword)


def generate_rss_message(product_name, price, groq_api_key, groq_model):
    """Gera mensagem de oferta para produto real do RSS da Amazon."""
    if not groq_api_key:
        return _default_rss_message(product_name, price)

    price_info = f"Preço atual: {price}" if price else "Preço: confira no link"
    prompt = (
        f"Você é um afiliado brasileiro criando uma mensagem para canal de ofertas no Telegram.\n"
        f"Produto real da Amazon: {product_name}\n"
        f"{price_info}\n\n"
        f"Regras:\n"
        f"- Máximo 4 linhas\n"
        f"- Tom animado e informal, como se fosse uma dica de amigo\n"
        f"- Destaque o produto e chame para ver o preço\n"
        f"- Inclua 1 ou 2 emojis relevantes\n"
        f"- Termine com: 'Veja o link abaixo 👇'\n"
        f"- NÃO invente especificações ou preços diferentes dos informados\n"
        f"- NÃO use hashtags em excesso (máximo 2)\n\n"
        f"Retorne APENAS o texto da mensagem."
    )

    try:
        client   = Groq(api_key=groq_api_key)
        response = client.chat.completions.create(
            model=groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.75,
            max_tokens=250,
        )
        text = response.choices[0].message.content.strip()
        logger.info(f"Mensagem RSS gerada via Groq para '{product_name}'")
        return text
    except Exception as e:
        logger.error(f"Erro ao gerar mensagem RSS Groq: {e}")
        return _default_rss_message(product_name, price)


def _default_rss_message(product_name, price):
    price_str = f" por {price}" if price else ""
    return (
        f"🔥 Em alta na Amazon agora!\n"
        f"📦 {product_name}{price_str}\n"
        f"Veja o link abaixo 👇"
    )


def generate_digital_message(product_name, category, groq_api_key, groq_model):
    """Gera mensagem para produto digital via Groq. Retorna string."""
    if not groq_api_key:
        return _default_digital_message(product_name)

    prompt = (
        f"Você é um afiliado digital brasileiro criando uma mensagem para Telegram.\n"
        f"Produto: {product_name} (categoria: {category})\n\n"
        f"Regras:\n"
        f"- Máximo 5 linhas\n"
        f"- Tom animado e informal, como dica de amigo\n"
        f"- Destaque o benefício principal que o produto entrega\n"
        f"- Inclua 1 ou 2 emojis relevantes\n"
        f"- Termine com: 'Acesse o link abaixo 👇'\n"
        f"- NÃO invente preços ou garantias falsas\n"
        f"- NÃO use hashtags em excesso (máximo 2)\n\n"
        f"Retorne APENAS o texto da mensagem."
    )

    try:
        client   = Groq(api_key=groq_api_key)
        response = client.chat.completions.create(
            model=groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        logger.info(f"Mensagem digital gerada via Groq para '{product_name}'")
        return text
    except Exception as e:
        logger.error(f"Erro ao gerar mensagem digital Groq: {e}")
        return _default_digital_message(product_name)


def _default_message(keyword):
    return (
        f"🔥 Oferta imperdível: {keyword}!\n"
        f"Encontrei opções incríveis pra você.\n"
        f"Veja o link abaixo 👇"
    )


def _default_digital_message(product_name):
    return (
        f"📚 Já ouviu falar de {product_name}?\n"
        f"Produto digital com ótima avaliação!\n"
        f"Acesse o link abaixo 👇"
    )
