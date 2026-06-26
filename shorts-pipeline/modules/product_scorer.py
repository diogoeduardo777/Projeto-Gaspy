import logging

logger = logging.getLogger(__name__)


def score_product(product):
    """
    Calcula score de potencial viral (0-100) para um produto.

    Critérios:
      - Histórico de vendas : 30pts
      - Qualidade de avaliação: 25pts
      - Faixa de preço (impulso): 25pts
      - Imagens disponíveis   : 20pts
    """
    score = 0

    # Vendas — até 30pts
    sold = product.get("sold", 0) or 0
    if sold >= 10000:
        score += 30
    elif sold >= 5000:
        score += 25
    elif sold >= 1000:
        score += 18
    elif sold >= 500:
        score += 12
    elif sold >= 100:
        score += 6

    # Avaliação — até 25pts
    rating = product.get("rating", 0) or 0
    rc = product.get("rating_count", 0) or 0
    if rating >= 4.8 and rc >= 100:
        score += 25
    elif rating >= 4.5 and rc >= 50:
        score += 20
    elif rating >= 4.0 and rc >= 20:
        score += 14
    elif rating >= 3.5:
        score += 7

    # Preço — até 25pts (faixa de compra por impulso)
    price = product.get("price", 0) or 0
    if 15 <= price <= 100:
        score += 25
    elif 100 < price <= 250:
        score += 18
    elif 250 < price <= 500:
        score += 10
    elif price > 0:
        score += 3

    # Imagens disponíveis — até 20pts
    images = product.get("images") or []
    if len(images) >= 4:
        score += 20
    elif len(images) >= 2:
        score += 13
    elif len(images) >= 1:
        score += 6

    final = min(score, 100)
    logger.debug(f"Score [{product.get('name', '')[:40]}]: {final}/100")
    return final
