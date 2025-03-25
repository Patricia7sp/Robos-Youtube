#!/usr/bin/env python
"""
Script de teste para o VisualDesignerAgent com a API do Qwen2.5
"""

import os
import json
import sys
from config.settings import API_KEYS
from agents.visual_designer import VisualDesignerAgent

def main():
    # Caminho para o roteiro gerado
    script_path = "/Users/patriciamenezes/anaconda3/Agents_Videos_Youtube/modern_system/output/projeto_20250317_200830/roteiro.json"
    
    # Diretório para salvar as imagens
    output_dir = "/Users/patriciamenezes/anaconda3/Agents_Videos_Youtube/modern_system/output/teste_imagens"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Testando VisualDesignerAgent com a API do Qwen2.5")
    print(f"Roteiro: {script_path}")
    print(f"Diretório de saída: {output_dir}")
    
    # Verificar as chaves de API carregadas
    print("\nChaves de API carregadas:")
    
    # Verifica e imprime a chave do Qwen (mascarada para segurança)
    qwen_key = os.environ.get('QWEN_API_KEY', '')
    if qwen_key:
        masked_key = qwen_key[:6] + '*' * (len(qwen_key) - 10) + qwen_key[-4:] if len(qwen_key) > 10 else qwen_key
        print(f"QWEN_API_KEY: ✓ Configurada - {masked_key} (tamanho: {len(qwen_key)})")
    else:
        print(f"QWEN_API_KEY: ✗ Não configurada")
    
    print(f"QWEN_IMAGE_API_KEY: {'✓ Configurada' if API_KEYS.get('QWEN_IMAGE_API_KEY') else '✗ Não configurada'}")
    
    # Verifica e imprime a chave da OpenAI (mascarada para segurança)
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    if openai_key:
        masked_key = openai_key[:6] + '*' * (len(openai_key) - 10) + openai_key[-4:] if len(openai_key) > 10 else openai_key
        print(f"OPENAI_API_KEY: ✓ Configurada - {masked_key} (tamanho: {len(openai_key)})")
        openai_model = os.environ.get('OPENAI_MODEL', 'não especificado')
        print(f"OPENAI_MODEL: {openai_model}")
    else:
        print(f"OPENAI_API_KEY: ✗ Não configurada")
    
    # Verifica e imprime a chave do ElevenLabs (mascarada para segurança)
    eleven_key = os.environ.get('ELEVENLABS_API_KEY', '')
    if eleven_key:
        masked_key = eleven_key[:6] + '*' * (len(eleven_key) - 10) + eleven_key[-4:] if len(eleven_key) > 10 else eleven_key
        print(f"ELEVENLABS_API_KEY: ✓ Configurada - {masked_key} (tamanho: {len(eleven_key)})")
    else:
        print(f"ELEVENLABS_API_KEY: ✗ Não configurada")
    
    # Verifica se o arquivo de roteiro existe
    if not os.path.exists(script_path):
        print(f"Erro: Arquivo de roteiro não encontrado em {script_path}")
        return
    
    # Carrega o roteiro para verificar seu conteúdo
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
        print(f"Roteiro carregado com sucesso. Contém {len(script_data)} cenas.")
    except Exception as e:
        print(f"Erro ao carregar o roteiro: {str(e)}")
        return
    
    # Inicializa o agente de design visual
    try:
        visual_agent = VisualDesignerAgent()
        print(f"VisualDesignerAgent inicializado. API Provider: {visual_agent.api_provider}")
    except Exception as e:
        print(f"Erro ao inicializar o VisualDesignerAgent: {str(e)}")
        return
    
    # Carrega o roteiro no agente
    try:
        visual_agent.load_script(script_path)
        print("Roteiro carregado no agente com sucesso.")
    except Exception as e:
        print(f"Erro ao carregar o roteiro no agente: {str(e)}")
        return
    
    # Testa a geração de imagens para um personagem
    try:
        # Pega o primeiro personagem do roteiro
        all_characters = set()
        for scene in script_data:
            all_characters.update(scene.get('characters', []))
        
        if all_characters:
            character = next(iter(all_characters))
            print(f"\nTestando geração de imagem para o personagem: {character}")
            
            prompt = visual_agent._generate_character_prompt(character)
            print(f"Prompt gerado: {prompt[:100]}...")
            
            image_data = visual_agent._generate_image(prompt)
            if image_data:
                # Salva a imagem
                character_dir = os.path.join(output_dir, 'characters')
                os.makedirs(character_dir, exist_ok=True)
                filename = f"{character.lower().replace(' ', '_')}.png"
                image_path = visual_agent._save_image(image_data, filename, character_dir)
                print(f"Imagem gerada com sucesso e salva em: {image_path}")
            else:
                print("Falha ao gerar a imagem do personagem.")
        else:
            print("Nenhum personagem encontrado no roteiro.")
    except Exception as e:
        print(f"Erro ao testar a geração de imagem: {str(e)}")
    
    # Testa a geração de imagens para uma cena
    try:
        if script_data:
            scene = script_data[0]  # Pega a primeira cena
            scene_number = scene.get('scene_number', 1)
            print(f"\nTestando geração de imagem para a cena {scene_number}: {scene.get('title', '')}")
            
            prompt = visual_agent._generate_scene_prompt(scene)
            print(f"Prompt gerado: {prompt[:100]}...")
            
            image_data = visual_agent._generate_image(prompt)
            if image_data:
                # Salva a imagem
                scene_dir = os.path.join(output_dir, 'scenes')
                os.makedirs(scene_dir, exist_ok=True)
                filename = f"scene_{scene_number}.png"
                image_path = visual_agent._save_image(image_data, filename, scene_dir)
                print(f"Imagem gerada com sucesso e salva em: {image_path}")
            else:
                print("Falha ao gerar a imagem da cena.")
        else:
            print("Nenhuma cena encontrada no roteiro.")
    except Exception as e:
        print(f"Erro ao testar a geração de imagem: {str(e)}")
    
    print("\nTeste concluído.")

if __name__ == "__main__":
    main()
