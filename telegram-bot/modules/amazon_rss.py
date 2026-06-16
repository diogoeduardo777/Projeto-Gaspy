import re
import json
import os
import logging
import requests
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Feeds RSS públicos da Amazon BR por categoria
_FEEDS_TECH = [
    "https://www.amazon.com.br/gp/rss/bestsellers/electronics/",
    "https://www.amazon.com.br/gp/rss/bestsellers/computers/",
    "https://www.amazon.com.br/gp/rss/bestsellers/videogames/",
]
_FEEDS_SPORTS = [
    "https://www.amazon.com.br/gp/rss/bestsellers/sporting-goods/",
]
_FEEDS_BY_NICHE = {
    "tech":   _FEEDS_TECH,
    "sports": _FEEDS_SPORTS,
    "both":   _FEEDS_TECH[:2] + _FEEDS_SPORTS,
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _extract_asin(url):
    match = re.search(r"/dp/([A-Z0-9]{10})", url)
    return match.group(1) if match else None


def _extract_price(html):
    match = re.search(r"R\$\s*([\d.,]+)", html or "")
    return f"R$ {match.group(1)}" if match else None


def _clean_title(raw):
    # Remove prefixo de ranking "#1 em Eletrônicos - "
    raw = re.sub(r"^#\d+\s+(?:em|in)\s+[^-]+-\s*", "", raw).strip()
    return raw[:80] + "..." if len(raw) > 80 else raw


def fetch_bestsellers(niche, affiliate_tag, limit=15):
    """Busca bestsellers do RSS da Amazon BR. Retorna lista de dicts."""
    feeds    = _FEEDS_BY_NICHE.get(niche, _FEEDS_TECH)
    products = []

    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"RSS {resp.status_code}: {feed_url}")
                continue

            root    = ET.fromstring(resp.content)
            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el  = item.find("link")
                desc_el  = item.find("description")

                if title_el is None or link_el is None:
                    continue

                raw_link = (link_el.text or "").strip()
                asin     = _extract_asin(raw_link)
                if not asin:
                    continue

                aff_url = (
                    f"https://www.amazon.com.br/dp/{asin}?tag={affiliate_tag}"
                    if affiliate_tag
                    else raw_link
                )

                products.append({
                    "name":  _clean_title((title_el.text or "").strip()),
                    "url":   aff_url,
                    "asin":  asin,
                    "price": _extract_price(desc_el.text if desc_el is not None else ""),
                })

                if len(products) >= limit:
                    break

        except ET.ParseError as e:
            logger.error(f"Erro ao parsear RSS {feed_url}: {e}")
        except requests.RequestException as e:
            logger.error(f"Erro de rede {feed_url}: {e}")

        if len(products) >= limit:
            break

    logger.info(f"Amazon RSS: {len(products)} produtos encontrados")
    return products


def get_next_rss_product(niche, affiliate_tag, state_file):
    """Busca bestsellers e retorna próximo produto em rotação circular."""
    products = fetch_bestsellers(niche, affiliate_tag)
    if not products:
        logger.warning("Amazon RSS: nenhum produto obtido.")
        return None

    # Carrega estado
    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

    idx     = state.get("rss_index", 0) % len(products)
    product = products[idx]

    state["rss_index"]    = (idx + 1) % len(products)
    state["total_posted"] = state.get("total_posted", 0) + 1

    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    logger.info(f"RSS produto [{idx}]: '{product['name']}'")
    return product
