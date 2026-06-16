import re
import time
import logging
from collections import Counter

logger = logging.getLogger(__name__)


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
    try:
        from youtubesearchpython import VideosSearch
        search = VideosSearch(keyword, limit=5, language="pt", region="BR")
        return search.result().get("result", [])
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
    Retorna lista de dicts: title, slug, score, top_keywords.
    """
    logger.info("Coletando tópicos em alta...")

    trend_scores = _get_google_trends(seed_keywords)
    topics = []

    for keyword in seed_keywords:
        base_score = trend_scores.get(keyword, 30)

        yt_results = _get_youtube_results(keyword)
        time.sleep(0.5)

        yt_boost = 0
        if yt_results:
            views = _parse_view_count(
                yt_results[0].get("viewCount", {}).get("short", "0")
            )
            yt_boost = min(20, int(views / 500_000))

        top_kws = _top_keywords_from_titles(yt_results, keyword)

        topics.append({
            "title": keyword.title(),
            "slug": _slugify(keyword),
            "score": min(100, base_score + yt_boost),
            "top_keywords": top_kws,
        })

    topics.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Top tópicos: {[t['title'] for t in topics[:max_topics]]}")
    return topics[:max_topics]
