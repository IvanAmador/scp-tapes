# video_pipeline/generate_scp_video.py
import argparse
import re
from pathlib import Path
import time
import sys
import importlib # Para importar o script do usuário

# Adiciona o diretório pai e atual ao sys.path
project_root = Path(__file__).resolve().parent.parent
current_dir = Path(__file__).resolve().parent
sys.path.append(str(project_root))
sys.path.append(str(current_dir))

import config # Importa configs

# Importa outros módulos da pipeline
from video_pipeline.tts_generator import generate_narration
from video_pipeline.subtitle_generator import get_word_timestamps, create_typing_subtitle_clips
from video_pipeline.intro_generator import create_intro
# Importa a função do script de background
from gen_bg_glitched import generate_background as generate_glitch_background
from video_pipeline.video_composer import assemble_video
from moviepy.editor import AudioFileClip

# Configurações removidas pois agora usamos o arquivo config.py e lemos o script do arquivo

def extract_scp_info(script_text: str, filename: str) -> (str, str, str):
    """Extrai o número, nome e a classe do SCP do nome do arquivo.
    
    Args:
        script_text: Texto do script SCP (não usado mais).
        filename: Nome do arquivo do script (usado como fonte principal).
        
    Returns:
        Tupla contendo (número do SCP, nome do SCP, classe do SCP).
    """
    scp_number = "SCP-?"
    scp_name = "Unknown"
    scp_class = "Unknown"
    
    # Extrai informações do nome do arquivo
    # Formato esperado: SCP-XXX-Nome-Do-SCP-Class-Classe.txt
    match_filename = re.search(r"(SCP-\d+)-(.+)-Class-([\w-]+)", filename, re.IGNORECASE)
    
    if match_filename:
        scp_number = match_filename.group(1).upper()
        
        # Processa o nome substituindo hífens por espaços
        raw_name = match_filename.group(2)
        scp_name = raw_name.replace('-', ' ')
        
        # Processa a classe
        scp_class = match_filename.group(3).capitalize()
    else:
        # Fallback para o método antigo se o formato do nome do arquivo não corresponder
        match_number = re.search(r"(SCP-\d+)", filename, re.IGNORECASE)
        if match_number: 
            scp_number = match_number.group(1).upper()
        
        match_class = re.search(r"Class-(\w+)", filename, re.IGNORECASE)
        if match_class: 
            scp_class = match_class.group(1).capitalize()
    
    print(f"Informações extraídas do nome do arquivo: Número={scp_number}, Nome={scp_name}, Classe={scp_class}")
    return scp_number, scp_name, scp_class

def main(script_path: Path):
    """Função principal para gerar um vídeo SCP com fundo glitch."""
    start_total_time = time.time()
    
    if not script_path.is_file():
        print(f"Erro: Arquivo de script não encontrado em {script_path}")
        return

    print(f"--- Iniciando Geração (Glitch BG) para: {script_path.name} ---")

    # 1. Ler Script e Extrair Informações
    print("1. Lendo script...")
    try:
        script_text = script_path.read_text(encoding='utf-8')
        scp_number, scp_name, scp_class = extract_scp_info(script_text, script_path.stem)
        base_filename = scp_number 
    except Exception as e:
        print(f"Erro ao ler script: {e}")
        return
    
    # Cria pasta específica para este SCP
    scp_output_dir = config.OUTPUT_DIR / scp_number
    scp_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Diretório de saída: {scp_output_dir}")

    # Define caminhos de saída com a nova estrutura de pastas
    narration_output_path = scp_output_dir / config.ARTIFACT_NARRATION
    background_video_output_path = scp_output_dir / config.ARTIFACT_BACKGROUND
    subtitles_data_path = scp_output_dir / config.ARTIFACT_SUBTITLES_DATA
    final_video_output_path = scp_output_dir / config.ARTIFACT_FINAL_VIDEO

    # Verifica se o vídeo final já existe
    if final_video_output_path.exists():
        print(f"Aviso: Vídeo final '{final_video_output_path}' já existe.")
        user_input = input("Deseja gerar novamente? (s/N): ").strip().lower()
        if user_input != 's':
            print("Geração cancelada pelo usuário.")
            return

    # --- Variáveis ---
    narration_path_str = None
    background_path_str = None
    intro_clip_obj = None
    narration_duration = 0.0
    word_timestamps = None
    # -----------------

    try:
        # 2. Gerar Narração (TTS) ou usar existente
        print("\n2. Processando Narração...")
        if narration_output_path.exists():
            print(f"Narração existente encontrada: {narration_output_path}")
            narration_path_str = str(narration_output_path)
        else:
            print("Gerando nova narração...")
            narration_path_str = generate_narration(script_text, narration_output_path)
            if not narration_path_str: raise RuntimeError("Falha ao gerar narração.")
        
        # Pega a duração
        narration_clip_temp = AudioFileClip(narration_path_str)
        narration_duration = narration_clip_temp.duration
        narration_clip_temp.close() 
        if narration_duration <= 0: raise ValueError("Duração da narração inválida.")
        print(f"Duração da narração: {narration_duration:.2f}s")

        # 3. Gerar Background Glitchy ou usar existente
        print("\n3. Processando Background Glitchy...")
        if background_video_output_path.exists():
            print(f"Vídeo de fundo existente encontrado: {background_video_output_path}")
            background_path_str = str(background_video_output_path)
        else:
            print("Gerando novo vídeo de fundo...")
            bg_duration = narration_duration + 1.0 # Duração um pouco maior
            background_path_str = generate_glitch_background(background_video_output_path, bg_duration) 
            if not background_path_str: raise RuntimeError("Falha ao gerar vídeo de background.")

        # 4. Obter Timestamps (STT) ou carregar existentes
        print("\n4. Processando Timestamps...")
        if subtitles_data_path.exists():
            print(f"Dados de legendas existentes encontrados: {subtitles_data_path}")
            try:
                import json
                with open(subtitles_data_path, 'r', encoding='utf-8') as f:
                    word_timestamps = json.load(f)
                print(f"Carregados {len(word_timestamps)} timestamps de palavras do arquivo.")
            except Exception as e:
                print(f"Erro ao carregar timestamps existentes: {e}")
                word_timestamps = None
        
        if word_timestamps is None:
            print("Obtendo novos timestamps...")
            word_timestamps = get_word_timestamps(Path(narration_path_str))
            # Salva os timestamps para uso futuro
            if word_timestamps:
                try:
                    import json
                    with open(subtitles_data_path, 'w', encoding='utf-8') as f:
                        json.dump(word_timestamps, f, ensure_ascii=False, indent=2)
                    print(f"Timestamps salvos em: {subtitles_data_path}")
                except Exception as e:
                    print(f"Erro ao salvar timestamps: {e}")
        
        if word_timestamps is None:
            print("Aviso: Falha ao obter timestamps. Vídeo sem legendas.")
            subtitle_clips = []
        else:
            # 5. Criar Clipes de Legenda
            print("\n5. Criando Legendas...")
            subtitle_clips = create_typing_subtitle_clips(word_timestamps, narration_duration)

        # 6. Criar Intro (pode usar trecho do background glitchy)
        print("\n6. Criando Introdução...")
        intro_clip_obj = create_intro(scp_number, scp_name, scp_class, Path(background_path_str)) # Passa o bg gerado
        if not intro_clip_obj: raise RuntimeError("Falha ao criar introdução.")

        # 7. Montar Vídeo Final
        print("\n7. Montando Vídeo Final...")
        success = assemble_video(
            intro_clip=intro_clip_obj, 
            background_video_path=Path(background_path_str),
            narration_path=Path(narration_path_str), 
            subtitle_clips=subtitle_clips, 
            output_path=final_video_output_path
        )

        end_total_time = time.time()
        total_time_taken = end_total_time - start_total_time

        if success:
            print(f"\n--- Geração para {scp_number} CONCLUÍDA! ({total_time_taken:.2f}s) ---")
            print(f"Todos os artefatos foram salvos em: {scp_output_dir}")
            print(f"Narração: {narration_output_path}")
            print(f"Vídeo de fundo: {background_video_output_path}")
            print(f"Dados de legendas: {subtitles_data_path}")
            print(f"Vídeo final: {final_video_output_path}")
        else:
            print(f"\n--- Geração para {scp_number} FALHOU. ({total_time_taken:.2f}s) ---")

    except Exception as e:
        print(f"\n--- ERRO GERAL NA GERAÇÃO (Glitch BG) PARA {script_path.name} ---")
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpeza final
        if intro_clip_obj:
            try: intro_clip_obj.close()
            except Exception: pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera vídeos SCP com fundo glitchy e logo opcional.")
    parser.add_argument("script_file", 
                        help="Caminho para o arquivo de texto do script SCP (ex: data/scripts/scp-096.txt)")
    
    args = parser.parse_args()
    script_file_path = Path(args.script_file).resolve() 
    main(script_file_path)
