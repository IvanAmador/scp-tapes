# video_pipeline/video_composer.py
import os
from moviepy.editor import (VideoFileClip, AudioFileClip, concatenate_videoclips,
                            CompositeVideoClip, VideoClip, ImageClip, ColorClip,
                            AudioClip, CompositeAudioClip)
from typing import List, Union
from pathlib import Path
import config
import time

def get_dev_mode_duration(audio_clip, default_duration=None):
    """
    Retorna a duração limitada pelo modo dev, se aplicável.
    
    Args:
        audio_clip: Clipe de áudio cujo tempo queremos limitar
        default_duration: Duração padrão para usar se o clipe for None
        
    Returns:
        Duração ajustada conforme modo dev ou duração original
    """
    if audio_clip is None and default_duration is None:
        return 0.0
        
    duration = audio_clip.duration if audio_clip is not None else default_duration
    
    # Verifica se estamos em modo dev
    if hasattr(config, 'DEV_MODE') and config.DEV_MODE and hasattr(config, 'DEV_MODE_VIDEO_DURATION'):
        max_duration = config.DEV_MODE_VIDEO_DURATION
        if duration > max_duration:
            print(f"⚠️ Modo DEV: Limitando duração do áudio de {duration:.2f}s para {max_duration}s")
            return max_duration
    
    return duration

def assemble_video(intro_clip: CompositeVideoClip, background_video_path: Path,
                   narration_path: Path, subtitle_clips: List[Union[ImageClip, CompositeVideoClip]],
                   output_path: Path) -> bool:
    """ Monta o vídeo final, evitando subclip explícito para o fundo. """
    # Lista simplificada para fechamento
    clips_to_close = []
    final_clip = None
    narration_audio = None
    logo_watermark_clip = None
    valid_subtitle_clips_refs = []
    bg_clip_full = None # Referência para o clipe de fundo completo
    temp_logo_wm = None
    narration_audio_original = None
    intro_clip_adjusted = None # Referência para intro ajustada
    main_content_video = None # Referência para vídeo de conteúdo
    final_clip_no_audio = None # Referência para vídeo sem áudio

    try:
        start_time = time.time()
        print(f"Iniciando montagem do vídeo final: {output_path.name}...")
        clips_to_close.append(intro_clip) # Adiciona intro original para fechar

        # 1. Carrega Narração e obtém duração
        print("Carregando narração...")
        if not narration_path.exists(): raise FileNotFoundError(f"Narração não encontrada: {narration_path}")
        narration_audio = AudioFileClip(str(narration_path))
        clips_to_close.append(narration_audio) # Adiciona para fechar
        
        # Verifica limitação de duração em modo dev
        original_duration = narration_audio.duration
        content_duration = get_dev_mode_duration(narration_audio)
        
        # Se houve limitação, cria um subclip
        if content_duration < original_duration:
            narration_audio_original = narration_audio  # Guarda referência
            clips_to_close.append(narration_audio_original)  # Garante que original será fechado
            narration_audio = narration_audio.subclip(0, content_duration)
            clips_to_close.append(narration_audio)  # Adiciona o subclip também
        else:
            content_duration = original_duration
            
        print(f"Duração da narração: {content_duration:.2f}s")
        total_duration_calc = intro_clip.duration + content_duration
        max_allowed_duration = config.MAX_VIDEO_DURATION_SECONDS
        if total_duration_calc > max_allowed_duration:
             print(f"Aviso: Duração calculada ({total_duration_calc:.2f}s) excede o limite ({max_allowed_duration}s). Ajustando...")
             allowed_content_duration = max(0, max_allowed_duration - intro_clip.duration)
             if allowed_content_duration <= 0: raise ValueError(f"Duração da intro ({intro_clip.duration}s) já excede ou iguala o limite máximo ({max_allowed_duration}s).")
             narration_audio_original = narration_audio # Guarda referência
             clips_to_close.append(narration_audio_original) # Garante que original será fechado
             narration_audio = narration_audio.subclip(0, allowed_content_duration)
             clips_to_close.append(narration_audio) # Adiciona o subclip também
             print(f"Áudio cortado para {allowed_content_duration:.2f}s")
             content_duration = allowed_content_duration

        # 2. Carrega o VÍDEO de Background
        print("Carregando vídeo de background...")
        if not background_video_path.exists(): raise FileNotFoundError(f"Vídeo de fundo não encontrado: {background_video_path}")
        try:
            # Verifique se o arquivo de vídeo é válido
            import os
            if os.path.getsize(background_video_path) == 0:
                raise ValueError(f"Arquivo de vídeo vazio: {background_video_path}")
                
            # Tente carregar o vídeo com diferentes configurações
            try:
                # Primeira tentativa: com target_resolution
                bg_clip_full = VideoFileClip(str(background_video_path), audio=False, target_resolution=(config.VIDEO_HEIGHT, config.VIDEO_WIDTH))
            except Exception as e1:
                print(f"Primeira tentativa falhou: {e1}. Tentando método alternativo...")
                # Segunda tentativa: sem target_resolution
                bg_clip_full = VideoFileClip(str(background_video_path), audio=False)
                
            # Verifique se o leitor foi carregado corretamente
            if bg_clip_full.reader is None:
                raise ValueError(f"Falha ao carregar o leitor de vídeo para {background_video_path}")
                
            # Tente acessar um frame para verificar se o vídeo é válido
            test_frame = bg_clip_full.get_frame(0)
            if test_frame is None:
                raise ValueError("Falha ao obter o primeiro frame do vídeo de fundo")
                
            clips_to_close.append(bg_clip_full) # Adiciona para fechar no final
        except Exception as e:
            print(f"Erro ao carregar vídeo de fundo: {e}")
            raise ValueError(f"Falha ao processar o vídeo de fundo: {e}")

        # Prepara o clipe de fundo para a composição (sem subclip)
        # Redimensiona/Corta se necessário ANTES de definir duração
        bg_clip_prepared = bg_clip_full
        if bg_clip_full.size != config.VIDEO_SIZE:
             print("Aviso: Redimensionando/cortando background.")
             bg_clip_prepared = (bg_clip_full.resize(height=config.VIDEO_HEIGHT)
                                .crop(x_center=bg_clip_full.w / 2, y_center=bg_clip_full.h / 2,
                                      width=config.VIDEO_WIDTH, height=config.VIDEO_HEIGHT))
             # Nota: O redimensionamento/corte cria um novo clipe implicitamente.
             # O bg_clip_full original ainda precisa ser fechado.
             # Adicionamos o preparado também, pois pode ter seu próprio estado.
             clips_to_close.append(bg_clip_prepared)
        # Define FPS e DURAÇÃO desejada para a composição
        bg_clip_prepared = bg_clip_prepared.set_fps(config.VIDEO_FPS).set_duration(content_duration)

        # 3. Cria Logo Marca d'água
        video_elements = [bg_clip_prepared] # Usa o clipe preparado
        if config.USE_LOGO_WATERMARK:
            if config.SCP_LOGO_FILE.exists():
                try:
                    logo_width = int(config.VIDEO_WIDTH * config.LOGO_SIZE_FACTOR_WATERMARK)
                    temp_logo_wm = ImageClip(str(config.SCP_LOGO_FILE)).resize(width=logo_width)
                    clips_to_close.append(temp_logo_wm)
                    logo_watermark_clip = (temp_logo_wm
                                     .set_duration(content_duration)
                                     .set_position(config.LOGO_POSITION_WATERMARK)
                                     .margin(left=config.LOGO_MARGIN_WATERMARK, right=config.LOGO_MARGIN_WATERMARK,
                                             top=config.LOGO_MARGIN_WATERMARK, bottom=config.LOGO_MARGIN_WATERMARK, opacity=0)
                                     .set_opacity(config.LOGO_OPACITY_WATERMARK)
                                     .set_fps(config.VIDEO_FPS))
                    clips_to_close.append(logo_watermark_clip)
                    video_elements.append(logo_watermark_clip)
                    print("Marca d'água do logo adicionada.")
                except Exception as e:
                    print(f"Aviso: Falha ao criar/adicionar marca d'água do logo: {e}")
                    # Fechar manualmente aqui em caso de erro nesta etapa
                    if logo_watermark_clip: logo_watermark_clip.close()
                    if temp_logo_wm: temp_logo_wm.close()
                    logo_watermark_clip = None # Garante que não será adicionado
            else:
                 print(f"Aviso: Arquivo do logo não encontrado em {config.SCP_LOGO_FILE}. Marca d'água não adicionada.")

        # 4. Compõe vídeo principal (Fundo + Logo? + Legendas)
        print("Compondo vídeo principal com legendas...")
        valid_subtitle_clips = []
        for sub in subtitle_clips:
             if sub is None or not hasattr(sub, 'start') or not hasattr(sub, 'duration'):
                 print("Aviso: Legenda inválida encontrada, pulando.")
                 clips_to_close.append(sub) # Adiciona para tentar fechar mesmo assim
                 continue
             sub_start = sub.start
             sub_duration = sub.duration
             clips_to_close.append(sub) # Adiciona legenda original para fechar
             if sub_start < content_duration:
                 new_duration = sub_duration
                 if sub_start + sub_duration > content_duration:
                     new_duration = content_duration - sub_start
                 if new_duration > 0.05:
                     adjusted_sub = sub.set_duration(new_duration).set_fps(config.VIDEO_FPS)
                     valid_subtitle_clips.append(adjusted_sub)
                     # Não adicionamos adjusted_sub à lista clips_to_close explicitamente
                     # pois ele é derivado de 'sub' que já está na lista.
                     valid_subtitle_clips_refs.append(sub) # Mantém referência original

        video_elements.extend(valid_subtitle_clips)
        main_content_video = CompositeVideoClip(video_elements, size=config.VIDEO_SIZE)
        main_content_video = main_content_video.set_duration(content_duration).set_fps(config.VIDEO_FPS)
        clips_to_close.append(main_content_video) # Adiciona para fechar

        # 5. Ajusta Intro
        print("Ajustando introdução...")
        # Verifica se o clipe de intro é válido
        intro_is_valid = True
        try:
            # Tenta acessar um frame para verificar se o clipe é válido
            test_frame = intro_clip.get_frame(0)
            if test_frame is None:
                raise ValueError("Intro inválida: frame nulo")
        except Exception as e:
            print(f"Aviso: Intro inválida, criando substituto: {e}")
            intro_is_valid = False
            
        if intro_is_valid:
            # Usa o clipe de intro original
            intro_clip_adjusted = intro_clip # Assume que é o mesmo por padrão
            if intro_clip.size != config.VIDEO_SIZE or intro_clip.duration != config.INTRO_DURATION:
                 print("Aviso: Redimensionando/ajustando duração da intro.")
                 try:
                     intro_clip_adjusted = (intro_clip.resize(height=config.VIDEO_HEIGHT)
                                  .crop(x_center=intro_clip.w / 2, y_center=intro_clip.h / 2,
                                        width=config.VIDEO_WIDTH, height=config.VIDEO_HEIGHT)
                                  .set_duration(config.INTRO_DURATION)
                                  .set_fps(config.VIDEO_FPS))
                     clips_to_close.append(intro_clip_adjusted) # Adiciona ajustado para fechar
                 except Exception as resize_e:
                     print(f"Erro ao redimensionar intro: {resize_e}")
                     intro_is_valid = False
        
        # Se a intro for inválida, cria uma nova intro simples
        if not intro_is_valid:
            print("Criando intro substituta (cor sólida)...")
            intro_clip_adjusted = ColorClip(size=config.VIDEO_SIZE, 
                                           color=config.INTRO_BACKGROUND_COLOR, 
                                           duration=config.INTRO_DURATION).set_fps(config.VIDEO_FPS)
            clips_to_close.append(intro_clip_adjusted)

        # 6. Concatena Intro e Conteúdo
        print("Concatenando...")
        # Verificar se os clipes são válidos antes de concatenar
        if not hasattr(intro_clip_adjusted, 'make_frame') or not hasattr(main_content_video, 'make_frame'):
            raise ValueError("Clipes de intro ou conteúdo principal inválidos")
            
        # Tente acessar um frame de cada clipe para verificar se estão válidos
        try:
            intro_test_frame = intro_clip_adjusted.get_frame(0)
            main_test_frame = main_content_video.get_frame(0)
        except Exception as e:
            print(f"Erro ao verificar frames dos clipes: {e}")
            # Em vez de falhar, tente uma abordagem alternativa
            print("Tentando método alternativo de composição...")
            try:
                intro_duration = intro_clip_adjusted.duration
                main_duration = main_content_video.duration
                total_duration = intro_duration + main_duration
                
                # Crie um novo clipe composto com os elementos em posições temporais específicas
                final_clip_no_audio = CompositeVideoClip([
                    intro_clip_adjusted.set_start(0),
                    main_content_video.set_start(intro_duration)
                ], size=config.VIDEO_SIZE).set_duration(total_duration)
                
                # Teste se o clipe resultante é válido
                test_frame = final_clip_no_audio.get_frame(0)
                clips_to_close.append(final_clip_no_audio)
            except Exception as alt_e:
                print(f"Método alternativo também falhou: {alt_e}")
                raise ValueError(f"Todos os métodos de composição falharam: {e}, {alt_e}")
            return
            
        # Use o método mais simples de concatenação para evitar problemas
        try:
            final_clip_no_audio = concatenate_videoclips(
                [intro_clip_adjusted.set_fps(config.VIDEO_FPS),
                 main_content_video.set_fps(config.VIDEO_FPS)],
                method="compose"
            )
            # Teste imediatamente se o clipe resultante é válido
            test_frame = final_clip_no_audio.get_frame(0)
            clips_to_close.append(final_clip_no_audio) # Adiciona para fechar
        except Exception as e:
            print(f"Erro ao concatenar clipes: {e}")
            # Tente uma abordagem alternativa
            print("Tentando método alternativo de composição após falha na concatenação...")
            try:
                intro_duration = intro_clip_adjusted.duration
                main_duration = main_content_video.duration
                total_duration = intro_duration + main_duration
                
                # Crie um novo clipe composto com os elementos em posições temporais específicas
                final_clip_no_audio = CompositeVideoClip([
                    intro_clip_adjusted.set_start(0),
                    main_content_video.set_start(intro_duration)
                ], size=config.VIDEO_SIZE).set_duration(total_duration)
                
                # Teste se o clipe resultante é válido
                test_frame = final_clip_no_audio.get_frame(0)
                clips_to_close.append(final_clip_no_audio)
            except Exception as alt_e:
                print(f"Método alternativo também falhou: {alt_e}")
                raise ValueError(f"Todos os métodos de composição falharam: {e}, {alt_e}")

        # 7. Adiciona Áudio (narração e música de fundo)
        print("Adicionando áudio...")
        final_audio_duration = intro_clip_adjusted.duration + narration_audio.duration
        
        try:
            audio_clips = []
            
            # Adiciona música de fundo se configurado
            bg_music_clip = None
            if config.USE_BG_MUSIC and config.BG_MUSIC_FILE.exists():
                try:
                    print(f"Carregando música de fundo: {config.BG_MUSIC_FILE}")
                    bg_music_clip = AudioFileClip(str(config.BG_MUSIC_FILE))
                    
                    # Se a música for mais curta que o vídeo, faça um loop
                    if bg_music_clip.duration < final_audio_duration:
                        print("Música de fundo mais curta que o vídeo, criando loop...")
                        # Calcule quantas vezes precisamos repetir a música
                        repeat_count = int(final_audio_duration / bg_music_clip.duration) + 1
                        # Crie clips para cada repetição
                        bg_music_clips = []
                        for i in range(repeat_count):
                            start_time = i * bg_music_clip.duration
                            if start_time < final_audio_duration:
                                clip = bg_music_clip.copy().set_start(start_time)
                                bg_music_clips.append(clip)
                                clips_to_close.append(clip)
                        # Combine os clips em um único clip de áudio
                        bg_music_clip = CompositeAudioClip(bg_music_clips).set_duration(final_audio_duration)
                    else:
                        # Corte a música se for mais longa que o vídeo
                        bg_music_clip = bg_music_clip.subclip(0, final_audio_duration)
                    
                    # Ajuste o volume da música de fundo
                    bg_music_clip = bg_music_clip.volumex(config.BG_MUSIC_VOLUME)
                    clips_to_close.append(bg_music_clip)
                    audio_clips.append(bg_music_clip)
                    print(f"Música de fundo adicionada com volume {config.BG_MUSIC_VOLUME * 100}%")
                except Exception as e:
                    print(f"Erro ao adicionar música de fundo: {e}")
                    if bg_music_clip: bg_music_clip.close()
            else:
                print("Música de fundo não configurada ou arquivo não encontrado.")
            
            # Crie o áudio silencioso para a intro (se não houver música de fundo)
            if not bg_music_clip:
                silent_intro_audio = AudioClip(lambda t: 0, duration=intro_clip_adjusted.duration, fps=44100)
                clips_to_close.append(silent_intro_audio)
                audio_clips.append(silent_intro_audio)
            
            # Adicione a narração com início após a intro
            narration_with_start = narration_audio.set_start(intro_clip_adjusted.duration)
            audio_clips.append(narration_with_start)
            
            # Crie o áudio composto
            final_audio = CompositeAudioClip(audio_clips).set_duration(final_audio_duration)
            clips_to_close.append(final_audio)
            
            # Crie uma cópia do vídeo sem áudio para evitar problemas de referência
            final_clip = final_clip_no_audio.copy()
            
            # Adicione o áudio e defina a duração
            final_clip = final_clip.set_audio(final_audio)
            final_clip = final_clip.set_duration(final_audio_duration)
            
            # Verifique se o clipe final é válido
            if not hasattr(final_clip, 'make_frame'):
                raise ValueError("Clipe final inválido após adicionar áudio")
                
            # Não adiciona final_clip à lista clips_to_close ainda, será fechado no finally
        except Exception as e:
            print(f"Erro ao adicionar áudio: {e}")
            raise ValueError(f"Falha ao adicionar áudio: {e}")

        # 8. Escreve Arquivo Final
        print(f"Escrevendo vídeo final em {output_path} (Duração: {final_clip.duration:.2f}s)...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Verifica se todos os componentes do vídeo estão válidos antes de renderizar
        if final_clip is None or not hasattr(final_clip, 'duration'):
            raise ValueError("Clipe final inválido ou não inicializado corretamente")
        
        # Tente uma abordagem alternativa se o método normal falhar
        try:
            # Tenta acessar o primeiro frame para verificar se o vídeo está válido
            test_frame = final_clip.get_frame(0)
            if test_frame is None:
                raise ValueError("Falha ao obter o primeiro frame do vídeo final")
                
            # Tente escrever o arquivo de vídeo
            final_clip.write_videofile(
                str(output_path),
                codec=config.VIDEO_CODEC,
                audio_codec=config.AUDIO_CODEC,
                fps=config.VIDEO_FPS,
                threads=config.VIDEO_THREADS,
                preset=config.VIDEO_PRESET,
                logger='bar',
                ffmpeg_params=["-crf", config.VIDEO_CRF]
            )
        except Exception as e:
            print(f"Erro ao renderizar vídeo com método padrão: {e}")
            print("Tentando método alternativo de renderização...")
            
            # Tente uma abordagem alternativa: recrie o vídeo do zero
            try:
                # Crie um novo clipe composto diretamente
                print("Criando novo clipe composto para renderização...")
                
                # Recrie o vídeo principal sem usar concatenate_videoclips
                all_elements = []
                
                # Adicione a introdução
                if hasattr(intro_clip_adjusted, 'make_frame'):
                    all_elements.append(intro_clip_adjusted.set_start(0))
                    
                # Adicione o conteúdo principal com deslocamento de tempo
                if hasattr(main_content_video, 'make_frame'):
                    all_elements.append(main_content_video.set_start(intro_clip_adjusted.duration))
                
                if len(all_elements) > 0:
                    # Crie um novo clipe composto
                    new_final_clip = CompositeVideoClip(all_elements, size=config.VIDEO_SIZE)
                    new_final_clip = new_final_clip.set_duration(final_audio_duration)
                    
                    # Adicione o áudio
                    if hasattr(final_audio, 'make_frame'):
                        new_final_clip = new_final_clip.set_audio(final_audio)
                    
                    # Tente renderizar o novo clipe
                    new_final_clip.write_videofile(
                        str(output_path),
                        codec=config.VIDEO_CODEC,
                        audio_codec=config.AUDIO_CODEC,
                        fps=config.VIDEO_FPS,
                        threads=config.VIDEO_THREADS,
                        preset=config.VIDEO_PRESET,
                        logger='bar',
                        ffmpeg_params=["-crf", config.VIDEO_CRF]
                    )
                    
                    # Adicione para fechar
                    clips_to_close.append(new_final_clip)
                    print("Renderização alternativa concluída com sucesso.")
                else:
                    raise ValueError("Não foi possível criar elementos para o método alternativo")
            except Exception as alt_e:
                print(f"Método alternativo também falhou: {alt_e}")
                raise ValueError(f"Todos os métodos de renderização falharam: {e}, {alt_e}")

        end_time = time.time()
        print(f"Vídeo final montado com sucesso em {output_path}!")
        print(f"Tempo total de montagem: {end_time - start_time:.2f} segundos.")
        return True

    except Exception as e:
        print(f"Erro durante a montagem do vídeo: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # FECHAMENTO CENTRALIZADO E CUIDADOSO
        print("Fechando clipes...")
        closed_clips = set() # Para evitar fechar o mesmo clipe duas vezes

        # Primeiro fecha o clipe final se ele foi criado
        if final_clip:
             try:
                 # Certifique-se de que o clipe final é válido antes de tentar fechá-lo
                 if hasattr(final_clip, 'close'):
                     final_clip.close()
                     closed_clips.add(id(final_clip))
                     print("  - Final clip fechado.")
                 else:
                     print("  - Final clip não possui método close.")
             except Exception as e: print(f"Erro ao fechar final_clip: {e}")

        # Fecha todos os outros clipes na lista
        for clip in reversed(clips_to_close): # Fecha em ordem reversa de adição
            if clip and id(clip) not in closed_clips:
                clip_info = f"clipe tipo {type(clip).__name__}"
                # Tenta obter nome do arquivo se for Video/AudioFileClip
                if hasattr(clip, 'filename'): clip_info += f" ({getattr(clip, 'filename', '')})"

                try:
                    clip.close()
                    closed_clips.add(id(clip))
                    # print(f"  - {clip_info} fechado.") # Descomente para log detalhado
                except Exception as e:
                    # Ignora erros comuns de fechamento de clipes já fechados ou inválidos
                    if "cannot close unregistered stream" not in str(e) and \
                       "object has no attribute 'close'" not in str(e):
                         print(f"Erro ao fechar {clip_info}: {e}")
            # elif id(clip) in closed_clips:
            #      print(f"  - Clipe já fechado anteriormente: {type(clip).__name__}")

        # Coleta de lixo
        import gc
        gc.collect()
        print("Fechamento de clipes concluído.")