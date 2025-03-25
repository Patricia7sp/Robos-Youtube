#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para o pipeline completo de geração de histórias animadas
Este script demonstra o fluxo completo do sistema, desde o processamento do texto
até a geração das imagens e a criação do vídeo, mesmo quando as APIs não estão disponíveis.
"""

import os
import sys
import json
import time
from datetime import datetime

# Importa as configurações e agentes
from config.settings import API_KEYS, OUTPUT_DIR
from agents.script_processor import ScriptProcessorAgent
from agents.visual_designer import VisualDesignerAgent
from agents.voice_actor import VoiceActorAgent
from agents.video_creator_fixed import VideoCreatorAgent

def print_section(title):
    """Imprime um título de seção formatado"""
    print("\n" + "=" * 80)
    print((" {} ".format(title)).center(80, "="))
    print("=" * 80 + "\n")

def print_api_status():
    """Verifica e imprime o status das chaves de API"""
    print_section("Status das APIs")
    
    # Função para mascarar chaves de API
    def mask_key(key):
        if not key or len(key) < 10:
            return key
        return key[:6] + '*' * (len(key) - 10) + key[-4:]
    
    # Verifica as chaves de API
    qwen_key = os.environ.get('QWEN_API_KEY', '')
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    elevenlabs_key = os.environ.get('ELEVENLABS_API_KEY', '')
    
    print("QWEN_API_KEY: {} {}".format('✓' if qwen_key else '✗', mask_key(qwen_key) if qwen_key else 'Não configurada'))
    print("OPENAI_API_KEY: {} {}".format('✓' if openai_key else '✗', mask_key(openai_key) if openai_key else 'Não configurada'))
    print("ELEVENLABS_API_KEY: {} {}".format('✓' if elevenlabs_key else '✗', mask_key(elevenlabs_key) if elevenlabs_key else 'Não configurada'))
    
    # Verifica modelo da OpenAI
    openai_model = os.environ.get('OPENAI_MODEL', 'não especificado')
    print("OPENAI_MODEL: {}".format(openai_model))
    
    # Determina o modo de operação
    if qwen_key or openai_key:
        print("\nModo de operação: API (usando APIs disponíveis)")
    else:
        print("\nModo de operação: SIMULAÇÃO (nenhuma API disponível)")

def main():
    # Cria um diretório de saída com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = os.path.join(OUTPUT_DIR, "projeto_{}".format(timestamp))
    os.makedirs(project_dir, exist_ok=True)
    
    print_section("Iniciando Pipeline de Geração de História Animada")
    print("Diretório do projeto: {}".format(project_dir))
    
    # Verifica o status das APIs
    print_api_status()
    
    # Carrega a história de exemplo
    print_section("Carregando História")
    
    # Exemplo de história sobre Alice (baseada na memória do sistema)
    story = """
    Era uma tarde ensolarada de primavera quando Alice, uma estudante de literatura na Universidade de Oxford, 
    encontrou uma ninhada de gatinhos abandonados no jardim do campus. Eram cinco filhotes, todos malhados 
    como sua mãe, uma gata cinzenta que Alice conhecia bem e chamava de Mia.
    
    Alice sabia que animais não eram permitidos nos dormitórios, mas não podia deixar os filhotes à própria sorte. 
    Decidiu escondê-los temporariamente em um cantinho isolado do jardim, atrás de uma moita de rosas, 
    enquanto pensava em uma solução.
    
    Todos os dias, Alice levava leite e comida para Mia e seus filhotes. Numa dessas visitas, notou um homem 
    de aparência excêntrica observando-a atentamente. Era o Professor Ludovico, que lecionava matemática 
    e tinha fama de ser extremamente rigoroso e um tanto quanto estranho.
    
    "Senhorita Alice, o que faz escondida entre as roseiras?", perguntou ele, ajustando os óculos no nariz pontudo.
    
    Alice congelou. Seria o fim de seu pequeno refúgio para os gatos? Para sua surpresa, quando explicou a situação, 
    o professor sorriu.
    
    "Eu também tenho um fraco por felinos", confessou ele. "Minha casa tem espaço suficiente para todos eles, 
    incluindo a mãe."
    
    Aliviada, Alice ajudou o professor a transferir os gatos para sua casa, uma charmosa residência vitoriana 
    próxima ao campus. Lá dentro, Alice ficou maravilhada com a quantidade de livros, quebra-cabeças matemáticos, 
    e curiosidades que decoravam o lugar.
    
    "Você gosta de jogos, senhorita Alice?", perguntou o professor, mostrando um tabuleiro de xadrez com peças 
    esculpidas à mão.
    
    Enquanto jogavam, o professor contava histórias fantásticas, misturando matemática e fantasia de um jeito 
    que Alice nunca tinha imaginado ser possível.
    
    O tempo passou, e Alice tornou-se uma visitante regular na casa do professor. Ajudava a cuidar dos gatos 
    e ouvia, fascinada, as histórias cada vez mais elaboradas que ele contava.
    
    Um dia, ao chegar para uma visita, Alice encontrou o professor apressado, consultando repetidamente um 
    relógio de bolso.
    
    "Estou atrasado, muito atrasado!", exclamou ele.
    
    "Para onde vai com tanta pressa, professor?", perguntou Alice, intrigada.
    
    "Para um passeio de barco pelo Tâmisa com algumas crianças. Quer vir? Prometo contar uma história especial."
    
    Alice sorriu e aceitou o convite. Enquanto caminhavam para o rio, não pôde deixar de notar um coelho branco 
    que cruzou seu caminho, parecendo tão apressado quanto o professor.
    
    Aquela tarde de barco seria o início de uma amizade que inspiraria uma das mais famosas histórias da literatura infantil.
    """
    
    print("História carregada: {} palavras".format(len(story.split())))
    
    # Salva a história original
    story_path = os.path.join(project_dir, "historia_original.txt")
    with open(story_path, "w", encoding="utf-8") as f:
        f.write(story)
    print("História salva em: {}".format(story_path))
    
    # Etapa 1: Processamento do roteiro
    print_section("Etapa 1: Processamento do Roteiro")
    script_processor = ScriptProcessorAgent(api_key=API_KEYS.get('QWEN_API_KEY', ''))
    script_processor.load_story(story)
    
    print("Processando história...")
    script = script_processor.process_story()
    
    # Salva o roteiro processado
    script_path = os.path.join(project_dir, "roteiro.json")
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    print("Roteiro processado e salvo em: {}".format(script_path))
    print("Número de cenas: {}".format(len(script)))
    
    # Etapa 2: Geração de imagens
    print_section("Etapa 2: Geração de Imagens")
    images_dir = os.path.join(project_dir, "imagens")
    os.makedirs(images_dir, exist_ok=True)
    
    visual_designer = VisualDesignerAgent(
        api_key=API_KEYS.get('QWEN_IMAGE_API_KEY', ''),
        api_provider='qwen'
    )
    visual_designer.load_script(script)
    
    print("Gerando imagens para personagens...")
    character_images = visual_designer.generate_character_designs(output_dir=images_dir)
    
    print("\nImagens de personagens geradas:")
    for char, img_path in character_images.items():
        print("- {}: {}".format(char, img_path))
    
    print("\nGerando imagens para cenas...")
    scene_images = visual_designer.generate_scene_images(output_dir=images_dir)
    
    print("\nImagens de cenas geradas:")
    for scene_num, img_path in scene_images.items():
        print("- Cena {}: {}".format(scene_num, img_path))
    
    # Etapa 3: Geração de vozes (simulada para este teste)
    print_section("Etapa 3: Geração de Vozes")
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    print("Simulando geração de vozes...")
    # Aqui seria implementada a geração de vozes usando o VoiceActorAgent
    # Para este teste, apenas criamos arquivos vazios
    
    for i, scene in enumerate(script):
        audio_path = os.path.join(audio_dir, "cena_{}.mp3".format(i+1))
        # Cria um arquivo de áudio vazio para simular
        with open(audio_path, "wb") as f:
            f.write(b"audio_simulado")
        print("Áudio simulado para cena {}: {}".format(i+1, audio_path))
    
    # Etapa 3: Geração de vozes
    print_section("Etapa 3: Geração de Vozes")
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    voice_actor = VoiceActorAgent(api_key=API_KEYS.get('ELEVENLABS_API_KEY', ''))
    voice_actor.load_script(script)
    
    print("Gerando áudios para as cenas...")
    audio_files = voice_actor.generate_all_audio(output_dir=audio_dir)
    
    print("\nÁudios gerados:")
    for scene_num, audio_path in audio_files.items():
        print("- Cena {}: {}".format(scene_num, audio_path))
    
    # Etapa 4: Criação do vídeo
    print_section("Etapa 4: Criação do Vídeo")
    video_dir = os.path.join(project_dir, "video")
    os.makedirs(video_dir, exist_ok=True)
    
    print("Criando vídeo final...")
    video_creator = VideoCreatorAgent()
    video_creator.load_assets(
        script=script,
        character_images=character_images,
        scene_images=scene_images,
        audio_files=audio_files
    )
    
    video_path = video_creator.create_final_video(video_dir)
    print("Vídeo final criado em: {}".format(video_path))
    
    # Conclusão
    print_section("Pipeline Concluído")
    print("Projeto gerado com sucesso em: {}".format(project_dir))
    print("\nArquivos gerados:")
    print("- História original: {}".format(story_path))
    print("- Roteiro processado: {}".format(script_path))
    print("- Imagens: {} ({} arquivos)".format(images_dir, len(character_images) + len(scene_images)))
    print("- Áudios: {} ({} arquivos)".format(audio_dir, len(script)))
    print("- Vídeo final: {}".format(video_path))
    
    print("\nPara visualizar o resultado, abra o diretório do projeto:")
    print("open {}".format(project_dir))

if __name__ == "__main__":
    main()
