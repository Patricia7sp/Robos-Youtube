#!/bin/bash

# Script para testar o sistema de cache de imagens usando o ambiente Anaconda

# Diretório do projeto
PROJECT_DIR="/Users/patriciamenezes/anaconda3/Agents_Videos_Youtube/modern_system"

# Ativa o ambiente Anaconda (ajuste o nome do ambiente se necessário)
source /Users/patriciamenezes/anaconda3/bin/activate

# Navega para o diretório do projeto
cd "$PROJECT_DIR"

# Executa o script de teste
python test_image_cache.py

# Desativa o ambiente Anaconda
conda deactivate
