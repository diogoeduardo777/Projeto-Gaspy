import os
from dotenv import load_dotenv

load_dotenv()

# LLM — provider: "groq" (recomendado, grátis) ou "ollama" (local)
LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "ollama")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL      = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Ollama (LLM local — usado se LLM_PROVIDER=ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.1")

# YouTube auto-upload
YOUTUBE_AUTO_UPLOAD      = os.getenv("YOUTUBE_AUTO_UPLOAD", "false").lower() == "true"
YOUTUBE_CREDENTIALS_FILE = os.getenv("YOUTUBE_CREDENTIALS_FILE", "client_secrets.json")
YOUTUBE_TOKEN_FILE       = os.getenv("YOUTUBE_TOKEN_FILE", "token.json")
YOUTUBE_PRIVACY          = os.getenv("YOUTUBE_PRIVACY", "private")

# Unsplash (imagens royalty-free)
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

# Afiliados
AMAZON_AFFILIATE_TAG       = os.getenv("AMAZON_AFFILIATE_TAG", "")
SHOPEE_AFFILIATE_ID        = os.getenv("SHOPEE_AFFILIATE_ID", "")
MERCADOLIVRE_AFFILIATE_ID  = os.getenv("MERCADOLIVRE_AFFILIATE_ID", "")

# Telegram — link do canal para divulgar nos Shorts (ex: https://t.me/seucanal)
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "")

# Kling AI (geração de vídeo por IA)
KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY", "")
KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY", "")

# Pipeline
MAX_VIDEOS = 3
MAX_TOPICS = 5

# Nicho ativo: "tech", "sports" ou "both"
# "both" mistura os dois nichos e aproveita sazonalidade (ex: Copa do Mundo)
ACTIVE_NICHE = os.getenv("ACTIVE_NICHE", "tech")

_KEYWORDS_TECH = [
    "mouse gamer", "teclado mecânico", "fone bluetooth",
    "headset gamer", "webcam full hd", "monitor gamer",
    "ssd externo", "carregador turbo", "hub usb",
]

_KEYWORDS_SPORTS = [
    "chuteira society", "camisa cbf copa", "smartwatch esportivo",
    "câmera de ação futebol", "caixinha bluetooth torcida",
    "bola futebol campo",
]

if ACTIVE_NICHE == "sports":
    NICHO         = "esportes e Copa do Mundo"
    SEED_KEYWORDS = _KEYWORDS_SPORTS
elif ACTIVE_NICHE == "both":
    NICHO         = "tecnologia gadgets e esportes Copa do Mundo"
    SEED_KEYWORDS = _KEYWORDS_TECH[:3] + _KEYWORDS_SPORTS[:3]
else:
    NICHO         = "periféricos e tecnologia gadgets"
    SEED_KEYWORDS = _KEYWORDS_TECH

# TTS
TTS_VOICE = "pt-BR-FranciscaNeural"
TTS_RATE  = "+5%"

# Vídeo
VIDEO_WIDTH        = 1080
VIDEO_HEIGHT       = 1920
VIDEO_MAX_DURATION = 30
# Encoder: "auto" detecta automaticamente (AMD AMF > NVENC > CPU)
VIDEO_ENCODER      = os.getenv("VIDEO_ENCODER", "auto")

# Paths
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, "data")
JOBS_DIR     = os.path.join(DATA_DIR, "jobs")
TOPICS_FILE  = os.path.join(DATA_DIR, "topics.json")
DB_PATH      = os.path.join(DATA_DIR, "pipeline.db")
