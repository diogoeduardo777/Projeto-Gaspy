import logging
import sys
import os
import schedule
import time
from datetime import datetime

import config
from modules.deals import (
    get_next_keyword,
    get_next_digital_product,
    peek_post_type,
    build_affiliate_links,
    build_open_links,
)
from modules.amazon_rss import get_next_rss_product
from modules.message import generate_deal_message, generate_digital_message, generate_rss_message
from modules.poster import build_full_message, send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.DATA_DIR, "bot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

os.makedirs(config.DATA_DIR, exist_ok=True)


def post_deal():
    logger.info(f"=== Postando oferta ({datetime.now().strftime('%H:%M')}) ===")

    has_digital = bool(config.DIGITAL_PRODUCTS)
    has_rss     = bool(config.AMAZON_AFFILIATE_TAG)  # RSS só faz sentido com tag configurada
    post_type   = peek_post_type(config.STATE_FILE, has_digital, has_rss)

    logger.info(f"Tipo de postagem: {post_type}")

    # Links abertos Amazon/Shopee — presentes em TODAS as postagens
    open_amazon, open_shopee = build_open_links(
        config.AMAZON_AFFILIATE_TAG,
        config.SHOPEE_AFFILIATE_ID,
    )

    if post_type == "rss":
        _post_rss(open_shopee)
    elif post_type == "digital":
        _post_digital(open_amazon, open_shopee)
    else:
        _post_physical(open_amazon, open_shopee)


def _post_rss(open_shopee):
    """Postagem de produto real do Amazon RSS Bestsellers."""
    product = get_next_rss_product(
        config.ACTIVE_NICHE,
        config.AMAZON_AFFILIATE_TAG,
        config.STATE_FILE,
    )

    if not product:
        logger.warning("RSS falhou, caindo para postagem física.")
        open_amazon, open_shopee2 = build_open_links(config.AMAZON_AFFILIATE_TAG, config.SHOPEE_AFFILIATE_ID)
        _post_physical(open_amazon, open_shopee2)
        return

    deal_text = generate_rss_message(
        product["name"],
        price=product.get("price"),
        groq_api_key=config.GROQ_API_KEY,
        groq_model=config.GROQ_MODEL,
    )

    full_text = build_full_message(
        deal_text,
        amazon_url=product["url"],   # link direto do produto com tag
        shopee_url=open_shopee,      # busca aberta Shopee
        price=product.get("price"),
    )

    ok = send_message(
        config.TELEGRAM_BOT_TOKEN,
        config.TELEGRAM_CHANNEL_ID,
        full_text,
        disable_web_page_preview=True,
    )

    if ok:
        logger.info(f"RSS enviado: '{product['name']}'")
    else:
        logger.error(f"Falha ao enviar RSS: '{product['name']}'")


def _post_physical(open_amazon, open_shopee):
    """Postagem de produto físico com busca por keyword na Amazon e Shopee."""
    keyword = get_next_keyword(config.DEAL_KEYWORDS, config.STATE_FILE)
    if not keyword:
        logger.error("Nenhum keyword configurado em DEAL_KEYWORDS.")
        return

    deal_text = generate_deal_message(
        keyword,
        niche=config.ACTIVE_NICHE,
        groq_api_key=config.GROQ_API_KEY,
        groq_model=config.GROQ_MODEL,
    )

    keyword_amazon, keyword_shopee = build_affiliate_links(
        keyword,
        amazon_tag=config.AMAZON_AFFILIATE_TAG,
        shopee_id=config.SHOPEE_AFFILIATE_ID,
    )

    full_text = build_full_message(deal_text, keyword_amazon, keyword_shopee)
    ok = send_message(
        config.TELEGRAM_BOT_TOKEN,
        config.TELEGRAM_CHANNEL_ID,
        full_text,
        disable_web_page_preview=True,
    )

    if ok:
        logger.info(f"Físico enviado: '{keyword}'")
    else:
        logger.error(f"Falha ao enviar físico: '{keyword}'")


def _post_digital(open_amazon, open_shopee):
    """Postagem de produto digital com link Hotmart + links abertos Amazon/Shopee."""
    product = get_next_digital_product(config.DIGITAL_PRODUCTS, config.STATE_FILE)
    if not product:
        logger.warning("Sem produtos digitais. Usando postagem física.")
        _post_physical(open_amazon, open_shopee)
        return

    deal_text = generate_digital_message(
        product["name"],
        category=product.get("category", "geral"),
        groq_api_key=config.GROQ_API_KEY,
        groq_model=config.GROQ_MODEL,
    )

    full_text = build_full_message(
        deal_text,
        amazon_url=open_amazon,
        shopee_url=open_shopee,
        hotmart_url=product["link"],
    )

    ok = send_message(
        config.TELEGRAM_BOT_TOKEN,
        config.TELEGRAM_CHANNEL_ID,
        full_text,
        disable_web_page_preview=True,
    )

    if ok:
        logger.info(f"Digital enviado: '{product['name']}'")
    else:
        logger.error(f"Falha ao enviar digital: '{product['name']}'")


def main():
    # --now posta imediatamente e sai
    if "--now" in sys.argv:
        logger.info("Modo --now: postando agora e saindo.")
        post_deal()
        return

    # Modo agendado
    logger.info(f"Bot iniciado. Postagens agendadas para: {config.POST_HOURS}h")
    logger.info(f"Produtos digitais: {len(config.DIGITAL_PRODUCTS)} | RSS Amazon: {'ativo' if config.AMAZON_AFFILIATE_TAG else 'inativo (sem tag)'}")

    for hour in config.POST_HOURS:
        schedule.every().day.at(f"{hour:02d}:00").do(post_deal)

    logger.info("Aguardando agendamento... (Ctrl+C para parar)")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
