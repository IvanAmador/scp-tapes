# video_pipeline/utils.py
from pathlib import Path
import config
import numpy as np

def convert_svg_to_png(svg_path: Path, output_path: Path, width: int = None, height: int = None) -> bool:
    """
    Converte um arquivo SVG para PNG usando cairosvg.
    Permite especificar largura OU altura, mantendo a proporção.

    Args:
        svg_path: Caminho para o arquivo SVG de entrada.
        output_path: Caminho para salvar o arquivo PNG de saída.
        width: Largura desejada em pixels para o PNG.
        height: Altura desejada em pixels para o PNG.

    Returns:
        True se a conversão for bem-sucedida, False caso contrário.
    """
    try:
        import cairosvg
        print(f"Convertendo {svg_path.name} para PNG (W:{width}, H:{height})...")

        if not svg_path.exists():
            print(f"Erro: Arquivo SVG não encontrado em {svg_path}")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Cairosvg prioriza width se ambos forem dados,
        # mas mantém proporção se apenas um for fornecido.
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(output_path),
            output_width=width,
            output_height=height # Adicionado para flexibilidade
        )

        # Verifica se o arquivo foi criado
        if not output_path.exists() or output_path.stat().st_size == 0:
             raise RuntimeError("Arquivo PNG de saída não foi criado ou está vazio.")

        print(f"SVG convertido com sucesso para {output_path}")
        return True
    except ImportError:
        print("Erro: Biblioteca 'cairosvg' não encontrada.")
        print("Instale com: pip install cairosvg cairocffi") # Adicionado cairocffi
        print("Pode ser necessário instalar dependências do sistema (como Pango, Cairo). Veja a documentação.")
        return False
    except Exception as e:
        print(f"Erro durante a conversão SVG para PNG: {e}")
        # Tenta remover arquivo potencialmente corrompido
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass
        return False

def create_fallback_logo(output_path: Path, width: int) -> bool:
    """
    Cria um logo SCP simples usando PIL quando a conversão SVG falha.
    Melhorado visualmente.

    Args:
        output_path: Caminho para salvar o logo PNG.
        width: Largura desejada para o logo.

    Returns:
        True se o logo foi criado com sucesso, False caso contrário.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Proporção quadrada para o fallback
        height = width
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        padding = int(width * 0.05) # Pequena margem interna

        # Círculo externo (cinza escuro)
        draw.ellipse(
            [(padding, padding), (width - padding, height - padding)],
            fill=(40, 40, 40, 255)
        )
        # Círculo interno (cinza claro)
        inner_padding = padding * 2
        draw.ellipse(
            [(inner_padding, inner_padding), (width - inner_padding, height - inner_padding)],
            fill=(210, 210, 210, 255)
        )

        # Texto "SCP"
        try:
            font_size = int(height * 0.4) # Tamanho relativo
            # Tenta fontes comuns
            try: font = ImageFont.truetype("Impact", font_size)
            except IOError:
                try: font = ImageFont.truetype("Arial-Bold", font_size)
                except IOError: font = ImageFont.load_default() # Último recurso
        except Exception as e:
            print(f"Aviso: Erro ao carregar fonte para fallback logo: {e}. Usando padrão.")
            font = ImageFont.load_default()

        text = "SCP"
        # Usar textbbox para centralizar melhor
        text_bbox = draw.textbbox((0, 0), text, font=font, anchor="lt") # left-top anchor
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_pos = ((width - text_width) / 2, (height - text_height) / 2 - int(height * 0.05)) # Ajuste vertical

        # Sombra leve para o texto
        shadow_offset = int(width * 0.01)
        draw.text((text_pos[0] + shadow_offset, text_pos[1] + shadow_offset), text, font=font, fill=(0, 0, 0, 150))
        # Texto principal
        draw.text(text_pos, text, font=font, fill=(10, 10, 10, 255)) # Preto

        # Salva a imagem
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))
        print(f"Logo alternativo criado com sucesso em {output_path}")
        return True
    except ImportError:
         print("Erro: Biblioteca 'Pillow' não encontrada para criar fallback logo.")
         print("Instale com: pip install Pillow")
         return False
    except Exception as e:
        print(f"Erro ao criar logo alternativo: {e}")
        return False

def get_logo_png_path(desired_width: int) -> Path | None:
    """
    Converte o logo SVG para PNG com a largura desejada (se necessário)
    e retorna o caminho do PNG. Usa cache na pasta temp.
    Tenta criar um fallback se a conversão falhar.

    Args:
        desired_width: Largura desejada para o logo em PNG.

    Returns:
        Path para o arquivo PNG do logo ou None se a conversão e o fallback falharem.
    """
    output_filename = f"scp_logo_{desired_width}w.png"
    logo_png_path = config.TEMP_DIR / output_filename

    # 1. Verifica Cache
    if logo_png_path.exists() and logo_png_path.stat().st_size > 0:
        # print(f"Usando logo PNG cacheado: {logo_png_path}")
        return logo_png_path

    # 2. Verifica se SVG existe
    if not config.SCP_LOGO_SVG.exists():
        print(f"Aviso: Arquivo SVG do logo não encontrado em {config.SCP_LOGO_SVG}. Tentando criar logo alternativo.")
        if create_fallback_logo(logo_png_path, desired_width):
            return logo_png_path
        else:
            print("Falha ao criar logo alternativo. O logo não será usado.")
            return None # Falha total

    # 3. Tenta Converter SVG
    print(f"Gerando PNG do logo com largura {desired_width}px...")
    if convert_svg_to_png(config.SCP_LOGO_SVG, logo_png_path, width=desired_width):
        if logo_png_path.exists() and logo_png_path.stat().st_size > 0:
             return logo_png_path
        else:
             print("Aviso: Conversão SVG parece ter falhado (arquivo vazio/não criado).")
             # Limpa o arquivo inválido, se existir
             if logo_png_path.exists(): logo_png_path.unlink()


    # 4. Tenta Criar Fallback se a Conversão Falhou
    print("Conversão SVG falhou ou resultado inválido. Tentando criar logo alternativo...")
    if create_fallback_logo(logo_png_path, desired_width):
        return logo_png_path
    else:
        print(f"Falha ao gerar PNG do logo e ao criar fallback. O logo não será usado.")
        return None # Falha total