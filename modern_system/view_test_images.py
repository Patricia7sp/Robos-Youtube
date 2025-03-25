#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para visualizar as imagens geradas no teste de consistência visual.
Este script abre as imagens usando a biblioteca PIL (Pillow).
"""

import os
import sys
import glob
from PIL import Image

def main():
    """Função principal para visualizar as imagens de teste."""
    # Define o diretório das imagens
    test_dir = "/Users/patriciamenezes/anaconda3/Agents_Videos_Youtube/output/seed_test_20250321_205214/seed_consistency_test"
    
    # Verifica se o diretório existe
    if not os.path.exists(test_dir):
        print(f"Diretório não encontrado: {test_dir}")
        return 1
    
    # Encontra todas as imagens PNG no diretório
    image_paths = glob.glob(os.path.join(test_dir, "*.png"))
    
    if not image_paths:
        print(f"Nenhuma imagem encontrada em: {test_dir}")
        return 1
    
    print(f"Encontradas {len(image_paths)} imagens. Abrindo cada uma...")
    
    # Agrupa as imagens por tipo
    character_images = sorted([img for img in image_paths if "Alice" in img])
    scene_images = sorted([img for img in image_paths if "scene" in img])
    location_images = sorted([img for img in image_paths if "Magic_Castle" in img])
    
    # Abre cada grupo de imagens
    print("\nAbrindo imagens do personagem 'Alice'...")
    for img_path in character_images:
        print(f"Abrindo: {os.path.basename(img_path)}")
        img = Image.open(img_path)
        img.show()  # Isso abrirá a imagem no visualizador padrão do sistema
    
    print("\nAbrindo imagens da cena 'Floresta'...")
    for img_path in scene_images:
        print(f"Abrindo: {os.path.basename(img_path)}")
        img = Image.open(img_path)
        img.show()
    
    print("\nAbrindo imagens do local 'Magic Castle'...")
    for img_path in location_images:
        print(f"Abrindo: {os.path.basename(img_path)}")
        img = Image.open(img_path)
        img.show()
    
    print("\nTodas as imagens foram abertas.")
    print("Observe que cada conjunto de imagens usa o mesmo seed, garantindo consistência visual.")
    print("Personagem 'Alice': Seed 4984498")
    print("Cena 'Floresta': Seed 6692942")
    print("Local 'Magic Castle': Seed 3555704")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
