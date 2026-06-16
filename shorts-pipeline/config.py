import os
from dotenv import load_dotenv

load_dotenv()

# Ollama (LLM local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.1")

# Unsplash (imagens royalty-free)
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

# Afiliados
AMAZON_AFFILIATE_TAG  = os.getenv("AMAZON_AFFILIATE_TAG", "")
SHOPEE_AFFILIATE_ID   = os.getenv("SHOPEE_AFFILIATE_ID", "")

# Kling AI (geração de vídeo por IA)
KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY", "")
KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY", "")

# Pipeline
NICHO         = "periféricos e tecnologia gadgets"
SEED_KEYWORDS = ["mouse gamer", "teclado mecânico", "fone bluetooth", "headset gamer", "webcam"]
MAX_VIDEOS    = 3
MAX_TOPICS    = 5

# TTS
TTS_VOICE = "pt-BR-FranciscaNeural"
TTS_RATE  = "+10%"

# Vídeo
VIDEO_WIDTH        = 1080
VIDEO_HEIGHT       = 1920
VIDEO_MAX_DURATION = 30

# Paths
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, "data")
JOBS_DIR     = os.path.join(DATA_DIR, "jobs")
TOPICS_FILE  = os.path.join(DATA_DIR, "topics.json")
