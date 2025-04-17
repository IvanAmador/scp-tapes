# video_pipeline/video_composer.py
import os
from moviepy.editor import (VideoFileClip, AudioFileClip, concatenate_videoclips,
                            CompositeVideoClip, ImageClip, ColorClip,
                            CompositeAudioClip)
from typing import List, Union
from pathlib import Path
import numpy as np
import config
import time
import math

def assemble_video(intro_clip: CompositeVideoClip | ColorClip, # Pode ser ColorClip do fallback
                   intro_duration: float, # <<< DURAÇÃO REAL DA INTRO ADICIONADA
                   background_video_path: Path,
                   narration_path: Path,
                   narration_text_clips: List[Union[ImageClip, CompositeVideoClip]],
                   output_path: Path,
                   final_duration: float) -> bool:
    """
    Monta o vídeo final usando durações precisas e posicionando clipes corretamente.

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
    # Adiciona clipe de intro recebido à lista de fechamento (será fechado no finally de generate_scp_video)
    # Não precisa adicionar aqui, pois o chamador é responsável por ele.
    final_clip = None
    narration_audio = None
    narration_audio_original = None
    bg_clip_full = None
    bg_clip_prepared = None
    logo_watermark_clip = None
    temp_logo_wm = None
    main_content_video = None # Clipe da parte do conteúdo (BG + Texto + Logo)
    final_audio = None
    bg_music_final = None

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
             # subclip corta, set_duration estende com silêncio
             narration_audio = narration_audio_original.subclip(0, content_duration) if narration_audio_original.duration > content_duration else narration_audio_original.set_duration(content_duration)
             clips_to_close.append(narration_audio) # Adiciona o clipe ajustado para fechar
        else:
             narration_audio = narration_audio_original # Usa o original

        # 3. Carregar e Preparar VÍDEO de Background para DURAÇÃO TOTAL
        # O background precisa cobrir Intro + Conteúdo
        print("Carregando e preparando vídeo de background...")
        if not background_video_path.exists(): raise FileNotFoundError(f"Vídeo de fundo não encontrado: {background_video_path}")
        if os.path.getsize(background_video_path) == 0: raise ValueError("Vídeo de fundo vazio.")

        try:
            # Carrega o vídeo completo
            bg_clip_full = VideoFileClip(str(background_video_path), audio=False)
            clips_to_close.append(bg_clip_full)
            if bg_clip_full.duration < final_duration - 0.1: # Verifica se tem duração suficiente
                 print(f"AVISO: Vídeo de fundo ({bg_clip_full.duration:.2f}s) é mais curto que a duração final ({final_duration:.2f}s). A parte final pode ficar preta.")
                 # Poderia fazer loop aqui se desejado, mas por ora só avisa

            # Prepara o clipe (redimensiona/corta se necessário) para o tamanho do vídeo
            bg_clip_prepared = bg_clip_full
            if bg_clip_full.size != config.VIDEO_SIZE:
                print(f"Aviso: Redimensionando/cortando background de {bg_clip_full.size} para {config.VIDEO_SIZE}.")
                bg_processed = bg_clip_full.resize(height=config.VIDEO_HEIGHT)
                if bg_processed.w < config.VIDEO_WIDTH:
                    bg_processed.close()
                    bg_processed = bg_clip_full.resize(width=config.VIDEO_WIDTH)
                bg_clip_prepared = bg_processed.crop(x_center=bg_processed.w / 2, y_center=bg_processed.h / 2,
                                                    width=config.VIDEO_WIDTH, height=config.VIDEO_HEIGHT)
                clips_to_close.append(bg_clip_prepared) # Adiciona processado para fechar

            # Define FPS e DURAÇÃO FINAL para o clipe de fundo que será usado
            bg_clip_prepared = bg_clip_prepared.set_fps(config.VIDEO_FPS).set_duration(final_duration)
            print(f"Background preparado (Duração: {bg_clip_prepared.duration:.2f}s)")

        except Exception as e:
            raise ValueError(f"Falha ao carregar/processar vídeo de fundo: {e}")

        # 4. Cria Logo Marca d'água (para a DURAÇÃO DO CONTEÚDO)
        video_elements_content = [] # Elementos que vão *sobre* o fundo na parte do conteúdo
        if config.USE_LOGO_WATERMARK and config.SCP_LOGO_FILE.exists():
            try:
                logo_width = int(config.VIDEO_WIDTH * config.LOGO_SIZE_FACTOR_WATERMARK)
                # Usa 'with' para garantir fechamento do ImageClip original
                with ImageClip(str(config.SCP_LOGO_FILE)).resize(width=logo_width) as temp_logo_wm:
                    logo_watermark_clip = (temp_logo_wm.copy() # Copia para poder usar fora do with
                                     .set_duration(content_duration) # Duração apenas do conteúdo
                                     .set_position(config.LOGO_POSITION_WATERMARK)
                                     .margin(left=config.LOGO_MARGIN_WATERMARK, right=config.LOGO_MARGIN_WATERMARK,
                                             top=config.LOGO_MARGIN_WATERMARK, bottom=config.LOGO_MARGIN_WATERMARK, opacity=0)
                                     .set_opacity(config.LOGO_OPACITY_WATERMARK)
                                     .set_fps(config.VIDEO_FPS)
                                     .set_start(intro_duration)) # <<< DEFINE O INÍCIO APÓS A INTRO
                    clips_to_close.append(logo_watermark_clip)
                    video_elements_content.append(logo_watermark_clip)
                    print("Marca d'água adicionada.")
            except Exception as e:
                print(f"Aviso: Falha ao criar marca d'água: {e}")
                if logo_watermark_clip and hasattr(logo_watermark_clip,'close'): logo_watermark_clip.close()

        elif config.USE_LOGO_WATERMARK:
             print(f"Aviso: Arquivo do logo não encontrado: {config.SCP_LOGO_FILE}")

        # 5. Ajusta e Adiciona Clipes de Texto da Narração (com offset)
        print("Ajustando e adicionando clipes de texto...")
        for i, text_clip in enumerate(narration_text_clips):
            if text_clip is None or not hasattr(text_clip, 'start') or not hasattr(text_clip, 'duration'):
                print(f"Aviso: Clipe de texto inválido no índice {i}, pulando.")
                if text_clip and hasattr(text_clip,'close'): clips_to_close.append(text_clip)
                continue

            clips_to_close.append(text_clip) # Adiciona original para fechar

            original_start = text_clip.start
            original_duration = text_clip.duration

            # Calcula novo início com offset da intro
            new_start = original_start + intro_duration
            # Calcula novo fim máximo (fim do vídeo)
            max_end_time = final_duration

            # Se o clipe começa depois do fim do vídeo, ignora
            if new_start >= max_end_time:
                continue

            # Calcula a duração ajustada para não ultrapassar o fim
            new_duration = min(original_duration, max_end_time - new_start)

            if new_duration > 0.01: # Duração mínima
                try:
                    adjusted_clip = (text_clip.copy()
                                     .set_start(new_start)
                                     .set_duration(new_duration)
                                     .set_fps(config.VIDEO_FPS))
                    # Não adiciona adjusted_clip a clips_to_close (é cópia)
                    video_elements_content.append(adjusted_clip)
                except Exception as clip_e:
                    print(f"Erro ao ajustar clipe de texto {i} (start={original_start:.2f}): {clip_e}")

        print(f"Adicionados {len(video_elements_content)} elementos (texto/logo) ao conteúdo.")

        # 6. Compõe Vídeo Final (Background + Intro + Elementos de Conteúdo)
        print("Compondo vídeo final...")

        # Garante que intro_clip é válido
        if not intro_clip or not hasattr(intro_clip, 'duration') or intro_clip.duration <= 0:
             raise ValueError("Clipe de introdução inválido para composição.")
         # Garante que o clipe de fundo preparado é válido
        if not bg_clip_prepared or not hasattr(bg_clip_prepared, 'duration') or bg_clip_prepared.duration <= 0:
             raise ValueError("Clipe de fundo preparado inválido para composição.")

        # Lista de elementos para o CompositeVideoClip final
        final_composite_elements = [
            bg_clip_prepared, # Fundo cobre toda a duração
            intro_clip.set_start(0).set_duration(intro_duration), # Intro no início
            *video_elements_content # Texto e Logo já têm start e duration definidos
        ]

        # Cria o clipe composto final SEM ÁUDIO por enquanto
        final_clip_no_audio = CompositeVideoClip(final_composite_elements, size=config.VIDEO_SIZE)
        # Define a duração final EXATA
        final_clip_no_audio = final_clip_no_audio.set_duration(final_duration).set_fps(config.VIDEO_FPS)
        clips_to_close.append(final_clip_no_audio) # Adiciona para fechar
        print(f"Vídeo base composto (Duração: {final_clip_no_audio.duration:.2f}s)")


        # 7. Prepara Áudio Final (Música + Narração)
        print("Preparando áudio final...")
        audio_clips_to_compose = []
        bg_music_final_for_compose = None # Guarda o clipe final da música a ser adicionado

        # Música de fundo (se habilitada)
        if config.USE_BG_MUSIC and config.BG_MUSIC_FILE.exists():
            bg_music_base = None # Referência ao clipe original
            bg_music_processed = None # Referência ao clipe após volume/corte/loop
            try:
                print(f"Processando música de fundo: {config.BG_MUSIC_FILE.name}")
                bg_music_base = AudioFileClip(str(config.BG_MUSIC_FILE))
                clips_to_close.append(bg_music_base) # Adiciona original para fechar

                # --- PASSO 1: Aplicar Volume PRIMEIRO ---
                bg_music_volumed = bg_music_base.volumex(config.BG_MUSIC_VOLUME)
                # Não adiciona a clips_to_close, pois é resultado de fx

                # --- PASSO 2: Loop ou Cortar o clipe JÁ COM VOLUME ---
                if bg_music_base.duration < final_duration - 0.1: # Precisa de loop (comparar com original)
                    num_loops = math.ceil(final_duration / bg_music_base.duration)
                    print(f"Looping música de fundo (já com volume) {num_loops}x...")
                    # Cria loops a partir do clipe JÁ COM VOLUME
                    looped_clips = []
                    for i in range(num_loops):
                         # Copia o clipe com volume para cada instância do loop
                         loop_instance = bg_music_volumed.copy().set_start(i * bg_music_base.duration)
                         looped_clips.append(loop_instance)
                         clips_to_close.append(loop_instance) # Adiciona cópias para fechar

                    # Compõe os loops
                    bg_music_processed = CompositeAudioClip(looped_clips).set_duration(final_duration)
                    # Não adiciona CompositeAudioClip a clips_to_close
                    print("Loop da música de fundo composto.")
                elif bg_music_base.duration > final_duration:
                     # Corta o clipe JÁ COM VOLUME
                     print(f"Cortando música de fundo (já com volume) para {final_duration:.2f}s.")
                     bg_music_processed = bg_music_volumed.subclip(0, final_duration)
                     clips_to_close.append(bg_music_processed) # Adiciona subclip para fechar
                else:
                     # Duração OK, usa o clipe com volume diretamente
                     bg_music_processed = bg_music_volumed
                     # Não precisa adicionar a clips_to_close de novo

                # Guarda a referência final para adicionar à composição
                bg_music_final_for_compose = bg_music_processed
                print(f"Música de fundo processada (Volume: {config.BG_MUSIC_VOLUME * 100:.0f}%)")

            except Exception as e:
                print(f"Erro CRÍTICO ao processar música de fundo: {e}")
                # Tenta fechar o que foi aberto
                if bg_music_base and hasattr(bg_music_base, 'close'): bg_music_base.close()
                if bg_music_processed and hasattr(bg_music_processed, 'close'): bg_music_processed.close()
                # Não adiciona à composição
                bg_music_final_for_compose = None
        elif config.USE_BG_MUSIC:
             print("Aviso: Música de fundo habilitada mas arquivo não encontrado.")

        # Adiciona a música processada (se existir) à lista de composição
        if bg_music_final_for_compose:
             audio_clips_to_compose.append(bg_music_final_for_compose)


        # Narração (posicionada após a intro)
        if narration_audio and hasattr(narration_audio, 'duration') and narration_audio.duration > 0:
            print(f"Posicionando narração (Duração: {narration_audio.duration:.2f}s) em t={intro_duration:.2f}s...")
            narration_positioned = narration_audio.set_start(intro_duration)
            audio_clips_to_compose.append(narration_positioned)
        else:
             print("Aviso: Áudio de narração inválido ou com duração zero. Não será adicionado.")


        # Compõe o áudio final
        if not audio_clips_to_compose:
            print("Aviso: Nenhum clipe de áudio para compor. Vídeo final ficará mudo.")
            final_audio = None
        else:
            print(f"Compondo áudio final a partir de {len(audio_clips_to_compose)} clipes...")
            try:
                # Garante que todos os clipes na lista são válidos
                valid_audio_clips = []
                for idx, clip in enumerate(audio_clips_to_compose):
                    if clip and hasattr(clip, 'duration') and clip.duration > 0 and hasattr(clip, 'get_frame'):
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
                 final_audio = None # Falhou

        # ... (Restante da Seção 8, 9 como antes: definir áudio no clipe, renderizar) ...

        # 8. Define Áudio e Duração Final do Clipe de Vídeo
        print("Finalizando clipe de vídeo (definindo áudio e duração)...")
        # ... (código para set_audio ou without_audio como antes) ...
        if final_audio and hasattr(final_audio, 'duration') and final_audio.duration > 0:
            final_clip = final_clip_no_audio.set_audio(final_audio)
        else:
            final_clip = final_clip_no_audio.without_audio()
            print("Clipe final não terá áudio.")
        final_clip = final_clip.set_duration(final_duration)

        # ... (verificação final e renderização write_videofile como antes) ...
        if not hasattr(final_clip, 'duration') or final_clip.duration <= 0 or not hasattr(final_clip, 'get_frame'):
             raise ValueError("Clipe final inválido antes da renderização.")

        # 9. Escreve Arquivo Final
        print(f"Renderizando vídeo final em {output_path}...")
        # ... (código write_videofile como antes) ...
        final_clip.write_videofile(
            str(output_path),
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            fps=config.VIDEO_FPS,
            threads=config.VIDEO_THREADS,
            preset=config.VIDEO_PRESET,
            logger='bar',
            ffmpeg_params=["-crf", str(config.VIDEO_CRF)]
        )

        end_time = time.time()
        print(f"\n✅ Vídeo final montado com sucesso!")
        print(f"Tempo total de montagem: {end_time - start_time:.2f} segundos.")
        return True

    # ... (bloco except e finally como antes) ...
    except Exception as e:
        print(f"\n--- ERRO DURANTE A MONTAGEM DO VÍDEO ---")
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\nFechando clipes e liberando recursos da montagem...")
        closed_clips_count = 0
        if final_clip and hasattr(final_clip, 'close'):
             try: final_clip.close(); closed_clips_count += 1
             except Exception: pass
        for clip in reversed(clips_to_close):
            if clip and hasattr(clip, 'close'):
                try: clip.close(); closed_clips_count += 1
                except Exception: pass
        import gc
        collected = gc.collect()
        print(f"Fechamento concluído. Tentativa de fechar {closed_clips_count} clipes. Coletados {collected} objetos.")