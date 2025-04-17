import argparse
import re
from pathlib import Path
import time
import sys
import json
import importlib

# Adiciona caminhos
project_root = Path(__file__).resolve().parent.parent
current_dir = Path(__file__).resolve().parent
sys.path.append(str(project_root))
sys.path.append(str(current_dir))

import config

# Importações da Pipeline
from video_pipeline.tts_generator import generate_narration
from video_pipeline.subtitle_generator import (
    get_word_timestamps,
    add_punctuation_to_whisper_data,
    create_narration_text_clips
)
# Importa a função de intro que agora retorna (clip, duration)
from video_pipeline.intro_generator import create_intro
try:
    from gen_bg_glitched import generate_background as generate_glitch_background
except ImportError:
    print("AVISO: Falha ao importar 'generate_background' de 'gen_bg_glitched.py'. Geração de fundo falhará.")
    generate_glitch_background = None
# Importa o composer que agora recebe intro_duration
from video_pipeline.video_composer import assemble_video
from moviepy.editor import AudioFileClip # Usado para pegar duração

def extract_scp_info(script_text: str, filename: str) -> tuple[str, str, str]:
    """Extrai informações do SCP do nome do arquivo."""
    # (Lógica existente parece boa)
    scp_number = "SCP-?"
    scp_name = "Unknown"
    scp_class = "Unknown"
    match_filename = re.search(r"(SCP-\d+)-(.+)-Class-([\w-]+)", filename, re.IGNORECASE)
    if match_filename:
        scp_number = match_filename.group(1).upper()
        raw_name = match_filename.group(2)
        scp_name = raw_name.replace('-', ' ').strip()
        scp_class = match_filename.group(3).replace('-', ' ').capitalize()
    else:
        print("Aviso: Nome do arquivo não no formato 'SCP-XXX-Nome-Class-Classe'. Tentando fallback...")
        match_number = re.search(r"(SCP-\d+)", filename, re.IGNORECASE)
        if match_number: scp_number = match_number.group(1).upper()
        match_name_simple = re.search(r"SCP-\d+-(.+?)(?:-Class-|$)", filename, re.IGNORECASE)
        if match_name_simple: scp_name = match_name_simple.group(1).replace('-', ' ').strip()
        match_class = re.search(r"Class-([\w-]+)", filename, re.IGNORECASE)
        if match_class: scp_class = match_class.group(1).replace('-', ' ').capitalize()
    print(f"Informações extraídas: Número={scp_number}, Nome={scp_name}, Classe={scp_class}")
    return scp_number, scp_name, scp_class

def main(script_path: Path):
    """Função principal para gerar vídeo SCP."""
    start_total_time = time.time()
    if not script_path.is_file():
        print(f"Erro: Arquivo de script não encontrado: {script_path}")
        return

    print(f"--- Iniciando Geração para: {script_path.name} ---")
    if config.DEV_MODE: print("⚠️ MODO DEV ATIVADO")

    # 1. Ler Script e Setup Inicial
    print("\n1. Lendo script e configurando paths...")
    try:
        original_script_content = script_path.read_text(encoding='utf-8')
        scp_number, scp_name, scp_class = extract_scp_info(original_script_content, script_path.stem)
    except Exception as e:
        print(f"Erro ao ler script ou extrair info: {e}")
        return

    scp_output_dir = config.OUTPUT_DIR / scp_number
    scp_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Diretório de saída: {scp_output_dir}")

    # Paths dos artefatos
    narration_output_path = scp_output_dir / config.ARTIFACT_NARRATION
    background_video_output_path = scp_output_dir / config.ARTIFACT_BACKGROUND
    punctuated_timestamps_path = scp_output_dir / config.ARTIFACT_PUNCTUATED_DATA
    raw_timestamps_path = scp_output_dir / config.ARTIFACT_TIMESTAMPS_RAW
    final_video_output_path = scp_output_dir / config.ARTIFACT_FINAL_VIDEO
    if config.DEV_MODE:
        final_video_output_path = final_video_output_path.with_stem(final_video_output_path.stem + "_dev")
        print(f"Nome do vídeo final (DEV): {final_video_output_path.name}")

    # Verifica se já existe
    if final_video_output_path.exists():
        if input(f"Vídeo final '{final_video_output_path.name}' já existe. Gerar novamente? (s/N): ").lower() != 's':
            print("Geração cancelada."); return

    # --- Variáveis de estado ---
    narration_path_str = None
    background_path_str = None
    intro_clip_obj = None # Armazenará o CLIPE da intro
    actual_intro_duration = 0.0 # Armazenará a DURAÇÃO REAL da intro
    actual_narration_duration = 0.0
    content_duration = 0.0 # Duração apenas da parte da narração/conteúdo
    final_video_duration = 0.0 # Duração total final (intro + conteúdo)
    punctuated_timestamps = None
    narration_text_clips = []
    # --------------------------
    main_success = False # Flag para indicar sucesso no final

    try:
        # 2. Gerar Narração (TTS)
        print("\n2. Processando Narração (TTS)...")
        # ... (lógica para gerar ou usar narração existente - igual a antes) ...
        if narration_output_path.exists():
            print(f"Usando narração existente: {narration_output_path.name}")
            narration_path_str = str(narration_output_path)
        else:
            print("Gerando nova narração...")
            narration_path_str = generate_narration(original_script_content, narration_output_path)
            if not narration_path_str: raise RuntimeError("Falha ao gerar narração.")
            print(f"Narração salva em: {narration_output_path.name}")

        # Pega a duração REAL da narração
        try:
            with AudioFileClip(narration_path_str) as audio_clip_temp:
                actual_narration_duration = audio_clip_temp.duration
            if actual_narration_duration <= 0: raise ValueError("Duração inválida.")
            print(f"Duração da narração detectada: {actual_narration_duration:.2f}s")
        except Exception as e:
            raise RuntimeError(f"Erro ao obter duração da narração {narration_path_str}: {e}")


        # 3. Criar Intro (agora retorna clipe E duração)
        print("\n3. Criando Introdução...")
        # Chama a função atualizada e desempacota o resultado
        intro_clip_obj, actual_intro_duration = create_intro(scp_number, scp_name, scp_class) # Não passa mais o background
        if not intro_clip_obj or actual_intro_duration <= 0:
            raise RuntimeError("Falha ao criar clipe de introdução ou duração inválida.")
        print(f"Introdução criada com duração: {actual_intro_duration:.2f}s")

        # 4. Calcular Durações Finais
        print("\n4. Calculando durações finais...")
        # Duração do conteúdo é a duração da narração, limitada pelo DEV_MODE
        content_duration = actual_narration_duration
        if config.DEV_MODE:
            content_duration = min(actual_narration_duration, config.DEV_MODE_VIDEO_DURATION)
            print(f"⚠️ Modo DEV: Duração do conteúdo limitada a {content_duration:.2f}s")

        # Duração total é Intro + Conteúdo, limitada pelo MAX geral
        total_intended_duration = actual_intro_duration + content_duration
        final_video_duration = min(total_intended_duration, config.MAX_VIDEO_DURATION_SECONDS)
        # Recalcula content_duration se MAX limitou o total
        content_duration = final_video_duration - actual_intro_duration
        if content_duration <= 0:
             raise ValueError(f"Erro de cálculo: Duração do conteúdo ({content_duration:.2f}s) inválida após aplicar limites.")

        print(f"Duração final do vídeo: {final_video_duration:.2f}s (Intro: {actual_intro_duration:.2f}s, Conteúdo: {content_duration:.2f}s)")

        # 5. Gerar Background (com duração final)
        print("\n5. Processando Background...")
        if generate_glitch_background is None:
             raise RuntimeError("Função generate_glitch_background não importada/disponível.")
        if background_video_output_path.exists():
             # Opcional: Validar duração do BG existente
             print(f"Usando vídeo de fundo existente: {background_video_output_path.name}")
             background_path_str = str(background_video_output_path)
        else:
             print(f"Gerando novo vídeo de fundo (duração: {final_video_duration:.2f}s)...")
             background_path_str = generate_glitch_background(background_video_output_path, final_video_duration) # Gera com duração TOTAL
             if not background_path_str: raise RuntimeError("Falha ao gerar vídeo de background.")
             print(f"Vídeo de fundo salvo em: {background_video_output_path.name}")


        # 6. Processar Timestamps (STT + Pontuação)
        print("\n6. Processando Timestamps e Pontuação...")
        # ... (lógica para carregar/gerar timestamps pontuados - igual a antes) ...
        if punctuated_timestamps_path.exists():
            print(f"Tentando carregar timestamps pontuados: {punctuated_timestamps_path.name}")
            try:
                with open(punctuated_timestamps_path, 'r', encoding='utf-8') as f: punctuated_timestamps = json.load(f)
                if isinstance(punctuated_timestamps, list): print(f"Carregados {len(punctuated_timestamps)} timestamps.")
                else: print("Erro: Arquivo não contém lista."); punctuated_timestamps = None
            except Exception as e: print(f"Erro ao carregar: {e}. Gerando novamente."); punctuated_timestamps = None

        if punctuated_timestamps is None:
            print("Gerando timestamps brutos via Whisper...")
            raw_timestamps = get_word_timestamps(Path(narration_path_str))
            if raw_timestamps:
                print(f"Obtidos {len(raw_timestamps)} timestamps brutos.")
                try: # Salva brutos para debug
                    with open(raw_timestamps_path, 'w', encoding='utf-8') as f: json.dump(raw_timestamps, f, ensure_ascii=False, indent=2)
                except Exception as e: print(f"Erro ao salvar timestamps brutos: {e}")

                print("Adicionando pontuação...")
                punctuated_timestamps = add_punctuation_to_whisper_data(original_script_content, raw_timestamps)
                if punctuated_timestamps:
                    print(f"Pontuação adicionada ({len(punctuated_timestamps)} timestamps finais).")
                    try: # Salva pontuados para futuro
                        with open(punctuated_timestamps_path, 'w', encoding='utf-8') as f: json.dump(punctuated_timestamps, f, ensure_ascii=False, indent=2)
                        print(f"Timestamps pontuados salvos em: {punctuated_timestamps_path.name}")
                    except Exception as e: print(f"Erro ao salvar timestamps pontuados: {e}")
                else:
                    print("Aviso: Falha ao adicionar pontuação. Usando brutos (se disponíveis).")
                    punctuated_timestamps = raw_timestamps
            else:
                print("Erro: Falha ao obter timestamps brutos.")
                punctuated_timestamps = []


        # Filtra timestamps para caber na DURAÇÃO DO CONTEÚDO
        if punctuated_timestamps:
            original_count = len(punctuated_timestamps)
            # Filtra palavras que começam ANTES do fim do conteúdo
            relevant_timestamps = [
                word for word in punctuated_timestamps
                if word.get('start', 0) < content_duration
            ]
            filtered_count = len(relevant_timestamps)
            if original_count != filtered_count:
                 print(f"Filtrados {filtered_count} de {original_count} timestamps para caber na duração do conteúdo ({content_duration:.2f}s)")
            punctuated_timestamps = relevant_timestamps


        # 7. Criar Clipes de Texto da Narração
        print("\n7. Criando Clipes de Texto...")
        if punctuated_timestamps:
            # Passa os timestamps filtrados e a DURAÇÃO TOTAL DO VÍDEO
            # A função interna create_text_image cuidará da limitação de tempo final dos clipes
            narration_text_clips = create_narration_text_clips(
                punctuated_word_timestamps=punctuated_timestamps,
                video_duration=final_video_duration, # Passa duração TOTAL
                original_script=original_script_content
            )
            print(f"Gerados {len(narration_text_clips)} clipes de texto.")
        else:
            print("Aviso: Sem timestamps válidos para gerar clipes de texto.")
            narration_text_clips = []


        # 8. Montar Vídeo Final
        print("\n8. Montando Vídeo Final...")
        # Passa a duração REAL da intro para o composer
        main_success = assemble_video(
            intro_clip=intro_clip_obj,
            intro_duration=actual_intro_duration, # <<< Passa a duração real da intro
            background_video_path=Path(background_path_str),
            narration_path=Path(narration_path_str),
            narration_text_clips=narration_text_clips,
            output_path=final_video_output_path,
            final_duration=final_video_duration # Passa a duração TOTAL final
        )

    except Exception as e:
        print(f"\n--- ERRO GERAL NA GERAÇÃO PARA {script_path.name} ---")
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        main_success = False # Garante que falhou
    finally:
        # --- Limpeza Final ---
        print("\nRealizando limpeza final...")
        # Fecha o clipe da intro que foi retornado
        if intro_clip_obj and hasattr(intro_clip_obj, 'close'):
            try:
                print("Fechando clipe da intro...")
                intro_clip_obj.close()
            except Exception as e: print(f"Erro ao fechar intro_clip: {e}")
        # Outros clipes intermediários devem ser fechados dentro de suas funções
        # (como em assemble_video e create_intro)

        end_total_time = time.time()
        total_time_taken = end_total_time - start_total_time

        print("-" * 40)
        if main_success:
            mode_indicator = "[DEV MODE]" if config.DEV_MODE else ""
            print(f"✅ Geração para {scp_number} CONCLUÍDA! {mode_indicator}")
            print(f"Tempo total: {total_time_taken:.2f}s")
            print(f"Vídeo final salvo em: {final_video_output_path}")
        else:
            print(f"❌ Geração para {scp_number} FALHOU.")
            print(f"Tempo total: {total_time_taken:.2f}s")
        print("-" * 40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera vídeos SCP com narração, texto sincronizado e fundo.")
    parser.add_argument("script_file", help="Caminho para o arquivo de texto do script SCP.")
    args = parser.parse_args()
    script_file_path = Path(args.script_file).resolve()
    main(script_file_path)
    print("\n--- Script principal finalizado ---")