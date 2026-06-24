import re
import time
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# Palavras que indicam intenção comercial — aumentam o score do tópico
_COMMERCIAL_SIGNALS = [
    "melhor", "vale a pena", "onde comprar", "review", "barato",
    "custo beneficio", "qual comprar", "comparativo", "top", "recomendo",
]
_COMMERCIAL_BOOST = 15  # pontos extras por sinal comercial detectado


def _commercial_intent_boost(keyword):
    """Retorna boost de score se o keyword tem intenção de compra."""
    kw_lower = keyword.lower()
    for signal in _COMMERCIAL_SIGNALS:
        if signal in kw_lower:
            return _COMMERCIAL_BOOST
    return 0


def _expand_with_commercial_keywords(seed_keywords):
    """
    Expande cada seed keyword com variações comerciais para capturar
    tópicos de alta intenção de compra além dos genéricos.
    """
    expanded = list(seed_keywords)
    commercial_prefixes = ["melhor", "review", "vale a pena"]
    for kw in seed_keywords[:3]:  # limita para não explodir a lista
        for prefix in commercial_prefixes:
            expanded.append(f"{prefix} {kw}")
    return expanded[:10]  # pytrends aceita no máximo 5, YouTube aceita mais


def _score_from_values(values):
    if not values:
        return 0
    recent = values[-3:]
    return min(100, int(sum(recent) / len(recent)))


def _get_google_trends(keywords, geo="BR"):
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="pt-BR", tz=-180)
        pytrends.build_payload(keywords[:5], timeframe="now 7-d", geo=geo)
        df = pytrends.interest_over_time()
        if df.empty:
            return {}
        return {kw: _score_from_values(df[kw].tolist()) for kw in keywords[:5] if kw in df.columns}
    except Exception as e:
        logger.warning(f"Google Trends indisponível: {e}")
        return {}


def _get_youtube_results(keyword):
    """
    Busca vídeos no YouTube via requests (sem httpx).
    Extrai títulos e contagem de views do ytInitialData.
    """
    try:
        import json as _json
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        resp = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": keyword},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()

        # Extrai ytInitialData embutido na página
        match = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", resp.text, re.DOTALL)
        if not match:
            return []

        data = _json.loads(match.group(1))
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        results = []
        for section in contents:
            for item in section.get("itemSectionRenderer", {}).get("contents", []):
                vr = item.get("videoRenderer", {})
                if not vr:
                    continue
                title = "".join(
                    r.get("text", "") for r in vr.get("title", {}).get("runs", [])
                )
                view_text = (
                    vr.get("viewCountText", {}).get("simpleText", "0")
                    or vr.get("viewCountText", {}).get("runs", [{}])[0].get("text", "0")
                )
                results.append({"title": title, "viewCount": {"short": view_text}})
                if len(results) >= 5:
                    break
            if len(results) >= 5:
                break

        return results

    except Exception as e:
        logger.warning(f"YouTube search falhou para '{keyword}': {e}")
        return []


def _parse_view_count(text):
    try:
        text = text.upper().replace(",", ".")
        if "M" in text:
            return float(text.replace("M", "").strip()) * 1_000_000
        if "K" in text:
            return float(text.replace("K", "").strip()) * 1_000
        return float(re.sub(r"[^\d.]", "", text) or 0)
    except Exception:
        return 0


def _top_keywords_from_titles(videos, fallback):
    stopwords = {
        "o", "a", "os", "as", "de", "da", "do", "em", "e", "para",
        "com", "um", "uma", "no", "na", "por", "que", "ao", "se",
    }
    words = []
    for v in videos[:3]:
        title = v.get("title", "")
        extracted = re.findall(r"\b[a-zA-ZÀ-ÿ]{3,}\b", title.lower())
        words.extend(w for w in extracted if w not in stopwords)
    top = [kw for kw, _ in Counter(words).most_common(3)]
    return top if top else fallback.split()[:3]


def _slugify(text):
    replacements = {
        "ê": "e", "â": "a", "ã": "a", "ç": "c", "é": "e",
        "ó": "o", "ú": "u", "á": "a", "í": "i", "õ": "o",
    }
    s = text.lower()
    for char, rep in replacements.items():
        s = s.replace(char, rep)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def collect_topics(seed_keywords, max_topics=5):
    """
    Coleta tópicos em alta via Google Trends + YouTube.
    Aplica boost de intenção comercial no score.
    Retorna lista de dicts: title, slug, score, top_keywords.
    """
    logger.info("Coletando tópicos em alta...")

    # Expande com variações comerciais para enriquecer a busca
    expanded = _expand_with_commercial_keywords(seed_keywords)

    trend_scores = _get_google_trends(seed_keywords)  # pytrends usa só os originais
    topics = []
    seen_slugs = set()

    for keyword in expanded:
        slug = _slugify(keyword)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Score base do Google Trends (usa keyword original se disponível)
        base_kw    = next((k for k in seed_keywords if k in keyword), keyword)
        base_score = trend_scores.get(base_kw, 30)

        yt_results = _get_youtube_results(keyword)
        time.sleep(0.5)

        yt_boost = 0
        if yt_results:
            views = _parse_view_count(
                yt_results[0].get("viewCount", {}).get("short", "0")
            )
            yt_boost = min(20, int(views / 500_000))

        # Boost por intenção comercial detectada na keyword
        intent_boost = _commercial_intent_boost(keyword)

        top_kws = _top_keywords_from_titles(yt_results, keyword)

        final_score = min(100, base_score + yt_boost + intent_boost)

        topics.append({
            "title":        keyword.title(),
            "slug":         slug,
            "score":        final_score,
            "top_keywords": top_kws,
            "has_commercial_intent": intent_boost > 0,
        })

    topics.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Top tópicos: {[(t['title'], t['score']) for t in topics[:max_topics]]}")
    return topics[:max_topics]
