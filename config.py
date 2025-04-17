# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Dev Mode ---
DEV_MODE = True # ATENÇÃO: Mude para False para produção final
DEV_MODE_VIDEO_DURATION = 10 # Duração do *conteúdo* (excluindo intro) em modo dev

# --- OpenAI API ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "SUA_API_KEY_AQUI_SE_NAO_USAR_VAR_AMBIENTE")
# Adicione avisos ou validações da chave API se necessário
if not OPENAI_API_KEY or OPENAI_API_KEY == "SUA_API_KEY_AQUI_SE_NAO_USAR_VAR_AMBIENTE":
    print("AVISO URGENTE: Chave da API OpenAI não configurada! O script pode falhar.")

# --- Caminhos ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SCRIPT_DIR = BASE_DIR / "data" / "scripts"
ASSETS_DIR = BASE_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
IMG_DIR = ASSETS_DIR / "img"
TEMP_DIR = OUTPUT_DIR / "temp"

# Cria diretórios necessários (executa apenas uma vez na importação)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
FONT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# --- Estrutura de Arquivos de Saída ---
ARTIFACT_SCRIPT = "script.txt"
ARTIFACT_NARRATION = "narration.mp3"
ARTIFACT_BACKGROUND = "background.mp4"
ARTIFACT_TIMESTAMPS_RAW = "timestamps_raw.json" # Timestamps brutos do Whisper
ARTIFACT_PUNCTUATED_DATA = "timestamps_punctuated.json" # Timestamps após adicionar pontuação
ARTIFACT_FINAL_VIDEO = "final.mp4"

# --- Arquivo do Logo ---
SCP_LOGO_FILE = Path(__file__).resolve().parent / "assets" / "svg" / "scp_logo.webp"

# --- Arquivos de Fonte ---
FONT_INTRO = str(FONT_DIR / "typewriter.ttf")
NARRATION_TEXT_FONT = str(FONT_DIR / "typewriter.ttf") # Fonte para o texto principal

# --- Configurações de Vídeo ---
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_SIZE = (VIDEO_WIDTH, VIDEO_HEIGHT)
# Duração máxima do vídeo final (Intro + Conteúdo)
MAX_VIDEO_DURATION_SECONDS = 180 # Ajuste conforme necessário (ex: 60 para shorts)

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
TTS_MODEL = "tts-1" # Ou "tts-1-hd" para maior qualidade (e custo)
TTS_VOICE = "onyx" # Escolha a voz: alloy, echo, fable, onyx, nova, shimmer

# --- Configurações de STT ---
STT_MODEL = "whisper-1"

# --- Configurações da Intro ---
INTRO_DURATION = 5 # Duração fixa da intro em segundos
INTRO_FONT_SIZE_NUMBER = 160
INTRO_FONT_SIZE_NAME = 110
INTRO_FONT_SIZE_CLASS = 90
INTRO_TEXT_COLOR = 'white'
INTRO_BACKGROUND_COLOR = (5, 0, 5) # Cor de fundo da intro (se não usar vídeo)
INTRO_TEXT_BG_ENABLED = True # Fundo atrás do texto da intro
INTRO_TEXT_BG_COLOR = (0, 0, 0)
INTRO_TEXT_BG_OPACITY = 0.6
INTRO_TEXT_PADDING = 25
INTRO_TYPING_EFFECT_SPEED = 0.30 # Segundos por caractere (menor = mais rápido)

# --- Configurações do Texto da Narração (Principal) ---
NARRATION_TEXT_FONT_SIZE = 70
NARRATION_TEXT_COLOR = 'white'
# Alinhamento Horizontal: 'center', 'left', 'right'
NARRATION_TEXT_H_ALIGN = 'center'
# Posição Vertical do CENTRO do bloco de texto (0.0 = topo, 0.5 = meio, 1.0 = fundo)
NARRATION_TEXT_V_ALIGN_PERCENT = 0.3 # Ajuste este valor (ex: 0.7, 0.8)
# Fator da largura do vídeo que o texto pode ocupar (0.0 a 1.0)
NARRATION_TEXT_MAX_WIDTH_FACTOR = 0.9
NARRATION_TEXT_BG_ENABLED = False # Fundo para legibilidade
NARRATION_TEXT_BG_COLOR = (0, 0, 0) # Cor do fundo
NARRATION_TEXT_BG_OPACITY = 0.7 # Opacidade do fundo (0.0 a 1.0)
NARRATION_TEXT_PADDING = 15 # Padding interno do fundo

# --- Configurações de Renderização (MoviePy) ---
# Configurações normais (não dev mode)
VIDEO_CODEC_NORMAL = "libx264"
AUDIO_CODEC_NORMAL = "aac"
VIDEO_PRESET_NORMAL = "medium" # Qualidade vs Velocidade: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
VIDEO_THREADS_NORMAL = os.cpu_count() or 4
VIDEO_CRF_NORMAL = "23" # Constant Rate Factor (menor = melhor qualidade, maior arquivo): 18-28 é uma faixa comum

# Configurações dev mode (rápido, menor qualidade)
VIDEO_CODEC_DEV = "libx264"
AUDIO_CODEC_DEV = "aac"
VIDEO_PRESET_DEV = "ultrafast"
VIDEO_THREADS_DEV = os.cpu_count() or 4
VIDEO_CRF_DEV = "28"

# Seleciona configurações baseadas no modo
VIDEO_CODEC = VIDEO_CODEC_DEV if DEV_MODE else VIDEO_CODEC_NORMAL
AUDIO_CODEC = AUDIO_CODEC_DEV if DEV_MODE else AUDIO_CODEC_NORMAL
VIDEO_PRESET = VIDEO_PRESET_DEV if DEV_MODE else VIDEO_PRESET_NORMAL
VIDEO_THREADS = VIDEO_THREADS_DEV if DEV_MODE else VIDEO_THREADS_NORMAL
VIDEO_CRF = VIDEO_CRF_DEV if DEV_MODE else VIDEO_CRF_NORMAL

# --- Configurações de Áudio de Fundo ---
BG_MUSIC_FILE = Path(__file__).resolve().parent / "assets" / "bg-sound" / "bg-sound.wav"
USE_BG_MUSIC = True
BG_MUSIC_VOLUME = 0.08 # Volume BEM baixo para ser ambiente (0.0 a 1.0)

# --- Impressão de Configurações Chave ---
print("-" * 30)
print("Configurações Carregadas:")
print(f"Modo DEV Ativado: {'Sim' if DEV_MODE else 'Não'}")
if DEV_MODE: print(f"  - Duração Conteúdo (DEV): {DEV_MODE_VIDEO_DURATION}s")
print(f"Duração Máxima Vídeo: {MAX_VIDEO_DURATION_SECONDS}s")
print(f"Fonte Texto Narração: {Path(NARRATION_TEXT_FONT).name}")
print(f"Alinhamento Horizontal Texto: {NARRATION_TEXT_H_ALIGN}")
print(f"Posição Vertical (Topo do Bloco) Texto Narração: {NARRATION_TEXT_V_ALIGN_PERCENT * 100:.0f}%")
print(f"Preset Renderização: {VIDEO_PRESET} (CRF: {VIDEO_CRF})")
print("-" * 30)