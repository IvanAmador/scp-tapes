# video_pipeline/subtitle_generator.py
import openai
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip # Apenas ImageClip é usado aqui diretamente
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import config # Importa as configurações globais
import os
from dotenv import load_dotenv
import numpy as np
import re # Para expressões regulares (limpeza de texto)
import difflib # Para alinhamento de texto (pontuação)
import time # Para medir tempo de execução

# --- Carregamento de Configs e API Key ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY") or config.OPENAI_API_KEY
if not api_key or api_key == "SUA_API_KEY_AQUI":
    print("AVISO URGENTE: Chave da API OpenAI não configurada no .env ou config.py!")
    client = None
else:
    try:
        client = openai.OpenAI(api_key=api_key)
        # Opcional: Testar conexão/chave (pode adicionar custo mínimo)
        # client.models.list()
        print("Cliente OpenAI inicializado com sucesso.")
    except openai.AuthenticationError:
        print("ERRO CRÍTICO: Chave da API OpenAI inválida ou expirada.")
        client = None
    except Exception as e:
        print(f"ERRO CRÍTICO ao inicializar cliente OpenAI: {e}")
        client = None

# --- Função para Adicionar Pontuação (Integrada) ---
def add_punctuation_to_whisper_data(original_script: str, word_timestamps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Adiciona pontuação do script original aos dados de timestamps do Whisper
    usando alinhamento de sequências.
    """
    if not word_timestamps:
        print("Aviso: Lista de timestamps vazia para adicionar pontuação.")
        return []
    if not original_script:
        print("Aviso: Script original vazio, não é possível adicionar pontuação.")
        return [item.copy() for item in word_timestamps] # Retorna cópia sem alterações

    print("Iniciando adição de pontuação aos timestamps...")
    start_time = time.time()

    # 1. Tokenizar Script Original (mantendo palavras e pontuações finais separadas)
    raw_tokens = re.findall(r"[\w'-]+|[.,!?;:\"\'()]|\S+", original_script)
    processed_tokens = []
    i = 0
    trailing_punct_regex = r'^[.,!?;:]+$'
    while i < len(raw_tokens):
        current_token = raw_tokens[i]
        punctuation = None
        # Verifica se é uma palavra (contém letras ou números)
        if re.search(r'[a-zA-Z0-9]', current_token):
            word = current_token
            # Verifica se o próximo token é uma pontuação final
            if i + 1 < len(raw_tokens) and re.match(trailing_punct_regex, raw_tokens[i+1]):
                punctuation = raw_tokens[i+1]
                processed_tokens.append({'word': word, 'punct': punctuation})
                i += 2 # Pula palavra e pontuação
            else:
                processed_tokens.append({'word': word, 'punct': None})
                i += 1
        else:
            # Ignora tokens que não são palavras (pontuações isoladas, etc.)
            i += 1
    script_words = [token['word'] for token in processed_tokens]

    # 2. Extrair Palavras dos Timestamps (já devem estar limpas de espaços extras)
    whisper_words = [item['word'] for item in word_timestamps]
    # Cria uma cópia para modificar com segurança
    output_word_timestamps = [item.copy() for item in word_timestamps]

    # 3. Alinhar Sequências (case-insensitive e ignorando pontuação básica no Whisper)
    matcher = difflib.SequenceMatcher(None,
                                      [w.lower() for w in script_words],
                                      [w.lower().strip(" .,!?;:") for w in whisper_words],
                                      autojunk=False)

    # 4. Transferir Pontuação do Script para os Timestamps Correspondentes
    script_to_whisper_map = {}
    # Mapeia índices de palavras correspondentes (iguais ou substituições 1-para-1)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and (i2 - i1) == (j2 - j1)):
            for offset in range(i2 - i1):
                 script_i = i1 + offset
                 whisper_j = j1 + offset
                 # Garante que os índices estão dentro dos limites das listas
                 if script_i < len(processed_tokens) and whisper_j < len(output_word_timestamps):
                     script_to_whisper_map[script_i] = whisper_j

    punctuation_added_count = 0
    # Itera sobre os tokens do script original
    for script_i, token_info in enumerate(processed_tokens):
        # Se o token do script tem pontuação e foi mapeado para um timestamp
        if token_info['punct'] and script_i in script_to_whisper_map:
            target_whisper_idx = script_to_whisper_map[script_i]
            # Garante que o índice mapeado é válido
            if target_whisper_idx < len(output_word_timestamps):
                current_word_data = output_word_timestamps[target_whisper_idx]
                original_whisper_word = current_word_data['word']
                # Adiciona a pontuação apenas se ela já não estiver lá
                # e se a palavra do Whisper não terminar com pontuação forte similar
                if not original_whisper_word.endswith(token_info['punct']) and \
                   not re.search(r'[.,!?;:]$', original_whisper_word):
                    current_word_data['word'] += token_info['punct']
                    punctuation_added_count += 1

    end_time = time.time()
    print(f"Adição de pontuação concluída em {end_time - start_time:.2f}s. {punctuation_added_count} pontuações adicionadas.")
    return output_word_timestamps

# --- Função para Obter Timestamps ---
def get_word_timestamps(audio_path: Path) -> Optional[List[Dict[str, Any]]]:
    """ Obtém timestamps palavra por palavra do Whisper via API OpenAI. """
    if not client:
        print("ERRO CRÍTICO: Cliente OpenAI não inicializado. Verifique a API Key.")
        # Poderia retornar um erro ou uma lista vazia, dependendo de como o chamador trata
        return None
    if not audio_path.exists():
        print(f"Erro: Arquivo de áudio não encontrado em {audio_path}")
        return None

    try:
        print(f"Obtendo timestamps para: {audio_path.name} (Usando modelo {config.STT_MODEL})...")
        start_api_time = time.time()
        with open(audio_path, "rb") as audio_file:
            # Faz a chamada para a API de transcrição
            transcript = client.audio.transcriptions.create(
                model=config.STT_MODEL,
                file=audio_file,
                response_format="verbose_json", # Necessário para timestamps
                timestamp_granularities=["word"] # Pede timestamps por palavra
            )
        end_api_time = time.time()
        print(f"Chamada à API Whisper concluída em {end_api_time - start_api_time:.2f}s.")

        # Verifica se a resposta contém os dados esperados
        if not transcript or not hasattr(transcript, 'words') or not transcript.words:
            print("Aviso: Resposta da API Whisper não contém timestamps de palavras ('words').")
            print(f"Resposta completa (para debug): {transcript}")
            return None

        print(f"Timestamps brutos obtidos ({len(transcript.words)} palavras). Processando e limpando...")
        corrected_words = []
        raw_words = transcript.words # A resposta deve ser uma lista de objetos/dicionários

        # Itera sobre as palavras retornadas pela API
        for i, word_obj in enumerate(raw_words):
            try:
                # Converte para dicionário de forma consistente
                if isinstance(word_obj, dict): word_data = word_obj
                elif hasattr(word_obj, 'model_dump'): word_data = word_obj.model_dump() # Pydantic v2+
                elif hasattr(word_obj, 'dict'): word_data = word_obj.dict() # Pydantic v1
                # Fallback para objetos com atributos diretos
                elif hasattr(word_obj, 'word') and hasattr(word_obj, 'start') and hasattr(word_obj, 'end'):
                     word_data = {'word': getattr(word_obj, 'word', ''), 'start': getattr(word_obj, 'start', 0.0), 'end': getattr(word_obj, 'end', 0.0)}
                else:
                    print(f"Aviso: Formato de palavra inesperado no índice {i}: {type(word_obj)}. Pulando.")
                    continue # Pula esta entrada se o formato for desconhecido

                # Extrai e valida os dados
                start = float(word_data.get('start', 0.0))
                end = float(word_data.get('end', 0.0))
                word = str(word_data.get('word', '')).strip() # Garante string e remove espaços nas bordas

                if not word: continue # Pula palavras vazias
                start = max(0.0, start) # Garante tempo não negativo
                end = max(start, end) # Garante que o fim seja >= início

                # Adiciona a palavra processada à lista
                corrected_words.append({'word': word, 'start': start, 'end': end})
            except Exception as e:
                print(f"Erro processando palavra bruta no índice {i}: '{str(word_obj)[:50]}...' -> {e}")
                continue # Pula palavra com erro

        # Verifica se alguma palavra válida foi extraída
        if not corrected_words:
            print("Aviso: Nenhum timestamp de palavra válido foi extraído após o processamento inicial.")
            return None

        print(f"Processamento inicial de timestamps concluído. {len(corrected_words)} palavras válidas.")
        return corrected_words

    except openai.AuthenticationError as e:
        print(f"ERRO CRÍTICO DE AUTENTICAÇÃO OpenAI: Verifique sua API Key. Detalhes: {e}")
        return None
    except openai.RateLimitError as e:
         print(f"ERRO CRÍTICO: Limite de taxa da API OpenAI atingido. Tente novamente mais tarde. Detalhes: {e}")
         return None
    except openai.APIConnectionError as e:
         print(f"ERRO CRÍTICO: Falha ao conectar à API OpenAI. Verifique sua conexão. Detalhes: {e}")
         return None
    except Exception as e:
        print(f"Erro GERAL e INESPERADO ao obter timestamps do Whisper: {e}")
        import traceback
        traceback.print_exc() # Imprime stack trace para debug
        return None

# --- Função Auxiliar para Criar Imagem de Texto (Pillow) ---
def create_text_image(text: str, font_path: str, font_size: int, text_color: str,
                       bg_enabled: bool, bg_color: tuple, bg_opacity: float, padding: int,
                       max_width: int, video_width: int, h_align: str = 'center') -> Tuple[Optional[np.ndarray], int, int]:
    """
    Cria uma imagem RGBA do texto usando Pillow, com quebra de linha automática,
    fundo opcional e alinhamento horizontal configurável.
    Retorna o array numpy da imagem, largura e altura.
    """
    try:
        # Tenta carregar a fonte especificada, com fallback para a padrão
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            print(f"Aviso: Não foi possível carregar a fonte '{font_path}'. Usando fonte padrão do Pillow.")
            font = ImageFont.load_default() # Pillow tenta encontrar uma fonte padrão

        lines = []
        if not text: return None, 0, 0 # Lida com texto vazio

        # Obtém métricas da fonte para calcular altura da linha
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        # Obtém largura do espaço (com fallback para getsize se getlength não existir)
        space_width = font.getlength(" ") if hasattr(font, 'getlength') else font.getsize(" ")[0]

        # Quebra o texto em linhas baseado na largura máxima
        words = text.split(' ')
        current_line = ""
        current_line_width = 0
        for word in words:
            # Obtém largura da palavra (com fallback)
            word_width = font.getlength(word) if hasattr(font, 'getlength') else font.getsize(word)[0]

            if not current_line: # Primeira palavra da linha
                if word_width > max_width: # Palavra sozinha é maior que a largura?
                    lines.append(word) # Adiciona como linha única (sem hifenização)
                    current_line = ""
                    current_line_width = 0
                else:
                    current_line = word
                    current_line_width = word_width
            # Verifica se adicionar a palavra (com espaço) cabe na linha
            elif current_line_width + space_width + word_width <= max_width:
                current_line += f" {word}"
                current_line_width += space_width + word_width
            else: # Não cabe, finaliza linha atual e começa nova
                lines.append(current_line)
                # Trata caso onde a nova palavra sozinha é maior que a largura
                if word_width > max_width:
                    lines.append(word)
                    current_line = ""
                    current_line_width = 0
                else:
                    current_line = word
                    current_line_width = word_width
        if current_line: # Adiciona a última linha formada
            lines.append(current_line)

        if not lines: return None, 0, 0 # Retorna se nenhuma linha foi gerada

        # Calcula dimensões da imagem final
        total_text_height = len(lines) * line_height
        actual_max_text_width = 0
        for line in lines:
             line_len = font.getlength(line) if hasattr(font, 'getlength') else font.getsize(line)[0]
             actual_max_text_width = max(actual_max_text_width, int(line_len))
        # Garante que a largura do texto não exceda o máximo permitido
        actual_max_text_width = min(actual_max_text_width, max_width)

        # Calcula dimensões do painel (com padding) e da imagem
        panel_w = actual_max_text_width + 2 * padding
        panel_h = total_text_height + 2 * padding
        # Imagem tem tamanho do painel se fundo ativo, senão só do texto
        img_w = panel_w if bg_enabled else actual_max_text_width
        img_h = panel_h if bg_enabled else total_text_height
        # Adiciona pequena margem para garantir que nada seja cortado nas bordas
        img_w = max(1, img_w + 2) # Largura mínima de 1px
        img_h = max(1, img_h + 2) # Altura mínima de 1px

        # Cria a imagem RGBA (transparente por padrão)
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Desenha o fundo retangular (arredondado) se habilitado
        if bg_enabled:
            panel_fill = (*bg_color[:3], int(255 * bg_opacity)) # Cor com opacidade
            radius = 10 # Raio dos cantos
            # Coordenadas do retângulo (com pequena margem interna)
            bg_x0, bg_y0 = 1, 1
            bg_x1, bg_y1 = img_w - 2, img_h - 2 # Ajustado para margem
            draw.rounded_rectangle([(bg_x0, bg_y0), (bg_x1 , bg_y1)], radius=radius, fill=panel_fill)

        # Desenha cada linha de texto
        current_y = (padding + 1) if bg_enabled else 1 # Posição Y inicial (com margem)
        for line in lines:
             line_len = font.getlength(line) if hasattr(font, 'getlength') else font.getsize(line)[0]
             # Calcula posição X baseado no alinhamento horizontal
             if h_align == 'center':
                 pos_x = (img_w - line_len) / 2
             elif h_align == 'right':
                 pos_x = img_w - line_len - (padding + 1 if bg_enabled else 1) # Alinha à direita com padding
             else: # 'left' (padrão)
                 pos_x = (padding + 1) if bg_enabled else 1 # Alinha à esquerda com padding

             pos_x = max(1, pos_x) # Garante pos_x >= 1

             # Desenha texto usando 'anchor="la"' (left, ascent) para alinhamento vertical consistente
             draw.text((pos_x, current_y), line, font=font, fill=text_color, anchor="la")
             current_y += line_height # Move para a próxima linha

        # Converte imagem Pillow para array NumPy
        img_array = np.array(img)
        return img_array, img_w, img_h

    except Exception as e:
        print(f"ERRO CRÍTICO ao criar imagem de texto com Pillow para '{text[:30]}...': {e}")
        import traceback
        traceback.print_exc()
        return None, 0, 0

# --- Função Principal: Cria Clipes de Texto Acumulado ---
def create_narration_text_clips(
    punctuated_word_timestamps: List[Dict[str, Any]],
    video_duration: float,
    original_script: str # Argumento necessário para a chamada, mesmo que não usado diretamente aqui
    ) -> List[ImageClip]:
    """
    Cria clipes de texto (ImageClip) que aparecem acumulando palavra por palavra,
    sincronizados com a narração, mantendo o topo do bloco de texto fixo verticalmente.
    """
    all_clips = []
    if not punctuated_word_timestamps:
        print("Aviso: Nenhum timestamp fornecido para criar clipes de texto.")
        return all_clips

    # Verifica se o arquivo de fonte existe
    font_path = config.NARRATION_TEXT_FONT
    if not Path(font_path).is_file():
        print(f"AVISO CRÍTICO: Arquivo de fonte '{font_path}' não encontrado! Pillow tentará usar fonte padrão.")
        # Poderia definir um fallback aqui, mas Pillow tentará um padrão.

    print("Iniciando criação de clipes de texto acumulado...")
    overall_start_time = time.time()

    # 1. Agrupamento por Sentenças/Blocos (para resetar o texto na tela)
    sentences = []
    current_sentence_words = []
    # Pontuações que indicam fim de um bloco visual (ajuste se necessário)
    sentence_ending_punct = ['.', '!', '?']
    for i, word_info in enumerate(punctuated_word_timestamps):
        current_sentence_words.append(word_info)
        word_text = word_info['word']
        is_last_word_overall = (i == len(punctuated_word_timestamps) - 1)
        # Verifica se a *palavra contém* pontuação final ou se é a última palavra
        if any(p in word_text for p in sentence_ending_punct) or is_last_word_overall:
            if current_sentence_words:
                sentences.append({'words': list(current_sentence_words)}) # Adiciona cópia da lista
                current_sentence_words = [] # Reseta para o próximo bloco
    # Garante que o último bloco seja adicionado se não terminar com pontuação
    if current_sentence_words:
         sentences.append({'words': list(current_sentence_words)})

    print(f"Texto agrupado em {len(sentences)} sentenças/blocos visuais.")

    # 2. Processa cada bloco para criar clipes de palavra acumulada
    clip_creation_start_time = time.time()
    total_clips_generated = 0
    for sentence_index, sentence_info in enumerate(sentences):
        sentence_words = sentence_info['words']
        if not sentence_words: continue # Pula blocos vazios

        phrase_start_time = sentence_words[0]['start'] # Início do bloco
        last_word_end_time = phrase_start_time # Rastreia o fim da palavra anterior
        current_phrase_text_list = [] # Acumula palavras do bloco atual

        # Itera sobre as palavras do bloco atual
        for word_index, word_info in enumerate(sentence_words):
            word = word_info['word']
            start = word_info['start']
            end = word_info['end']

            # Garante que tempos estejam dentro dos limites do vídeo
            start = max(0.0, start)
            end = max(start, end)
            start = min(start, video_duration)
            end = min(end, video_duration)

            # Calcula quando este estado do texto deve começar a ser exibido
            # Começa no fim da palavra anterior, mas não antes do início do bloco
            display_start_time = max(phrase_start_time, last_word_end_time)
            display_start_time = min(display_start_time, video_duration) # Limita ao vídeo

            # Calcula quando este estado do texto deve terminar de ser exibido (fim da palavra atual)
            display_end_time = end
            display_end_time = min(display_end_time, video_duration) # Limita ao vídeo

            # Calcula a duração da exibição deste estado do texto
            word_display_duration = max(0.01, display_end_time - display_start_time) # Duração mínima de 10ms

            # Pula se o clipe começaria fora do vídeo ou tem duração insignificante
            if display_start_time >= video_duration or word_display_duration < 0.01:
                last_word_end_time = end # Atualiza o tempo para a próxima palavra mesmo pulando
                continue

            # Adiciona a palavra atual ao texto acumulado do bloco
            current_phrase_text_list.append(word)
            accumulated_text = " ".join(current_phrase_text_list)
            # Limpa espaços antes de pontuações comuns
            accumulated_text = re.sub(r'\s+([.,!?;:])', r'\1', accumulated_text)

            # Cria a imagem para o texto acumulado atual
            text_image_array, img_w, img_h = create_text_image(
                text=accumulated_text,
                font_path=font_path,
                font_size=config.NARRATION_TEXT_FONT_SIZE,
                text_color=config.NARRATION_TEXT_COLOR,
                bg_enabled=config.NARRATION_TEXT_BG_ENABLED,
                bg_color=config.NARRATION_TEXT_BG_COLOR,
                bg_opacity=config.NARRATION_TEXT_BG_OPACITY,
                padding=config.NARRATION_TEXT_PADDING,
                max_width=int(config.VIDEO_WIDTH * config.NARRATION_TEXT_MAX_WIDTH_FACTOR),
                video_width=config.VIDEO_WIDTH,
                h_align=config.NARRATION_TEXT_H_ALIGN # Passa alinhamento horizontal
            )

            # Verifica se a criação da imagem falhou
            if text_image_array is None or img_w <= 0 or img_h <= 0:
                print(f"AVISO: Falha ao criar imagem para texto: '{accumulated_text[:50]}...' Pulando clipe.")
                last_word_end_time = end # Atualiza tempo
                continue

            # Cria o ImageClip com a imagem gerada
            try:
                word_clip = ImageClip(text_image_array, ismask=False) # ismask=False para RGBA
                word_clip = word_clip.set_start(display_start_time)
                word_clip = word_clip.set_duration(word_display_duration)

                # --- Calcula a Posição Vertical FIXA (Alinhada pelo Topo) ---
                target_v_align_percent = config.NARRATION_TEXT_V_ALIGN_PERCENT
                # Calcula a coordenada Y do TOPO do clipe
                fixed_top_y_coordinate = config.VIDEO_HEIGHT * target_v_align_percent
                # Garante que o clipe não saia da tela (importante para textos altos)
                fixed_top_y_coordinate = max(0, min(fixed_top_y_coordinate, config.VIDEO_HEIGHT - img_h))

                # --- Define a Posição (Horizontal e Vertical Fixa) ---
                word_clip = word_clip.set_position((config.NARRATION_TEXT_H_ALIGN, fixed_top_y_coordinate))

                # Define FPS para consistência na composição final
                word_clip = word_clip.set_fps(config.VIDEO_FPS)

                all_clips.append(word_clip) # Adiciona o clipe pronto à lista
                total_clips_generated += 1

            except Exception as e:
                 print(f"ERRO ao criar ou configurar ImageClip para palavra '{word}': {e}")
                 import traceback
                 traceback.print_exc()
                 # Tentar fechar clipe parcialmente criado? Geralmente não necessário para ImageClip

            # Atualiza o tempo final da última palavra processada para a próxima iteração
            last_word_end_time = end

    # Logs finais do processo de criação de clipes
    clip_creation_end_time = time.time()
    print(f"Criação dos clipes de texto ({total_clips_generated} clipes) concluída em {clip_creation_end_time - clip_creation_start_time:.2f}s.")
    overall_end_time = time.time()
    print(f"Processo total de geração de clipes de narração levou {overall_end_time - overall_start_time:.2f}s.")

    return all_clips # Retorna a lista de ImageClips prontos para composição