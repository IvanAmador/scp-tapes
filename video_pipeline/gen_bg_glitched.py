# video_pipeline/gen_bg_glitched.py
import os
import numpy as np
from pathlib import Path
import sys
from PIL import Image, ImageOps
import cv2
from moviepy.editor import VideoClip
import time

# Adiciona o diretório pai ao sys.path para poder importar config
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Tenta importar config
try:
    import config
except ImportError:
    print("Aviso: Não foi possível importar config. Usando valores padrão.")
    class DummyConfig:
        VIDEO_WIDTH = 1080
        VIDEO_HEIGHT = 1920
        VIDEO_FPS = 24
        VIDEO_SIZE = (VIDEO_WIDTH, VIDEO_HEIGHT)
    config = DummyConfig()

def criar_video_glitch(img_path, output_path, duration=10, fps=30):
    """Cria um vídeo com efeito glitch a partir de uma imagem base."""
    if os.path.exists(output_path):
        print(f"✔️ Vídeo de fundo já existe: {output_path}")
        return str(output_path)

    print(f"⏳ Gerando vídeo glitch a partir de {img_path}...")
    try:
        # Carrega a imagem usando OpenCV para evitar problemas com o Pillow
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"Não foi possível carregar a imagem: {img_path}")
        
        # Converte BGR para RGB (OpenCV usa BGR por padrão)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Redimensiona para o tamanho de vídeo configurado
        img = cv2.resize(img, (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
        
        # Cria diretório de saída se não existir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Configura o escritor de vídeo
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec para MP4
        video_writer = cv2.VideoWriter(
            output_path, 
            fourcc, 
            fps, 
            (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
        )
        
        # Número total de frames
        total_frames = int(duration * fps)
        
        print(f"Gerando {total_frames} frames com efeito glitch...")
        start_time = time.time()
        
        # Gera frames com efeito glitch
        for frame_num in range(total_frames):
            # Copia o frame base
            frame = img.copy()
            
            # Intensidade do glitch varia com o tempo
            t = frame_num / fps  # Tempo em segundos
            num_glitches = int(5 + 3 * np.sin(t * 2))
            
            # Aplica efeitos de glitch
            for _ in range(num_glitches):
                # Efeito de deslocamento horizontal
                y = np.random.randint(0, frame.shape[0])
                h = np.random.randint(5, 30)
                dx = np.random.randint(-50, 50)
                
                if y + h < frame.shape[0]:
                    slice_to_shift = frame[y:y+h].copy()
                    # Desloca horizontalmente
                    slice_to_shift = np.roll(slice_to_shift, dx, axis=1)
                    frame[y:y+h] = slice_to_shift
                
                # Adiciona efeito de cor aleatório ocasionalmente
                if np.random.random() < 0.2:
                    channel = np.random.randint(0, 3)
                    y2 = np.random.randint(0, frame.shape[0])
                    h2 = np.random.randint(10, 40)
                    
                    if y2 + h2 < frame.shape[0]:
                        # Aumenta a intensidade de um canal de cor
                        frame[y2:y2+h2, :, channel] = np.clip(
                            frame[y2:y2+h2, :, channel] * 1.5, 0, 255
                        ).astype(np.uint8)
            
            # Adiciona ruído ocasionalmente
            if np.random.random() < 0.1:
                noise = np.random.randint(0, 50, size=frame.shape, dtype=np.uint8)
                frame = cv2.add(frame, noise)
            
            # Converte RGB para BGR para salvar com OpenCV
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            video_writer.write(frame_bgr)
            
            # Mostra progresso a cada 10%
            if frame_num % (total_frames // 10) == 0 or frame_num == total_frames - 1:
                percent = (frame_num + 1) / total_frames * 100
                elapsed = time.time() - start_time
                print(f"Progresso: {percent:.1f}% ({frame_num+1}/{total_frames} frames, {elapsed:.1f}s)")
        
        # Libera recursos
        video_writer.release()
        
        print(f"✅ Vídeo gerado: {output_path}")
        return str(output_path)
    except Exception as e:
        print(f"❌ Erro ao gerar vídeo glitch: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_background(output_path: Path, duration: float) -> str | None:
    """Função principal esperada pelo script generate_scp_video.py.
    
    Args:
        output_path: Caminho onde o vídeo de fundo será salvo.
        duration: Duração do vídeo em segundos.
        
    Returns:
        Caminho do vídeo gerado como string ou None em caso de erro.
    """
    # Verifica se o arquivo de background já existe
    if output_path.exists():
        print(f"✔️ Vídeo de fundo já existe: {output_path}")
        return str(output_path)
    
    # Procura por uma imagem de fundo
    bg_image = None
    possible_paths = [
        # Tenta usar a imagem bg.png na raiz do projeto
        Path(__file__).resolve().parent.parent / "bg.png",
        Path(__file__).resolve().parent.parent / "bg.png.png",  # Nome estranho mas visto nos arquivos
        # Tenta em assets/bg
        Path(__file__).resolve().parent.parent / "assets" / "bg" / "bg.png",
        # Tenta outras pastas
        Path(__file__).resolve().parent.parent / "assets" / "bg.png",
    ]
    
    for path in possible_paths:
        if path.exists():
            bg_image = str(path)
            print(f"Usando imagem de fundo: {bg_image}")
            break
    
    if not bg_image:
        print("❌ Nenhuma imagem de fundo encontrada. Criando fundo preto...")
        # Cria uma imagem preta como fallback
        try:
            black_bg = Path(__file__).resolve().parent.parent / "assets" / "bg.png"
            black_bg.parent.mkdir(parents=True, exist_ok=True)
            
            # Cria imagem preta usando OpenCV em vez de Pillow
            black_img = np.zeros((config.VIDEO_HEIGHT, config.VIDEO_WIDTH, 3), dtype=np.uint8)
            cv2.imwrite(str(black_bg), black_img)
            
            bg_image = str(black_bg)
        except Exception as e:
            print(f"❌ Erro ao criar imagem de fundo preta: {e}")
            return None
    
    # Gera o vídeo glitch
    fps = getattr(config, 'VIDEO_FPS', 24)
    return criar_video_glitch(bg_image, str(output_path), duration=duration, fps=fps)

# Permite executar o script diretamente para testes
if __name__ == "__main__":
    output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "bg_glitched_test.mp4"
    
    result = generate_background(output_path, duration=10)
    if result:
        print(f"Teste concluído com sucesso: {result}")
    else:
        print("Teste falhou.")
