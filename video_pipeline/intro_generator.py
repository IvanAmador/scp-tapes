# video_pipeline/intro_generator.py
from moviepy.editor import (CompositeVideoClip, ImageClip, VideoClip, ColorClip,
                            AudioFileClip, concatenate_audioclips, AudioClip, afx)
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os
from pathlib import Path
import random
import math
import time
from typing import Tuple
import config

def create_intro(scp_number: str, scp_name: str, scp_class: str, background_video_path: Path | None = None) -> Tuple[CompositeVideoClip | ColorClip, float]:
    """
    Cria a introdução com imagem de fundo, texto digitando em duas linhas (SCP# e Nome),
    som sincronizado e duração adaptável com pausas.
    IGNORA o background_video_path passado.

    Returns:
        Tupla (clipe_intro, duracao_intro_segundos).
    """
    print("--- Iniciando criação da intro (2 Linhas, Adaptável, Som) ---")
    start_time_intro = time.time()

    # --- Parâmetros e Caminhos ---
    project_root = Path(__file__).resolve().parent.parent
    bg_img_path = project_root / "assets" / "img" / "intro-bg.png"
    font_path_intro = Path(config.FONT_INTRO) # Fonte específica da intro
    type_sound_dir = project_root / "assets" / "type-sound"

    video_size = config.VIDEO_SIZE
    fps = config.VIDEO_FPS
    typing_speed = config.INTRO_TYPING_EFFECT_SPEED
    if typing_speed <= 0: typing_speed = 0.15 # Fallback

    # --- Textos e Fontes ---
    text_line1 = scp_number
    text_line2 = f"- {scp_name}" # Adiciona hífen para separação visual
    num_chars1 = len(text_line1)
    num_chars2 = len(text_line2)
    total_chars = num_chars1 + num_chars2

    font_size1 = config.INTRO_FONT_SIZE_NUMBER
    font_size2 = config.INTRO_FONT_SIZE_NAME
    text_color = config.INTRO_TEXT_COLOR
    # Posição INICIAL (X, Y) da PRIMEIRA linha (Ajuste!)
    line1_pos = (80, 220)
    line_spacing = 20 # Espaço vertical entre as linhas (Ajuste!)

    # --- Cálculo da Duração Adaptável ---
    pause_start_sec = 0.8
    typing_duration_sec = total_chars * typing_speed
    pause_end_sec = 2.0 # Aumenta um pouco a pausa final
    total_duration = pause_start_sec + typing_duration_sec + pause_end_sec
    print(f"Texto Intro: L1='{text_line1}' ({num_chars1}), L2='{text_line2}' ({num_chars2})")
    print(f"Duração Intro Calculada: {total_duration:.2f}s (Pausa Início: {pause_start_sec:.1f}s, Digitação: {typing_duration_sec:.2f}s, Pausa Fim: {pause_end_sec:.1f}s)")

    # --- Variáveis ---
    bg_clip = None
    clips_to_close = []
    text_clip_visual = None
    text_clip_audio = None
    final_clip = None
    fallback_duration = 5.0
    final_audio_array = None
    memo_fonts = {} # Cache para ambas as fontes

    try:
        # --- Carregar Fundo (igual a antes) ---
        if not bg_img_path.is_file():
            print(f"AVISO: Imagem de fundo '{bg_img_path.name}' não encontrada. Usando cor sólida.")
            bg_clip = ColorClip(size=video_size, color=config.INTRO_BACKGROUND_COLOR, duration=total_duration).set_fps(fps)
        else:
            # ... (código de carregamento, redimensionamento/corte do bg_clip como antes) ...
            print(f"Carregando imagem de fundo: {bg_img_path.name}")
            with ImageClip(str(bg_img_path), ismask=False, transparent=True) as temp_bg_imgclip:
                temp_bg_duration_set = temp_bg_imgclip.set_duration(total_duration)
                clips_to_close.append(temp_bg_duration_set)
                if temp_bg_duration_set.size != video_size:
                    print(f"Redimensionando/cortando fundo de {temp_bg_duration_set.size} para {video_size}")
                    bg_processed = temp_bg_duration_set.resize(height=video_size[1])
                    if bg_processed.w < video_size[0]:
                        bg_processed.close(); bg_processed = temp_bg_duration_set.resize(width=video_size[0])
                    bg_clip = bg_processed.crop(x_center=bg_processed.w / 2, y_center=bg_processed.h / 2, width=video_size[0], height=video_size[1])
                    clips_to_close.append(bg_clip)
                else:
                    bg_clip = temp_bg_duration_set.copy(); clips_to_close.append(bg_clip)
            if bg_clip is None: raise ValueError("Falha ao processar bg_clip.")
            bg_clip = bg_clip.set_fps(fps); print(f"Clipe de fundo processado: Duração={bg_clip.duration:.2f}s")


        # --- Carregar Sons (igual a antes) ---
        type_sounds = []
        # ... (código para carregar sons em type_sounds e adicioná-los a clips_to_close) ...
        if type_sound_dir.is_dir():
            for sound_file in type_sound_dir.glob("type-*.wav"):
                try:
                    audio_clip = AudioFileClip(str(sound_file))
                    if audio_clip and audio_clip.duration > 0:
                         type_sounds.append(audio_clip); clips_to_close.append(audio_clip)
                    elif audio_clip: audio_clip.close()
                except Exception as e: print(f"Aviso: Falha ao carregar som '{sound_file.name}': {e}")
            print(f"Carregados {len(type_sounds)} sons de digitação válidos.")
        else: print(f"Aviso: Diretório de sons '{type_sound_dir}' não encontrado.")


        # --- Efeito de Digitação Visual (2 Linhas) ---
        typing_start_time = pause_start_sec
        # Tempo para digitar a primeira linha
        typing_duration_line1 = num_chars1 * typing_speed
        # Tempo para digitar a segunda linha (começa após a primeira)
        typing_duration_line2 = num_chars2 * typing_speed
        # Tempo total de digitação (sem pausas entre linhas por enquanto)
        typing_total_active_time = typing_duration_line1 + typing_duration_line2

        # Função para carregar fontes com cache
        def get_font(size):
            key = (font_path_intro, size)
            font = memo_fonts.get(key)
            if font is None:
                try:
                    font = ImageFont.truetype(str(font_path_intro), size) if font_path_intro.is_file() else ImageFont.load_default()
                except Exception: font = ImageFont.load_default()
                memo_fonts[key] = font
            return font

        font1 = get_font(font_size1)
        font2 = get_font(font_size2)
        # Calcula a altura da primeira linha para posicionar a segunda
        try:
            # Usa textbbox para obter a altura real da fonte renderizada
            line1_bbox = font1.getbbox("A") # Bbox de um caractere alto
            line1_height = line1_bbox[3] - line1_bbox[1] if line1_bbox else font_size1 # Fallback para font_size
        except Exception:
             line1_height = font_size1 # Fallback mais simples

        line2_pos = (line1_pos[0], line1_pos[1] + line1_height + line_spacing) # Pos X igual, Y abaixo

        def make_frame_visual(t):
            img_txt = Image.new("RGBA", video_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img_txt)

            # Tempo relativo desde o início da digitação (após pausa inicial)
            time_since_typing_start = max(0, t - typing_start_time)

            # Calcula quantos caracteres mostrar na linha 1
            chars1_float = time_since_typing_start / typing_speed
            chars1 = min(num_chars1, math.floor(chars1_float))

            # Calcula quantos caracteres mostrar na linha 2 (só começa após linha 1)
            time_for_line2 = max(0, time_since_typing_start - typing_duration_line1)
            chars2_float = time_for_line2 / typing_speed
            chars2 = min(num_chars2, math.floor(chars2_float))

            # Texto a exibir
            display_text1 = text_line1[:chars1]
            display_text2 = text_line2[:chars2]

            # Lógica do cursor
            cursor = " "
            total_chars_shown = chars1 + chars2
            # Mostra cursor se não terminou de digitar TUDO e durante a digitação ativa
            if total_chars_shown < total_chars and t >= typing_start_time and t < (typing_start_time + typing_total_active_time + 0.1): # 0.1s margem
                cursor = "|" if math.floor(t * 2) % 2 == 0 else " "
            # Mostra cursor piscando também na pausa inicial
            elif t < typing_start_time:
                 cursor = "|" if math.floor(t * 2) % 2 == 0 else " "


            # Desenha linha 1 (com cursor se for a linha ativa)
            cursor1 = cursor if chars1 < num_chars1 else " "
            draw.text(line1_pos, display_text1 + cursor1, font=font1, fill=text_color)

            # Desenha linha 2 (com cursor se for a linha ativa)
            cursor2 = cursor if chars1 == num_chars1 and chars2 < num_chars2 else " "
            draw.text(line2_pos, display_text2 + cursor2, font=font2, fill=text_color)

            # Converte para RGB
            img_rgb = img_txt.convert("RGB")
            return np.array(img_rgb)

        print("Criando clipe visual da digitação (2 linhas)...")
        text_clip_visual = VideoClip(make_frame_visual, duration=total_duration).set_fps(fps)
        clips_to_close.append(text_clip_visual)

        # --- Geração de Áudio Antecipada (2 Linhas) ---
        if type_sounds:
            print("Gerando áudio completo da digitação (2 linhas)...")
            audio_fps = 44100
            num_audio_frames = int(total_duration * audio_fps)
            accumulated_audio = np.zeros((num_audio_frames, 2), dtype=np.float32)

            # Tempos de pressionar tecla para linha 1
            char_press_times1 = [typing_start_time + (i * typing_speed) for i in range(num_chars1)]
            # Tempos de pressionar tecla para linha 2 (começa depois da linha 1)
            start_time_line2 = typing_start_time + typing_duration_line1
            char_press_times2 = [start_time_line2 + (i * typing_speed) for i in range(num_chars2)]

            all_press_times = sorted(char_press_times1 + char_press_times2)

            for press_time in all_press_times:
                target_sample_index = max(0, min(int(press_time * audio_fps), num_audio_frames - 1))
                sound_clip = random.choice(type_sounds)
                try:
                    sound_samples = sound_clip.to_soundarray(fps=audio_fps, nbytes=4, quantize=False)
                    if sound_samples.ndim == 1: sound_samples = np.column_stack((sound_samples, sound_samples))
                    start_insert = target_sample_index
                    end_insert = min(start_insert + len(sound_samples), num_audio_frames)
                    samples_to_insert = end_insert - start_insert
                    if samples_to_insert > 0:
                        accumulated_audio[start_insert:end_insert] += sound_samples[:samples_to_insert]
                except Exception as audio_err:
                    print(f"Erro ao processar áudio de tecla: {audio_err}")

            max_abs_val = np.max(np.abs(accumulated_audio))
            if max_abs_val > 1.0:
                print(f"Normalizando áudio da intro (pico: {max_abs_val:.2f})")
                accumulated_audio /= max_abs_val
            final_audio_array = accumulated_audio
            print("Áudio completo da digitação gerado.")

            print("Criando clipe de áudio da digitação...")
            def get_audio_frame(t_audio):
                 idx = min(int(t_audio * audio_fps), num_audio_frames - 1)
                 return final_audio_array[idx]
            text_clip_audio = AudioClip(get_audio_frame, duration=total_duration, fps=audio_fps)
            clips_to_close.append(text_clip_audio)

        # --- Composição Final ---
        print("Compondo clipe final da intro...")
        if not bg_clip or not hasattr(bg_clip, 'get_frame'): raise ValueError("BG inválido.")
        if not text_clip_visual or not hasattr(text_clip_visual, 'get_frame'): raise ValueError("Texto visual inválido.")

        final_clip = CompositeVideoClip([bg_clip, text_clip_visual], size=video_size, use_bgclip=True)

        if text_clip_audio:
            final_clip = final_clip.set_audio(text_clip_audio)
            print("Áudio da digitação anexado.")
        else:
             print("AVISO: Clipe de áudio da digitação não foi criado ou anexado.")


        final_clip = final_clip.set_duration(total_duration).set_fps(fps)

        # --- Validação ---
        print("Validando frame de teste da intro final...")
        test_time = total_duration / 2
        test_frame = final_clip.get_frame(test_time)
        if test_frame is None or not isinstance(test_frame, np.ndarray) or test_frame.size == 0:
             raise ValueError("Frame de teste da intro final é inválido.")
        print(f"Frame de teste (t={test_time:.2f}s) validado (shape: {test_frame.shape}).")

        end_time_intro = time.time()
        print(f"Clipe de introdução criado com sucesso em {end_time_intro - start_time_intro:.2f}s.")
        return final_clip, total_duration

    except Exception as e:
        print(f"Erro Crítico durante a criação ou composição final da intro: {e}")
        import traceback
        traceback.print_exc()
        print("Retornando clipe preto como fallback seguro.")
        fallback_duration_final = total_duration if 'total_duration' in locals() and total_duration > 0 else fallback_duration
        fallback_clip = ColorClip(size=video_size, color=(0, 0, 0), duration=fallback_duration_final).set_fps(fps)
        return fallback_clip, fallback_duration_final
    finally:
        print("Fechando clipes intermediários da intro...")
        closed_count = 0
        # ... (código de fechamento como antes) ...
        for clip in clips_to_close:
             if clip and hasattr(clip, 'close'):
                 try: clip.close(); closed_count += 1
                 except Exception: pass
        print(f"Tentativa de fechar {closed_count} clipes intermediários da intro.")