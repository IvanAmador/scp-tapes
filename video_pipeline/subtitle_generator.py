# video_pipeline/subtitle_generator.py
import openai
# ADICIONADO: Importar Image, Draw, Font do Pillow e ImageClip
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import CompositeVideoClip, ColorClip, ImageClip # Removido TextClip daqui
from pathlib import Path
from typing import List, Dict, Any, Tuple
import config
import os
from dotenv import load_dotenv
import numpy as np

# ... (código do load_dotenv e client OpenAI existente) ...
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY") or config.OPENAI_API_KEY
if not api_key or api_key == "SUA_API_KEY_AQUI": # Corrigido nome da chave placeholder
    print("AVISO: Chave da API OpenAI não configurada no .env ou config.py!")
    client = None
else:
    client = openai.OpenAI(api_key=api_key)

def get_word_timestamps(audio_path: Path) -> List[Dict[str, Any]] | None: # Alterado tipo de retorno para Dict
    """ Obtém timestamps (espera retornar lista de dicts) """
    if not client:
        print("Erro: Cliente OpenAI não inicializado. Verifique a API Key.")
        return None
    if not audio_path.exists():
        print(f"Erro: Arquivo de áudio não encontrado em {audio_path}")
        return None
    try:
        print(f"Obtendo timestamps para: {audio_path.name}...")
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=config.STT_MODEL, # Usando config STT_MODEL
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )

        # Verifica se 'words' existe e não está vazio
        if not transcript or not hasattr(transcript, 'words') or not transcript.words:
            print("Aviso: Resposta da API Whisper não contém timestamps de palavras ('words').")
            # print(f"Resposta completa da API: {transcript}") # Descomente para debug
            return None

        print(f"Timestamps obtidos ({len(transcript.words)} palavras). Processando...")
        # Processa a resposta garantindo o formato dict e corrigindo tempos
        corrected_words = []
        raw_words = transcript.words # Assumindo que words é uma lista

        # IMPORTANTE: A API pode retornar uma lista de objetos Pydantic ou Dicionários
        # Vamos converter tudo para dicionário para consistência
        for i, word_obj in enumerate(raw_words):
            try:
                if isinstance(word_obj, dict):
                    # Já é um dict, apenas pega os valores
                    word_data = word_obj
                elif hasattr(word_obj, 'model_dump'): # Verifica se é um objeto Pydantic v2+
                    word_data = word_obj.model_dump()
                elif hasattr(word_obj, 'dict'): # Verifica se é um objeto Pydantic v1
                     word_data = word_obj.dict()
                elif hasattr(word_obj, 'word') and hasattr(word_obj, 'start') and hasattr(word_obj, 'end'):
                    # Caso seja um objeto simples com atributos
                     word_data = {
                         'word': getattr(word_obj, 'word', ''),
                         'start': getattr(word_obj, 'start', 0.0),
                         'end': getattr(word_obj, 'end', 0.0)
                     }
                else:
                    print(f"Aviso: Formato de palavra inesperado no índice {i}: {word_obj}. Pulando.")
                    continue

                start = float(word_data.get('start', 0.0))
                end = float(word_data.get('end', 0.0))
                word = str(word_data.get('word', '')).strip() # Garante que é string e remove espaços extras

                # Ignora palavras vazias ou com tempos inválidos
                if not word:
                    # print(f"Aviso: Palavra vazia no índice {i}. Pulando.")
                    continue
                # Corrige se start for maior que end (pode acontecer)
                if start > end:
                    # print(f"Aviso: Tempo de início ({start}) > tempo de fim ({end}) para '{word}'. Ajustando end = start.")
                    end = start

                corrected_words.append({
                    'word': word,
                    'start': max(0.0, start), # Garante não negativo
                    'end': max(0.0, end)      # Garante não negativo
                })
            except Exception as e:
                print(f"Erro processando palavra no índice {i}: {word_obj} -> {e}")
                continue # Pula esta palavra em caso de erro

        if not corrected_words:
            print("Aviso: Nenhum timestamp de palavra válido foi extraído após o processamento.")
            return None

        print(f"Processamento concluído. {len(corrected_words)} palavras válidas.")
        return corrected_words

    except openai.AuthenticationError as e:
        print(f"Erro de autenticação OpenAI: Verifique sua API Key. {e}")
        return None
    except Exception as e:
        print(f"Erro ao obter timestamps: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- Função Auxiliar para Criar Texto com PIL ---
def create_subtitle_image(text: str, font_path: str, font_size: int, text_color: str,
                          bg_enabled: bool, bg_color: tuple, bg_opacity: float, padding: int,
                          max_width: int) -> Tuple[np.ndarray | None, int, int]:
    """Cria uma imagem RGBA do texto usando Pillow, com fundo opcional."""
    try:
        # Tenta carregar a fonte
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            print(f"Aviso: Não foi possível carregar a fonte '{font_path}'. Usando fonte padrão.")
            font = ImageFont.load_default()

        # --- Quebra de linha manual simples ---
        lines = []
        current_line = ""
        words = text.split()
        temp_img = Image.new('RGBA', (1, 1)) # Imagem temporária para medir texto
        draw_temp = ImageDraw.Draw(temp_img)
        space_width = draw_temp.textlength(" ", font=font)

        for word in words:
            word_width = draw_temp.textlength(word, font=font)
            line_width = draw_temp.textlength(current_line, font=font)

            if not current_line: # Primeira palavra da linha
                 current_line = word
            # Verifica se adicionar a palavra (com espaço) excede a largura máxima
            elif line_width + space_width + word_width <= max_width:
                 current_line += f" {word}"
            else:
                 # Finaliza linha atual e começa nova com a palavra
                 lines.append(current_line)
                 current_line = word
        lines.append(current_line) # Adiciona a última linha

        # Calcula o tamanho da imagem final baseado nas linhas
        line_height = font.getmetrics()[0] # Altura aproximada da fonte
        total_text_height = len(lines) * line_height
        # Encontra a largura máxima real das linhas renderizadas
        actual_max_width = 0
        for line in lines:
             line_len = draw_temp.textlength(line, font=font)
             if line_len > actual_max_width:
                  actual_max_width = int(line_len)

        # Define tamanho do painel e da imagem
        panel_w = actual_max_width + 2 * padding
        panel_h = total_text_height + 2 * padding
        img_w = panel_w if bg_enabled else actual_max_width
        img_h = panel_h if bg_enabled else total_text_height

        # Cria imagem final transparente
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Desenha o painel de fundo se habilitado
        if bg_enabled:
            panel_fill = (*bg_color[:3], int(255 * bg_opacity)) # Cor RGBA
            # Ajuste para desenhar um retângulo arredondado se quiser
            # draw.rectangle([(0, 0), (img_w, img_h)], fill=panel_fill)
            radius = 10 # Exemplo de raio para cantos arredondados
            draw.rounded_rectangle([(0, 0), (img_w -1 , img_h -1)], radius=radius, fill=panel_fill, outline=None, width=1)


        # Desenha cada linha de texto
        current_y = padding if bg_enabled else 0
        for line in lines:
             line_len = draw_temp.textlength(line, font=font)
             # Centraliza a linha horizontalmente
             pos_x = (img_w - line_len) / 2
             # Desenha sombra (opcional, pode deixar mais lento)
             # shadow_offset = 1
             # draw.text((pos_x + shadow_offset, current_y + shadow_offset), line, font=font, fill=(0,0,0,128))
             # Desenha texto principal
             draw.text((pos_x, current_y), line, font=font, fill=text_color)
             current_y += line_height

        img_array = np.array(img)
        return img_array, img_w, img_h

    except Exception as e:
        print(f"Erro ao criar imagem de legenda com Pillow para '{text[:30]}...': {e}")
        return None, 0, 0


def create_typing_subtitle_clips(word_timestamps: List[Dict[str, Any]],
                                 video_duration: float) -> List[CompositeVideoClip]:
    """ Cria clipes de legendas (modo 'phrase') usando Pillow/ImageClip com melhor formatação. """
    subtitle_clips = []
    if not word_timestamps:
        # Mensagem de aviso já dada em get_word_timestamps se a lista original era vazia
        # ou se o processamento falhou.
        return subtitle_clips

    # Verifica se FONT_SUBTITLE é um caminho válido
    font_path = config.FONT_SUBTITLE
    if not Path(font_path).is_file():
        print(f"AVISO: Arquivo de fonte da legenda não encontrado em '{font_path}'. Usando fonte padrão do sistema.")
        # Tenta usar uma fonte padrão se a personalizada falhar
        # Pillow tentará carregar uma fonte padrão se o caminho for inválido
        # Poderia definir um nome de fonte padrão aqui, como "Arial"
        # font_path = "Arial" # Descomente se quiser forçar Arial como fallback

    print(f"Criando clipes de legenda (Modo: {config.SUBTITLE_MODE} usando Pillow)...")

    # --- Agrupamento melhorado com preservação de pontuação ---
    def group_words_into_phrases(words_list, max_chars):
        phrases = []
        current_phrase_words = []
        current_phrase_text = ""
        phrase_start_time = -1
        
        # Caracteres de pontuação que não devem ter espaço antes
        punctuation_no_space_before = ['.', ',', '!', '?', ':', ';', ')', ']', '}']
        # Caracteres de pontuação que não devem ter espaço depois
        punctuation_no_space_after = ['(', '[', '{']

        for i, word_info in enumerate(words_list):
            word = word_info['word'] # Já deve estar limpa
            start = word_info['start']
            end = word_info['end']

            if phrase_start_time < 0: phrase_start_time = start # Define o início da primeira frase

            # Determina se precisa adicionar espaço antes da palavra
            need_space = True
            if not current_phrase_text:  # Primeira palavra da frase
                need_space = False
            elif word and word[0] in punctuation_no_space_before:  # Palavra começa com pontuação
                need_space = False
            elif current_phrase_text and current_phrase_text[-1] in punctuation_no_space_after:  # Frase termina com pontuação
                need_space = False
                
            # Adiciona a palavra com ou sem espaço
            word_to_add = f" {word}" if need_space else word
            potential_text = current_phrase_text + word_to_add

            # Verifica se adicionar a palavra excede o limite de caracteres
            if len(potential_text) <= max_chars:
                current_phrase_text = potential_text
                current_phrase_words.append(word_info)
                is_last_word = (i == len(words_list) - 1)
                # Finaliza a frase se for a última palavra do áudio
                if is_last_word:
                     phrases.append({
                        'text': current_phrase_text,
                        'start': phrase_start_time,
                        'end': end
                     })
            else:
                # Finaliza a frase atual (sem a palavra nova)
                if current_phrase_words:
                    last_word_end = current_phrase_words[-1]['end']
                    # Garante que o fim da frase não seja antes do início
                    phrase_end_time = max(phrase_start_time, last_word_end)
                    phrases.append({
                        'text': current_phrase_text,
                        'start': phrase_start_time,
                        'end': phrase_end_time
                    })
                # Inicia nova frase com a palavra atual
                current_phrase_words = [word_info]
                current_phrase_text = word
                phrase_start_time = start
                # Se esta palavra sozinha já inicia a última frase
                if i == len(words_list) - 1:
                     phrases.append({
                        'text': current_phrase_text,
                        'start': phrase_start_time,
                        'end': max(phrase_start_time, end) # Garante end >= start
                     })
        return phrases
    # --- Fim do Agrupamento ---

    phrases = group_words_into_phrases(word_timestamps, config.SUBTITLE_MAX_LINE_CHARS)

    if not phrases:
         print("Aviso: Nenhuma frase foi gerada a partir dos timestamps.")
         return []

    # --- Cria Clipes para Cada Frase usando Pillow ---
    for phrase in phrases:
        text = phrase['text']
        start_time = phrase['start']
        end_time = phrase['end']

        clip_duration = max(0.1, end_time - start_time)
        if start_time >= video_duration: continue
        if start_time + clip_duration > video_duration:
            clip_duration = max(0.1, video_duration - start_time)

        if clip_duration <= 0.1: continue

        # Melhora o formato do texto antes de criar a imagem
        # Capitaliza a primeira letra de cada frase se não estiver já capitalizada
        if text and not text[0].isupper() and text[0].isalpha():
            text = text[0].upper() + text[1:]
            
        # Garante que a frase termine com pontuação
        if text and text[-1] not in ['.', '!', '?', ':', ';']:
            text += '.'
            
        # Cria a imagem da legenda usando a função auxiliar
        subtitle_img_array, img_w, img_h = create_subtitle_image(
            text=text,
            font_path=font_path,
            font_size=config.SUBTITLE_FONT_SIZE,
            text_color=config.SUBTITLE_COLOR,
            bg_enabled=config.SUBTITLE_BG_ENABLED,
            bg_color=config.SUBTITLE_BG_COLOR,
            bg_opacity=config.SUBTITLE_BG_OPACITY,
            padding=config.SUBTITLE_PADDING,
            max_width=int(config.VIDEO_WIDTH * 0.9) # Max largura da imagem de texto
        )

        # Se a criação da imagem falhou, pula esta legenda
        if subtitle_img_array is None or img_w == 0 or img_h == 0:
            continue

        # Cria o clipe de imagem a partir do array numpy
        try:
            subtitle_image_clip = ImageClip(subtitle_img_array, ismask=False) # ismask=False para RGBA
            subtitle_image_clip = subtitle_image_clip.set_duration(clip_duration).set_start(start_time)
            # Define a posição final do clipe de legenda
            final_subtitle_clip = subtitle_image_clip.set_position(config.SUBTITLE_POSITION)
            # Define FPS para evitar problemas de concatenação
            final_subtitle_clip = final_subtitle_clip.set_fps(config.VIDEO_FPS)

            subtitle_clips.append(final_subtitle_clip)
        except Exception as e:
             print(f"Erro ao criar ImageClip para legenda '{text[:30]}...': {e}")
             # Tenta fechar o clipe se ele foi parcialmente criado
             if 'subtitle_image_clip' in locals() and subtitle_image_clip:
                 try: subtitle_image_clip.close()
                 except: pass


    print(f"Criados {len(subtitle_clips)} clipes de legenda usando Pillow.")
    return subtitle_clips # Retorna lista de ImageClips