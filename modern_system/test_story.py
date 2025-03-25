#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import json
import sys
import argparse

# Importa os agentes necessários
from agents.visual_designer import VisualDesignerAgent
from agents.video_creator import VideoCreatorAgent
from agents.voice_actor import VoiceActorAgent
from agents.youtube_publisher import YouTubePublisherAgent

# Importa configurações
from config.settings import IMAGE_STYLES

def main():
    # Configura argumentos da linha de comando
    parser = argparse.ArgumentParser(description='Sistema de geração de vídeos animados')
    parser.add_argument('--skip-images', action='store_true', help='Pular geração de imagens')
    parser.add_argument('--skip-audio', action='store_true', help='Pular geração de áudio')
    parser.add_argument('--skip-video', action='store_true', help='Pular geração de vídeo')
    parser.add_argument('--upload', action='store_true', help='Fazer upload para o YouTube')
    parser.add_argument('--style', type=str, choices=list(IMAGE_STYLES.keys()), help='Estilo de imagem a ser usado')
    args = parser.parse_args()
    
    # Configuração de diretórios
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data')
    output_dir = os.path.join(data_dir, 'output')
    
    # Carrega o script estruturado
    script_path = os.path.join(output_dir, 'script.json')
    with open(script_path, 'r') as f:
        script = json.load(f)
    
    # Determina o estilo de imagem a ser usado
    if args.style:
        # Usa o estilo fornecido como argumento de linha de comando
        selected_style = args.style
        print(f"\nUsando estilo fornecido via argumento: {selected_style.replace('_', ' ')}")
    else:
        # Solicita ao usuário o estilo de imagem desejado
        print("\nEscolha o estilo de imagem para o vídeo:")
        for i, (style_key, style_desc) in enumerate(IMAGE_STYLES.items(), 1):
            print(f"{i}. {style_key.replace('_', ' ')} - {style_desc}")
        
        # Obtém a escolha do usuário
        while True:
            try:
                choice = int(input("\nDigite o número do estilo desejado (1-{}): ".format(len(IMAGE_STYLES))))
                if 1 <= choice <= len(IMAGE_STYLES):
                    selected_style = list(IMAGE_STYLES.keys())[choice-1]
                    break
                else:
                    print("Por favor, escolha um número entre 1 e {}".format(len(IMAGE_STYLES)))
            except ValueError:
                print("Por favor, digite um número válido.")
        
        print(f"\nEstilo selecionado: {selected_style.replace('_', ' ')}")
    
    # Inicializa os agentes
    visual_agent = VisualDesignerAgent(image_style=selected_style)
    voice_agent = VoiceActorAgent()
    video_agent = VideoCreatorAgent()
    youtube_agent = YouTubePublisherAgent()
    
    # Gera imagens para cada cena
    print("\nGerando imagens para as cenas...")
    images_dir = os.path.join(output_dir, 'images')
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
    
    scene_images = {}
    character_images = {}
    
    # Carrega o script no agente visual
    visual_agent.load_script(script['scenes'])
    
    # Gera imagens para todas as cenas de uma vez
    try:
        scene_images = visual_agent.generate_scene_images(images_dir)
        print("Imagens de cenas geradas com sucesso.")
    except Exception as e:
        print("Erro ao gerar imagens de cenas: {0}".format(str(e)))
        scene_images = {}
    
    # Gera imagens para personagens
    try:
        # Extrai todos os personagens do script
        all_characters = set()
        for scene in script['scenes']:
            for character in scene.get('characters', []):
                all_characters.add(character)
        
        # Define prompts para cada personagem
        character_prompts = {}
        for character in all_characters:
            if character == "Alice":
                character_prompts[character] = "Uma menina curiosa e imaginativa de 10 anos, cabelos castanhos, vestido azul simples, estilo Alice no País das Maravilhas"
            elif character == "Ludovico":
                character_prompts[character] = "Um professor alto e magro, aparência excêntrica e gentil, olhos azuis intensos, roupas formais mas um pouco desarrumadas"
            elif character in ["Lóri", "Edith"]:
                character_prompts[character] = "Uma menina jovem, irmã de Alice, vestido simples da época vitoriana"
            else:
                character_prompts[character] = "Personagem {0} da história, estilo ilustração infantil".format(character)
        
        # Configura os prompts no agente visual
        visual_agent.character_prompts = character_prompts
        
        # Gera os designs dos personagens
        character_images = visual_agent.generate_character_designs(images_dir)
        print("Imagens de personagens geradas com sucesso.")
    except Exception as e:
        print("Erro ao gerar imagens de personagens: {0}".format(str(e)))
        character_images = {}
    
    # Gera áudio para cada cena
    audio_files = {}
    if not args.skip_audio:
        try:
            print("\nGerando áudio para as cenas...")
            audio_dir = os.path.join(output_dir, 'audio')
            if not os.path.exists(audio_dir):
                os.makedirs(audio_dir)
            
            # Carrega o script no agente de voz
            voice_agent.load_script(script['scenes'])
            
            # Gera áudio para cada cena
            for i, scene in enumerate(script['scenes']):
                scene_number = scene.get('scene_number', i + 1)
                audio_path = voice_agent.generate_scene_audio(scene, audio_dir)
                if audio_path:
                    audio_files[scene_number] = audio_path
            
            print("Áudio gerado com sucesso para {0} cenas.".format(len(audio_files)))
        except Exception as e:
            print("Erro ao gerar áudio: {0}".format(str(e)))
            audio_files = {}
    
    # Cria o vídeo final
    final_video = None
    if not args.skip_video:
        try:
            # Carrega os recursos no agente de vídeo
            print("\nCarregando recursos no agente de vídeo...")
            video_agent.load_assets(
                script=script['scenes'],
                character_images=character_images,
                scene_images=scene_images,
                audio_files=audio_files
            )
            
            # Configura o modo de animação
            video_agent.animation_mode = "ken_burns"  # Modo de animação Ken Burns para dar movimento às imagens estáticas
            
            # Cria o vídeo final
            print("\nCriando vídeo final...")
            final_video = video_agent.create_final_video(output_dir)
            print("\nVídeo criado com sucesso: {0}".format(final_video))
            
        except Exception as e:
            print("\nErro ao criar vídeo: {0}".format(str(e)))
    
    # Upload para o YouTube
    if args.upload and final_video and os.path.exists(final_video):
        try:
            print("\nPreparando upload para o YouTube...")
            # Extrai título e descrição do script
            title = script.get('title', 'História Animada')
            description = script.get('description', 'Uma história animada gerada automaticamente.')
            
            # Prepara as tags
            tags = ['história infantil', 'animação', 'contos para crianças']
            if 'tags' in script:
                tags.extend(script['tags'])
            
            # Gera metadados otimizados
            metadata = {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22',  # Categoria 22 = People & Blogs
                'privacyStatus': 'unlisted'  # Começa como não-listado para revisão
            }
            
            # Carrega o script no agente do YouTube para otimização de SEO
            youtube_agent.load_script(script_path)
            
            # Opcionalmente, pode usar metadados gerados automaticamente
            # metadata = youtube_agent.generate_metadata()
            
            # Salva os metadados para referência
            metadata_path = youtube_agent.save_metadata(metadata, output_dir)
            
            # Faz o upload
            video_id = youtube_agent.upload_video(final_video, metadata)
            
            if video_id:
                print("\nVídeo enviado com sucesso para o YouTube: https://www.youtube.com/watch?v={0}".format(video_id))
            else:
                print("\nErro ao fazer upload do vídeo para o YouTube.")
                
        except Exception as e:
            print("\nErro ao fazer upload para o YouTube: {0}".format(str(e)))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\nErro no programa principal: {0}".format(str(e)))
