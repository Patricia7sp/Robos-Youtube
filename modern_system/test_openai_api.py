#!/usr/bin/env python
"""
Script de teste para a API da OpenAI usando o modelo gpt-4o-mini
"""

import os
import json
import requests
from dotenv import load_dotenv

def main():
    # Carrega as variáveis de ambiente do arquivo .env
    load_dotenv()
    
    # Obtém a chave da API da OpenAI
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
    
    if not openai_key:
        print("Erro: Chave da API da OpenAI não configurada")
        return
    
    # Mascara a chave para exibição segura
    masked_key = openai_key[:6] + '*' * (len(openai_key) - 10) + openai_key[-4:] if len(openai_key) > 10 else openai_key
    print(f"Testando API da OpenAI com o modelo {openai_model}")
    print(f"Chave da API: {masked_key} (tamanho: {len(openai_key)})")
    
    # Configuração para a API da OpenAI
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_key}"
    }
    
    # Teste simples com o modelo de texto
    payload = {
        "model": openai_model,
        "messages": [
            {"role": "system", "content": "Você é um assistente útil."},
            {"role": "user", "content": "Crie uma pequena história infantil sobre uma menina chamada Alice e um coelho."}
        ],
        "max_tokens": 500
    }
    
    try:
        print("\nEnviando requisição para a API da OpenAI...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\nResposta recebida com sucesso!")
            print("\nHistória gerada:")
            print("-" * 50)
            print(result["choices"][0]["message"]["content"])
            print("-" * 50)
            print(f"\nModelo usado: {result.get('model', 'desconhecido')}")
            print(f"Tokens usados: {result.get('usage', {}).get('total_tokens', 'desconhecido')}")
        else:
            print(f"\nErro na API da OpenAI: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"\nErro ao processar a requisição: {str(e)}")

if __name__ == "__main__":
    main()
