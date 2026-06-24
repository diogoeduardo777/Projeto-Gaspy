import os
import urllib.parse
import logging

logger = logging.getLogger(__name__)

_AMAZON_SEARCH_URL = "https://www.amazon.com.br/s"
_SHOPEE_SEARCH_URL = "https://shopee.com.br/search"
_ML_SEARCH_URL     = "https://www.mercadolivre.com.br/jm/search"

_HASHTAGS_FIXED = "#Shorts #ProdutoNacional #ValePena #Gadgets #Review #CompraInteligente"


def generate_amazon_link(keywords, affiliate_tag):
    """
    Gera link de busca Amazon com tag de afiliado embutida.
    Cadastro: associados.amazon.com.br
    """
    if not affiliate_tag:
        logger.warning("AMAZON_AFFILIATE_TAG não configurado. Cadastre em associados.amazon.com.br")
        return None

    query = urllib.parse.quote_plus(" ".join(keywords[:3]))
    return f"{_AMAZON_SEARCH_URL}?k={query}&tag={affiliate_tag}"


def generate_shopee_link(keywords, affiliate_id):
    """
    Gera link de busca Shopee com ID de afiliado.
    Cadastro: affiliate.shopee.com.br
    """
    if not affiliate_id:
        logger.warning("SHOPEE_AFFILIATE_ID não configurado. Cadastre em affiliate.shopee.com.br")
        return None

    query = urllib.parse.quote_plus(" ".join(keywords[:3]))
    return f"{_SHOPEE_SEARCH_URL}?keyword={query}&af_id={affiliate_id}"


def generate_mercadolivre_link(keywords, affiliate_id):
    """
    Gera link de busca Mercado Livre com ID de parceiro.
    Cadastro: afiliados.mercadopago.com.br ou parceiros.mercadolivre.com.br
    Use o partner_id fornecido pelo painel de afiliados ML.
    """
    if not affiliate_id:
        logger.info("MERCADOLIVRE_AFFILIATE_ID não configurado — link ML não gerado.")
        return None

    query = urllib.parse.quote_plus(" ".join(keywords[:3]))
    return f"{_ML_SEARCH_URL}?as_word={query}&partner_id={affiliate_id}"


def generate_description(topic_title, script_short, amazon_link, shopee_link, top_keywords,
                         telegram_channel="", mercadolivre_link=None):
    """
    Gera descrição completa para o YouTube com CTA, links de afiliado e hashtags.
    Inclui disclaimer de afiliado obrigatório por lei brasileira (CDC/art. 39 CDC).
    """
    kw_hashtags = " ".join(
        f"#{kw.replace(' ', '').replace('-', '').capitalize()}" for kw in top_keywords[:6]
    )

    lines = [script_short, ""]
    lines += ["🔗 LINKS NA DESCRIÇÃO:", ""]

    if amazon_link:
        lines += [f"🛒 Amazon → {amazon_link}", ""]
    if shopee_link:
        lines += [f"🛍️ Shopee → {shopee_link}", ""]
    if mercadolivre_link:
        lines += [f"🟡 Mercado Livre → {mercadolivre_link}", ""]

    if not amazon_link and not shopee_link and not mercadolivre_link:
        lines += ["🔍 Pesquise o produto no link da bio!", ""]

    if telegram_channel:
        lines += [
            "---",
            "",
            f"📢 Mais ofertas todo dia no Telegram: {telegram_channel}",
            "Entra no canal e ativa as notificações!",
            "",
        ]

    lines += [
        "---",
        "",
        f"{kw_hashtags} {_HASHTAGS_FIXED}",
        "",
        "⚠️ Links de afiliado: posso receber comissão em compras feitas por eles, sem custo extra para você.",
    ]

    return "\n".join(lines)


def save_publish_assets(job_dir, topic_title, slug, script_short, amazon_link, shopee_link,
                        top_keywords, telegram_channel="", mercadolivre_link=None):
    """Salva description.txt e links de afiliado no diretório do job."""
    os.makedirs(job_dir, exist_ok=True)

    description = generate_description(
        topic_title, script_short, amazon_link, shopee_link, top_keywords,
        telegram_channel, mercadolivre_link,
    )

    desc_path = os.path.join(job_dir, "description.txt")
    with open(desc_path, "w", encoding="utf-8") as f:
        f.write(description)

    for fname, content in [
        ("link_amazon.txt",       amazon_link or "não configurado"),
        ("link_shopee.txt",       shopee_link or "não configurado"),
        ("link_mercadolivre.txt", mercadolivre_link or "não configurado"),
    ]:
        with open(os.path.join(job_dir, fname), "w", encoding="utf-8") as f:
            f.write(content)

    logger.info(f"Assets de publicação salvos: {job_dir}")
    return desc_path
