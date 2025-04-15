# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- OpenAI API ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "SUA_API_KEY_AQUI_SE_NAO_USAR_VAR_AMBIENTE")
# ... (avisos sobre chave) ...

# --- Caminhos ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SCRIPT_DIR = BASE_DIR / "data" / "scripts"
ASSETS_DIR = BASE_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
# REMOVIDO: SVG_DIR = ASSETS_DIR / "svg"
IMG_DIR = ASSETS_DIR / "img" # NOVA PASTA PARA IMAGENS (PNG, JPG, etc.)
TEMP_DIR = OUTPUT_DIR / "temp"

# Cria diretórios necessários
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
FONT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True) # Cria pasta img
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# --- Estrutura de Arquivos de Saída ---
# Artefatos que serão salvos para cada SCP
ARTIFACT_NARRATION = "narration.mp3"  # Áudio da narração
ARTIFACT_BACKGROUND = "background.mp4"  # Vídeo de fundo
ARTIFACT_SUBTITLES_DATA = "subtitles.json"  # Dados de legendas (timestamps)
ARTIFACT_FINAL_VIDEO = "final.mp4"  # Vídeo final

# --- Arquivo do Logo (WEBP) ---
SCP_LOGO_FILE = Path(__file__).resolve().parent / "assets" / "svg" / "scp_logo.webp"

# --- Arquivos de Fonte ---
# ... (igual) ...
FONT_INTRO = "Arial-Bold"
FONT_SUBTITLE = str(FONT_DIR / "typewriter.ttf")

# --- Configurações de Vídeo ---
# ... (igual) ...
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_SIZE = (VIDEO_WIDTH, VIDEO_HEIGHT)
MAX_VIDEO_DURATION_SECONDS = 180

# --- Configurações de Logo ---
USE_LOGO_IN_INTRO = True
USE_LOGO_WATERMARK = True
LOGO_SIZE_FACTOR_INTRO = 0.25
LOGO_SIZE_FACTOR_WATERMARK = 0.15
LOGO_POSITION_INTRO = ('right', 'top')
LOGO_MARGIN_INTRO = 30
LOGO_POSITION_WATERMARK = ('right', 'bottom')
LOGO_MARGIN_WATERMARK = 20
LOGO_OPACITY_WATERMARK = 0.6

# --- Configurações de TTS ---
# ... (igual) ...
TTS_MODEL = "tts-1"
TTS_VOICE = "onyx"

# --- Configurações de STT ---
# ... (igual) ...
STT_MODEL = "whisper-1"

# --- Configurações da Intro ---
INTRO_DURATION = 7  # Aumentado para dar mais tempo para a intro
INTRO_FONT_SIZE_NUMBER = 130  # Código SCP maior
INTRO_FONT_SIZE_NAME = 100  # Nome do SCP
INTRO_FONT_SIZE_CLASS = 90  # Classe
INTRO_TEXT_COLOR = 'white'
INTRO_BACKGROUND_COLOR = (5, 0, 5)
INTRO_TEXT_BG_ENABLED = True
INTRO_TEXT_BG_COLOR = (0, 0, 0)
INTRO_TEXT_BG_OPACITY = 0.6
INTRO_TEXT_PADDING = 25  # Aumentado para melhor espaçamento

# --- Configurações de Legenda ---
SUBTITLE_FONT_SIZE = 65  # Aumentado para texto maior
SUBTITLE_COLOR = 'lime'
SUBTITLE_HIGHLIGHT_COLOR = 'white'
SUBTITLE_POSITION = ('center', 0.5)  # Centralizado na tela
SUBTITLE_MAX_LINE_CHARS = 60  # Mais caracteres por linha
SUBTITLE_BG_ENABLED = True
SUBTITLE_BG_COLOR = (0, 0, 0)
SUBTITLE_BG_OPACITY = 0.7
SUBTITLE_PADDING = 20  # Aumentado para melhor espaçamento
SUBTITLE_MODE = 'phrase'  # Mantém o modo de frase

# --- Configurações de Renderização (MoviePy) ---
# ... (igual) ...
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
VIDEO_PRESET = "medium"
VIDEO_THREADS = os.cpu_count() or 4
VIDEO_CRF = "23"

# --- Configurações de Áudio de Fundo ---
BG_MUSIC_FILE = Path(__file__).resolve().parent / "assets" / "bg-sound" / "bg-sound.wav"
USE_BG_MUSIC = True
BG_MUSIC_VOLUME = 0.8  # 80% do volume da narração

print("Configurações carregadas.")