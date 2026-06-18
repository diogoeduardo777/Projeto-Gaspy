import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Afiliados
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "")
SHOPEE_AFFILIATE_ID  = os.getenv("SHOPEE_AFFILIATE_ID", "")

# YouTube — link do canal para cross-promotion nas mensagens Telegram (ex: https://youtube.com/@seucanal)
YOUTUBE_CHANNEL = os.getenv("YOUTUBE_CHANNEL", "")

# Nicho
ACTIVE_NICHE = os.getenv("ACTIVE_NICHE", "tech")

# Horários de postagem (lidos do .env ou padrão 8h, 13h, 20h)
_hours_raw = os.getenv("POST_HOURS", "8,13,20")
POST_HOURS = [int(h.strip()) for h in _hours_raw.split(",")]

# Keywords por nicho
_KEYWORDS_TECH = [
    "mouse gamer", "teclado mecânico", "fone bluetooth",
    "headset gamer", "webcam full hd", "monitor gamer",
    "ssd externo", "smartwatch", "carregador turbo",
]

_KEYWORDS_SPORTS = [
    "chuteira society", "camisa cbf copa", "smartwatch esportivo",
    "câmera de ação", "caixinha bluetooth torcida",
    "bola futebol campo", "meião futebol",
]

if ACTIVE_NICHE == "sports":
    DEAL_KEYWORDS = _KEYWORDS_SPORTS
elif ACTIVE_NICHE == "both":
    DEAL_KEYWORDS = _KEYWORDS_TECH[:5] + _KEYWORDS_SPORTS[:4]
else:
    DEAL_KEYWORDS = _KEYWORDS_TECH

# Produtos digitais — Hotmart, Eduzz, Monetizze
# Adicione seus links de afiliado abaixo. Deixe a lista vazia para desativar.
# Formato: {"name": "Nome do Produto", "link": "https://go.hotmart.com/XXXXX", "category": "categoria"}
DIGITAL_PRODUCTS = [
    # {"name": "Curso de Excel do Zero", "link": "https://go.hotmart.com/XXXXX", "category": "produtividade"},
    # {"name": "Método de Inglês Fluente", "link": "https://go.hotmart.com/YYYYY", "category": "idiomas"},
    # {"name": "Dieta Low Carb Definitiva", "link": "https://go.hotmart.com/ZZZZZ", "category": "saúde"},
    # {"name": "Curso de Programação Python", "link": "https://go.hotmart.com/WWWWW", "category": "tecnologia"},
]

# Paths
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
