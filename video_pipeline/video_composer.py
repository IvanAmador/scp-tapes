# video_pipeline/video_composer.py
import os
from moviepy.editor import (VideoFileClip, AudioFileClip, concatenate_videoclips,
                            CompositeVideoClip, ImageClip, ColorClip,
                            CompositeAudioClip, afx) # Adicionado afx para volumex
from typing import List, Union
from pathlib import Path
import numpy as np
import config
import time
import math

# !! ADICIONADO AVISO SOBRE WEBP !!
print("AVISO: O carregamento direto de WebP no video_composer depende da instalação da biblioteca 'libwebp' e do suporte do Pillow.")

def assemble_video(intro_clip: CompositeVideoClip | ColorClip, # Pode ser ColorClip do fallback
                   intro_duration: float, # <<< DURAÇÃO REAL DA INTRO ADICIONADA
                   background_video_path: Path,
                   narration_path: Path,
                   narration_text_clips: List[Union[ImageClip, CompositeVideoClip]],
                   output_path: Path,
                   final_duration: float) -> bool:
    """
    Monta o vídeo final usando durações precisas e posicionando clipes corretamente.
    Tenta usar logo .webp como marca d'água se configurado.

    Args:
        intro_clip: Clipe de vídeo da introdução.
        intro_duration: Duração real da introdução (em segundos).
        background_video_path: Caminho para o vídeo de fundo.
        narration_path: Caminho para o áudio da narração.
        narration_text_clips: Lista de clipes de texto (ImageClip) sincronizados.
        output_path: Caminho para salvar o vídeo final.
        final_duration: A duração exata desejada para o vídeo final (intro + conteúdo).

    Returns:
        True se a montagem for bem-sucedida, False caso contrário.
    """
    print(f"\n--- Iniciando Montagem do Vídeo: {output_path.name} ---")
    start_time = time.time()
    clips_to_close = []
    # Clipe de intro é responsabilidade do chamador (generate_scp_video) fechar
    final_clip = None
    narration_audio = None
    narration_audio_original = None
    bg_clip_full = None
    bg_clip_prepared = None
    logo_watermark_clip = None
    temp_logo_wm_base = None # Para fechar clipe base da logo watermark
    main_content_video = None # Clipe da parte do conteúdo (BG + Texto + Logo)
    final_audio = None
    bg_music_base = None # Referência ao clipe original da música
    bg_music_final = None # Áudio final da música processada
    bg_music_final_for_compose = None

    try:
        # 1. Calcular Duração do Conteúdo
        content_duration = final_duration - intro_duration
        if content_duration <= 0:
            raise ValueError(f"Erro: Duração do conteúdo calculada ({content_duration:.2f}s) é inválida. "
                             f"(Duração Final: {final_duration:.2f}s, Duração Intro: {intro_duration:.2f}s)")
        print(f"Montagem - Duração Final: {final_duration:.2f}s, Intro: {intro_duration:.2f}s, Conteúdo: {content_duration:.2f}s")

        # 2. Carregar e Ajustar Narração para DURAÇÃO DO CONTEÚDO
        print("Carregando e ajustando narração...")
        if not narration_path.exists(): raise FileNotFoundError(f"Narração não encontrada: {narration_path}")
        narration_audio_original = AudioFileClip(str(narration_path))
        clips_to_close.append(narration_audio_original)

        # Corta ou estende a narração para caber exatamente na duração do conteúdo
        if abs(narration_audio_original.duration - content_duration) > 0.1: # Tolerância pequena
             print(f"Ajustando narração de {narration_audio_original.duration:.2f}s para {content_duration:.2f}s.")
             narration_audio = narration_audio_original.subclip(0, content_duration) if narration_audio_original.duration > content_duration else narration_audio_original.set_duration(content_duration)
             # O resultado de subclip/set_duration não precisa ser adicionado explicitamente para fechar
             # MoviePy geralmente lida com isso, mas o original sim.
        else:
             narration_audio = narration_audio_original # Usa o original sem modificar

        # 3. Carregar e Preparar VÍDEO de Background para DURAÇÃO TOTAL
        print("Carregando e preparando vídeo de background...")
        if not background_video_path.exists(): raise FileNotFoundError(f"Vídeo de fundo não encontrado: {background_video_path}")
        if os.path.getsize(background_video_path) == 0: raise ValueError("Vídeo de fundo vazio.")

        try:
            bg_clip_full = VideoFileClip(str(background_video_path), audio=False)
            clips_to_close.append(bg_clip_full)
            if bg_clip_full.duration < final_duration - 0.1:
                 print(f"AVISO: Vídeo de fundo ({bg_clip_full.duration:.2f}s) é mais curto que a duração final ({final_duration:.2f}s).")

            bg_clip_prepared = bg_clip_full
            if bg_clip_full.size != config.VIDEO_SIZE:
                print(f"Aviso: Redimensionando/cortando background de {bg_clip_full.size} para {config.VIDEO_SIZE}.")
                # Utiliza a lógica original de resize/crop
                bg_processed = bg_clip_full.resize(height=config.VIDEO_HEIGHT)
                if bg_processed.w < config.VIDEO_WIDTH:
                    if hasattr(bg_processed,'close'): bg_processed.close()
                    bg_processed = bg_clip_full.resize(width=config.VIDEO_WIDTH)

                bg_clip_prepared = bg_processed.crop(x_center=bg_processed.w / 2, y_center=bg_processed.h / 2,
                                                    width=config.VIDEO_WIDTH, height=config.VIDEO_HEIGHT)
                # Se bg_processed foi criado (diferente de bg_clip_full), adiciona para fechar
                if bg_processed is not bg_clip_full:
                     clips_to_close.append(bg_processed)
                # Adiciona o resultado do crop também se for um novo objeto
                if bg_clip_prepared is not bg_processed:
                     clips_to_close.append(bg_clip_prepared)
            else:
                 # Se não precisou processar, bg_clip_prepared é o mesmo que bg_clip_full (já na lista)
                 pass

            # Define FPS e DURAÇÃO FINAL para o clipe de fundo que será usado
            bg_clip_prepared = bg_clip_prepared.set_duration(final_duration).set_fps(config.VIDEO_FPS)
            print(f"Background preparado (Duração: {bg_clip_prepared.duration:.2f}s)")

        except Exception as e:
            raise ValueError(f"Falha ao carregar/processar vídeo de fundo: {e}")

        # --- *** ATUALIZADO: Cria Logo Marca d'água (WebP) *** ---
        video_elements_content = [] # Elementos que vão *sobre* o fundo na parte do conteúdo
        if config.USE_LOGO_WATERMARK:
            logo_path = config.SCP_LOGO_FILE # Caminho do WebP
            if logo_path.exists():
                try:
                    print(f"Tentando carregar logo WebP para marca d'água: {logo_path.name}")
                    logo_width = int(config.VIDEO_WIDTH * config.LOGO_SIZE_FACTOR_WATERMARK)

                    # Carrega WebP diretamente, ismask=False para usar transparência
                    temp_logo_wm_base = ImageClip(str(logo_path), ismask=False, transparent=True)
                    clips_to_close.append(temp_logo_wm_base) # Adiciona clipe base para fechar

                    logo_watermark_clip = (temp_logo_wm_base
                                         .resize(width=logo_width)
                                         .set_duration(content_duration) # Duração apenas do conteúdo
                                         .set_position(config.LOGO_POSITION_WATERMARK)
                                         .margin(left=config.LOGO_MARGIN_WATERMARK, right=config.LOGO_MARGIN_WATERMARK,
                                                 top=config.LOGO_MARGIN_WATERMARK, bottom=config.LOGO_MARGIN_WATERMARK, opacity=0) # Margem transparente
                                         .set_opacity(config.LOGO_OPACITY_WATERMARK)
                                         .set_fps(config.VIDEO_FPS)
                                         .set_start(intro_duration)) # <<< DEFINE O INÍCIO APÓS A INTRO

                    # Não adiciona o clipe transformado à lista de fechar, só o base.
                    video_elements_content.append(logo_watermark_clip)
                    print("Marca d'água (WebP) adicionada.")
                except Exception as e:
                    print(f"AVISO: Falha ao carregar ou processar logo WebP para marca d'água: {e}")
                    print("       Verifique se 'libwebp' está instalado e o Pillow o suporta.")
                    # Limpa ref base se falhou após criar
                    if temp_logo_wm_base and temp_logo_wm_base in clips_to_close:
                        clips_to_close.remove(temp_logo_wm_base)
                        if hasattr(temp_logo_wm_base, 'close'): temp_logo_wm_base.close()
            else:
                 print(f"Aviso: Marca d'água habilitada, mas arquivo do logo não encontrado: {logo_path}")


        # 5. Ajusta e Adiciona Clipes de Texto da Narração (com offset - igual a antes)
        print("Ajustando e adicionando clipes de texto...")
        text_clips_added_count = 0
        for i, text_clip in enumerate(narration_text_clips):
            if text_clip is None or not hasattr(text_clip, 'start') or not hasattr(text_clip, 'duration'):
                print(f"Aviso: Clipe de texto inválido no índice {i}, pulando.")
                # Adiciona para fechar mesmo se inválido, caso tenha sido carregado parcialmente
                if text_clip and hasattr(text_clip,'close'): clips_to_close.append(text_clip)
                continue

            clips_to_close.append(text_clip) # Adiciona original para fechar

            original_start = text_clip.start
            original_duration = text_clip.duration

            new_start = original_start + intro_duration
            max_end_time = final_duration

            if new_start >= max_end_time: continue

            new_duration = min(original_duration, max_end_time - new_start)

            if new_duration > 0.01:
                try:
                    # Cria uma CÓPIA para ajustar start/duration
                    # É importante copiar para não modificar o clipe original na lista narration_text_clips
                    adjusted_clip = (text_clip.copy()
                                     .set_start(new_start)
                                     .set_duration(new_duration)
                                     .set_fps(config.VIDEO_FPS))
                    video_elements_content.append(adjusted_clip)
                    text_clips_added_count += 1
                except Exception as clip_e:
                    print(f"Erro ao ajustar clipe de texto {i} (start={original_start:.2f}): {clip_e}")

        print(f"Adicionados {text_clips_added_count} clipes de texto e {len(video_elements_content) - text_clips_added_count} outros elementos (logo?) ao conteúdo.")


        # 6. Compõe Vídeo Final (Background + Intro + Elementos de Conteúdo)
        print("Compondo vídeo final...")
        if not intro_clip or not hasattr(intro_clip, 'duration') or intro_clip.duration <= 0: raise ValueError("Clipe de introdução inválido para composição.")
        if not bg_clip_prepared or not hasattr(bg_clip_prepared, 'duration') or bg_clip_prepared.duration <= 0: raise ValueError("Clipe de fundo preparado inválido para composição.")

        final_composite_elements = [
            bg_clip_prepared, # Fundo cobre toda a duração
            intro_clip.set_start(0).set_duration(intro_duration), # Intro no início
            *video_elements_content # Texto e Logo já têm start e duration definidos
        ]

        final_clip_no_audio = CompositeVideoClip(final_composite_elements, size=config.VIDEO_SIZE)
        final_clip_no_audio = final_clip_no_audio.set_duration(final_duration).set_fps(config.VIDEO_FPS)
        # Não adiciona final_clip_no_audio para fechar ainda, será usado para criar final_clip
        print(f"Vídeo base composto (Duração: {final_clip_no_audio.duration:.2f}s)")


        # 7. Prepara Áudio Final (Música + Narração - Lógica original mantida)
        print("Preparando áudio final...")
        audio_clips_to_compose = []
        bg_music_final_for_compose = None

        if config.USE_BG_MUSIC and config.BG_MUSIC_FILE.exists():
            bg_music_processed = None
            try:
                print(f"Processando música de fundo: {config.BG_MUSIC_FILE.name}")
                bg_music_base = AudioFileClip(str(config.BG_MUSIC_FILE))
                clips_to_close.append(bg_music_base)

                # Aplica volume ANTES de loop/corte
                bg_music_volumed = bg_music_base.fx(afx.volumex, config.BG_MUSIC_VOLUME)
                # O resultado de fx não é adicionado para fechar automaticamente

                if bg_music_base.duration < final_duration - 0.1:
                    num_loops = math.ceil(final_duration / bg_music_base.duration)
                    print(f"Looping música de fundo {num_loops}x (com volume aplicado)...")
                    looped_clips = [bg_music_volumed.copy().set_start(i * bg_music_base.duration) for i in range(num_loops)]
                    # Adiciona as cópias para fechar
                    clips_to_close.extend(looped_clips)
                    bg_music_processed = CompositeAudioClip(looped_clips).set_duration(final_duration)
                    # CompositeAudioClip não precisa ser adicionado para fechar explicitamente aqui
                elif bg_music_base.duration > final_duration:
                    print(f"Cortando música de fundo (com volume aplicado) para {final_duration:.2f}s.")
                    bg_music_processed = bg_music_volumed.subclip(0, final_duration)
                    # Resultado de subclip não precisa add para fechar
                else:
                    bg_music_processed = bg_music_volumed # Usa o clipe com volume

                bg_music_final_for_compose = bg_music_processed
                print(f"Música de fundo processada (Volume: {config.BG_MUSIC_VOLUME * 100:.0f}%)")

            except Exception as e:
                print(f"Erro CRÍTICO ao processar música de fundo: {e}")
                bg_music_final_for_compose = None
                # Tenta fechar base se foi aberto
                if bg_music_base and bg_music_base in clips_to_close:
                    clips_to_close.remove(bg_music_base)
                    if hasattr(bg_music_base, 'close'): bg_music_base.close()

        elif config.USE_BG_MUSIC:
            print("Aviso: Música de fundo habilitada mas arquivo não encontrado.")

        if bg_music_final_for_compose:
            audio_clips_to_compose.append(bg_music_final_for_compose)

        if narration_audio and hasattr(narration_audio, 'duration') and narration_audio.duration > 0:
            print(f"Posicionando narração (Duração: {narration_audio.duration:.2f}s) em t={intro_duration:.2f}s...")
            narration_positioned = narration_audio.set_start(intro_duration)
            audio_clips_to_compose.append(narration_positioned)
        else:
             print("Aviso: Áudio de narração inválido ou com duração zero. Não será adicionado.")

        if not audio_clips_to_compose:
            print("Aviso: Nenhum clipe de áudio para compor. Vídeo final ficará mudo.")
            final_audio = None
        else:
            print(f"Compondo áudio final a partir de {len(audio_clips_to_compose)} clipes...")
            try:
                valid_audio_clips = []
                for idx, clip in enumerate(audio_clips_to_compose):
                    # Verifica se é um clipe de áudio válido
                    if clip and hasattr(clip, 'duration') and clip.duration > 0 and hasattr(clip, 'get_frame'): # get_frame é um check básico
                        valid_audio_clips.append(clip)
                    else:
                        print(f"Aviso: Removendo clipe de áudio inválido na posição {idx} antes da composição.")
                if not valid_audio_clips:
                     print("Erro: Nenhum clipe de áudio válido restante para composição.")
                     final_audio = None
                else:
                    final_audio = CompositeAudioClip(valid_audio_clips).set_duration(final_duration)
                    print(f"Áudio final composto (Duração: {final_audio.duration:.2f}s)")
            except Exception as audio_comp_err:
                 print(f"Erro CRÍTICO ao compor áudio final: {audio_comp_err}")
                 import traceback
                 traceback.print_exc()
                 final_audio = None

        # 8. Define Áudio e Duração Final do Clipe de Vídeo
        print("Finalizando clipe de vídeo (definindo áudio e duração)...")
        if final_audio and hasattr(final_audio, 'duration') and final_audio.duration > 0:
            final_clip = final_clip_no_audio.set_audio(final_audio)
        else:
            final_clip = final_clip_no_audio.without_audio()
            print("Clipe final não terá áudio.")

        # Adiciona o clipe base (sem audio) e o final (com audio) para fechar
        clips_to_close.append(final_clip_no_audio)
        clips_to_close.append(final_clip)

        final_clip = final_clip.set_duration(final_duration)

        if not hasattr(final_clip, 'duration') or final_clip.duration <= 0 or not hasattr(final_clip, 'get_frame'):
             raise ValueError("Clipe final inválido antes da renderização.")

        # 9. Escreve Arquivo Final
        print(f"Renderizando vídeo final em {output_path}...")
        render_start_time = time.time()
        final_clip.write_videofile(
            str(output_path),
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            fps=config.VIDEO_FPS,
            threads=config.VIDEO_THREADS,
            preset=config.VIDEO_PRESET,
            logger='bar',
            ffmpeg_params=["-crf", str(config.VIDEO_CRF)] # Parâmetros CRF mantidos
        )
        render_end_time = time.time()
        print(f"Renderização levou {render_end_time - render_start_time:.2f}s")

        end_time = time.time()
        print(f"\n✅ Vídeo final montado com sucesso!")
        print(f"Tempo total de montagem: {end_time - start_time:.2f} segundos.")
        return True

    except Exception as e:
        print(f"\n--- ERRO DURANTE A MONTAGEM DO VÍDEO ---")
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\nFechando clipes e liberando recursos da montagem...")
        closed_clips_count = 0
        # Itera sobre uma cópia da lista para poder modificar original se necessário
        for clip in list(clips_to_close):
            # Verifica se o clipe ainda está na lista (pode ter sido removido em caso de erro)
            if clip in clips_to_close and hasattr(clip, 'close'):
                try:
                    clip.close()
                    closed_clips_count += 1
                    clips_to_close.remove(clip) # Remove da lista após fechar
                except Exception as close_err:
                    print(f"Erro menor ao fechar clipe: {close_err}")
            # Garante que clipes finais sejam fechados (mesmo que não estivessem na lista original)
            elif clip is final_clip and hasattr(clip, 'close'):
                 try: clip.close(); closed_clips_count += 1
                 except Exception: pass
            elif clip is final_clip_no_audio and hasattr(clip, 'close'):
                 try: clip.close(); closed_clips_count += 1
                 except Exception: pass

        import gc
        collected = gc.collect()
        print(f"Fechamento concluído. Tentativa de fechar {closed_clips_count} clipes. Coletados {collected} objetos.")