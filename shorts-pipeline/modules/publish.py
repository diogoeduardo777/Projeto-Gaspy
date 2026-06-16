import os
import urllib.parse
import logging

logger = logging.getLogger(__name__)

_AMAZON_SEARCH_URL = "https://www.amazon.com.br/s"
_SHOPEE_SEARCH_URL = "https://shopee.com.br/search"


def generate_amazon_link(keywords, affiliate_tag):
    """
    Gera link de busca Amazon com tag de afiliado embutida.
    Qualquer compra feita nos 30 dias seguintes gera comissão.

    Exemplo de saída:
      https://www.amazon.com.br/s?k=mouse+gamer&tag=seunome-20
    """
    if not affiliate_tag:
        logger.warning(
            "AMAZON_AFFILIATE_TAG não configurado. "
            "Cadastre-se em associados.amazon.com.br e adicione ao .env"
        )
        return None

    query = urllib.parse.quote_plus(" ".join(keywords[:3]))
    return f"{_AMAZON_SEARCH_URL}?k={query}&tag={affiliate_tag}"


def generate_shopee_link(keywords, affiliate_id):
    """
    Gera link de busca Shopee com ID de afiliado.
    Cadastro gratuito em affiliate.shopee.com.br.

    Exemplo de saída:
      https://shopee.com.br/search?keyword=mouse+gamer&af_id=seuid
    """
    if not affiliate_id:
        logger.warning(
            "SHOPEE_AFFILIATE_ID não configurado. "
            "Cadastre-se em affiliate.shopee.com.br e adicione ao .env"
        )
        return None

    query = urllib.parse.quote_plus(" ".join(keywords[:3]))
    return f"{_SHOPEE_SEARCH_URL}?keyword={query}&af_id={affiliate_id}"


def generate_description(topic_title, script_short, amazon_link, shopee_link, top_keywords, telegram_channel=""):
    """
    Gera texto de descrição para o YouTube com CTA e hashtags.
    Inclui disclaimer de afiliado obrigatório por lei brasileira (CDC).
    """
    hashtags = " ".join(
        f"#{kw.replace(' ', '').replace('-', '')}" for kw in top_keywords[:5]
    )

    lines = [script_short, ""]

    if amazon_link:
        lines += [f"Amazon: {amazon_link}", ""]
    if shopee_link:
        lines += [f"Shopee: {shopee_link}", ""]
    if not amazon_link and not shopee_link:
        lines += ["Pesquise o produto no link da bio!", ""]

    if telegram_channel:
        lines += [
            "---",
            "",
            f"📢 Ofertas diárias no Telegram: {telegram_channel}",
            "",
        ]

    lines += [
        "---",
        "",
        f"{hashtags} #Shorts #Tech #Gadgets",
        "",
        "* Links de afiliado: posso receber comissão em compras feitas por eles, sem custo adicional para você.",
    ]

    return "\n".join(lines)


def save_publish_assets(job_dir, topic_title, slug, script_short, amazon_link, shopee_link, top_keywords, telegram_channel=""):
    """
    Salva description.txt e affiliate_link.txt no diretório do job.
    Retorna (desc_path, link_path).
    """
    os.makedirs(job_dir, exist_ok=True)

    description = generate_description(topic_title, script_short, amazon_link, shopee_link, top_keywords, telegram_channel)

    desc_path   = os.path.join(job_dir, "description.txt")
    amazon_path = os.path.join(job_dir, "link_amazon.txt")
    shopee_path = os.path.join(job_dir, "link_shopee.txt")

    with open(desc_path, "w", encoding="utf-8") as f:
        f.write(description)

    with open(amazon_path, "w", encoding="utf-8") as f:
        f.write(amazon_link or "não configurado")

    with open(shopee_path, "w", encoding="utf-8") as f:
        f.write(shopee_link or "não configurado")

    logger.info(f"Assets de publicação salvos: {job_dir}")
    return desc_path, amazon_path, shopee_path
