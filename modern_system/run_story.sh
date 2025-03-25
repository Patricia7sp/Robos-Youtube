#!/bin/bash

# Script para executar o sistema de geração de vídeos usando o Python do Anaconda
ANACONDA_PYTHON="/Users/patriciamenezes/anaconda3/bin/python"

# Verificar se o Python do Anaconda existe
if [ ! -f "$ANACONDA_PYTHON" ]; then
    echo "Erro: Python do Anaconda não encontrado em $ANACONDA_PYTHON"
    exit 1
fi

# Definir o estilo de imagem padrão
IMAGE_STYLE="Disney_3.0"

# Verificar se foi passado um estilo como argumento
if [ $# -ge 1 ]; then
    IMAGE_STYLE="$1"
fi

# Executar o script principal
echo "Executando o sistema de geração de vídeos com Python do Anaconda..."
echo "Usando estilo de imagem: $IMAGE_STYLE"
"$ANACONDA_PYTHON" test_story.py --style "$IMAGE_STYLE"

# Verificar se a execução foi bem-sucedida
if [ $? -eq 0 ]; then
    echo "Sistema executado com sucesso!"
else
    echo "Erro durante a execução do sistema."
    exit 1
fi
