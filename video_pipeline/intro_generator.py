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

# !! ADICIONADO AVISO SOBRE WEBP !!
print("AVISO: O carregamento direto de WebP no intro_generator depende da instalação da biblioteca 'libwebp' e do suporte do Pillow.")

def create_intro(scp_number: str, scp_name: str, scp_class: str, background_video_path: Path | None = None) -> Tuple[CompositeVideoClip | ColorClip, float]:
    """
    Cria a introdução com imagem de fundo, texto digitando em duas linhas (SCP# e Nome),
    som sincronizado e duração adaptável com pausas.
    Tenta adicionar logo .webp se configurado.
    IGNORA o background_video_path passado.

    Returns:
        Tupla (clipe_intro, duracao_intro_segundos).
    """
    print("--- Iniciando criação da intro (2 Linhas, Adaptável, Som, Logo WebP?) ---")
    start_time_intro = time.time()

    # --- Parâmetros e Caminhos ---
    project_root = Path(__file__).resolve().parent.parent
    bg_img_path = project_root / "assets" / "img" / "intro-bg.png"
    font_path_intro = Path(config.FONT_INTRO) # Fonte específica da intro
    type_sound_dir = project_root / "assets" / "type-sound"
    logo_path = config.SCP_LOGO_FILE # Usa o caminho do WebP diretamente

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
    logo_intro_clip = None # Para o clipe da logo da intro
    temp_logo_intro_base = None # Para fechar o clipe base da logo

    try:
        # --- Carregar Fundo (igual a antes) ---
        if not bg_img_path.is_file():
            print(f"AVISO: Imagem de fundo '{bg_img_path.name}' não encontrada. Usando cor sólida.")
            bg_clip = ColorClip(size=video_size, color=config.INTRO_BACKGROUND_COLOR, duration=total_duration).set_fps(fps)
        else:
            print(f"Carregando imagem de fundo: {bg_img_path.name}")
            # Usando 'with' garante o fechamento do ImageClip temporário
            with ImageClip(str(bg_img_path)) as temp_bg_imgclip:
                # Ajuste de tamanho/crop (igual ao código original)
                bg_clip_resized = temp_bg_imgclip
                if temp_bg_imgclip.size != video_size:
                    print(f"Redimensionando/cortando fundo de {temp_bg_imgclip.size} para {video_size}")
                    bg_clip_resized = temp_bg_imgclip.resize(height=video_size[1])
                    if bg_clip_resized.w < video_size[0]:
                         bg_clip_resized.close() # Fecha intermediário
                         bg_clip_resized = temp_bg_imgclip.resize(width=video_size[0])
                    # Realiza o crop no clipe redimensionado
                    bg_clip_cropped = bg_clip_resized.crop(
                        x_center=bg_clip_resized.w / 2, y_center=bg_clip_resized.h / 2,
                        width=video_size[0], height=video_size[1]
                    )
                    bg_clip = bg_clip_cropped # O clipe final para uso é o cortado
                    if bg_clip_resized is not temp_bg_imgclip: # Se houve redimensionamento
                        clips_to_close.append(bg_clip_resized) # Adiciona redimensionado para fechar
                else:
                     bg_clip = temp_bg_imgclip.copy() # Copia se o tamanho já estava certo

                # Define duração e FPS no clipe final de fundo
                bg_clip = bg_clip.set_duration(total_duration).set_fps(fps)
                clips_to_close.append(bg_clip) # Adiciona o bg_clip final para fechar

            if bg_clip is None: raise ValueError("Falha ao processar bg_clip.")
            print(f"Clipe de fundo processado: Duração={bg_clip.duration:.2f}s")


        # --- Carregar Sons (igual a antes) ---
        type_sounds = []
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


        # --- Efeito de Digitação Visual (2 Linhas - igual a antes) ---
        typing_start_time = pause_start_sec
        typing_duration_line1 = num_chars1 * typing_speed
        typing_duration_line2 = num_chars2 * typing_speed
        typing_total_active_time = typing_duration_line1 + typing_duration_line2

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
        try:
            line1_bbox = font1.getbbox("A")
            line1_height = line1_bbox[3] - line1_bbox[1] if line1_bbox else font_size1
        except Exception: line1_height = font_size1
        line2_pos = (line1_pos[0], line1_pos[1] + line1_height + line_spacing)

        def make_frame_visual(t):
            img_txt = Image.new("RGBA", video_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(img_txt)
            time_since_typing_start = max(0, t - typing_start_time)
            chars1_float = time_since_typing_start / typing_speed
            chars1 = min(num_chars1, math.floor(chars1_float))
            time_for_line2 = max(0, time_since_typing_start - typing_duration_line1)
            chars2_float = time_for_line2 / typing_speed
            chars2 = min(num_chars2, math.floor(chars2_float))
            display_text1 = text_line1[:chars1]
            display_text2 = text_line2[:chars2]
            cursor = " "
            total_chars_shown = chars1 + chars2
            if total_chars_shown < total_chars and t >= typing_start_time and t < (typing_start_time + typing_total_active_time + 0.1):
                cursor = "|" if math.floor(t * 2) % 2 == 0 else " "
            elif t < typing_start_time:
                 cursor = "|" if math.floor(t * 2) % 2 == 0 else " "
            cursor1 = cursor if chars1 < num_chars1 else " "
            draw.text(line1_pos, display_text1 + cursor1, font=font1, fill=text_color)
            cursor2 = cursor if chars1 == num_chars1 and chars2 < num_chars2 else " "
            draw.text(line2_pos, display_text2 + cursor2, font=font2, fill=text_color)
            img_rgb = img_txt.convert("RGB") # Converte para RGB para VideoClip padrão
            return np.array(img_rgb)

        print("Criando clipe visual da digitação (2 linhas)...")
        text_clip_visual = VideoClip(make_frame_visual, duration=total_duration).set_fps(fps)
        clips_to_close.append(text_clip_visual)

        # --- Geração de Áudio Antecipada (2 Linhas - igual a antes) ---
        if type_sounds:
            print("Gerando áudio completo da digitação (2 linhas)...")
            audio_fps = 44100
            num_audio_frames = int(total_duration * audio_fps)
            accumulated_audio = np.zeros((num_audio_frames, 2), dtype=np.float32)
            char_press_times1 = [typing_start_time + (i * typing_speed) for i in range(num_chars1)]
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

        # --- *** NOVO: Adicionar Logo na Intro (se configurado) *** ---
        intro_elements = [bg_clip, text_clip_visual] # Começa com fundo e texto
        if config.USE_LOGO_IN_INTRO:
            if logo_path.exists():
                try:
                    print(f"Tentando carregar logo WebP para intro: {logo_path.name}")
                    logo_width_intro = int(config.VIDEO_WIDTH * config.LOGO_SIZE_FACTOR_INTRO)

                    # Carrega WebP diretamente - definindo ismask=False para transparência
                    temp_logo_intro_base = ImageClip(str(logo_path), ismask=False, transparent=True)
                    clips_to_close.append(temp_logo_intro_base) # Adiciona base para fechar

                    logo_intro_clip = (temp_logo_intro_base
                                       .resize(width=logo_width_intro)
                                       .set_duration(total_duration) # Logo dura toda a intro
                                       .set_position(config.LOGO_POSITION_INTRO)
                                       .margin(left=config.LOGO_MARGIN_INTRO, right=config.LOGO_MARGIN_INTRO,
                                               top=config.LOGO_MARGIN_INTRO, bottom=config.LOGO_MARGIN_INTRO, opacity=0) # Margem transparente
                                       .set_fps(fps))

                    intro_elements.append(logo_intro_clip) # Adiciona logo aos elementos da composição
                    print("Logo adicionado à intro.")
                except Exception as e:
                    print(f"AVISO: Falha ao carregar ou processar logo WebP para intro: {e}")
                    print("       Verifique se 'libwebp' está instalado e o Pillow o suporta.")
                    # Limpa ref base se falhou após criar
                    if temp_logo_intro_base and temp_logo_intro_base in clips_to_close:
                        clips_to_close.remove(temp_logo_intro_base)
                        if hasattr(temp_logo_intro_base, 'close'): temp_logo_intro_base.close()
            else:
                 print(f"Aviso: Logo para intro habilitado, mas arquivo não encontrado: {logo_path}")

        # --- Composição Final ---
        print("Compondo clipe final da intro...")
        if not bg_clip or not hasattr(bg_clip, 'get_frame'): raise ValueError("BG inválido.")
        if not text_clip_visual or not hasattr(text_clip_visual, 'get_frame'): raise ValueError("Texto visual inválido.")

        # Usa intro_elements que agora contém [bg, texto, logo(opcional)]
        final_clip = CompositeVideoClip(intro_elements, size=video_size, use_bgclip=True)

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
        # Itera em cópia para poder remover durante iteração se necessário
        for clip in list(clips_to_close):
             if clip and hasattr(clip, 'close'):
                 try:
                     clip.close(); closed_count += 1
                 except Exception as close_err:
                      print(f"Erro menor ao fechar clipe da intro: {close_err}")
        print(f"Tentativa de fechar {closed_count} clipes intermediários da intro.")