# video_pipeline/tts_generator.py
import openai
from pathlib import Path
import config
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Usa a API key do arquivo .env ou do config.py como fallback
api_key = os.getenv("OPENAI_API_KEY") or config.OPENAI_API_KEY
client = openai.OpenAI(api_key=api_key)

def generate_narration(script_text: str, output_path: Path, 
                       voice_style: str = config.TTS_VOICE) -> str | None:
    """
    Gera narração de áudio a partir do texto do script usando a API OpenAI TTS.
    
    Args:
        script_text: Texto do script para narrar.
        output_path: Caminho onde o arquivo de áudio será salvo.
        voice_style: Estilo de voz a ser usado (default: config.TTS_VOICE).
        
    Returns:
        Caminho do arquivo de áudio gerado ou None em caso de erro.
    """
    try:
        print(f"Gerando narração para: {output_path.name}...")
        response = client.audio.speech.create(
            model=config.TTS_MODEL,
            voice=voice_style,
            input=script_text,
            response_format="mp3" 
        )
        output_path.parent.mkdir(parents=True, exist_ok=True) 
        response.stream_to_file(str(output_path)) 
        print(f"Narração salva com sucesso em: {output_path}")
        return str(output_path)
    except openai.AuthenticationError as e:
        print(f"Erro de autenticação OpenAI: Verifique sua API Key. {e}")
        return None
    except Exception as e:
        print(f"Erro ao gerar narração: {e}")
        return None
