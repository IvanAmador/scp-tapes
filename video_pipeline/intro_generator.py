# video_pipeline/intro_generator.py
from moviepy.editor import CompositeVideoClip, ImageClip, VideoClip, ColorClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os
from pathlib import Path
import config # Importar config para usar as dimensões e FPS

def create_intro(scp_number: str, scp_name: str, scp_class: str, background_video_path: Path | None = None):
    """
    Cria a introdução usando a imagem assets/img/intro-bg.png
    e texto com efeito de digitação.
    IGNORA o background_video_path passado como argumento.
    """
    print("--- Iniciando criação da intro com Imagem de Fundo e Texto Digitando ---")
    # Caminhos dos assets (verifique se estão corretos!)
    project_root = Path(__file__).resolve().parent.parent
    bg_img_path = project_root / "assets" / "img" / "intro-bg.png"
    font_path = project_root / "assets" / "fonts" / "typewriter.ttf"

    # Texto da intro
    intro_text = f"{scp_number} - {scp_name}\nClasse: {scp_class}"

    # Parâmetros visuais
    duration = config.INTRO_DURATION # Usar duração do config
    font_size = 64 # Ajuste se necessário
    color = "white" # Cor do texto
    text_pos = (80, 180) # Posição (X, Y) do texto - ajuste para sua imagem
    video_size = config.VIDEO_SIZE # Usar tamanho do config
    fps = config.VIDEO_FPS # Usar FPS do config

    # Cria o fundo a partir da IMAGEM
    try:
        if not bg_img_path.is_file():
            print(f"Erro Crítico: Imagem de fundo da intro NÃO encontrada em {bg_img_path}")
            # Retornar None aqui causa o erro 'NoneType' object has no attribute 'get_frame'
            # Poderíamos retornar um clipe preto sólido como fallback seguro.
            print("Retornando clipe preto como fallback seguro para intro.")
            return ColorClip(size=video_size, color=(0, 0, 0), duration=duration).set_fps(fps)
            # raise FileNotFoundError(f"Arquivo de imagem de fundo não encontrado: {bg_img_path}")

        print(f"Carregando imagem de fundo para intro: {bg_img_path}")
        bg_clip = ImageClip(str(bg_img_path)).set_duration(duration)

        # Redimensiona a imagem de fundo para o tamanho do vídeo final, se necessário
        if bg_clip.size != video_size:
             print(f"Redimensionando fundo da intro de {bg_clip.size} para {video_size}")
             # Redimensiona preenchendo (pode distorcer se proporções forem diferentes)
             bg_clip = bg_clip.resize(video_size)
        
        # Define o FPS do clipe de fundo
        bg_clip = bg_clip.set_fps(fps)

    except Exception as e:
        print(f"Erro Crítico ao carregar/processar imagem de fundo da intro: {e}")
        print("Retornando clipe preto como fallback seguro para intro.")
        # Retorna um clipe válido em caso de erro para evitar o 'NoneType'
        return ColorClip(size=video_size, color=(0, 0, 0), duration=duration).set_fps(fps)

    # --- Efeito de digitação ---
    memo = {} # Cache simples para fontes

    def make_typing_frame(t):
        # Garante que t esteja no intervalo [0, duration]
        t = max(0, min(t, duration))

        # Calcula o número de caracteres a exibir
        progress = t / duration
        chars_to_show = int(len(intro_text) * progress)

        if t > 0 and chars_to_show == 0: chars_to_show = 1
        elif t == 0: chars_to_show = 0

        current_text = intro_text[:chars_to_show]

        # Cria uma imagem transparente para o texto
        img_txt = Image.new("RGBA", video_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img_txt)

        # Carrega a fonte (com cache)
        font = memo.get(font_path)
        if font is None:
            try:
                if not font_path.is_file():
                    print(f"Aviso: Arquivo de fonte não encontrado em {font_path}. Usando padrão.")
                    font = ImageFont.load_default()
                else:
                    font = ImageFont.truetype(str(font_path), font_size)
                memo[font_path] = font # Armazena no cache
            except Exception as e:
                print(f"Aviso: Não foi possível carregar a fonte '{font_path}'. Usando padrão. Erro: {e}")
                font = ImageFont.load_default()
                memo[font_path] = font # Armazena fallback no cache

        # Desenha o texto na posição definida
        draw.multiline_text(text_pos, current_text, font=font, fill=color, spacing=8)

        # Converte para formato que MoviePy entende (array NumPy RGB)
        frame_rgb = np.array(img_txt.convert("RGB"))
        return frame_rgb
    # --- Fim Efeito de digitação ---

    try:
        # Cria o clipe de vídeo a partir da função que desenha cada frame
        txt_clip = VideoClip(make_typing_frame, duration=duration).set_fps(fps)

        # Composição final: coloca o clipe de texto sobre o clipe de fundo
        final_clip = CompositeVideoClip([bg_clip, txt_clip.set_position((0, 0))], size=video_size)
        
        # Testa um frame para validação básica ANTES de retornar
        print("Validando frame de teste da intro...")
        test_frame = final_clip.get_frame(0.1) # Pega um frame do início
        if test_frame is None or test_frame.size == 0:
             print("Erro Crítico: Frame de teste da intro é inválido (None ou vazio).")
             # Retorna fallback seguro
             return ColorClip(size=video_size, color=(0, 0, 0), duration=duration).set_fps(fps)

        print("Clipe de introdução (Imagem + Texto Digitado) criado com sucesso.")
        return final_clip

    except Exception as e:
        print(f"Erro Crítico durante a criação do clipe de texto ou composição final da intro: {e}")
        import traceback
        traceback.print_exc()
        print("Retornando clipe preto como fallback seguro para intro.")
        # Retorna um clipe válido em caso de erro
        return ColorClip(size=video_size, color=(0, 0, 0), duration=duration).set_fps(fps)