import logging
import requests

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def send_message(bot_token, channel_id, text, disable_web_page_preview=False):
    """Envia mensagem de texto para o canal Telegram. Retorna True se ok."""
    if not bot_token or not channel_id:
        logger.error("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHANNEL_ID não configurados.")
        return False

    url     = _TELEGRAM_API.format(token=bot_token, method="sendMessage")
    payload = {
        "chat_id":    channel_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            msg_id = data["result"]["message_id"]
            logger.info(f"Mensagem enviada ao Telegram (id={msg_id})")
            return True
        else:
            logger.error(f"Telegram API erro: {data.get('description')}")
            return False
    except requests.RequestException as e:
        logger.error(f"Erro de rede ao enviar para Telegram: {e}")
        return False


def build_full_message(deal_text, amazon_url, shopee_url, hotmart_url=None, price=None):
    """Monta a mensagem final com links de afiliado.

    - hotmart_url: produto digital em destaque + links abertos Amazon/Shopee embaixo
    - price: exibe preço logo após o texto (para produtos RSS)
    - Sem hotmart_url: links diretos Amazon/Shopee
    """
    lines = [deal_text]

    if price:
        lines.append(f"💰 <b>{price}</b>")

    lines.append("")

    if hotmart_url:
        lines.append(f"🎓 <b>Acessar produto:</b> {hotmart_url}")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🛍️ <b>Aproveite e explore ofertas:</b>")

    if amazon_url:
        lines.append(f"🛒 <b>Amazon:</b> {amazon_url}")
    if shopee_url:
        lines.append(f"🏪 <b>Shopee:</b> {shopee_url}")

    if amazon_url or shopee_url or hotmart_url:
        lines.append("")
        lines.append("⚠️ <i>Links de afiliado — comprar por eles apoia o canal sem custo extra para você.</i>")

    return "\n".join(lines)
