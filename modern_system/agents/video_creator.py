#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agente de criação de vídeo para o sistema de animação automatizada.
Este módulo é responsável por criar vídeos animados a partir de imagens e áudio.
"""

import os
import time
import json
import random
import tempfile
import shutil
import sys

# Adiciona o diretório raiz ao path para importar módulos do projeto
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.append(sys_path)

try:
    import numpy as np
    from PIL import Image
    import moviepy.editor as mpy
    from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips
    
    # Corrige o problema com ANTIALIAS em versões mais recentes do Pillow
    if not hasattr(Image, 'ANTIALIAS'):
        # Em versões mais recentes do Pillow, ANTIALIAS foi substituído por LANCZOS
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    print("AVISO: Bibliotecas de processamento de vídeo não encontradas.")
    print("Execute: pip install numpy pillow moviepy")

from config.settings import OUTPUT_DIR

class VideoCreatorAgent:
    """
    Agente responsável pela criação de vídeos animados a partir de imagens e áudio.
    Utiliza a biblioteca MoviePy para criar efeitos de animação e combinar elementos.
    """
    
    def __init__(self):
        """
        Inicializa o agente de criação de vídeo.
        """
        self.script = []
        self.character_images = {}
        self.scene_images = {}
        self.audio_files = {}
        self.fps = 30  # Aumentado para animações mais suaves
        self.resolution = (1920, 1080)  # Formato 16:9 padrão
        self.transition_duration = 1.0  # Duração das transições em segundos
        
        # Modo de animação ("simple", "complex", "ken_burns", "parallax")
        self.animation_mode = "simple"
        
        # Parâmetros de animação
        self.animation_params = {
            "ken_burns": {
                "zoom_range": (1.0, 1.3),  # (min_zoom, max_zoom)
                "pan_range": (-0.2, 0.2),  # (min_pan, max_pan) como fração da imagem
                "duration_factor": 0.8,    # Fração da duração total para cada movimento
                "smooth_factor": 0.3       # Suavidade das transições (0-1)
            },
            "parallax": {
                "depth_layers": 3,         # Número de camadas para efeito parallax
                "depth_factor": 0.1,       # Intensidade do efeito de profundidade
                "movement_speed": 0.5      # Velocidade do movimento parallax
            }
        }
        
        # Verifica se as bibliotecas necessárias estão disponíveis
        self.libraries_available = True
        try:
            import numpy as np
            import moviepy.editor as mpy
            from PIL import Image
        except ImportError:
            self.libraries_available = False
            print("AVISO: Algumas bibliotecas necessárias não estão disponíveis.")
            print("O agente funcionará em modo simulado.")
    
    def load_assets(self, script, character_images, scene_images, audio_files):
        """
        Carrega os recursos necessários para a criação do vídeo.
        
        Args:
            script: Lista de cenas do roteiro
            character_images: Dicionário mapeando personagens para caminhos de imagens
            scene_images: Dicionário mapeando números de cena para caminhos de imagens
            audio_files: Dicionário mapeando números de cena para caminhos de arquivos de áudio
        """
        self.script = script
        self.character_images = character_images
        self.scene_images = scene_images
        self.audio_files = audio_files
    
    def _create_scene_animation(self, scene, scene_image_path, audio_path, output_dir):
        """
        Cria uma animação para uma cena específica.
        
        Args:
            scene: Dicionário com informações da cena
            scene_image_path: Caminho para a imagem da cena
            audio_path: Caminho para o arquivo de áudio da cena
            output_dir: Diretório de saída para o vídeo da cena
            
        Returns:
            Caminho para o arquivo de vídeo da cena
        """
        if not self.libraries_available:
            # Modo simulado - apenas cria um arquivo vazio
            scene_number = scene.get("scene_number", 0)
            output_path = os.path.join(output_dir, "cena_{0}.mp4".format(scene_number))
            with open(output_path, "wb") as f:
                f.write(b"VIDEO_SIMULADO")
            return output_path
        
        scene_number = scene.get("scene_number", 0)
        scene_title = scene.get("title", "Cena {0}".format(scene_number))
        
        # Carrega a imagem da cena
        try:
            scene_img = Image.open(scene_image_path)
            scene_img_array = np.array(scene_img)
        except Exception as e:
            print("Erro ao carregar imagem da cena: {0}".format(str(e)))
            # Cria uma imagem preta como fallback
            scene_img_array = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        # Carrega o áudio da cena
        try:
            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration
        except Exception as e:
            print("Erro ao carregar áudio da cena: {0}".format(str(e)))
            # Define uma duração padrão se não conseguir carregar o áudio
            audio_duration = 10.0
            audio_clip = None
        
        # Cria o clip de imagem base
        image_clip = ImageClip(scene_img_array)
        
        # Aplica efeitos de animação avançados
        animated_clips = []
        
        # Define parâmetros de animação com base no modo selecionado
        zoom_duration = audio_duration
        
        # Parâmetros padrão
        zoom_factor = 1.15
        pan_range = 100  # Pixels para movimento panorâmico
        rotation_angle = 3  # Graus para rotação suave
        
        # Ajusta parâmetros com base no modo de animação
        if self.animation_mode == "ken_burns":
            # Parâmetros para efeito Ken Burns
            kb_params = self.animation_params["ken_burns"]
            min_zoom, max_zoom = kb_params["zoom_range"]
            min_pan, max_pan = kb_params["pan_range"]
            smooth_factor = kb_params["smooth_factor"]
            
            # Gera valores aleatórios para esta cena
            import random
            start_zoom = random.uniform(min_zoom, max_zoom)
            end_zoom = random.uniform(min_zoom, max_zoom)
            
            # Garante que haja uma diferença mínima entre os zooms
            while abs(start_zoom - end_zoom) < 0.1:
                end_zoom = random.uniform(min_zoom, max_zoom)
            
            # Define pontos de foco para o pan (de onde para onde)
            # Escolhe aleatoriamente entre cantos e centro
            positions = [(-min_pan, -min_pan), (min_pan, -min_pan), 
                         (-min_pan, min_pan), (min_pan, min_pan), (0, 0)]
            start_pos = random.choice(positions)
            end_pos = random.choice([p for p in positions if p != start_pos])
            
            print(f"Aplicando efeito Ken Burns: Zoom {start_zoom:.2f}->{end_zoom:.2f}, Pan {start_pos}->{end_pos}")
        
        def complex_animation(t):
            # Combina zoom, pan e rotação
            progress = t / zoom_duration
            current_zoom = 1 + (zoom_factor - 1) * (np.sin(progress * np.pi) ** 2)
            
            # Movimento panorâmico suave
            pan_x = pan_range * np.sin(progress * 2 * np.pi)
            pan_y = pan_range/2 * np.sin(progress * 3 * np.pi)
            
            # Rotação suave
            angle = rotation_angle * np.sin(progress * 2 * np.pi)
            
            return current_zoom, (pan_x, pan_y), angle
            
        def ken_burns_animation(t):
            # Efeito Ken Burns: movimento suave de um ponto focal para outro com zoom
            progress = t / zoom_duration
            
            # Suaviza a progressão com uma função de easing
            # Usa uma curva de Bezier cúbica para suavizar o movimento
            smooth_progress = progress * progress * (3 - 2 * progress)
            
            # Interpola entre os zooms inicial e final
            current_zoom = start_zoom + (end_zoom - start_zoom) * smooth_progress
            
            # Interpola entre as posições de pan inicial e final
            pan_x = start_pos[0] + (end_pos[0] - start_pos[0]) * smooth_progress
            pan_y = start_pos[1] + (end_pos[1] - start_pos[1]) * smooth_progress
            
            # Converte os valores de pan de frações para pixels
            pan_x_pixels = pan_x * self.resolution[0]
            pan_y_pixels = pan_y * self.resolution[1]
            
            # Sem rotação para o efeito Ken Burns clássico
            angle = 0
            
            return current_zoom, (pan_x_pixels, pan_y_pixels), angle
            
        def parallax_animation(t):
            # Efeito parallax: camadas da imagem movendo-se em velocidades diferentes
            progress = t / zoom_duration
            params = self.animation_params["parallax"]
            
            # Zoom suave
            current_zoom = 1.0 + 0.1 * np.sin(progress * np.pi)
            
            # Movimento horizontal com efeito parallax
            pan_x = pan_range * np.sin(progress * 2 * np.pi * params["movement_speed"])
            pan_y = pan_range/3 * np.sin(progress * 3 * np.pi * params["movement_speed"])
            
            # Pequena rotação
            angle = rotation_angle/2 * np.sin(progress * np.pi)
            
            return current_zoom, (pan_x, pan_y), angle
        
        # Aplica os efeitos com base no modo de animação selecionado
        try:
            # Seleciona a função de animação com base no modo
            animation_func = complex_animation  # Padrão
            
            if self.animation_mode == "ken_burns":
                animation_func = ken_burns_animation
            elif self.animation_mode == "parallax":
                animation_func = parallax_animation
            elif self.animation_mode == "simple":
                # Modo simples: apenas zoom suave sem pan ou rotação
                def simple_animation(t):
                    progress = t / zoom_duration
                    current_zoom = 1 + 0.05 * np.sin(progress * np.pi)
                    return current_zoom, (0, 0), 0
                animation_func = simple_animation
            
            # Aplica a função de animação selecionada
            animated_clip = image_clip.resize(lambda t: animation_func(t)[0])
            animated_clip = animated_clip.rotate(lambda t: animation_func(t)[2])
            
            def dynamic_position(t):
                _, (pan_x, pan_y), _ = animation_func(t)
                return ('center', 'center', pan_x, pan_y)
            
            animated_clip = animated_clip.set_position(dynamic_position)
            animated_clip = animated_clip.set_duration(zoom_duration)
            
            # Adiciona fade in/out suave
            animated_clip = animated_clip.crossfadein(self.transition_duration)
            animated_clip = animated_clip.crossfadeout(self.transition_duration)
            
            animated_clips.append(animated_clip)
        except Exception as e:
            print("Erro ao aplicar efeitos de animação: {0}".format(str(e)))
            # Fallback para clip sem efeito
            image_clip = image_clip.set_position("center").set_duration(zoom_duration)
            animated_clips.append(image_clip)
        
        # Se houver personagens na cena, adiciona suas imagens
        characters = scene.get("characters", [])
        if characters and self.character_images:
            for i, character in enumerate(characters):
                character_name = character if isinstance(character, str) else character.get("name", "")
                if character_name in self.character_images:
                    try:
                        char_img_path = self.character_images[character_name]
                        char_img = Image.open(char_img_path)
                        char_img_array = np.array(char_img)
                        
                        # Redimensiona a imagem do personagem
                        char_clip = ImageClip(char_img_array)
                        
                        # Usa resize com valor fixo em vez de função
                        char_clip = char_clip.resize(height=400)  # Altura fixa de 400 pixels
                        
                        # Posiciona o personagem na cena
                        position_x = 300 + i * 400  # Espaçamento horizontal
                        position_y = 600  # Posição vertical fixa
                        
                        # Adiciona efeitos de movimento complexos para personagens
                        def char_position(t):
                            # Movimento fluido combinando várias funções trigonométricas
                            progress = t / zoom_duration
                            
                            # Movimento vertical suave
                            y_offset = 30 * np.sin(progress * 2 * np.pi)
                            
                            # Movimento horizontal suave
                            x_offset = 20 * np.sin(progress * 3 * np.pi)
                            
                            # Movimento em figura-8
                            figure8_x = 15 * np.sin(progress * 4 * np.pi)
                            figure8_y = 10 * np.sin(progress * 8 * np.pi)
                            
                            return (position_x + x_offset + figure8_x,
                                    position_y + y_offset + figure8_y)
                        
                        # Aplica efeitos aos personagens
                        char_clip = char_clip.set_position(char_position)
                        
                        # Adiciona rotação suave
                        char_clip = char_clip.rotate(lambda t: 5 * np.sin(t * 2 * np.pi / 3))
                        
                        # Adiciona efeito de escala pulsante
                        char_clip = char_clip.resize(lambda t: 1 + 0.05 * np.sin(t * 2 * np.pi))
                        
                        # Define duração e adiciona fade
                        char_clip = char_clip.set_duration(zoom_duration)
                        char_clip = char_clip.crossfadein(self.transition_duration/2)
                        char_clip = char_clip.crossfadeout(self.transition_duration/2)
                        
                        animated_clips.append(char_clip)
                    except Exception as e:
                        print("Erro ao adicionar personagem {0}: {1}".format(character_name, str(e)))
        
        # Adiciona título da cena
        try:
            # Cria título com efeitos mais elaborados
            title_clip = TextClip(scene_title, fontsize=70, color='white', font="Arial-Bold")
            
            def title_position(t):
                # Movimento suave para o título
                y_base = 100
                x_offset = 20 * np.sin(t * 2 * np.pi)
                y_offset = 10 * np.sin(t * 3 * np.pi)
                return ('center', y_base + y_offset, x_offset)
            
            title_clip = title_clip.set_position(title_position)
            title_clip = title_clip.set_duration(5)  # Duração aumentada
            
            # Efeitos de entrada e saída mais suaves
            title_clip = title_clip.crossfadein(1.0)
            title_clip = title_clip.crossfadeout(1.0)
            
            # Adiciona um brilho pulsante
            title_clip = title_clip.resize(lambda t: 1 + 0.03 * np.sin(t * 4 * np.pi))
            
            animated_clips.append(title_clip)
        except Exception as e:
            print("Erro ao adicionar título: {0}".format(str(e)))
        
        # Combina todos os clips
        composite_clip = CompositeVideoClip(animated_clips, size=self.resolution)
        
        # Define a duração baseada no áudio
        composite_clip = composite_clip.set_duration(audio_duration)
        
        # Adiciona o áudio
        if audio_clip:
            composite_clip = composite_clip.set_audio(audio_clip)
        
        # Define o caminho de saída
        output_path = os.path.join(output_dir, "cena_{0}.mp4".format(scene_number))
        
        # Salva o vídeo
        try:
            composite_clip.write_videofile(
                output_path, 
                fps=self.fps, 
                codec='libx264', 
                audio_codec='aac',
                preset='ultrafast',  # Para testes, use 'medium' para produção
                threads=4
            )
            print("Vídeo da cena {0} salvo em: {1}".format(scene_number, output_path))
        except Exception as e:
            print("Erro ao salvar vídeo: {0}".format(str(e)))
            # Cria um arquivo vazio como fallback
            with open(output_path, "wb") as f:
                f.write(b"VIDEO_SIMULADO")
        
        # Libera recursos
        if audio_clip:
            audio_clip.close()
        
        return output_path
    
    def create_scene_videos(self, output_dir):
        """
        Cria vídeos para todas as cenas do roteiro.
        
        Args:
            output_dir: Diretório de saída para os vídeos
            
        Returns:
            Dicionário mapeando número da cena para caminho do arquivo de vídeo
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        scene_videos = {}
        
        for scene in self.script:
            scene_number = scene.get("scene_number", 0)
            
            # Verifica se temos a imagem e o áudio para esta cena
            if scene_number in self.scene_images and scene_number in self.audio_files:
                scene_image_path = self.scene_images[scene_number]
                audio_path = self.audio_files[scene_number]
                
                # Cria o vídeo da cena
                video_path = self._create_scene_animation(
                    scene, 
                    scene_image_path, 
                    audio_path, 
                    output_dir
                )
                
                scene_videos[scene_number] = video_path
            else:
                print("AVISO: Recursos faltando para a cena {0}".format(scene_number))
        
        return scene_videos
    
    def combine_videos(self, scene_videos, output_path):
        """
        Combina os vídeos de todas as cenas em um único vídeo final.
        
        Args:
            scene_videos: Dicionário mapeando número da cena para caminho do arquivo de vídeo
            output_path: Caminho para o arquivo de vídeo final
            
        Returns:
            Caminho para o arquivo de vídeo final
        """
        if not self.libraries_available:
            # Modo simulado - apenas cria um arquivo vazio
            with open(output_path, "wb") as f:
                f.write(b"VIDEO_FINAL_SIMULADO")
            return output_path
        
        # Ordena os vídeos por número de cena
        sorted_videos = sorted(scene_videos.items())
        video_paths = [path for _, path in sorted_videos]
        
        if not video_paths:
            print("AVISO: Nenhum vídeo de cena disponível para combinar")
            with open(output_path, "wb") as f:
                f.write(b"VIDEO_FINAL_SIMULADO")
            return output_path
        
        try:
            # Carrega os clips de vídeo
            video_clips = []
            for path in video_paths:
                try:
                    clip = mpy.VideoFileClip(path)
                    video_clips.append(clip)
                except Exception as e:
                    print("Erro ao carregar vídeo {0}: {1}".format(path, str(e)))
            
            if not video_clips:
                raise Exception("Nenhum clip de vídeo pôde ser carregado")
            
            # Adiciona transições elaboradas entre os clips
            final_clips = []
            transition_duration = self.transition_duration
            
            for i, clip in enumerate(video_clips):
                if i > 0:
                    # Aplica uma combinação de efeitos de transição
                    # Fade in com zoom suave
                    clip = clip.crossfadein(transition_duration)
                    
                    # Efeito de zoom durante a transição
                    start_time = clip.duration - transition_duration
                    
                    def transition_effect(t):
                        if t < transition_duration:
                            # Efeito de entrada
                            scale = 1.1 - 0.1 * (t / transition_duration)
                            return scale
                        return 1.0
                    
                    clip = clip.resize(transition_effect)
                    
                    # Adiciona um leve movimento panorâmico durante a transição
                    def pan_effect(t):
                        if t < transition_duration:
                            # Movimento suave da direita para o centro
                            x = 50 * (1 - t / transition_duration)
                            return ('center', 'center', x, 0)
                        return ('center', 'center', 0, 0)
                    
                    clip = clip.set_position(pan_effect)
                
                final_clips.append(clip)
            
            # Concatena todos os clips
            final_video = concatenate_videoclips(final_clips, method="compose")
            
            # Adiciona uma introdução e créditos finais
            try:
                # Título do vídeo com efeitos especiais
                title = "Aventuras no Jardim Mágico"
                subtitle = "Uma História Encantada"
                
                def title_animation(t):
                    # Movimento suave para o título
                    scale = 1 + 0.1 * np.sin(t * 2 * np.pi)
                    y_offset = 20 * np.sin(t * 3 * np.pi)
                    return ('center', 400 + y_offset), scale
                
                # Cria o título principal com animação
                intro_text = TextClip(title, fontsize=100, color='white', font="Arial-Bold", stroke_color='black', stroke_width=2)
                intro_text = intro_text.set_duration(7)
                
                # Aplica animação ao título
                intro_text = intro_text.set_position(lambda t: title_animation(t)[0])
                intro_text = intro_text.resize(lambda t: title_animation(t)[1])
                intro_text = intro_text.crossfadein(1.5).crossfadeout(1.5)
                
                # Cria o subtítulo com animação diferente
                subtitle_text = TextClip(subtitle, fontsize=60, color='white', font="Arial-Bold")
                subtitle_text = subtitle_text.set_duration(7)
                
                def subtitle_animation(t):
                    # Movimento mais sutil para o subtítulo
                    y_base = 500
                    y_offset = 10 * np.sin(t * 4 * np.pi)
                    opacity = min(1, 2 * t) if t < 0.5 else min(1, 2 * (1-t))
                    return ('center', y_base + y_offset), opacity
                
                subtitle_text = subtitle_text.set_position(lambda t: subtitle_animation(t)[0])
                subtitle_text = subtitle_text.set_opacity(lambda t: subtitle_animation(t)[1])
                
                # Créditos finais animados
                credits = [
                    ("Fim", 100),
                    ("Uma Produção Original", 60),
                    ("Criado com Inteligência Artificial", 50),
                    ("2024", 40)
                ]
                
                credits_clips = []
                for i, (text, size) in enumerate(credits):
                    clip = TextClip(text, fontsize=size, color='white', font="Arial-Bold",
                                  stroke_color='black', stroke_width=1)
                    
                    def credit_animation(t, index):
                        # Movimento suave de baixo para cima
                        y_base = 1080 - (400 * index)
                        y_pos = y_base - (200 * t)  # Move para cima
                        scale = 1 + 0.05 * np.sin(t * 2 * np.pi)
                        return ('center', y_pos), scale
                    
                    clip = clip.set_position(lambda t: credit_animation(t, i)[0])
                    clip = clip.resize(lambda t: credit_animation(t, i)[1])
                    clip = clip.set_duration(5)
                    clip = clip.crossfadein(1.0).crossfadeout(1.0)
                    
                    credits_clips.append(clip)
                
                # Cria um fundo gradiente animado
                def gradient_color(t):
                    # Cores que mudam suavemente ao longo do tempo
                    r = 20 + 10 * np.sin(t * np.pi)
                    g = 10 + 5 * np.sin(t * 2 * np.pi)
                    b = 30 + 15 * np.sin(t * 1.5 * np.pi)
                    return (int(r), int(g), int(b))
                
                # Fundo com gradiente animado para introdução
                intro_bg = mpy.ColorClip(size=self.resolution, color=gradient_color)
                intro_bg = intro_bg.set_duration(7)
                
                # Cria a sequência de introdução
                intro_clip = CompositeVideoClip([
                    intro_bg,
                    intro_text,
                    subtitle_text
                ])
                
                # Fundo com gradiente animado para créditos
                credits_bg = mpy.ColorClip(size=self.resolution, color=gradient_color)
                credits_bg = credits_bg.set_duration(5)
                
                # Cria a sequência de créditos
                # Cria a sequência final de créditos
                credits_clip = CompositeVideoClip(
                    [credits_bg] + credits_clips,
                    size=self.resolution
                ).set_duration(5)
                
                # Adiciona efeitos de transição para a sequência completa
                final_video = concatenate_videoclips(
                    [intro_clip, final_video, credits_clip],
                    method="compose",
                    padding=-self.transition_duration,  # Sobreposição para transições suaves
                    crossfade=True
                )
                
                # Aplica efeitos de pós-produção
                def post_process(frame):
                    # Converte para float32 para operações de ponto flutuante
                    frame = frame.astype(np.float32)
                    
                    # Ajuste de saturação
                    saturation = 1.2
                    frame = frame * saturation
                    
                    # Ajuste de contraste
                    contrast = 1.1
                    mean = frame.mean()
                    frame = (frame - mean) * contrast + mean
                    
                    # Ajuste de brilho
                    brightness = 1.05
                    frame = frame * brightness
                    
                    # Garante que os valores estão no intervalo válido
                    frame = np.clip(frame, 0, 255)
                    
                    # Converte de volta para uint8
                    return frame.astype(np.uint8)
                
                # Aplica os efeitos de pós-produção
                final_video = final_video.fl_image(post_process)
                
            except Exception as e:
                print("Erro ao adicionar introdução/créditos: {0}".format(str(e)))
            
            # Salva o vídeo final
            final_video.write_videofile(
                output_path, 
                fps=self.fps, 
                codec='libx264', 
                audio_codec='aac',
                preset='ultrafast',  # Para testes, use 'medium' para produção
                threads=4
            )
            
            print("Vídeo final salvo em: {0}".format(output_path))
            
            # Libera recursos
            for clip in video_clips:
                clip.close()
            final_video.close()
            
            return output_path
            
        except Exception as e:
            print("Erro ao combinar vídeos: {0}".format(str(e)))
            # Cria um arquivo vazio como fallback
            with open(output_path, "wb") as f:
                f.write(b"VIDEO_FINAL_SIMULADO")
            return output_path
    
    def create_final_video(self, output_dir):
        """
        Cria o vídeo final completo.
        
        Args:
            output_dir: Diretório de saída para os vídeos
            
        Returns:
            Caminho para o arquivo de vídeo final
        """
        # Cria diretório para vídeos de cenas
        scenes_dir = os.path.join(output_dir, "cenas_videos")
        if not os.path.exists(scenes_dir):
            os.makedirs(scenes_dir)
        
        # Cria vídeos para cada cena
        scene_videos = self.create_scene_videos(scenes_dir)
        
        # Combina os vídeos em um único vídeo final
        final_video_path = os.path.join(output_dir, "video_final.mp4")
        return self.combine_videos(scene_videos, final_video_path)
