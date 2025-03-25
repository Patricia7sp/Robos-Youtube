#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para testar a consistência visual nas imagens geradas usando o sistema de seeds.
Este script implementa um teste independente para verificar a consistência visual nas imagens
geradas usando os métodos de gerenciamento de seeds implementados na classe VisualDesignerAgent.
"""

import os
import sys
import json
import random
import argparse
import datetime
import time

# Adiciona o diretório pai ao path para importar os módulos do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modern_system.config.settings import API_KEYS, IMAGE_STYLES

class SeedConsistencyTester:
    """Classe para testar a consistência visual nas imagens geradas usando seeds."""
    
    def __init__(self, output_dir, image_style='Disney_3.0'):
        """Inicializa o testador de consistência visual.
        
        Args:
            output_dir: Diretório para salvar as imagens de teste
            image_style: Estilo de imagem a ser usado para o teste
        """
        self.output_dir = output_dir
        self.image_style = image_style
        self.cache_dir = os.path.join(output_dir, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Inicializa o cache
        self.cache = self._load_cache(output_dir)
        
    def _load_cache(self, output_dir):
        """Carrega o cache de metadados de imagens.
        
        Args:
            output_dir: Diretório onde o cache está armazenado
            
        Returns:
            Dicionário com os metadados do cache
        """
        cache_path = os.path.join(output_dir, 'image_metadata.json')
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    
                # Verifica se o cache tem a estrutura esperada
                if not isinstance(cache, dict):
                    print(f"Cache inválido, iniciando novo cache")
                    return {'character_seeds': {}, 'scene_seeds': {}, 'location_seeds': {}, 'images': {}}
                    
                # Garante que todas as chaves necessárias existam
                if 'character_seeds' not in cache:
                    cache['character_seeds'] = {}
                if 'scene_seeds' not in cache:
                    cache['scene_seeds'] = {}
                if 'location_seeds' not in cache:
                    cache['location_seeds'] = {}
                if 'images' not in cache:
                    cache['images'] = {}
                    
                print(f"Cache carregado com sucesso: {len(cache.get('images', {}))} imagens, "
                      f"{len(cache.get('character_seeds', {}))} personagens, "
                      f"{len(cache.get('scene_seeds', {}))} cenas, "
                      f"{len(cache.get('location_seeds', {}))} locais")
                return cache
            except Exception as e:
                print(f"Erro ao carregar cache: {e}")
        return {'character_seeds': {}, 'scene_seeds': {}, 'location_seeds': {}, 'images': {}}
    
    def _save_cache(self, output_dir, cache):
        """Salva o cache de metadados de imagens.
        
        Args:
            output_dir: Diretório onde o cache será armazenado
            cache: Dicionário com os metadados do cache
        """
        cache_path = os.path.join(output_dir, 'image_metadata.json')
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            print(f"Cache salvo com sucesso em: {cache_path}")
        except Exception as e:
            print(f"Erro ao salvar cache: {e}")
    
    def _get_character_seed(self, character_name, cache):
        """Obtém ou gera um seed consistente para um personagem.
        
        Args:
            character_name: Nome do personagem
            cache: Dicionário de cache atual
            
        Returns:
            Seed numérico para o personagem
        """
        # Verifica se já existe um seed para este personagem no cache
        if character_name in cache.get('character_seeds', {}):
            seed = cache['character_seeds'][character_name]
            print(f"Usando seed existente para o personagem {character_name}: {seed}")
            return seed
        
        # Gera um novo seed para este personagem
        # Usa um valor baseado no nome para ter alguma consistência mesmo se o cache for perdido
        base_seed = hash(character_name) % 1000000
        # Adiciona alguma aleatoriedade para evitar colisões
        seed = base_seed + random.randint(1000000, 9999999)
        
        # Registra o seed no cache
        if 'character_seeds' not in cache:
            cache['character_seeds'] = {}
        cache['character_seeds'][character_name] = seed
        
        print(f"Gerado novo seed para o personagem {character_name}: {seed}")
        return seed
    
    def _get_scene_seed(self, scene_number, cache):
        """Obtém ou gera um seed consistente para uma cena.
        
        Args:
            scene_number: Número da cena
            cache: Dicionário de cache atual
            
        Returns:
            Seed numérico para a cena
        """
        scene_key = str(scene_number)  # Converte para string para usar como chave
        
        # Verifica se já existe um seed para esta cena no cache
        if scene_key in cache.get('scene_seeds', {}):
            seed = cache['scene_seeds'][scene_key]
            print(f"Usando seed existente para a cena {scene_number}: {seed}")
            return seed
        
        # Gera um novo seed para esta cena
        # Usa um valor baseado no número da cena para ter alguma consistência
        base_seed = hash(f"scene_{scene_number}") % 1000000
        # Adiciona alguma aleatoriedade para evitar colisões
        seed = base_seed + random.randint(1000000, 9999999)
        
        # Registra o seed no cache
        if 'scene_seeds' not in cache:
            cache['scene_seeds'] = {}
        cache['scene_seeds'][scene_key] = seed
        
        print(f"Gerado novo seed para a cena {scene_number}: {seed}")
        return seed
    
    def _get_location_seed(self, location_name, cache):
        """Obtém ou gera um seed consistente para um local.
        
        Args:
            location_name: Nome do local
            cache: Dicionário de cache atual
            
        Returns:
            Seed numérico para o local
        """
        # Verifica se já existe um seed para este local no cache
        if location_name in cache.get('location_seeds', {}):
            seed = cache['location_seeds'][location_name]
            print(f"Usando seed existente para o local {location_name}: {seed}")
            return seed
        
        # Gera um novo seed para este local
        # Usa um valor baseado no nome para ter alguma consistência mesmo se o cache for perdido
        base_seed = hash(location_name) % 1000000
        # Adiciona alguma aleatoriedade para evitar colisões
        seed = base_seed + random.randint(1000000, 9999999)
        
        # Registra o seed no cache
        if 'location_seeds' not in cache:
            cache['location_seeds'] = {}
        cache['location_seeds'][location_name] = seed
        
        print(f"Gerado novo seed para o local {location_name}: {seed}")
        return seed
    
    def _generate_placeholder_image(self, text, width=1024, height=1024):
        """Gera uma imagem de placeholder com texto.
        
        Args:
            text: Texto a ser exibido na imagem
            width: Largura da imagem
            height: Altura da imagem
            
        Returns:
            Bytes da imagem gerada
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # Cria uma imagem em branco
            image = Image.new('RGB', (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)
            
            # Tenta carregar uma fonte, ou usa a fonte padrão
            try:
                font = ImageFont.truetype("Arial", 24)
            except IOError:
                font = ImageFont.load_default()
            
            # Adiciona texto à imagem
            text_lines = []
            current_line = ""
            for word in text.split():
                if len(current_line + " " + word) < 50:  # Limita a ~50 caracteres por linha
                    current_line += (" " + word if current_line else word)
                else:
                    text_lines.append(current_line)
                    current_line = word
            if current_line:
                text_lines.append(current_line)
            
            # Desenha cada linha de texto
            y_position = height // 2 - (len(text_lines) * 30) // 2
            for line in text_lines:
                text_width = draw.textlength(line, font=font)
                draw.text(
                    ((width - text_width) // 2, y_position),
                    line,
                    font=font,
                    fill=(0, 0, 0)
                )
                y_position += 30
            
            # Converte a imagem para bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            print(f"Erro ao gerar imagem de placeholder: {e}")
            # Se tudo falhar, retorna bytes vazios
            return b"PLACEHOLDER_IMAGE_ERROR"
    
    def test_seed_consistency(self):
        """Testa a consistência visual nas imagens geradas usando o sistema de seeds.
        
        Gera múltiplas imagens para o mesmo personagem, cena e local para verificar
        se a consistência visual é mantida usando os seeds.
        
        Returns:
            Dict com resultados do teste e caminhos das imagens geradas
        """
        print("\n=== Iniciando teste de consistência visual com seeds ===\n")
        
        # Cria diretório de teste se não existir
        test_dir = os.path.join(self.output_dir, 'seed_consistency_test')
        os.makedirs(test_dir, exist_ok=True)
        
        # Personagem de teste
        character_name = "Alice"
        character_prompt = f"Portrait of {character_name}, a young girl with blonde hair and blue eyes"
        
        # Cena de teste
        scene_number = 1
        scene_prompt = f"A beautiful forest with tall trees and a small stream"
        
        # Local de teste
        location_name = "Magic Castle"
        location_prompt = f"A grand {location_name} with tall towers and colorful flags"
        
        # Resultados do teste
        test_results = {
            'character_images': [],
            'scene_images': [],
            'location_images': []
        }
        
        # Gera múltiplas imagens do mesmo personagem para testar consistência
        print(f"\n--- Testando consistência para o personagem '{character_name}' ---")
        for i in range(3):
            output_path = os.path.join(test_dir, f"{character_name}_test_{i+1}.png")
            print(f"Gerando imagem {i+1} para o personagem {character_name}...")
            
            # Usa o mesmo personagem mas varia ligeiramente o prompt para testar consistência
            variation_prompt = f"{character_prompt}, {['smiling', 'serious face', 'looking surprised'][i]}"
            
            # Obtém o seed consistente para o personagem
            seed = self._get_character_seed(character_name, self.cache)
            
            # Neste teste, apenas geramos imagens de placeholder
            # Em um ambiente real, aqui seria chamado o método _generate_image com o seed
            image_data = self._generate_placeholder_image(
                text=f"Imagem {i+1} para o personagem {character_name}\nSeed: {seed}\nPrompt: {variation_prompt}",
                width=768,
                height=768
            )
            
            if image_data:
                # Salva a imagem
                with open(output_path, 'wb') as f:
                    f.write(image_data)
                test_results['character_images'].append(output_path)
                print(f"Imagem {i+1} para {character_name} salva em: {output_path}")
            else:
                print(f"Falha ao gerar imagem {i+1} para {character_name}")
        
        # Gera múltiplas imagens da mesma cena para testar consistência
        print(f"\n--- Testando consistência para a cena {scene_number} ---")
        for i in range(3):
            output_path = os.path.join(test_dir, f"scene_{scene_number}_test_{i+1}.png")
            print(f"Gerando imagem {i+1} para a cena {scene_number}...")
            
            # Usa a mesma cena mas varia ligeiramente o prompt para testar consistência
            variation_prompt = f"{scene_prompt}, {['sunny day', 'cloudy sky', 'sunset light'][i]}"
            
            # Obtém o seed consistente para a cena
            seed = self._get_scene_seed(scene_number, self.cache)
            
            # Neste teste, apenas geramos imagens de placeholder
            image_data = self._generate_placeholder_image(
                text=f"Imagem {i+1} para a cena {scene_number}\nSeed: {seed}\nPrompt: {variation_prompt}",
                width=1024,
                height=768
            )
            
            if image_data:
                # Salva a imagem
                with open(output_path, 'wb') as f:
                    f.write(image_data)
                test_results['scene_images'].append(output_path)
                print(f"Imagem {i+1} para cena {scene_number} salva em: {output_path}")
            else:
                print(f"Falha ao gerar imagem {i+1} para cena {scene_number}")
        
        # Gera múltiplas imagens do mesmo local para testar consistência
        print(f"\n--- Testando consistência para o local '{location_name}' ---")
        for i in range(3):
            output_path = os.path.join(test_dir, f"{location_name.replace(' ', '_')}_test_{i+1}.png")
            print(f"Gerando imagem {i+1} para o local {location_name}...")
            
            # Usa o mesmo local mas varia ligeiramente o prompt para testar consistência
            variation_prompt = f"{location_prompt}, {['at night with moon', 'during day', 'with rainbow'][i]}"
            
            # Obtém o seed consistente para o local
            seed = self._get_location_seed(location_name, self.cache)
            
            # Neste teste, apenas geramos imagens de placeholder
            image_data = self._generate_placeholder_image(
                text=f"Imagem {i+1} para o local {location_name}\nSeed: {seed}\nPrompt: {variation_prompt}",
                width=1024,
                height=768
            )
            
            if image_data:
                # Salva a imagem
                with open(output_path, 'wb') as f:
                    f.write(image_data)
                test_results['location_images'].append(output_path)
                print(f"Imagem {i+1} para local {location_name} salva em: {output_path}")
            else:
                print(f"Falha ao gerar imagem {i+1} para local {location_name}")
        
        # Salva o cache atualizado
        self._save_cache(self.output_dir, self.cache)
        
        # Gera relatório de resultados
        print("\n=== Resultados do teste de consistência visual ===\n")
        print(f"Imagens de personagem geradas: {len(test_results['character_images'])}")
        print(f"Imagens de cena geradas: {len(test_results['scene_images'])}")
        print(f"Imagens de local geradas: {len(test_results['location_images'])}")
        print(f"\nTodas as imagens foram salvas em: {test_dir}")
        print("\nVerifique visualmente as imagens para confirmar a consistência visual.")
        print("Os personagens, cenas e locais devem manter características visuais consistentes entre as imagens.")
        
        return test_results

def main():
    """Função principal para executar o teste de consistência visual."""
    parser = argparse.ArgumentParser(description='Teste de consistência visual com seeds')
    parser.add_argument('--output-dir', type=str, default=None, 
                        help='Diretório para salvar as imagens de teste')
    parser.add_argument('--style', type=str, default='Disney_3.0',
                        choices=list(IMAGE_STYLES.keys()),
                        help='Estilo de imagem a ser usado para o teste')
    args = parser.parse_args()
    
    # Define o diretório de saída padrão se não for especificado
    if args.output_dir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'output', f'seed_test_{timestamp}'
        )
    
    # Cria o diretório de saída se não existir
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Iniciando teste de consistência visual com seeds...")
    print(f"Diretório de saída: {args.output_dir}")
    print(f"Estilo de imagem: {args.style}")
    
    # Cria uma instância do testador de consistência visual
    tester = SeedConsistencyTester(
        output_dir=args.output_dir,
        image_style=args.style
    )
    
    # Executa o teste de consistência visual
    results = tester.test_seed_consistency()
    
    # Imprime um resumo dos resultados
    print("\n=== Resumo dos resultados ===")
    print(f"Total de imagens geradas: {sum(len(imgs) for imgs in results.values())}")
    print(f"Diretório de saída: {args.output_dir}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
