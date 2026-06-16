import json
import os
import logging

logger = logging.getLogger(__name__)


def _load_state(state_file):
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"index": 0, "total_posted": 0}


def _save_state(state_file, state):
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_next_keyword(keywords, state_file):
    """Retorna próximo keyword em rotação e avança o índice."""
    if not keywords:
        return None

    state = _load_state(state_file)
    idx     = state.get("index", 0) % len(keywords)
    keyword = keywords[idx]

    state["index"]        = (idx + 1) % len(keywords)
    state["total_posted"] = state.get("total_posted", 0) + 1
    _save_state(state_file, state)

    logger.info(f"Keyword selecionada: '{keyword}' (índice {idx}, total postado: {state['total_posted']})")
    return keyword


def get_next_digital_product(products, state_file):
    """Retorna próximo produto digital em rotação. Retorna None se lista vazia."""
    if not products:
        return None

    state = _load_state(state_file)
    idx     = state.get("digital_index", 0) % len(products)
    product = products[idx]

    state["digital_index"] = (idx + 1) % len(products)
    state["total_posted"]  = state.get("total_posted", 0) + 1
    _save_state(state_file, state)

    logger.info(f"Produto digital selecionado: '{product['name']}' (índice {idx})")
    return product


def peek_post_type(state_file, has_digital, has_rss):
    """Determina tipo da próxima postagem sem alterar o estado.

    Rotação com os 3 tipos ativos: rss → physical → digital → rss → ...
    Adapta automaticamente se digital ou rss não estiverem configurados.
    """
    state = _load_state(state_file)
    total = state.get("total_posted", 0)

    if has_rss and has_digital:
        return ["rss", "physical", "digital"][total % 3]
    if has_rss:
        return "rss" if total % 2 == 0 else "physical"
    if has_digital:
        return "digital" if total % 2 == 1 else "physical"
    return "physical"


def build_affiliate_links(keyword, amazon_tag, shopee_id):
    """Gera URLs de busca com tag de afiliado para Amazon e Shopee."""
    query = keyword.replace(" ", "+")

    amazon_url = ""
    if amazon_tag:
        amazon_url = f"https://www.amazon.com.br/s?k={query}&tag={amazon_tag}"

    shopee_url = ""
    if shopee_id:
        shopee_url = f"https://shopee.com.br/search?keyword={query}&af_id={shopee_id}"

    return amazon_url, shopee_url


def build_open_links(amazon_tag, shopee_id):
    """Gera links de busca genérica (sem keyword) para Amazon e Shopee."""
    amazon_url = f"https://www.amazon.com.br/?tag={amazon_tag}" if amazon_tag else ""
    shopee_url = f"https://shopee.com.br/?af_id={shopee_id}" if shopee_id else ""
    return amazon_url, shopee_url
