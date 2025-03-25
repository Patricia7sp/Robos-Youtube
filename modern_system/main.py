"""
Sistema de Animação Automatizada para YouTube
--------------------------------------------
Sistema principal que coordena todos os agentes para criar animações a partir de histórias
e fazer upload para o YouTube.
"""

import os
import argparse
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any

# Importação dos agentes
from agents.script_processor import ScriptProcessorAgent
from agents.visual_designer import VisualDesignerAgent
from agents.voice_actor import VoiceActorAgent  
from agents.animator import AnimatorAgent
from agents.video_editor import VideoEditorAgent
from agents.youtube_publisher import YouTubePublisherAgent

def setup_directories():
    """Configura os diretórios necessários para o sistema."""
    dirs = [
        'data', 
        'config',
        'output', 
        'output/images', 
        'output/images/characters',
        'output/images/scenes',
        'output/audio', 
        'output/audio/narration',
        'output/audio/dialogue',
        'output/animations',
        'output/animations/extended',
        'output/video',
        'output/video/scenes',
        'output/youtube',
        'cache'
    ]
    for directory in dirs:
        os.makedirs(os.path.join(os.path.dirname(__file__), directory), exist_ok=True)
    print("Diretórios configurados com sucesso.")

def process_story(story_path: str, output_dir: str) -> str:
    """
    Processa uma história e gera um roteiro estruturado.
    
    Args:
        story_path: Caminho para o arquivo de texto com a história
        output_dir: Diretório para salvar os resultados
        
    Returns:
        Caminho para o arquivo JSON do roteiro
    """
    print(f"\n{'='*50}")
    print("ETAPA 1: PROCESSAMENTO DE ROTEIRO")
    print(f"{'='*50}\n")
    
    # Inicializa o agente de processamento de roteiro
    script_agent = ScriptProcessorAgent()
    
    # Carrega a história
    script_agent.load_story_from_file(story_path)
    
    # Processa a história
    script = script_agent.process_story()
    
    # Salva o roteiro
    script_path = os.path.join(output_dir, 'roteiro.json')
    script_agent.save_script(script_path)
    
    # Exibe um resumo do roteiro
    print(f"\nRoteiro gerado com {len(script)} cenas.")
    print(f"Roteiro salvo em: {script_path}")
    
    # Exibe o roteiro formatado
    formatted_script_path = os.path.join(output_dir, 'roteiro_formatado.txt')
    with open(formatted_script_path, 'w', encoding='utf-8') as f:
        f.write(script_agent.get_formatted_script())
    
    print(f"Roteiro formatado salvo em: {formatted_script_path}")
    
    return script_path

def generate_images(script_path: str, output_dir: str) -> str:
    """
    Gera imagens para todas as cenas do roteiro.
    
    Args:
        script_path: Caminho para o arquivo JSON do roteiro
        output_dir: Diretório para salvar as imagens
        
    Returns:
        Caminho para o diretório de imagens
    """
    print(f"\n{'='*50}")
    print("ETAPA 2: GERAÇÃO DE IMAGENS")
    print(f"{'='*50}\n")
    
    # Inicializa o agente de design visual
    visual_agent = VisualDesignerAgent()
    
    # Carrega o roteiro
    visual_agent.load_script(script_path)
    
    # Cria o diretório de saída para imagens
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # Gera todas as imagens
    print("Gerando imagens para personagens e cenas...")
    character_designs, scene_images = visual_agent.generate_all_images(images_dir)
    
    print(f"\nImagens geradas:")
    print(f"- {len(character_designs)} designs de personagens")
    print(f"- {len(scene_images)} imagens de cenas")
    print(f"Imagens salvas em: {images_dir}")
    
    return images_dir

def generate_audio(script_path: str, output_dir: str) -> str:
    """
    Gera áudios para todas as cenas do roteiro.
    
    Args:
        script_path: Caminho para o arquivo JSON do roteiro
        output_dir: Diretório para salvar os áudios
        
    Returns:
        Caminho para o diretório de áudios
    """
    print(f"\n{'='*50}")
    print("ETAPA 3: GERAÇÃO DE ÁUDIO")
    print(f"{'='*50}\n")
    
    # Inicializa o agente de voz e áudio
    audio_agent = VoiceActorAgent()
    
    # Carrega o roteiro
    audio_agent.load_script(script_path)
    
    # Cria o diretório de saída para áudios
    audio_dir = os.path.join(output_dir, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    
    # Gera todos os áudios
    print("Gerando áudios para narração e diálogos...")
    all_audio_metadata = audio_agent.generate_all_audio(audio_dir)
    
    print(f"\nÁudios gerados para {len(all_audio_metadata)} cenas")
    print(f"Áudios salvos em: {audio_dir}")
    
    return audio_dir

def create_animations(script_path: str, images_dir: str, output_dir: str) -> str:
    """
    Cria animações para todas as cenas do roteiro.
    
    Args:
        script_path: Caminho para o arquivo JSON do roteiro
        images_dir: Diretório contendo as imagens geradas
        output_dir: Diretório para salvar as animações
        
    Returns:
        Caminho para o diretório de animações
    """
    print(f"\n{'='*50}")
    print("ETAPA 4: ANIMAÇÃO")
    print(f"{'='*50}\n")
    
    # Inicializa o agente de animação
    animator_agent = AnimatorAgent()
    
    # Carrega o roteiro
    animator_agent.load_script(script_path)
    
    # Cria o diretório de saída para animações
    animations_dir = os.path.join(output_dir, 'animations')
    os.makedirs(animations_dir, exist_ok=True)
    
    # Anima todas as cenas
    print("Criando animações para todas as cenas...")
    animations = animator_agent.animate_all_scenes(images_dir, animations_dir)
    
    # Estende as animações para durações adequadas
    print("\nEstendendo animações para durações adequadas...")
    extended_animations = animator_agent.extend_animations(animations_dir)
    
    print(f"\nAnimações criadas para {len(animations)} cenas")
    print(f"Animações salvas em: {animations_dir}")
    
    return animations_dir

def edit_video(script_path: str, animations_dir: str, audio_dir: str, output_dir: str) -> Optional[str]:
    """
    Edita o vídeo final combinando animações e áudios.
    
    Args:
        script_path: Caminho para o arquivo JSON do roteiro
        animations_dir: Diretório contendo as animações
        audio_dir: Diretório contendo os áudios
        output_dir: Diretório para salvar o vídeo
        
    Returns:
        Caminho para o vídeo final ou None em caso de falha
    """
    print(f"\n{'='*50}")
    print("ETAPA 5: EDIÇÃO DE VÍDEO")
    print(f"{'='*50}\n")
    
    # Inicializa o agente de edição de vídeo
    editor_agent = VideoEditorAgent()
    
    # Carrega o roteiro
    editor_agent.load_script(script_path)
    
    # Cria o diretório de saída para vídeos
    video_dir = os.path.join(output_dir, 'video')
    os.makedirs(video_dir, exist_ok=True)
    
    # Cria o vídeo final
    print("Criando vídeo final...")
    final_video_path = editor_agent.create_final_video(animations_dir, audio_dir, video_dir)
    
    if final_video_path:
        if final_video_path.startswith('[Simulado]'):
            print(f"\nVídeo final simulado")
        else:
            print(f"\nVídeo final criado: {final_video_path}")
    else:
        print("\nErro: Não foi possível criar o vídeo final")
    
    return final_video_path

def publish_to_youtube(script_path: str, video_path: str, output_dir: str, client_secrets_file: Optional[str] = None) -> Optional[str]:
    """
    Publica o vídeo no YouTube com metadados otimizados.
    
    Args:
        script_path: Caminho para o arquivo JSON do roteiro
        video_path: Caminho para o vídeo final
        output_dir: Diretório para salvar os metadados
        client_secrets_file: Caminho para o arquivo client_secrets.json (opcional)
        
    Returns:
        ID do vídeo no YouTube ou None em caso de falha
    """
    print(f"\n{'='*50}")
    print("ETAPA 6: PUBLICAÇÃO NO YOUTUBE")
    print(f"{'='*50}\n")
    
    # Inicializa o agente de publicação no YouTube
    publisher_agent = YouTubePublisherAgent(client_secrets_file)
    
    # Carrega o roteiro
    publisher_agent.load_script(script_path)
    
    # Cria o diretório de saída para metadados do YouTube
    youtube_dir = os.path.join(output_dir, 'youtube')
    os.makedirs(youtube_dir, exist_ok=True)
    
    # Gera metadados otimizados
    print("Gerando metadados otimizados para SEO...")
    metadata = publisher_agent.generate_metadata()
    
    # Salva os metadados
    metadata_path = publisher_agent.save_metadata(metadata, youtube_dir)
    
    # Faz upload do vídeo para o YouTube
    print("\nFazendo upload do vídeo para o YouTube...")
    video_id = publisher_agent.upload_video(video_path, metadata)
    
    if video_id:
        if video_id.startswith("SIMULATED"):
            print(f"\nUpload simulado para o YouTube")
        else:
            print(f"\nVídeo publicado no YouTube: https://www.youtube.com/watch?v={video_id}")
    else:
        print("\nErro: Não foi possível fazer upload do vídeo para o YouTube")
    
    return video_id

def main():
    """Função principal que coordena todo o fluxo de trabalho."""
    parser = argparse.ArgumentParser(description='Sistema de Animação Automatizada para YouTube')
    parser.add_argument('--story', type=str, default='data/historia.txt',
                        help='Caminho para o arquivo de texto com a história')
    parser.add_argument('--output', type=str, default='output',
                        help='Diretório para salvar os resultados')
    parser.add_argument('--client-secrets', type=str, default=None,
                        help='Caminho para o arquivo client_secrets.json para autenticação do YouTube')
    parser.add_argument('--steps', type=str, default='all',
                        help='Etapas a serem executadas (comma-separated): script,images,audio,animation,video,youtube')
    
    args = parser.parse_args()
    
    # Configura os diretórios
    setup_directories()
    
    # Verifica se o arquivo da história existe
    story_path = os.path.join(os.path.dirname(__file__), args.story)
    if not os.path.exists(story_path):
        print(f"Erro: O arquivo da história não foi encontrado em {story_path}")
        return
    
    # Cria um diretório de saída com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.dirname(__file__), args.output, f"projeto_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nIniciando processamento da história: {story_path}")
    print(f"Resultados serão salvos em: {output_dir}\n")
    
    # Determina quais etapas executar
    steps = args.steps.lower()
    run_all = steps == 'all'
    
    # Etapa 1: Processamento de roteiro
    script_path = None
    if run_all or 'script' in steps:
        script_path = process_story(story_path, output_dir)
    else:
        # Se não estamos processando o roteiro, procura por um roteiro existente
        script_path = os.path.join(output_dir, 'roteiro.json')
        if not os.path.exists(script_path):
            print(f"Erro: Roteiro não encontrado em {script_path}")
            return
    
    # Etapa 2: Geração de imagens
    images_dir = None
    if run_all or 'images' in steps:
        images_dir = generate_images(script_path, output_dir)
    else:
        images_dir = os.path.join(output_dir, 'images')
    
    # Etapa 3: Geração de áudio
    audio_dir = None
    if run_all or 'audio' in steps:
        audio_dir = generate_audio(script_path, output_dir)
    else:
        audio_dir = os.path.join(output_dir, 'audio')
    
    # Etapa 4: Animação
    animations_dir = None
    if run_all or 'animation' in steps:
        animations_dir = create_animations(script_path, images_dir, output_dir)
    else:
        animations_dir = os.path.join(output_dir, 'animations')
    
    # Etapa 5: Edição de vídeo
    video_path = None
    if run_all or 'video' in steps:
        video_path = edit_video(script_path, animations_dir, audio_dir, output_dir)
    else:
        # Procura pelo vídeo final
        video_dir = os.path.join(output_dir, 'video')
        potential_video = os.path.join(video_dir, 'video_final.mp4')
        if os.path.exists(potential_video):
            video_path = potential_video
    
    # Etapa 6: Upload para YouTube
    if (run_all or 'youtube' in steps) and video_path:
        client_secrets_file = args.client_secrets
        publish_to_youtube(script_path, video_path, output_dir, client_secrets_file)
    
    # Registra o tempo total de processamento
    end_time = datetime.now()
    
    print(f"\n{'='*50}")
    print("PROCESSAMENTO CONCLUÍDO")
    print(f"{'='*50}\n")
    print(f"Todos os resultados foram salvos em: {output_dir}")

if __name__ == "__main__":
    start_time = datetime.now()
    main()
    end_time = datetime.now()
    processing_time = end_time - start_time
    print(f"\nTempo total de processamento: {processing_time}")

if __name__ == "__main__":
    main()
