"""
Animator Agent
-------------
Este agente é responsável por transformar imagens estáticas em animações
para cada cena, utilizando técnicas de animação e movimento.
"""

import os
import json
import time
import requests
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path para importar módulos do projeto
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import API_KEYS, VIDEO_SETTINGS

class AnimatorAgent:
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o agente de animação.
        
        Args:
            api_key: Chave da API para serviço de animação (opcional)
        """
        self.api_key = api_key or API_KEYS.get('RUNWAY_API_KEY') or os.environ.get('RUNWAY_API_KEY')
        if not self.api_key:
            print("AVISO: Nenhuma chave de API fornecida. O agente funcionará em modo simulado.")
        
        self.video_settings = VIDEO_SETTINGS
        self.script = None
        self.scene_animations = {}
        
    def load_script(self, script_path: str) -> None:
        """
        Carrega o roteiro processado a partir de um arquivo JSON.
        
        Args:
            script_path: Caminho para o arquivo JSON do roteiro
        """
        with open(script_path, 'r', encoding='utf-8') as file:
            self.script = json.load(file)
        print(f"Roteiro carregado: {len(self.script)} cenas")
    
    def load_image_metadata(self, metadata_path: str) -> Dict[str, Any]:
        """
        Carrega os metadados das imagens geradas.
        
        Args:
            metadata_path: Caminho para o arquivo JSON de metadados
            
        Returns:
            Dicionário com metadados das imagens
        """
        with open(metadata_path, 'r', encoding='utf-8') as file:
            metadata = json.load(file)
        print(f"Metadados de imagens carregados: {len(metadata.get('scenes', {}))} cenas")
        return metadata
    
    def _generate_animation_prompt(self, scene: Dict[str, Any]) -> str:
        """
        Gera um prompt para orientar a animação de uma cena.
        
        Args:
            scene: Dicionário contendo informações da cena
            
        Returns:
            Prompt detalhado para geração da animação
        """
        title = scene.get('title', 'Cena sem título')
        location = scene.get('location', 'Indefinido')
        characters = scene.get('characters', [])
        actions = scene.get('actions', [])
        
        # Base do prompt
        prompt = f"Anime a cena '{title}' que se passa em {location}."
        
        # Adiciona personagens
        if characters:
            prompt += f" Com {', '.join(characters)} presentes."
        
        # Adiciona ações
        if actions:
            action_text = " ".join(actions)
            prompt += f" Ações principais: {action_text}."
        
        # Adiciona instruções de estilo
        prompt += " Estilo de animação suave e fluida para crianças, com movimentos naturais e expressivos."
        
        # Adiciona instruções técnicas
        prompt += f" Resolução {self.video_settings['resolution']}, {self.video_settings['fps']} FPS."
        
        return prompt
    
    def _animate_image_with_runway(self, image_path: str, prompt: str) -> Optional[str]:
        """
        Anima uma imagem usando a API Runway Gen-2.
        
        Args:
            image_path: Caminho para a imagem a ser animada
            prompt: Prompt descrevendo a animação desejada
            
        Returns:
            Caminho para o vídeo animado ou None em caso de falha
        """
        if not self.api_key:
            print("Modo simulado: Animando imagem com prompt:", prompt[:100] + "...")
            # Simula o tempo de animação
            time.sleep(3)
            return "animacao_simulada.mp4"
        
        try:
            # Endpoint da API Runway Gen-2
            url = "https://api.runwayml.com/v1/model/gen-2/generate"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Lê a imagem como base64
            with open(image_path, "rb") as image_file:
                import base64
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            payload = {
                "prompt": prompt,
                "input_image": encoded_image,
                "motion_bucket_id": 50,  # Controla a quantidade de movimento
                "cfg_scale": 7.0,        # Controla a fidelidade ao prompt
                "duration": 4            # Duração em segundos (máximo 4)
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                video_url = result.get("output_video_url")
                
                if video_url:
                    # Baixa o vídeo
                    video_response = requests.get(video_url)
                    if video_response.status_code == 200:
                        return video_response.content
            
            print(f"Erro ao animar imagem: {response.status_code}")
            print(response.text)
            return None
            
        except Exception as e:
            print(f"Erro ao animar imagem: {str(e)}")
            return None
    
    def _save_animation(self, animation_data: bytes, filename: str, output_dir: str) -> str:
        """
        Salva os dados da animação em um arquivo.
        
        Args:
            animation_data: Dados binários da animação
            filename: Nome do arquivo
            output_dir: Diretório de saída
            
        Returns:
            Caminho completo para a animação salva
        """
        os.makedirs(output_dir, exist_ok=True)
        animation_path = os.path.join(output_dir, filename)
        
        with open(animation_path, 'wb') as f:
            f.write(animation_data)
        
        return animation_path
    
    def animate_scene(self, scene_number: int, image_path: str, output_dir: str) -> Optional[str]:
        """
        Anima uma cena específica a partir de uma imagem.
        
        Args:
            scene_number: Número da cena
            image_path: Caminho para a imagem da cena
            output_dir: Diretório para salvar a animação
            
        Returns:
            Caminho para a animação gerada ou None em caso de falha
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi carregado. Execute load_script() primeiro.")
        
        # Encontra a cena pelo número
        scene = None
        for s in self.script:
            if s.get('scene_number') == scene_number:
                scene = s
                break
        
        if not scene:
            raise ValueError(f"Cena {scene_number} não encontrada no roteiro.")
        
        print(f"Animando Cena {scene_number}: {scene.get('title', '')}")
        
        # Gera o prompt para a animação
        prompt = self._generate_animation_prompt(scene)
        
        # Em modo de simulação, apenas registra o prompt
        if not self.api_key:
            print(f"Prompt para animação da Cena {scene_number}: {prompt}")
            animation_path = f"[Simulado] animation_scene_{scene_number:03d}.mp4"
            self.scene_animations[scene_number] = animation_path
            return animation_path
        
        # Anima a imagem com Runway
        animation_data = self._animate_image_with_runway(image_path, prompt)
        
        if animation_data:
            # Salva a animação
            filename = f"animation_scene_{scene_number:03d}.mp4"
            animation_path = self._save_animation(animation_data, filename, output_dir)
            self.scene_animations[scene_number] = animation_path
            print(f"Animação para Cena {scene_number} salva em: {animation_path}")
            return animation_path
        else:
            print(f"Falha ao animar Cena {scene_number}")
            return None
    
    def animate_all_scenes(self, images_dir: str, output_dir: str) -> Dict[int, str]:
        """
        Anima todas as cenas do roteiro.
        
        Args:
            images_dir: Diretório contendo as imagens das cenas
            output_dir: Diretório para salvar as animações
            
        Returns:
            Dicionário mapeando números de cenas para caminhos de animações
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi carregado. Execute load_script() primeiro.")
        
        # Carrega os metadados das imagens
        metadata_path = os.path.join(images_dir, 'image_metadata.json')
        if os.path.exists(metadata_path):
            image_metadata = self.load_image_metadata(metadata_path)
        else:
            raise FileNotFoundError(f"Metadados de imagens não encontrados em {metadata_path}")
        
        print(f"Animando {len(self.script)} cenas...")
        
        # Cria o diretório de saída para animações
        os.makedirs(output_dir, exist_ok=True)
        
        # Anima cada cena
        for scene in self.script:
            scene_number = scene.get('scene_number')
            
            # Obtém o nome do arquivo da imagem da cena
            scene_image_filename = image_metadata.get('scenes', {}).get(str(scene_number))
            if not scene_image_filename:
                print(f"Imagem para Cena {scene_number} não encontrada nos metadados.")
                continue
            
            # Remove o prefixo "[Simulado] " se existir
            if scene_image_filename.startswith('[Simulado] '):
                scene_image_filename = scene_image_filename[11:]
            
            # Caminho completo para a imagem
            scene_image_path = os.path.join(images_dir, 'scenes', scene_image_filename)
            
            # Verifica se a imagem existe
            if not os.path.exists(scene_image_path) and not scene_image_filename.startswith('[Simulado]'):
                print(f"Arquivo de imagem não encontrado: {scene_image_path}")
                continue
            
            # Anima a cena
            self.animate_scene(scene_number, scene_image_path, output_dir)
        
        # Salva os metadados das animações
        animation_metadata = {
            'animations': {str(k): os.path.basename(v) for k, v in self.scene_animations.items()}
        }
        
        metadata_path = os.path.join(output_dir, 'animation_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(animation_metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Animação de todas as cenas concluída. Metadados salvos em: {metadata_path}")
        
        return self.scene_animations
    
    def extend_animations(self, output_dir: str) -> Dict[int, str]:
        """
        Estende as animações para durações adequadas com base no roteiro.
        
        Args:
            output_dir: Diretório contendo as animações originais
            
        Returns:
            Dicionário mapeando números de cenas para caminhos de animações estendidas
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi carregado. Execute load_script() primeiro.")
        
        print("Estendendo animações para durações adequadas...")
        
        # Cria o diretório para animações estendidas
        extended_dir = os.path.join(output_dir, 'extended')
        os.makedirs(extended_dir, exist_ok=True)
        
        # Dicionário para armazenar caminhos das animações estendidas
        extended_animations = {}
        
        # Para cada cena, estende a animação com base no conteúdo
        for scene in self.script:
            scene_number = scene.get('scene_number')
            
            # Obtém o caminho da animação original
            original_animation = self.scene_animations.get(scene_number)
            if not original_animation:
                print(f"Animação para Cena {scene_number} não encontrada.")
                continue
            
            # Calcula a duração ideal com base no conteúdo da cena
            narration = scene.get('narration', '')
            dialogues = scene.get('dialogues', [])
            
            # Estimativa simples: 1 segundo para cada 15 caracteres de narração
            narration_duration = len(narration) / 15
            
            # Estimativa para diálogos: 1 segundo para cada 10 caracteres
            dialogue_duration = sum(len(d.get('text', '')) for d in dialogues) / 10
            
            # Duração total estimada
            estimated_duration = narration_duration + dialogue_duration
            
            # Limita a duração aos valores mínimo e máximo definidos
            duration = max(self.video_settings['scene_duration_min'], 
                          min(estimated_duration, self.video_settings['scene_duration_max']))
            
            print(f"Estendendo animação da Cena {scene_number} para {duration:.1f} segundos")
            
            # Em modo de simulação, apenas registra a extensão
            if original_animation.startswith('[Simulado]'):
                extended_path = f"[Simulado] extended_animation_scene_{scene_number:03d}.mp4"
                extended_animations[scene_number] = extended_path
                continue
            
            try:
                # Usa FFmpeg para estender a animação (loop)
                from moviepy.editor import VideoFileClip
                
                # Carrega o vídeo original
                clip = VideoFileClip(original_animation)
                
                # Calcula quantas vezes precisamos repetir o vídeo
                repeat_count = int(duration / clip.duration) + 1
                
                # Cria um novo clipe repetindo o original
                extended_clip = clip.loop(repeat_count)
                
                # Corta para a duração exata desejada
                extended_clip = extended_clip.subclip(0, duration)
                
                # Salva o vídeo estendido
                extended_filename = f"extended_animation_scene_{scene_number:03d}.mp4"
                extended_path = os.path.join(extended_dir, extended_filename)
                
                extended_clip.write_videofile(
                    extended_path,
                    codec='libx264',
                    audio=False,
                    fps=self.video_settings['fps']
                )
                
                # Fecha os clipes para liberar recursos
                clip.close()
                extended_clip.close()
                
                extended_animations[scene_number] = extended_path
                print(f"Animação estendida para Cena {scene_number} salva em: {extended_path}")
                
            except Exception as e:
                print(f"Erro ao estender animação para Cena {scene_number}: {str(e)}")
        
        # Salva os metadados das animações estendidas
        extended_metadata = {
            'extended_animations': {str(k): os.path.basename(v) for k, v in extended_animations.items()}
        }
        
        metadata_path = os.path.join(extended_dir, 'extended_animation_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(extended_metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Extensão de animações concluída. Metadados salvos em: {metadata_path}")
        
        return extended_animations


# Exemplo de uso
if __name__ == "__main__":
    agent = AnimatorAgent()
    
    # Carregar roteiro
    script_path = "../output/roteiro.json"
    if os.path.exists(script_path):
        agent.load_script(script_path)
        
        # Animar todas as cenas
        images_dir = "../output/images"
        output_dir = "../output/animations"
        
        animations = agent.animate_all_scenes(images_dir, output_dir)
        
        # Estender animações para durações adequadas
        agent.extend_animations(output_dir)
    else:
        print(f"Erro: Roteiro não encontrado em {script_path}")
