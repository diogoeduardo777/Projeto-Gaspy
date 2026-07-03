import re
import json
import time
import logging
import requests

logger = logging.getLogger(__name__)

_SHOPEE_IMAGE_BASE = "https://down-br.img.susercontent.com/file/"
_SHOPEE_SEARCH_V4  = "https://shopee.com.br/api/v4/search/search_items"
_SHOPEE_SEARCH_V2  = "https://shopee.com.br/api/v2/search_items/"
_SHOPEE_DETAIL_URL = "https://shopee.com.br/api/v4/item/get"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "X-API-SOURCE": "pc",
    "Connection": "keep-alive",
}

_session = None


def _get_session():
    """Retorna sessão HTTP com cookies do Shopee (visita homepage para obtê-los)."""
    global _session
    if _session is not None:
        return _session

    _session = requests.Session()
    _session.headers.update(_BROWSER_HEADERS)

    try:
        logger.info("Iniciando sessão Shopee (carregando cookies da homepage)...")
        resp = _session.get(
            "https://shopee.com.br/",
            timeout=15,
            allow_redirects=True,
        )
        logger.info(f"Shopee homepage: {resp.status_code}, cookies: {list(_session.cookies.keys())}")
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Não foi possível carregar homepage Shopee: {e}")

    return _session


def _extract_rating_count(rc):
    if isinstance(rc, list):
        return sum(rc)
    if isinstance(rc, (int, float)):
        return int(rc)
    return 0


def _price_brl(raw_price):
    if not raw_price:
        return 0.0
    return round(raw_price / 100000, 2)


def search_shopee_trending(keyword, limit=10):
    """Busca produtos em alta na Shopee com sessão autenticada via cookies."""
    sess = _get_session()

    # Tenta v4 primeiro, depois v2
    attempts = [
        (
            _SHOPEE_SEARCH_V4,
            {
                "by": "sales", "keyword": keyword, "limit": limit,
                "order": "desc", "page_type": "search",
                "scenario": "PAGE_GLOBAL_SEARCH", "version": 2,
            },
            {"Referer": f"https://shopee.com.br/search?keyword={keyword.replace(' ', '+')}&sortBy=sales"},
        ),
        (
            _SHOPEE_SEARCH_V2,
            {
                "by": "sales", "keyword": keyword, "limit": limit,
                "newest": 0, "order": "desc", "page_type": "search",
            },
            {"Referer": f"https://shopee.com.br/search?keyword={keyword.replace(' ', '+')}"},
        ),
    ]

    for url, params, extra_headers in attempts:
        try:
            resp = sess.get(url, params=params, headers=extra_headers, timeout=15)
            if resp.status_code == 403:
                logger.warning(f"Shopee {url.split('/')[-1]} bloqueado para '{keyword}'")
                continue
            resp.raise_for_status()
            data = resp.json()

            items_raw = data.get("items") or data.get("item", []) or []
            products = []
            for item in items_raw:
                info = item.get("item_basic") or item or {}
                item_id = info.get("itemid") or info.get("item_id")
                if not item_id:
                    continue
                ir = info.get("item_rating") or {}
                products.append({
                    "platform":     "shopee",
                    "item_id":      item_id,
                    "shop_id":      info.get("shopid") or info.get("shop_id"),
                    "name":         info.get("name", ""),
                    "price":        _price_brl(info.get("price")),
                    "rating":       ir.get("rating_star", 0),
                    "rating_count": _extract_rating_count(ir.get("rating_count", 0)),
                    "sold":         info.get("historical_sold", 0),
                    "image_hash":   info.get("image", ""),
                })
            if products:
                return products
        except Exception as e:
            logger.warning(f"Shopee search tentativa falhou '{keyword}': {e}")

    return []


def _validate_image_urls(urls):
    """
    Filtra a lista de imagens do products.json mantendo apenas URLs http(s)
    válidas — evita que entradas erradas quebrem o download depois.
    """
    if not isinstance(urls, list):
        return []
    valid = []
    for u in urls:
        if isinstance(u, str) and u.strip().lower().startswith(("http://", "https://")):
            valid.append(u.strip())
        elif u:
            logger.warning(f"URL de imagem inválida ignorada no products.json: {str(u)[:80]}")
    return valid


def fetch_shopee_product_detail(item_id, shop_id, max_retries=2):
    """Busca detalhes completos (imagens, categoria, descrição) de um produto Shopee."""
    sess = _get_session()
    try:
        product_referer = f"https://shopee.com.br/produto-i.{shop_id}.{item_id}"
        resp = None
        for attempt in range(max_retries):
            try:
                resp = sess.get(
                    _SHOPEE_DETAIL_URL,
                    params={"itemid": item_id, "shopid": shop_id},
                    headers={"Referer": product_referer},
                    timeout=15,
                )
                break
            except requests.RequestException as e:
                if attempt + 1 >= max_retries:
                    raise
                logger.warning(f"Shopee detail erro de rede ({item_id}): {e} — retry em 2s...")
                time.sleep(2)
        if resp.status_code == 403:
            logger.warning(f"Shopee detail bloqueado para {item_id}")
            return None
        resp.raise_for_status()
        data = resp.json().get("item") or {}
        if not data:
            return None

        ir = data.get("item_rating") or {}
        images = [
            f"{_SHOPEE_IMAGE_BASE}{h}"
            for h in (data.get("images") or [])[:6]
            if h
        ]
        categories = data.get("categories") or []
        category = categories[-1].get("display_name", "") if categories else ""

        return {
            "platform":     "shopee",
            "item_id":      data.get("itemid"),
            "shop_id":      data.get("shopid"),
            "name":         data.get("name", ""),
            "price":        _price_brl(data.get("price")),
            "price_max":    _price_brl(data.get("price_max")),
            "rating":       ir.get("rating_star", 0),
            "rating_count": _extract_rating_count(ir.get("rating_count", 0)),
            "sold":         data.get("historical_sold") or data.get("sold", 0),
            "description":  (data.get("description") or "")[:400],
            "images":       images,
            "category":     category,
        }
    except Exception as e:
        logger.error(f"Shopee detail error {item_id}: {e}")
        return None


def parse_shopee_url(url):
    """Extrai shop_id e item_id de uma URL Shopee como i.SHOPID.ITEMID."""
    m = re.search(r"-i\.(\d+)\.(\d+)", url)
    if not m:
        m = re.search(r"i\.(\d+)\.(\d+)", url)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def parse_amazon_url(url):
    """Extrai ASIN e nome de produto de uma URL Amazon (sem PA-API)."""
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if not asin_match:
        asin_match = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    if not asin_match:
        logger.warning(f"ASIN não encontrado na URL: {url}")
        return None

    asin = asin_match.group(1)
    name_match = re.search(r"amazon\.com\.br/([^/]+)/dp/", url)
    name = name_match.group(1).replace("-", " ").title() if name_match else asin

    return {
        "platform":     "amazon",
        "asin":         asin,
        "name":         name,
        "price":        0,
        "rating":       0,
        "rating_count": 0,
        "sold":         0,
        "images":       [],
        "description":  "",
        "category":     "",
    }


def load_manual_products(filepath):
    """
    Carrega produtos de um arquivo JSON manual (products.json).

    Campos obrigatórios: platform, product_url
    Campos opcionais (se ausentes, tenta buscar via API):
      name, price, rating, rating_count, sold, description, category, images, affiliate_link

    Formato mínimo:
      {"platform": "shopee", "product_url": "https://shopee.com.br/...-i.SHOP.ITEM"}
    Formato completo:
      {"platform": "shopee", "product_url": "...", "affiliate_link": "...",
       "name": "Produto X", "price": 49.90, "rating": 4.8, ...}
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            entries = json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.error(f"Erro ao ler products.json: {e}")
        return []

    products = []
    for entry in entries:
        platform  = entry.get("platform", "").lower()
        url       = entry.get("product_url", "")
        affiliate = entry.get("affiliate_link", "")

        if platform == "shopee":
            shop_id, item_id = parse_shopee_url(url)

            # Se o JSON já tem os campos principais, usa-os diretamente
            if entry.get("name"):
                product = {
                    "platform":     "shopee",
                    "item_id":      item_id,
                    "shop_id":      shop_id,
                    "name":         entry.get("name", ""),
                    "price":        float(entry.get("price", 0)),
                    "price_max":    float(entry.get("price_max", entry.get("price", 0))),
                    "rating":       float(entry.get("rating", 0)),
                    "rating_count": int(entry.get("rating_count", 0)),
                    "sold":         int(entry.get("sold", 0)),
                    "description":  entry.get("description", ""),
                    "category":     entry.get("category", ""),
                    "images":       _validate_image_urls(entry.get("images", [])),
                }
                # Tenta buscar imagens via API se não fornecidas
                if not product["images"] and shop_id and item_id:
                    detail = fetch_shopee_product_detail(item_id, shop_id)
                    if detail and detail.get("images"):
                        product["images"] = detail["images"]
            elif shop_id and item_id:
                # Sem dados manuais: busca tudo via API
                product = fetch_shopee_product_detail(item_id, shop_id)
                if not product:
                    logger.warning(f"Não foi possível obter dados do produto Shopee: {url}")
                    continue
            else:
                logger.warning(f"Não foi possível extrair IDs da URL Shopee: {url}")
                continue

            if affiliate:
                product["affiliate_override"] = affiliate
            products.append(product)
            logger.info(f"Produto Shopee carregado: {product['name'][:40]}")

        elif platform == "amazon":
            # Usa dados manuais se existirem, senão parse da URL
            if entry.get("name"):
                asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
                product = {
                    "platform":     "amazon",
                    "asin":         asin_match.group(1) if asin_match else "",
                    "name":         entry.get("name", ""),
                    "price":        float(entry.get("price", 0)),
                    "rating":       float(entry.get("rating", 0)),
                    "rating_count": int(entry.get("rating_count", 0)),
                    "sold":         int(entry.get("sold", 0)),
                    "description":  entry.get("description", ""),
                    "category":     entry.get("category", ""),
                    "images":       _validate_image_urls(entry.get("images", [])),
                }
            else:
                product = parse_amazon_url(url)
                if not product:
                    continue

            if affiliate:
                product["affiliate_override"] = affiliate
            products.append(product)
            logger.info(f"Produto Amazon carregado: {product['name'][:40]}")

    logger.info(f"products.json: {len(products)} produtos carregados")
    return products


def discover_shopee_products(keywords, max_per_keyword=5):
    """
    Descobre produtos em alta na Shopee varrendo múltiplas keywords.
    Retorna lista de produtos com detalhes completos, sem duplicatas.
    """
    seen_ids = set()
    candidates = []

    for keyword in keywords:
        results = search_shopee_trending(keyword, limit=max_per_keyword)
        for r in results:
            iid = r["item_id"]
            if iid in seen_ids:
                continue
            seen_ids.add(iid)
            detail = fetch_shopee_product_detail(iid, r["shop_id"])
            if detail and detail.get("images"):
                candidates.append(detail)
            elif r.get("image_hash"):
                r["images"] = [f"{_SHOPEE_IMAGE_BASE}{r['image_hash']}"]
                candidates.append(r)
            time.sleep(0.3)

    logger.info(f"Shopee auto-discovery: {len(candidates)} produtos encontrados")
    return candidates
