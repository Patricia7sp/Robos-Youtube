# -*- coding: utf-8 -*-
"""
Configurações do Sistema de Animação Automatizada
------------------------------------------------
Este arquivo contém todas as configurações e chaves de API necessárias para o sistema.
"""

import os
import sys

# Simples leitura manual de variáveis do arquivo .env
def load_env_vars():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        print("Carregando variáveis do arquivo .env")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    else:
        print("Arquivo .env não encontrado")

# Carrega as variáveis de ambiente
load_env_vars()

# Diretórios base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Configurações de API
# Substitua com suas próprias chaves de API quando estiver pronto para usar
API_KEYS = {
    # APIs de Texto e Análise
    'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY', ''),
    'OPENAI_MODEL': os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
    'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY', ''),
    'QWEN_API_KEY': os.environ.get('QWEN_API_KEY', ''),
    'IA_STUDIO_API_KEY': os.environ.get('IA_STUDIO_API_KEY', ''),
    'IA_STUDIO_MODEL': os.environ.get('IA_STUDIO_MODEL', 'gemini-2.0-flash'),
    'DEEPSEEK_API_KEY': os.environ.get('DEEPSEEK_API_KEY', ''),
    'DEEPSEEK_MODEL': os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat'),
    
    # APIs de Geração de Imagens
    'DALLE_API_KEY': os.environ.get('OPENAI_API_KEY', ''),  # Usa a mesma chave da OpenAI
    'QWEN_IMAGE_API_KEY': os.environ.get('QWEN_API_KEY', ''),  # Usa a mesma chave do Qwen para texto e imagem
    'IA_STUDIO_IMAGE_API_KEY': os.environ.get('IA_STUDIO_API_KEY', ''),  # Usa a mesma chave do IA Studio
    'DEEPSEEK_IMAGE_API_KEY': os.environ.get('DEEPSEEK_API_KEY', ''),  # Usa a mesma chave do Deepseek
    'STABILITY_API_KEY': os.environ.get('STABILITY_API_KEY', ''),
    
    # APIs de Animação
    'RUNWAY_API_KEY': os.environ.get('RUNWAY_API_KEY', ''),
    'DID_API_KEY': os.environ.get('DID_API_KEY', ''),
    
    # APIs de Áudio e Voz
    'ELEVENLABS_API_KEY': os.environ.get('ELEVENLABS_API_KEY', ''),
    'MUBERT_API_KEY': os.environ.get('MUBERT_API_KEY', ''),
    
    # API do YouTube
    'YOUTUBE_API_KEY': os.environ.get('YOUTUBE_API_KEY', ''),
}

# Configurações de estilo visual
ANIMATION_STYLE = {
    'style': 'children_storybook',  # Opções: children_storybook, anime, realistic, cartoon
    'color_palette': 'vibrant',     # Opções: vibrant, pastel, muted, dark
    'art_style': 'watercolor',      # Opções: watercolor, digital, pencil, oil_painting
}

# Configurações de voz
VOICE_SETTINGS = {
    'narrator': {
        'voice_id': 'onyx',  # ID da voz no ElevenLabs
        'stability': 0.5,
        'similarity_boost': 0.75,
    },
    'characters': {
        'Alice': {
            'voice_id': 'bella',  # ID da voz no ElevenLabs
            'stability': 0.3,
            'similarity_boost': 0.8,
        },
        'Ludovico': {
            'voice_id': 'josh',  # ID da voz no ElevenLabs
            'stability': 0.6,
            'similarity_boost': 0.7,
        },
        # Adicione mais personagens conforme necessário
    },
}

# Configurações de vídeo
VIDEO_SETTINGS = {
    'resolution': '1920x1080',
    'fps': 30,
    'transition_duration': 1.0,  # segundos
    'scene_duration_min': 5.0,   # duração mínima de uma cena em segundos
    'scene_duration_max': 15.0,  # duração máxima de uma cena em segundos
}

# Configurações do YouTube
YOUTUBE_SETTINGS = {
    'category': '22',  # Categoria "People & Blogs"
    'privacy_status': 'private',  # Opções: private, public, unlisted
    'tags': ['história infantil', 'animação', 'contos', 'crianças'],
    'default_language': 'pt-BR',
}

# Estilos de imagem disponíveis
IMAGE_STYLES = {
    '3D_cartoon': '3D cartoon style with vibrant colors and smooth textures',
    'Disney_3.0': 'Disney 3.0 style with expressive characters and magical atmosphere',
    'Epic': 'Epic fantasy style with dramatic lighting and detailed environments',
    'Realistic': 'Realistic style with natural proportions and detailed textures',
    'Animals': 'Stylized animal characters with expressive features and natural environments'
}

# Estilo de imagem padrão
IMAGE_STYLE = os.environ.get('IMAGE_STYLE', 'Disney_3.0')

# Configurações de processamento
PROCESSING_SETTINGS = {
    'max_concurrent_tasks': 2,
    'timeout': 300,  # segundos
}

# Configurações de cache
CACHE_SETTINGS = {
    'enabled': True,
    'directory': os.path.join(BASE_DIR, 'cache'),
    'max_size_gb': 2,
}
