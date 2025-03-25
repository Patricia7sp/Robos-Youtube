#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para testar o sistema de cache de imagens do VisualDesignerAgent.
"""

import os
import sys
import time

# Comentário: Não estamos usando dotenv para simplificar o teste

# Adiciona o diretório atual ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.visual_designer import VisualDesignerAgent
from config.settings import API_KEYS, IMAGE_STYLES

def test_image_cache():
    """Testa o sistema de cache de imagens usando exclusivamente a Stability AI."""
    print("Iniciando teste do sistema de cache de imagens com Stability AI...")
    
    # Inicializa o agente com a API da Stability AI
    agent = VisualDesignerAgent(api_provider='stability')
    
    # Verifica se o agente está usando apenas Stability AI
    if agent.api_provider != 'stability':
        print("ERRO: O agente não está usando Stability AI como provedor principal!")
        return
    
    print("Provedor configurado corretamente: {}".format(agent.api_provider))
    
    # Define um prompt de teste
    test_prompt = "Alice no jardim da universidade com os gatinhos"
    
    # Primeira geração - deve usar a API e salvar no cache
    print("\n=== Primeira geração (sem cache) ===")
    start_time = time.time()
    image_data = agent._generate_image(test_prompt)
    first_gen_time = time.time() - start_time
    print("Tempo de geração: {:.2f} segundos".format(first_gen_time))
    print("Tamanho da imagem: {} bytes".format(len(image_data)))
    
    # Segunda geração - deve usar o cache
    print("\n=== Segunda geração (com cache) ===")
    start_time = time.time()
    cached_image_data = agent._generate_image(test_prompt)
    second_gen_time = time.time() - start_time
    print("Tempo de geração: {:.2f} segundos".format(second_gen_time))
    print("Tamanho da imagem: {} bytes".format(len(cached_image_data)))
    
    # Verifica se a segunda geração foi mais rápida (usando cache)
    if second_gen_time < first_gen_time:
        print("\n✅ Teste bem-sucedido: A segunda geração foi mais rápida, indicando uso do cache.")
        print("Economia de tempo: {:.2f} segundos ({:.1f}%)".format(first_gen_time - second_gen_time, (1 - second_gen_time/first_gen_time) * 100))
    else:
        print("\n❌ Teste falhou: A segunda geração não foi mais rápida.")
        
    # Verifica se o provedor usado foi Stability AI
    if agent.api_provider != 'stability':
        print("\n❌ Teste falhou: O agente não está usando Stability AI como provedor!")
    
    # Verifica se as imagens são idênticas
    if image_data == cached_image_data:
        print("✅ Teste bem-sucedido: As imagens são idênticas.")
    else:
        print("❌ Teste falhou: As imagens são diferentes.")
    
    # Teste com um prompt diferente
    print("\n=== Teste com prompt diferente ===")
    different_prompt = "O professor Ludovico na sala de aula de matemática"
    start_time = time.time()
    different_image = agent._generate_image(different_prompt)
    different_time = time.time() - start_time
    print("Tempo de geração: {:.2f} segundos".format(different_time))
    print("Tamanho da imagem: {} bytes".format(len(different_image)))
    
    # Verifica se a imagem com prompt diferente é diferente
    if different_image != image_data:
        print("✅ Teste bem-sucedido: A imagem com prompt diferente é diferente.")
    else:
        print("❌ Teste falhou: A imagem com prompt diferente é igual à primeira.")
    
    print("\nTeste do sistema de cache concluído.")

if __name__ == "__main__":
    test_image_cache()
