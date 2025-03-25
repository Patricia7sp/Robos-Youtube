"""
Video Editor Agent
----------------
Este agente é responsável por combinar animações, narrações e diálogos
para criar o vídeo final da história animada.

Utiliza FFmpeg para processamento avançado de vídeo e integra-se com o
AnimationGeneratorAgent para criar transições fluidas entre cenas.
"""

import os
import json
import time
import logging
import subprocess
import tempfile
import shutil
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import sys
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, TextClip, CompositeAudioClip, ImageClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

# Adiciona o diretório raiz ao path para importar módulos do projeto
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import VIDEO_SETTINGS
from agents.animation_generator import AnimationGeneratorAgent

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VideoEditorAgent:
    def __init__(self, animation_api_key=None, animation_provider="stability"):
        """
        Inicializa o agente de edição de vídeo.
        
        Args:
            animation_api_key: Chave da API de animação (opcional)
            animation_provider: Provedor da API de animação (stability, runway, etc.)
        """
        self.video_settings = VIDEO_SETTINGS
        self.script = None
        self.animations = {}
        self.audio_files = {}
        self.checkpoint_data = {}
        
        # Inicializa o gerador de animações
        self.animation_generator = AnimationGeneratorAgent(
            api_key=animation_api_key,
            api_provider=animation_provider
        )
        
        # Verifica se o FFmpeg está instalado
        self._check_ffmpeg()
        
        logger.info("VideoEditorAgent inicializado com sucesso")
        
    def _check_ffmpeg(self) -> bool:
        """
        Verifica se o FFmpeg está instalado no sistema e se possui os recursos necessários
        para as transições avançadas de vídeo.
        
        Returns:
            bool: True se o FFmpeg estiver instalado com os recursos necessários, False caso contrário
        """
        try:
            # Verifica se o FFmpeg está instalado
            result = subprocess.run(["ffmpeg", "-version"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True,
                                   check=False)
            
            if result.returncode != 0:
                logger.warning("FFmpeg não encontrado. Algumas funcionalidades podem não funcionar corretamente.")
                return False
                
            # Extrai informações da versão
            ffmpeg_version = result.stdout.split('\n')[0]
            logger.info(f"FFmpeg instalado: {ffmpeg_version}")
            
            # Verifica se tem suporte a libx264 (necessário para as transições)
            if 'libx264' not in result.stdout:
                logger.warning("FFmpeg não tem suporte explícito a libx264. Algumas transições podem não funcionar.")
            
            # Verifica os filtros disponíveis
            filters_result = subprocess.run(["ffmpeg", "-filters"], 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE,
                                          text=True,
                                          check=False)
            
            if filters_result.returncode == 0:
                # Verifica filtros essenciais para as transições
                essential_filters = ['fade', 'overlay', 'scale', 'crop', 'zoompan']
                missing_filters = [f for f in essential_filters if f not in filters_result.stdout]
                
                if missing_filters:
                    logger.warning(f"FFmpeg está faltando alguns filtros essenciais: {', '.join(missing_filters)}")
                else:
                    logger.info("FFmpeg tem todos os filtros necessários para as transições avançadas")
            
            # Salva um checkpoint com as informações do FFmpeg
            if hasattr(self, '_save_checkpoint'):
                self._save_checkpoint("ffmpeg_check", {
                    "available": True,
                    "version": ffmpeg_version,
                    "has_libx264": 'libx264' in result.stdout,
                    "timestamp": time.time()
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Erro ao verificar FFmpeg: {str(e)}")
            return False
            
    def check_dependencies(self) -> bool:
        """
        Verifica e instala (quando possível) as dependências necessárias para o sistema.
        
        Returns:
            bool: True se todas as dependências estiverem disponíveis, False caso contrário
        """
        logger.info("Verificando dependências do sistema...")
        dependencies_ok = True
        
        # Verifica FFmpeg
        if not self._check_ffmpeg():
            logger.warning("FFmpeg é necessário para processamento de vídeo. Por favor, instale-o manualmente.")
            dependencies_ok = False
        
        # Verifica bibliotecas Python necessárias
        try:
            import numpy
            logger.info("NumPy instalado.")
        except ImportError:
            logger.warning("NumPy não encontrado. Tentando instalar...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "numpy"], check=True)
                logger.info("NumPy instalado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao instalar NumPy: {str(e)}")
                dependencies_ok = False
        
        try:
            from PIL import Image
            logger.info("Pillow (PIL) instalado.")
        except ImportError:
            logger.warning("Pillow não encontrado. Tentando instalar...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
                logger.info("Pillow instalado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao instalar Pillow: {str(e)}")
                dependencies_ok = False
        
        try:
            import moviepy
            logger.info(f"MoviePy instalado: {moviepy.__version__}")
        except ImportError:
            logger.warning("MoviePy não encontrado. Tentando instalar...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "moviepy"], check=True)
                logger.info("MoviePy instalado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao instalar MoviePy: {str(e)}")
                dependencies_ok = False
                
        # Verifica espaço em disco disponível para processamento de vídeo
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024 ** 3)  # Converte para GB
            logger.info(f"Espaço livre em disco: {free_gb:.2f} GB")
            if free_gb < 5.0:  # Alerta se menos de 5GB disponíveis
                logger.warning(f"Pouco espaço em disco disponível ({free_gb:.2f} GB). Recomendado pelo menos 5 GB para processamento de vídeo.")
        except Exception as e:
            logger.error(f"Erro ao verificar espaço em disco: {str(e)}")
        
        if dependencies_ok:
            logger.info("Todas as dependências verificadas e disponíveis.")
        else:
            logger.warning("Algumas dependências estão faltando. O sistema pode não funcionar corretamente.")
        
        return dependencies_ok
    
    def _save_checkpoint(self, checkpoint_id: str, data: Dict[str, Any]) -> None:
        """
        Salva um checkpoint durante o processamento de vídeo.
        
        Args:
            checkpoint_id: Identificador único do checkpoint
            data: Dados a serem salvos no checkpoint
        """
        try:
            # Cria o diretório de checkpoints se não existir
            os.makedirs(os.path.join(self.checkpoint_dir, 'transitions'), exist_ok=True)
            
            # Adiciona timestamp ao checkpoint
            checkpoint_data = {
                "timestamp": time.time(),
                "checkpoint_id": checkpoint_id,
                **data
            }
            
            # Salva o checkpoint em memória
            self.checkpoint_data[checkpoint_id] = checkpoint_data
            
            # Salva o checkpoint em disco
            checkpoint_path = os.path.join(self.checkpoint_dir, 'transitions', f"{checkpoint_id}.json")
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Checkpoint salvo: {checkpoint_id}")
        except Exception as e:
            logger.error(f"Erro ao salvar checkpoint {checkpoint_id}: {str(e)}")
            
    def _optimize_transition_quality(self, clip1, clip2, transition_type: str, transition_duration: float) -> tuple:
        """
        Otimiza a qualidade da transição entre dois clips de vídeo.
        
        Args:
            clip1: Primeiro clip de vídeo
            clip2: Segundo clip de vídeo
            transition_type: Tipo de transição
            transition_duration: Duração da transição em segundos
            
        Returns:
            Tuple[VideoClip, VideoClip, dict]: Clips otimizados e parâmetros adicionais
        """
        # Parâmetros adicionais para a transição
        params = {}
        
        # Verifica e ajusta as resoluções dos clips
        w1, h1 = clip1.size
        w2, h2 = clip2.size
        
        # Salva um checkpoint com informações sobre os clips originais
        self._save_checkpoint(f"transition_optimization_start_{int(time.time())}", {
            "clip1_size": (w1, h1),
            "clip2_size": (w2, h2),
            "transition_type": transition_type,
            "transition_duration": transition_duration
        })
        
        # Se as resoluções forem diferentes, redimensiona para a maior
        if w1 != w2 or h1 != h2:
            logger.info(f"Ajustando resoluções para transição: {w1}x{h1} e {w2}x{h2}")
            
            # Escolhe a maior resolução para preservar qualidade
            target_w = max(w1, w2)
            target_h = max(h1, h2)
            
            # Garante que as dimensões sejam pares (exigido por alguns codecs)
            target_w = target_w + (target_w % 2)
            target_h = target_h + (target_h % 2)
            
            # Redimensiona os clips se necessário
            if w1 != target_w or h1 != target_h:
                clip1 = clip1.resize((target_w, target_h))
            
            if w2 != target_w or h2 != target_h:
                clip2 = clip2.resize((target_w, target_h))
                
            logger.info(f"Clips redimensionados para {target_w}x{target_h}")
            
            # Adiciona informações aos parâmetros
            params["resized"] = True
            params["target_size"] = (target_w, target_h)
        
        # Ajusta a taxa de quadros (fps) se forem diferentes
        fps1 = getattr(clip1, 'fps', self.video_settings['fps'])
        fps2 = getattr(clip2, 'fps', self.video_settings['fps'])
        
        if fps1 != fps2:
            target_fps = max(fps1, fps2)
            logger.info(f"Ajustando FPS para transição: {fps1} e {fps2} para {target_fps}")
            
            # Ajusta o FPS dos clips
            if fps1 != target_fps:
                clip1 = clip1.set_fps(target_fps)
            
            if fps2 != target_fps:
                clip2 = clip2.set_fps(target_fps)
                
            # Adiciona informações aos parâmetros
            params["adjusted_fps"] = target_fps
        
        # Adiciona parâmetros específicos para cada tipo de transição
        if transition_type == "fade":
            # Ajusta a opacidade para um fade mais suave
            params["opacity_curve"] = "smooth"
            params["edge_softness"] = 5
        
        elif transition_type.startswith("wipe"):
            # Adiciona suavização às bordas do wipe
            params["edge_softness"] = 10
            params["direction"] = transition_type.split("_")[1] if "_" in transition_type else "right"
        
        elif transition_type == "zoom":
            # Define o fator de zoom e a curva de aceleração
            params["zoom_factor"] = 0.7
            params["acceleration"] = "ease-in-out"
        
        elif transition_type == "morph":
            # Define a qualidade do morph
            params["morph_quality"] = "high"
            params["blend_frames"] = int(transition_duration * self.video_settings['fps'] * 0.5)
        
        # Salva um checkpoint com os parâmetros de otimização
        self._save_checkpoint(f"transition_optimization_complete_{int(time.time())}", {
            "transition_type": transition_type,
            "params": params,
            "clip1_final_size": clip1.size,
            "clip2_final_size": clip2.size
        })
        
        return clip1, clip2, params
    
    def _load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Carrega um checkpoint salvo anteriormente.
        
        Args:
            checkpoint_id: Identificador único do checkpoint
            
        Returns:
            Dados do checkpoint ou None se não encontrado
        """
        try:
            # Verifica se o checkpoint está em memória
            if checkpoint_id in self.checkpoint_data:
                return self.checkpoint_data[checkpoint_id]
            
            # Tenta carregar do disco
            checkpoint_path = os.path.join(self.checkpoint_dir, 'transitions', f"{checkpoint_id}.json")
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                    
                # Armazena em memória para acesso mais rápido
                self.checkpoint_data[checkpoint_id] = checkpoint_data
                return checkpoint_data
            
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar checkpoint {checkpoint_id}: {str(e)}")
            return None
    
    def _resume_from_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Verifica se existe um checkpoint e retorna os dados para continuar o processamento.
        
        Args:
            checkpoint_id: Identificador único do checkpoint
            
        Returns:
            Dados do último checkpoint ou None se não houver checkpoint
        """
        checkpoint_data = self._load_checkpoint(checkpoint_id)
        
        if checkpoint_data:
            logger.info(f"Retomando processamento a partir do checkpoint: {checkpoint_id} (status: {checkpoint_data.get('status', 'desconhecido')})")
            return checkpoint_data
        
        logger.info(f"Nenhum checkpoint encontrado para {checkpoint_id}. Iniciando processamento do zero.")
        return None
    
    def load_script(self, script_path: str) -> None:
        """
        Carrega o roteiro processado a partir de um arquivo JSON.
        
        Args:
            script_path: Caminho para o arquivo JSON do roteiro
        """
        with open(script_path, 'r', encoding='utf-8') as file:
            self.script = json.load(file)
        logger.info(f"Roteiro carregado: {len(self.script)} cenas")
        
        # Salva o checkpoint após carregar o roteiro
        self._save_checkpoint("script_loaded", {"script_path": script_path})
    
    def _save_checkpoint(self, stage: str, data: Dict[str, Any]) -> None:
        """
        Salva um checkpoint do estado atual do processamento.
        
        Args:
            stage: Estágio atual do processamento
            data: Dados relevantes para o checkpoint
        """
        self.checkpoint_data[stage] = {
            "timestamp": time.time(),
            "data": data
        }
        
        # Salva o checkpoint em disco
        checkpoint_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'checkpoints'
        )
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        checkpoint_path = os.path.join(checkpoint_dir, 'video_editor_checkpoint.json')
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoint_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Checkpoint salvo: {stage}")
    
    def _load_checkpoint(self) -> Dict[str, Any]:
        """
        Carrega o último checkpoint salvo.
        
        Returns:
            Dicionário com dados do checkpoint ou dicionário vazio se não existir
        """
        checkpoint_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'checkpoints'
        )
        checkpoint_path = os.path.join(checkpoint_dir, 'video_editor_checkpoint.json')
        
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    self.checkpoint_data = json.load(f)
                logger.info(f"Checkpoint carregado: {list(self.checkpoint_data.keys())}")
                return self.checkpoint_data
            except Exception as e:
                logger.error(f"Erro ao carregar checkpoint: {str(e)}")
                return {}
        else:
            logger.info("Nenhum checkpoint encontrado")
            return {}
    
    def load_animation_metadata(self, metadata_path: str) -> Dict[str, Any]:
        """
        Carrega os metadados das animações.
        
        Args:
            metadata_path: Caminho para o arquivo JSON de metadados
            
        Returns:
            Dicionário com metadados das animações
        """
        with open(metadata_path, 'r', encoding='utf-8') as file:
            metadata = json.load(file)
        logger.info(f"Metadados de animações carregados")
        
        # Salva o checkpoint após carregar os metadados
        self._save_checkpoint("animation_metadata_loaded", {"metadata_path": metadata_path})
        
        return metadata
    
    def load_audio_metadata(self, metadata_path: str) -> Dict[str, Any]:
        """
        Carrega os metadados dos áudios.
        
        Args:
            metadata_path: Caminho para o arquivo JSON de metadados
            
        Returns:
            Dicionário com metadados dos áudios
        """
        with open(metadata_path, 'r', encoding='utf-8') as file:
            metadata = json.load(file)
        logger.info(f"Metadados de áudios carregados")
        
        # Salva o checkpoint após carregar os metadados
        self._save_checkpoint("audio_metadata_loaded", {"metadata_path": metadata_path})
        
        return metadata
        
    def generate_animation_from_images(self, image_paths: List[str], output_path: str, 
                                     animation_type: str = "morph", duration: float = 3.0, 
                                     fps: int = 24, seed: Optional[int] = None, 
                                     force_regenerate: bool = False, **kwargs) -> str:
        """
        Gera uma animação a partir de uma sequência de imagens estáticas.
        
        Args:
            image_paths: Lista de caminhos para as imagens de origem
            output_path: Caminho para salvar a animação gerada
            animation_type: Tipo de animação (morph, zoom, pan, etc.)
            duration: Duração da animação em segundos
            fps: Frames por segundo
            seed: Seed para consistência na geração
            force_regenerate: Se True, força a regeneração mesmo se existir no cache
            **kwargs: Parâmetros adicionais para a API
            
        Returns:
            Caminho para a animação gerada ou mensagem de erro
        """
        logger.info(f"Gerando animação a partir de {len(image_paths)} imagens")
        
        # Verifica se todas as imagens existem
        for img_path in image_paths:
            if not os.path.exists(img_path):
                error_msg = f"Imagem não encontrada: {img_path}"
                logger.error(error_msg)
                return f"[Erro] {error_msg}"
        
        # Cria o diretório de saída se não existir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Gera a animação usando o AnimationGeneratorAgent
        success = self.animation_generator.generate_animation(
            image_paths, 
            output_path, 
            animation_type=animation_type, 
            duration=duration, 
            fps=fps, 
            seed=seed, 
            force_regenerate=force_regenerate, 
            **kwargs
        )
        
        if success:
            logger.info(f"Animação gerada com sucesso: {output_path}")
            
            # Salva o checkpoint após gerar a animação
            self._save_checkpoint("animation_generated", {
                "image_paths": image_paths,
                "output_path": output_path,
                "animation_type": animation_type,
                "duration": duration,
                "fps": fps,
                "seed": seed
            })
            
            return output_path
        else:
            error_msg = f"Falha ao gerar animação a partir das imagens"
            logger.error(error_msg)
            return f"[Erro] {error_msg}"
    
    def _create_scene_video(self, scene_number: int, animation_path: str, audio_metadata: Dict[str, Any], 
                          output_dir: str) -> Optional[str]:
        """
        Cria um vídeo para uma cena combinando animação e áudio.
        
        Args:
            scene_number: Número da cena
            animation_path: Caminho para o arquivo de animação
            audio_metadata: Metadados dos áudios da cena
            output_dir: Diretório para salvar o vídeo
            
        Returns:
            Caminho para o vídeo da cena ou None em caso de falha
        """
        try:
            from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
            
            logger.info(f"Criando vídeo para Cena {scene_number}...")
            
            # Verifica se a animação é simulada
            if isinstance(animation_path, str) and animation_path.startswith('[Simulado]'):
                logger.info(f"Animação simulada para Cena {scene_number}. Pulando edição real.")
                return f"[Simulado] scene_video_{scene_number:03d}.mp4"
            
            # Salva o checkpoint antes de processar o vídeo
            self._save_checkpoint(f"scene_video_processing_started_{scene_number}", {
                "scene_number": scene_number,
                "animation_path": animation_path
            })
            
            # Carrega o vídeo da animação
            video_clip = VideoFileClip(animation_path)
            
            # Coleta todos os arquivos de áudio para esta cena
            audio_clips = []
            
            # Adiciona narrações
            narration_files = audio_metadata.get('narration', [])
            audio_dir = os.path.dirname(os.path.dirname(audio_metadata.get('narration_dir', '')))
            
            for i, narration_file in enumerate(narration_files):
                # Remove o prefixo "[Simulado] " se existir
                if isinstance(narration_file, str) and narration_file.startswith('[Simulado] '):
                    logger.info(f"Áudio de narração simulado para Cena {scene_number}. Pulando.")
                    continue
                
                narration_path = os.path.join(audio_dir, 'narration', narration_file)
                if os.path.exists(narration_path):
                    narration_clip = AudioFileClip(narration_path)
                    # Posiciona as narrações em sequência
                    if i > 0 and audio_clips:
                        start_time = sum(clip.duration for clip in audio_clips)
                        narration_clip = narration_clip.set_start(start_time)
                    audio_clips.append(narration_clip)
            
            # Adiciona diálogos
            dialogues = audio_metadata.get('dialogues', {})
            for character, dialogue_files in dialogues.items():
                for dialogue_file in dialogue_files:
                    # Remove o prefixo "[Simulado] " se existir
                    if isinstance(dialogue_file, str) and dialogue_file.startswith('[Simulado] '):
                        logger.info(f"Áudio de diálogo simulado para {character} na Cena {scene_number}. Pulando.")
                        continue
                    
                    dialogue_path = os.path.join(audio_dir, 'dialogue', dialogue_file)
                    if os.path.exists(dialogue_path):
                        dialogue_clip = AudioFileClip(dialogue_path)
                        # Posiciona os diálogos após as narrações
                        if audio_clips:
                            start_time = sum(clip.duration for clip in audio_clips)
                            dialogue_clip = dialogue_clip.set_start(start_time)
                        audio_clips.append(dialogue_clip)
            
            # Se temos áudios, combinamos com o vídeo
            if audio_clips:
                composite_audio = CompositeAudioClip(audio_clips)
                
                # Calcula a duração total do áudio
                audio_duration = max(clip.end for clip in audio_clips)
                
                # Ajusta a duração do vídeo para corresponder ao áudio
                if video_clip.duration < audio_duration:
                    # Se o vídeo for mais curto, estende-o (loop)
                    repeat_count = int(audio_duration / video_clip.duration) + 1
                    video_clip = video_clip.loop(repeat_count)
                
                # Corta o vídeo para a duração do áudio
                video_clip = video_clip.subclip(0, audio_duration)
                
                # Adiciona o áudio ao vídeo
                video_clip = video_clip.set_audio(composite_audio)
            
            # Salva o vídeo da cena
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"scene_video_{scene_number:03d}.mp4")
            
            # Usa FFmpeg diretamente para melhor controle e qualidade
            temp_video_path = os.path.join(output_dir, f"temp_scene_{scene_number:03d}.mp4")
            video_clip.write_videofile(
                temp_video_path,
                codec='libx264',
                audio_codec='aac',
                fps=self.video_settings['fps']
            )
            
            # Aplica filtros adicionais com FFmpeg para melhorar a qualidade
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', temp_video_path,
                '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
                '-c:a', 'aac', '-b:a', '192k',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                output_path
            ]
            
            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                # Remove o arquivo temporário
                if os.path.exists(temp_video_path):
                    os.remove(temp_video_path)
            except subprocess.CalledProcessError as e:
                logger.error(f"Erro ao processar vídeo com FFmpeg: {e.stderr.decode() if e.stderr else str(e)}")
                # Se falhar, usa o arquivo temporário como saída
                if os.path.exists(temp_video_path):
                    shutil.move(temp_video_path, output_path)
            
            # Fecha os clips para liberar recursos
            video_clip.close()
            for clip in audio_clips:
                clip.close()
            
            # Salva o checkpoint após processar o vídeo
            self._save_checkpoint(f"scene_video_processed_{scene_number}", {
                "scene_number": scene_number,
                "output_path": output_path
            })
            
            logger.info(f"Vídeo para Cena {scene_number} salvo em: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erro ao criar vídeo para Cena {scene_number}: {str(e)}")
            return None
    
    def _add_transition(self, clip1, clip2, transition_duration: float, transition_type: str = "fade", **kwargs) -> VideoFileClip:
        """
        Adiciona uma transição suave entre dois clips.
        
        Args:
            clip1: Primeiro clip de vídeo
            clip2: Segundo clip de vídeo
            transition_duration: Duração da transição em segundos
            transition_type: Tipo de transição (fade, wipe_right, wipe_left, wipe_up, wipe_down, zoom, morph, rotate3d, page_turn)
            **kwargs: Parâmetros adicionais específicos para cada tipo de transição
                - fade: fade_color (lista RGB)
                - wipe_*: edge_softness (int)
                - zoom: zoom_factor (float), zoom_direction ("in"/"out"), focus_point ("center"/"top"/"bottom"/"left"/"right"), acceleration (string)
                - morph: morph_quality ("low"/"medium"/"high"), blend_frames (int)
                - rotate3d: rotation_angle (float), rotation_axis ("x"/"y"/"z"), perspective (float)
                - page_turn: turn_direction ("left-to-right"/"right-to-left"), shadow_intensity (float), page_curve (float)
            
        Returns:
            Clip de vídeo com transição
        """
        logger.info(f"Adicionando transição {transition_type} entre clips")
        
        # Cria um checkpoint antes de iniciar a transição
        checkpoint_id = f"transition_{hash(str(clip1) + str(clip2) + transition_type)}"
        self._save_checkpoint(checkpoint_id, {
            "transition_type": transition_type,
            "transition_duration": transition_duration,
            "status": "iniciando"
        })
        
        # Otimiza a qualidade dos clips antes da transição
        clip1, clip2, params = self._optimize_transition_quality(clip1, clip2, transition_type, transition_duration)
        
        # Tenta usar o AnimationGeneratorAgent para criar uma transição avançada
        try:
            # Extrai frames dos clips para usar como entrada para o gerador de animações
            with tempfile.TemporaryDirectory() as temp_dir:
                # Salva o último frame do primeiro clip
                last_frame_path = os.path.join(temp_dir, "last_frame.png")
                clip1.save_frame(last_frame_path, t=clip1.duration-0.1)
                
                # Salva o primeiro frame do segundo clip
                first_frame_path = os.path.join(temp_dir, "first_frame.png")
                clip2.save_frame(first_frame_path, t=0)
                
                # Atualiza o checkpoint
                self._save_checkpoint(checkpoint_id, {
                    "transition_type": transition_type,
                    "transition_duration": transition_duration,
                    "status": "frames_extraidos",
                    "last_frame_path": last_frame_path,
                    "first_frame_path": first_frame_path,
                    "optimization_params": params
                })
                
                # Gera a animação de transição
                transition_path = os.path.join(temp_dir, "transition.mp4")
                
                # Usa os parâmetros otimizados para a transição
                transition_params = params.copy()
                
                # Adiciona parâmetros específicos para diferentes tipos de transição
                if transition_type == "zoom":
                    # Configurações para transição de zoom
                    transition_params.update({
                        "zoom_factor": kwargs.get("zoom_factor", params.get("zoom_factor", 1.5)),
                        "zoom_direction": kwargs.get("zoom_direction", "in"),
                        "focus_point": kwargs.get("focus_point", "center"),
                        "zoom_quality": kwargs.get("zoom_quality", "high"),
                        "acceleration": kwargs.get("acceleration", params.get("acceleration", "ease-in-out")),
                        "use_advanced": kwargs.get("use_advanced", True)
                    })
                elif transition_type == "morph":
                    # Configurações para transição de morphing
                    transition_params.update({
                        "morph_quality": kwargs.get("morph_quality", params.get("morph_quality", "high")),
                        "blend_frames": kwargs.get("blend_frames", params.get("blend_frames", int(transition_duration * self.video_settings['fps'] * 0.5)))
                    })
                elif transition_type.startswith("wipe"):
                    # Configurações para transições de wipe
                    transition_params.update({
                        "edge_softness": kwargs.get("edge_softness", params.get("edge_softness", 10)),
                        "direction": kwargs.get("direction", params.get("direction", transition_type.split("_")[1] if "_" in transition_type else "right"))
                    })
                elif transition_type == "rotate3d":
                    # Configurações para transição de rotação 3D
                    transition_params.update({
                        "rotation_angle": kwargs.get("rotation_angle", 180),
                        "rotation_axis": kwargs.get("rotation_axis", "y"),
                        "perspective": kwargs.get("perspective", 0.0008),
                        "acceleration": kwargs.get("acceleration", "ease-in-out")
                    })
                elif transition_type == "page_turn":
                    # Configurações para transição de página virando
                    transition_params.update({
                        "turn_direction": kwargs.get("turn_direction", "left-to-right"),
                        "shadow_intensity": kwargs.get("shadow_intensity", 0.5),
                        "page_curve": kwargs.get("page_curve", 0.3),
                        "acceleration": kwargs.get("acceleration", "ease-in-out")
                    })
                elif transition_type == "fade":
                    # Configurações para transição de fade
                    transition_params.update({
                        "fade_color": kwargs.get("fade_color", [0, 0, 0])  # Preto por padrão
                    })
                
                # Atualiza o checkpoint
                self._save_checkpoint(checkpoint_id, {
                    "transition_type": transition_type,
                    "transition_duration": transition_duration,
                    "status": "gerando_transicao",
                    "transition_params": transition_params
                })
                
                # Gera a transição com os parâmetros específicos
                success = self.animation_generator.generate_scene_transition(
                    last_frame_path, 
                    first_frame_path, 
                    transition_path,
                    transition_type=transition_type,
                    duration=transition_duration,
                    fps=params.get("adjusted_fps", self.video_settings['fps']),
                    **transition_params
                )
                
                if success and os.path.exists(transition_path):
                    # Atualiza o checkpoint
                    self._save_checkpoint(checkpoint_id, {
                        "transition_type": transition_type,
                        "transition_duration": transition_duration,
                        "status": "transicao_gerada",
                        "transition_path": transition_path,
                        "transition_params": transition_params
                    })
                    
                    # Carrega a transição gerada
                    transition_clip = VideoFileClip(transition_path)
                    
                    # Ajusta a duração da transição se necessário
                    if abs(transition_clip.duration - transition_duration) > 0.1:
                        logger.warning(f"Ajustando duração da transição de {transition_clip.duration} para {transition_duration}")
                        transition_clip = transition_clip.fx(vfx.speedx, transition_clip.duration / transition_duration)
                    
                    # Aplica efeitos adicionais baseados nos parâmetros otimizados
                    if params.get("edge_softness", 0) > 0:
                        transition_clip = transition_clip.fx(vfx.gaussian_blur, params["edge_softness"])
                    
                    # Corta o final do primeiro clip e o início do segundo clip
                    clip1_trimmed = clip1.subclip(0, clip1.duration - (transition_duration / 2))
                    clip2_trimmed = clip2.subclip(transition_duration / 2, clip2.duration)
                    
                    # Ajusta o início do segundo clip
                    clip2_trimmed = clip2_trimmed.set_start(clip1_trimmed.duration)
                    
                    # Posiciona a transição entre os clips
                    transition_clip = transition_clip.set_start(clip1_trimmed.duration - (transition_duration / 2))
                    
                    # Combina os três clips
                    result = CompositeVideoClip([clip1_trimmed, transition_clip, clip2_trimmed])
                    
                    # Atualiza o checkpoint final
                    self._save_checkpoint(checkpoint_id, {
                        "transition_type": transition_type,
                        "transition_duration": transition_duration,
                        "status": "concluido",
                        "success": True
                    })
                    
                    return result
        except Exception as e:
            logger.warning(f"Erro ao criar transição avançada: {str(e)}. Usando transição simples.")
            # Atualiza o checkpoint com o erro
            self._save_checkpoint(checkpoint_id, {
                "transition_type": transition_type,
                "transition_duration": transition_duration,
                "status": "erro",
                "error": str(e),
                "fallback": "usando_transicao_simples"
            })
        
        # Fallback: Cria uma transição de fade simples se a transição avançada falhar
        logger.info("Usando transição de fade simples como fallback")
        
        # Usa os parâmetros otimizados mesmo no fallback
        if transition_type == "fade" or transition_type == "dissolve":
            # Transição de fade com curva de opacidade personalizada
            opacity_curve = kwargs.get("opacity_curve", params.get("opacity_curve"))
            fade_color = kwargs.get("fade_color", [0, 0, 0])  # RGB para preto por padrão
            
            if opacity_curve == "smooth":
                # Usa uma curva de fade mais suave
                def smooth_fade(t):
                    import numpy as np
                    # Usa uma curva sigmoide para suavizar a transição
                    return 1 / (1 + np.exp(-12 * (t - 0.5)))
                
                # Verifica se deve usar fade para uma cor específica
                if fade_color != [0, 0, 0]:
                    # Converte para valores entre 0 e 1
                    r, g, b = [c/255 for c in fade_color]
                    # Fade para a cor especificada e depois para o segundo clip
                    color_clip = ColorClip(size=clip1.size, color=[r, g, b], duration=transition_duration/2)
                    color_clip = color_clip.set_start(clip1.duration - transition_duration/2)
                    
                    clip1 = clip1.crossfadeout(transition_duration/2, transition_func=smooth_fade)
                    clip2 = clip2.set_start(clip1.duration)
                    clip2 = clip2.crossfadein(transition_duration/2, transition_func=smooth_fade)
                    
                    # Combina os três clips
                    return concatenate_videoclips([clip1, color_clip, clip2], method="compose")
                else:
                    # Fade direto entre clips
                    clip1 = clip1.crossfadeout(transition_duration, transition_func=smooth_fade)
                    clip2 = clip2.crossfadein(transition_duration, transition_func=smooth_fade)
            else:
                # Fade padrão
                # Verifica se deve usar fade para uma cor específica
                if fade_color != [0, 0, 0]:
                    # Converte para valores entre 0 e 1
                    r, g, b = [c/255 for c in fade_color]
                    # Fade para a cor especificada e depois para o segundo clip
                    color_clip = ColorClip(size=clip1.size, color=[r, g, b], duration=transition_duration/2)
                    color_clip = color_clip.set_start(clip1.duration - transition_duration/2)
                    
                    clip1 = clip1.crossfadeout(transition_duration/2)
                    clip2 = clip2.set_start(clip1.duration)
                    clip2 = clip2.crossfadein(transition_duration/2)
                    
                    # Combina os três clips
                    return concatenate_videoclips([clip1, color_clip, clip2], method="compose")
                else:
                    # Fade direto entre clips
                    clip1 = clip1.crossfadeout(transition_duration)
                    clip2 = clip2.crossfadein(transition_duration)
                
        elif transition_type.startswith("wipe"):
            # Tenta simular um wipe com moviepy
            try:
                from moviepy.video.fx import mask_and_multiplier
                
                # Cria uma máscara para simular o wipe
                def make_wipe_mask(t):
                    import numpy as np
                    h, w = clip1.size
                    progress = t / transition_duration
                    
                    # Usa a direção dos parâmetros passados ou otimizados
                    # Extrai a direção do nome do tipo de transição se disponível
                    default_direction = transition_type.split("_")[1] if "_" in transition_type else "right"
                    direction = kwargs.get("direction", params.get("direction", default_direction))
                    edge_softness = kwargs.get("edge_softness", params.get("edge_softness", 10)) / 100.0  # Converte para porcentagem
                    
                    # Aplica a curva de aceleração ao progresso
                    acceleration = kwargs.get("acceleration", params.get("acceleration", "linear"))
                    if acceleration == "ease-in":
                        # Aceleração gradual (começa devagar, termina rápido)
                        progress = progress * progress
                    elif acceleration == "ease-out":
                        # Desaceleração gradual (começa rápido, termina devagar)
                        progress = 1 - (1 - progress) * (1 - progress)
                    elif acceleration == "ease-in-out":
                        # Aceleração e desaceleração (devagar-rápido-devagar)
                        progress = 0.5 * (1 - np.cos(np.pi * progress))
                    
                    # Cria a máscara baseada na direção
                    if direction == "right":
                        mask = np.tile(np.array([1 if x < w * progress else 0 for x in range(w)]), (h, 1))
                    elif direction == "left":
                        mask = np.tile(np.array([1 if x > w * (1 - progress) else 0 for x in range(w)]), (h, 1))
                    elif direction == "up":
                        mask = np.tile(np.array([1 if y > h * (1 - progress) else 0 for y in range(h)]).reshape(-1, 1), (1, w))
                    elif direction == "down":
                        mask = np.tile(np.array([1 if y < h * progress else 0 for y in range(h)]).reshape(-1, 1), (1, w))
                    elif direction == "diagonal-right-down":
                        # Wipe diagonal do canto superior esquerdo para o canto inferior direito
                        mask = np.zeros((h, w))
                        for y in range(h):
                            for x in range(w):
                                if (x/w + y/h) / 2 < progress:
                                    mask[y, x] = 1
                    elif direction == "diagonal-left-down":
                        # Wipe diagonal do canto superior direito para o canto inferior esquerdo
                        mask = np.zeros((h, w))
                        for y in range(h):
                            for x in range(w):
                                if ((w-x)/w + y/h) / 2 < progress:
                                    mask[y, x] = 1
                    elif direction == "center":
                        # Wipe do centro para as bordas (como uma iris)
                        center_x, center_y = w//2, h//2
                        mask = np.zeros((h, w))
                        max_dist = np.sqrt((w/2)**2 + (h/2)**2)
                        
                        for y in range(h):
                            for x in range(w):
                                dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                                if dist < max_dist * progress:
                                    mask[y, x] = 1
                    else:
                        # Fallback para wipe horizontal
                        mask = np.tile(np.array([1 if x < w * progress else 0 for x in range(w)]), (h, 1))
                    
                    # Aplica suavização às bordas se especificado
                    if edge_softness > 0:
                        from scipy.ndimage import gaussian_filter
                        mask = gaussian_filter(mask, sigma=edge_softness * min(w, h) / 100)
                    
                    return mask
                
                # Cria clips para a transição
                clip1_part = clip1.subclip(clip1.duration - transition_duration, clip1.duration)
                clip2_part = clip2.subclip(0, transition_duration)
                
                # Aplica a máscara para criar o efeito de wipe
                wipe_clip = CompositeVideoClip([
                    clip1_part,
                    mask_and_multiplier.mask_color(clip2_part, make_wipe_mask, ismask=True)
                ], size=clip1.size)
                
                # Combina os clips
                clip1_main = clip1.subclip(0, clip1.duration - transition_duration)
                clip2_main = clip2.subclip(transition_duration, clip2.duration)
                
                # Ajusta os tempos de início
                wipe_clip = wipe_clip.set_start(clip1_main.duration)
                clip2_main = clip2_main.set_start(clip1_main.duration + transition_duration)
                
                # Atualiza o checkpoint
                self._save_checkpoint(checkpoint_id, {
                    "transition_type": transition_type,
                    "transition_duration": transition_duration,
                    "status": "concluido",
                    "success": True,
                    "method": "moviepy_wipe_simulation"
                })
                
                return CompositeVideoClip([clip1_main, wipe_clip, clip2_main])
            except Exception as e:
                logger.warning(f"Erro ao criar wipe com moviepy: {str(e)}. Usando fade simples.")
                # Fallback para fade simples
                clip1 = clip1.crossfadeout(transition_duration)
                clip2 = clip2.crossfadein(transition_duration)
                
        elif transition_type == "zoom":
            try:
                # Parâmetros avançados do zoom
                zoom_factor = kwargs.get("zoom_factor", params.get("zoom_factor", 1.5))
                zoom_direction = kwargs.get("zoom_direction", params.get("zoom_direction", "in"))
                acceleration = kwargs.get("acceleration", params.get("acceleration", "ease-in-out"))
                focus_point = kwargs.get("focus_point", params.get("focus_point", "center"))
                use_advanced = kwargs.get("use_advanced", params.get("use_advanced", True))
                
                # Verifica se deve usar o método avançado baseado em frames
                if use_advanced:
                    # Cria frames temporários para processamento avançado
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Extrai frames-chave dos clips
                        frame1_path = os.path.join(temp_dir, "frame1.png")
                        frame2_path = os.path.join(temp_dir, "frame2.png")
                        clip1.save_frame(frame1_path, t=clip1.duration-0.1)
                        clip2.save_frame(frame2_path, t=0)
                        
                        # Carrega as imagens com OpenCV para processamento avançado
                        frame1 = cv2.imread(frame1_path)
                        frame2 = cv2.imread(frame2_path)
                        
                        if frame1 is None or frame2 is None:
                            raise ValueError("Não foi possível carregar os frames para a transição de zoom")
                        
                        # Determina o ponto focal do zoom baseado no parâmetro
                        h, w = frame1.shape[:2]
                        if focus_point == "center":
                            center = (w//2, h//2)
                        elif focus_point == "left":
                            center = (w//4, h//2)
                        elif focus_point == "right":
                            center = (3*w//4, h//2)
                        elif focus_point == "top":
                            center = (w//2, h//4)
                        elif focus_point == "bottom":
                            center = (w//2, 3*h//4)
                        else:  # default: center
                            center = (w//2, h//2)
                        
                        # Gera frames intermediários para o zoom
                        zoom_frames = []
                        num_frames = int(transition_duration * self.video_settings['fps'])
                        
                        for i in range(num_frames):
                            # Calcula o fator de progresso (0 a 1)
                            progress = i / (num_frames - 1) if num_frames > 1 else 0.5
                            
                            # Aplica aceleração ao progresso
                            if acceleration == "ease-in":
                                # Aceleração gradual (começa devagar, termina rápido)
                                progress = progress * progress
                            elif acceleration == "ease-out":
                                # Desaceleração gradual (começa rápido, termina devagar)
                                progress = 1 - (1 - progress) * (1 - progress)
                            elif acceleration == "ease-in-out":
                                # Aceleração e desaceleração (devagar-rápido-devagar)
                                progress = 0.5 * (1 - np.cos(np.pi * progress))
                            elif acceleration == "bounce":
                                # Efeito de quicar (ideal para conteúdo infantil)
                                # Implementação baseada na função de easing "bounce"
                                bounce_progress = progress
                                if bounce_progress < 0.2:
                                    # Sobe rápido no início
                                    bounce_progress = bounce_progress / 0.2
                                    progress = 0.5 * bounce_progress * bounce_progress
                                elif bounce_progress < 0.5:
                                    # Primeiro quique
                                    bounce_progress = (bounce_progress - 0.2) / 0.3
                                    progress = 0.5 + 0.25 * (1 - (1 - bounce_progress) * (1 - bounce_progress))
                                elif bounce_progress < 0.7:
                                    # Segundo quique
                                    bounce_progress = (bounce_progress - 0.5) / 0.2
                                    progress = 0.75 - 0.1 * np.cos(bounce_progress * np.pi)
                                elif bounce_progress < 0.9:
                                    # Terceiro quique (menor)
                                    bounce_progress = (bounce_progress - 0.7) / 0.2
                                    progress = 0.75 + 0.15 * (1 - (1 - bounce_progress) * (1 - bounce_progress))
                                else:
                                    # Estabiliza no final
                                    bounce_progress = (bounce_progress - 0.9) / 0.1
                                    progress = 0.9 + 0.1 * bounce_progress
                            
                            # Determina qual frame usar baseado na posição na transição
                            if i < num_frames // 2:
                                # Primeira metade: usa o primeiro frame
                                frame = frame1.copy()
                                if zoom_direction == "in":
                                    # Zoom in: escala aumenta de 1 até zoom_factor
                                    scale = 1 + (zoom_factor - 1) * (2 * progress)
                                else:
                                    # Zoom out: escala diminui de zoom_factor até 1
                                    scale = zoom_factor - (zoom_factor - 1) * (2 * progress)
                            else:
                                # Segunda metade: usa o segundo frame
                                frame = frame2.copy()
                                if zoom_direction == "in":
                                    # Zoom in: escala diminui de zoom_factor até 1
                                    second_progress = (progress - 0.5) * 2  # 0->1
                                    scale = zoom_factor - (zoom_factor - 1) * second_progress
                                else:
                                    # Zoom out: escala aumenta de 1 até zoom_factor
                                    second_progress = (progress - 0.5) * 2  # 0->1
                                    scale = 1 + (zoom_factor - 1) * second_progress
                            
                            # Verifica se deve aplicar rotação durante o zoom
                            bounce_effect = kwargs.get("bounce_effect", params.get("bounce_effect", False))
                            rotation_angle = kwargs.get("rotation_angle", params.get("rotation_angle", 0))
                            
                            # Calcula o ângulo de rotação para o frame atual
                            angle = 0
                            if rotation_angle != 0:
                                # Aplica uma rotação suave que vai e volta
                                angle = rotation_angle * np.sin(progress * np.pi)
                            
                            # Adiciona um efeito de balanço extra se bounce_effect estiver ativado
                            if bounce_effect and acceleration == "bounce":
                                # Adiciona um pequeno balanço adicional durante os quiques
                                if 0.5 < progress < 0.9:
                                    # Amplitude do balanço diminui com o tempo
                                    swing_amplitude = 5 * (1 - (progress - 0.5) / 0.4)
                                    angle += swing_amplitude * np.sin(progress * 8 * np.pi)
                            
                            # Aplica a transformação de zoom com rotação
                            M = cv2.getRotationMatrix2D(center, angle, scale)
                            zoomed_frame = cv2.warpAffine(frame, M, (w, h))
                            
                            # Salva o frame processado
                            frame_path = os.path.join(temp_dir, f"zoom_frame_{i:04d}.png")
                            cv2.imwrite(frame_path, zoomed_frame)
                            zoom_frames.append(frame_path)
                        
                        # Cria um clip com os frames do zoom
                        zoom_clip = ImageSequenceClip(zoom_frames, fps=self.video_settings['fps'])
                        
                        # Ajusta a duração do zoom
                        if zoom_clip.duration != transition_duration:
                            zoom_clip = zoom_clip.set_duration(transition_duration)
                        
                        # Combina os clips com o zoom
                        clip1 = clip1.subclip(0, clip1.duration - transition_duration/2)
                        clip2 = clip2.subclip(transition_duration/2)
                        
                        # Atualiza o checkpoint
                        self._save_checkpoint(checkpoint_id, {
                            "transition_type": transition_type,
                            "transition_duration": transition_duration,
                            "status": "concluido",
                            "success": True,
                            "method": "advanced_zoom",
                            "zoom_params": {
                                "factor": zoom_factor,
                                "direction": zoom_direction,
                                "acceleration": acceleration,
                                "focus_point": focus_point
                            }
                        })
                        
                        return concatenate_videoclips([clip1, zoom_clip, clip2])
                else:
                    # Método original baseado em funções de transformação
                    # Função de aceleração personalizada
                    def get_zoom_progress(t):
                        progress = t / transition_duration
                        if acceleration == "ease-in-out":
                            # Curva suave de aceleração e desaceleração
                            return 0.5 * (1 - np.cos(np.pi * progress))
                        elif acceleration == "ease-in":
                            # Aceleração gradual
                            return progress ** 2
                        elif acceleration == "ease-out":
                            # Desaceleração gradual
                            return 1 - (1 - progress) ** 2
                        else:
                            # Linear
                            return progress
                    
                    # Aplica o zoom ao primeiro clip
                    def zoom_transform(get_frame, t, is_first_clip=True):
                        frame = get_frame(t)
                        progress = get_zoom_progress(t if is_first_clip else transition_duration - t)
                        
                        if zoom_direction == "in" and is_first_clip or zoom_direction == "out" and not is_first_clip:
                            # Zoom in para o primeiro clip ou zoom out para o segundo
                            scale = 1 + (zoom_factor - 1) * progress
                        else:
                            # Zoom out para o primeiro clip ou zoom in para o segundo
                            scale = zoom_factor - (zoom_factor - 1) * progress
                        
                        h, w = frame.shape[:2]
                        
                        # Determina o ponto focal
                        if focus_point == "center":
                            center = (w/2, h/2)
                        elif focus_point == "left":
                            center = (w/4, h/2)
                        elif focus_point == "right":
                            center = (3*w/4, h/2)
                        elif focus_point == "top":
                            center = (w/2, h/4)
                        elif focus_point == "bottom":
                            center = (w/2, 3*h/4)
                        else:  # default: center
                            center = (w/2, h/2)
                        
                        M = cv2.getRotationMatrix2D(center, 0, scale)
                        return cv2.warpAffine(frame, M, (w, h))
                    
                    clip1 = clip1.fl(lambda gf, t: zoom_transform(gf, t, True))
                    clip2 = clip2.fl(lambda gf, t: zoom_transform(gf, t, False))
                    
                    # Ajusta o início do segundo clip
                    clip2 = clip2.set_start(clip1.duration - transition_duration)
                    
                    # Atualiza o checkpoint
                    self._save_checkpoint(checkpoint_id, {
                        "transition_type": transition_type,
                        "transition_duration": transition_duration,
                        "status": "concluido",
                        "success": True,
                        "method": "moviepy_zoom",
                        "zoom_params": {
                            "factor": zoom_factor,
                            "direction": zoom_direction,
                            "acceleration": acceleration,
                            "focus_point": focus_point
                        }
                    })
                    
                    return concatenate_videoclips([clip1, clip2], method="compose")
                
            except Exception as e:
                logger.warning(f"Erro ao criar zoom: {str(e)}. Usando fade simples.")
                clip1 = clip1.crossfadeout(transition_duration)
                clip2 = clip2.crossfadein(transition_duration)
        
        elif transition_type == "morph":
            try:
                # Parâmetros do morph dos parâmetros passados ou otimizados
                morph_quality = kwargs.get("morph_quality", params.get("morph_quality", "high"))
                blend_frames = kwargs.get("blend_frames", params.get("blend_frames", int(transition_duration * self.video_settings['fps'] * 0.5)))
                smooth_edges = kwargs.get("smooth_edges", params.get("smooth_edges", True))
                flow_method = kwargs.get("flow_method", params.get("flow_method", "tvl1"))
                
                # Extraí frames para o morphing
                with tempfile.TemporaryDirectory() as temp_dir:
                    frame1_path = os.path.join(temp_dir, "frame1.png")
                    frame2_path = os.path.join(temp_dir, "frame2.png")
                    
                    clip1.save_frame(frame1_path, t=clip1.duration-0.1)
                    clip2.save_frame(frame2_path, t=0)
                    
                    # Gera frames intermediarios usando morphing
                    morph_frames = self.animation_generator.generate_morph_frames(
                        frame1_path,
                        frame2_path,
                        num_frames=blend_frames,
                        quality=morph_quality,
                        smooth_edges=smooth_edges,
                        flow_method=flow_method
                    )
                    
                    # Verifica se deve aplicar o efeito de color_shift
                    color_shift = kwargs.get("color_shift", params.get("color_shift", False))
                    color_intensity = kwargs.get("color_intensity", params.get("color_intensity", 0.3))
                    rainbow_effect = kwargs.get("rainbow_effect", params.get("rainbow_effect", False))
                    
                    if color_shift:
                        # Cores vibrantes para conteúdo infantil
                        vibrant_colors = [
                            [255, 0, 0],     # Vermelho
                            [255, 165, 0],   # Laranja
                            [255, 255, 0],   # Amarelo
                            [0, 255, 0],     # Verde
                            [0, 255, 255],   # Ciano
                            [0, 0, 255],     # Azul
                            [128, 0, 128],   # Roxo
                            [255, 0, 255],   # Magenta
                            [255, 192, 203]  # Rosa
                        ]
                        
                        # Processa cada frame para adicionar o efeito de cor
                        processed_frames = []
                        for i, frame_path in enumerate(morph_frames):
                            # Carrega o frame
                            frame = cv2.imread(frame_path)
                            
                            if frame is None:
                                continue
                                
                            # Determina a cor a ser aplicada
                            if rainbow_effect:
                                # Efeito arco-íris - cores mudam ao longo da transição
                                color_index = int((i / len(morph_frames)) * len(vibrant_colors))
                                color = vibrant_colors[color_index % len(vibrant_colors)]
                            else:
                                # Cor aleatória consistente para toda a transição
                                if i == 0:
                                    color_index = random.randint(0, len(vibrant_colors) - 1)
                                    color = vibrant_colors[color_index]
                                    
                            # Converte para BGR (formato do OpenCV)
                            color_bgr = [color[2], color[1], color[0]]
                            
                            # Cria uma camada de cor
                            color_layer = np.ones_like(frame) * np.array(color_bgr, dtype=np.uint8)
                            
                            # Calcula a intensidade baseada na posição do frame
                            # Mais intenso no meio da transição
                            position_factor = 1 - abs(2 * (i / (len(morph_frames) - 1)) - 1) if len(morph_frames) > 1 else 0.5
                            current_intensity = color_intensity * position_factor
                            
                            # Aplica a camada de cor com a intensidade calculada
                            blended_frame = cv2.addWeighted(frame, 1 - current_intensity, color_layer, current_intensity, 0)
                            
                            # Salva o frame processado
                            processed_path = os.path.join(os.path.dirname(frame_path), f"processed_{os.path.basename(frame_path)}")
                            cv2.imwrite(processed_path, blended_frame)
                            processed_frames.append(processed_path)
                        
                        # Usa os frames processados se existirem
                        if processed_frames:
                            morph_frames = processed_frames
                    
                    # Cria um clip com os frames do morph
                    morph_clip = ImageSequenceClip(morph_frames, fps=self.video_settings['fps'])
                    
                    # Ajusta a duração do morph
                    if morph_clip.duration != transition_duration:
                        morph_clip = morph_clip.set_duration(transition_duration)
                    
                    # Combina os clips com o morph
                    clip1 = clip1.subclip(0, clip1.duration - transition_duration/2)
                    clip2 = clip2.subclip(transition_duration/2)
                    
                    # Atualiza o checkpoint
                    self._save_checkpoint(checkpoint_id, {
                        "transition_type": transition_type,
                        "transition_duration": transition_duration,
                        "status": "concluido",
                        "success": True,
                        "method": "moviepy_morph",
                        "morph_params": {
                            "quality": morph_quality,
                            "blend_frames": blend_frames,
                            "smooth_edges": smooth_edges,
                            "flow_method": flow_method
                        }
                    })
                    
                    return concatenate_videoclips([clip1, morph_clip, clip2])
                    
            except Exception as e:
                logger.warning(f"Erro ao criar morph: {str(e)}. Usando fade simples.")
                clip1 = clip1.crossfadeout(transition_duration)
                clip2 = clip2.crossfadein(transition_duration)
        
        elif transition_type == "rotate3d":
            try:
                # Parâmetros da rotação 3D
                rotation_angle = kwargs.get("rotation_angle", params.get("rotation_angle", 180))  # Ângulo de rotação em graus
                rotation_axis = kwargs.get("rotation_axis", params.get("rotation_axis", "y"))    # Eixo de rotação (x, y, z)
                perspective = kwargs.get("perspective", params.get("perspective", 0.0008))     # Fator de perspectiva
                acceleration = kwargs.get("acceleration", params.get("acceleration", "ease-in-out"))
                background_color = kwargs.get("background_color", params.get("background_color", [0, 0, 0]))  # Cor de fundo (RGB)
                
                # Cria frames temporários para processamento avançado
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extrai frames-chave dos clips
                    frame1_path = os.path.join(temp_dir, "frame1.png")
                    frame2_path = os.path.join(temp_dir, "frame2.png")
                    clip1.save_frame(frame1_path, t=clip1.duration-0.1)
                    clip2.save_frame(frame2_path, t=0)
                    
                    # Carrega as imagens com OpenCV
                    frame1 = cv2.imread(frame1_path)
                    frame2 = cv2.imread(frame2_path)
                    
                    if frame1 is None or frame2 is None:
                        raise ValueError("Não foi possível carregar os frames para a transição de rotação 3D")
                    
                    # Garante que ambos os frames tenham o mesmo tamanho
                    h, w = frame1.shape[:2]
                    frame2 = cv2.resize(frame2, (w, h))
                    
                    # Gera frames intermediários para a rotação
                    rotation_frames = []
                    num_frames = int(transition_duration * self.video_settings['fps'])
                    
                    for i in range(num_frames):
                        # Calcula o fator de progresso (0 a 1)
                        progress = i / (num_frames - 1) if num_frames > 1 else 0.5
                        
                        # Aplica aceleração ao progresso
                        if acceleration == "ease-in":
                            progress = progress * progress
                        elif acceleration == "ease-out":
                            progress = 1 - (1 - progress) * (1 - progress)
                        elif acceleration == "ease-in-out":
                            progress = 0.5 * (1 - np.cos(np.pi * progress))
                        
                        # Calcula o ângulo atual baseado no progresso
                        current_angle = rotation_angle * progress
                        
                        # Determina qual frame mostrar baseado no ângulo
                        if current_angle < rotation_angle / 2:
                            # Primeira metade da rotação: mostra o primeiro frame rotacionando
                            src_frame = frame1.copy()
                            angle = current_angle
                        else:
                            # Segunda metade da rotação: mostra o segundo frame rotacionando
                            src_frame = frame2.copy()
                            angle = rotation_angle - current_angle
                        
                        # Aplica a transformação de rotação 3D
                        center = (w // 2, h // 2)
                        
                        # Cria a matriz de transformação para simular rotação 3D
                        if rotation_axis == "y":
                            # Rotação em torno do eixo Y (horizontal)
                            alpha = angle * np.pi / 180.0
                            d = perspective * w
                            A1 = np.cos(alpha)
                            A2 = d * np.sin(alpha)
                            A3 = -np.sin(alpha) / d
                            A4 = np.cos(alpha)
                            
                            # Matriz de transformação para rotação em Y
                            transform = np.array([
                                [A1, 0, A2, 0],
                                [0, 1, 0, 0],
                                [A3, 0, A4, 0],
                                [0, 0, 0, 1]
                            ])
                        elif rotation_axis == "x":
                            # Rotação em torno do eixo X (vertical)
                            alpha = angle * np.pi / 180.0
                            d = perspective * h
                            A1 = 1
                            A2 = 0
                            A3 = 0
                            A4 = np.cos(alpha)
                            A5 = d * np.sin(alpha)
                            A6 = -np.sin(alpha) / d
                            A7 = np.cos(alpha)
                            
                            # Matriz de transformação para rotação em X
                            transform = np.array([
                                [1, 0, 0, 0],
                                [0, A4, A5, 0],
                                [0, A6, A7, 0],
                                [0, 0, 0, 1]
                            ])
                        else:  # "z" ou outro
                            # Rotação em torno do eixo Z (profundidade)
                            M = cv2.getRotationMatrix2D(center, angle, 1.0)
                            rotated_frame = cv2.warpAffine(src_frame, M, (w, h))
                            
                            # Salva o frame processado
                            frame_path = os.path.join(temp_dir, f"rotate_frame_{i:04d}.png")
                            cv2.imwrite(frame_path, rotated_frame)
                            rotation_frames.append(frame_path)
                            continue  # Pula o resto do processamento para o eixo Z
                        
                        # Aplica a transformação de perspectiva para eixos X e Y
                        pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
                        
                        # Calcula os pontos transformados
                        pts2 = np.zeros((4, 2), dtype=np.float32)
                        for j in range(4):
                            # Coordenadas homogêneas
                            pt = np.array([pts1[j][0] - center[0], pts1[j][1] - center[1], 0, 1])
                            
                            # Aplica a transformação
                            pt_transformed = np.dot(transform, pt)
                            
                            # Normaliza as coordenadas homogêneas
                            pt_transformed = pt_transformed[:3] / pt_transformed[3]
                            
                            # Converte de volta para coordenadas da imagem
                            pts2[j][0] = pt_transformed[0] + center[0]
                            pts2[j][1] = pt_transformed[1] + center[1]
                        
                        # Aplica a transformação de perspectiva com cor de fundo personalizada
                        # Converte a cor de fundo de RGB para BGR (formato do OpenCV)
                        bg_color = background_color.copy()
                        if len(bg_color) == 3:
                            bg_color[0], bg_color[2] = bg_color[2], bg_color[0]  # Troca R e B
                        
                        # Cria um fundo com a cor especificada
                        bg = np.ones((h, w, 3), dtype=np.uint8)
                        bg[:, :] = bg_color
                        
                        # Aplica a transformação de perspectiva
                        M = cv2.getPerspectiveTransform(pts1, pts2)
                        warped_frame = cv2.warpPerspective(src_frame, M, (w, h), borderMode=cv2.BORDER_TRANSPARENT, dst=bg.copy())
                        
                        # Adiciona efeito de confete se solicitado
                        confetti_effect = kwargs.get("confetti_effect", params.get("confetti_effect", False))
                        if confetti_effect:
                            # Determina a quantidade de confete baseada no progresso da transição
                            # Mais confete no meio da transição
                            confetti_amount = int(100 * (1 - abs(2*progress - 1)))
                            
                            # Cores vibrantes para o confete
                            confetti_colors = [
                                [255, 0, 0],     # Vermelho
                                [0, 255, 0],     # Verde
                                [0, 0, 255],     # Azul
                                [255, 255, 0],   # Amarelo
                                [255, 0, 255],   # Magenta
                                [0, 255, 255],   # Ciano
                                [255, 165, 0],   # Laranja
                                [128, 0, 128],   # Roxo
                                [255, 192, 203], # Rosa
                                [152, 251, 152]  # Verde claro
                            ]
                            
                            # Adiciona confete à imagem
                            for _ in range(confetti_amount):
                                # Posição aleatória
                                x = np.random.randint(0, w)
                                y = np.random.randint(0, h)
                                
                                # Tamanho aleatório
                                size = np.random.randint(3, 10)
                                
                                # Forma aleatória (círculo, quadrado, triângulo)
                                shape_type = np.random.choice(["circle", "rectangle", "triangle"])
                                
                                # Cor aleatória
                                color = random.choice(confetti_colors)
                                # Converte para BGR para o OpenCV
                                color_bgr = [color[2], color[1], color[0]]
                                
                                # Desenha a forma
                                if shape_type == "circle":
                                    cv2.circle(warped_frame, (x, y), size, color_bgr, -1)
                                elif shape_type == "rectangle":
                                    cv2.rectangle(warped_frame, 
                                                 (x - size, y - size), 
                                                 (x + size, y + size), 
                                                 color_bgr, -1)
                                elif shape_type == "triangle":
                                    # Cria um triângulo
                                    pts = np.array([[x, y - size], 
                                                   [x - size, y + size], 
                                                   [x + size, y + size]], 
                                                  np.int32)
                                    pts = pts.reshape((-1, 1, 2))
                                    cv2.fillPoly(warped_frame, [pts], color_bgr)
                        
                        # Salva o frame processado
                        frame_path = os.path.join(temp_dir, f"rotate_frame_{i:04d}.png")
                        cv2.imwrite(frame_path, warped_frame)
                        rotation_frames.append(frame_path)
                    
                    # Cria um clip com os frames da rotação
                    rotation_clip = ImageSequenceClip(rotation_frames, fps=self.video_settings['fps'])
                    
                    # Ajusta a duração da transição
                    if rotation_clip.duration != transition_duration:
                        rotation_clip = rotation_clip.set_duration(transition_duration)
                    
                    # Combina os clips com a rotação
                    clip1 = clip1.subclip(0, clip1.duration - transition_duration/2)
                    clip2 = clip2.subclip(transition_duration/2)
                    
                    # Atualiza o checkpoint
                    self._save_checkpoint(checkpoint_id, {
                        "transition_type": transition_type,
                        "transition_duration": transition_duration,
                        "status": "concluido",
                        "success": True,
                        "method": "rotate3d",
                        "rotation_params": {
                            "angle": rotation_angle,
                            "axis": rotation_axis,
                            "perspective": perspective,
                            "acceleration": acceleration,
                            "background_color": background_color
                        }
                    })
                    
                    return concatenate_videoclips([clip1, rotation_clip, clip2])
            except Exception as e:
                logger.warning(f"Erro ao criar rotação 3D: {str(e)}. Usando fade simples.")
                clip1 = clip1.crossfadeout(transition_duration)
                clip2 = clip2.crossfadein(transition_duration)
        
        elif transition_type == "page_turn":
            try:
                # Parâmetros da transição de página virando
                turn_direction = kwargs.get("turn_direction", params.get("turn_direction", "left-to-right"))  # left-to-right ou right-to-left
                shadow_intensity = kwargs.get("shadow_intensity", params.get("shadow_intensity", 0.5))  # Intensidade da sombra (0-1)
                page_curve = kwargs.get("page_curve", params.get("page_curve", 0.3))  # Curvatura da página (0-1)
                acceleration = kwargs.get("acceleration", params.get("acceleration", "ease-in-out"))
                page_color = kwargs.get("page_color", params.get("page_color", [255, 255, 255]))  # Cor da página (RGB)
                texture_effect = kwargs.get("texture_effect", params.get("texture_effect", False))  # Aplicar textura de papel
                sparkle_effect = kwargs.get("sparkle_effect", params.get("sparkle_effect", False))  # Aplicar efeito de brilho
                brightness_effect = kwargs.get("brightness_effect", params.get("brightness_effect", False))  # Aplicar efeito de brilho gradual
                
                # Cria frames temporários para processamento avançado
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extrai frames-chave dos clips
                    frame1_path = os.path.join(temp_dir, "frame1.png")
                    frame2_path = os.path.join(temp_dir, "frame2.png")
                    clip1.save_frame(frame1_path, t=clip1.duration-0.1)
                    clip2.save_frame(frame2_path, t=0)
                    
                    # Carrega as imagens com OpenCV
                    frame1 = cv2.imread(frame1_path)
                    frame2 = cv2.imread(frame2_path)
                    
                    if frame1 is None or frame2 is None:
                        raise ValueError("Não foi possível carregar os frames para a transição de página virando")
                    
                    # Garante que ambos os frames tenham o mesmo tamanho
                    h, w = frame1.shape[:2]
                    frame2 = cv2.resize(frame2, (w, h))
                    
                    # Gera frames intermediários para a animação de página virando
                    page_frames = []
                    num_frames = int(transition_duration * self.video_settings['fps'])
                    
                    for i in range(num_frames):
                        # Calcula o fator de progresso (0 a 1)
                        progress = i / (num_frames - 1) if num_frames > 1 else 0.5
                        
                        # Aplica aceleração ao progresso
                        if acceleration == "ease-in":
                            progress = progress * progress
                        elif acceleration == "ease-out":
                            progress = 1 - (1 - progress) * (1 - progress)
                        elif acceleration == "ease-in-out":
                            progress = 0.5 * (1 - np.cos(np.pi * progress))
                        
                        # Cria uma imagem em branco para o resultado
                        result = np.zeros_like(frame1)
                        
                        # Inverte a direção se necessário
                        actual_progress = progress if turn_direction == "left-to-right" else 1 - progress
                        
                        # Calcula a posição da dobra da página
                        fold_position = int(w * actual_progress)
                        
                        # Desenha a primeira imagem (página atual)
                        if actual_progress < 1.0:
                            # Parte visível da primeira imagem
                            visible_width = max(0, fold_position)
                            if visible_width > 0:
                                if turn_direction == "left-to-right":
                                    result[:, 0:visible_width] = frame1[:, 0:visible_width]
                                else:
                                    result[:, w-visible_width:w] = frame1[:, w-visible_width:w]
                        
                        # Desenha a segunda imagem (página seguinte)
                        if actual_progress > 0.0:
                            # Parte visível da segunda imagem
                            visible_width = max(0, w - fold_position)
                            if visible_width > 0:
                                if turn_direction == "left-to-right":
                                    result[:, fold_position:w] = frame2[:, fold_position:w]
                                else:
                                    result[:, 0:w-fold_position] = frame2[:, 0:w-fold_position]
                        
                        # Simula a dobra da página
                        if 0.05 < actual_progress < 0.95:
                            # Largura da dobra
                            fold_width = int(w * page_curve * (1 - abs(2*actual_progress - 1)))
                            fold_width = max(5, min(fold_width, w//4))  # Limita o tamanho da dobra
                            
                            # Posição da dobra
                            if turn_direction == "left-to-right":
                                fold_start = max(0, fold_position - fold_width)
                                fold_end = min(w, fold_position + fold_width)
                            else:
                                fold_start = max(0, fold_position - fold_width)
                                fold_end = min(w, fold_position + fold_width)
                            
                            # Aplica textura de papel se solicitado
                            if texture_effect:
                                # Cria uma textura de papel simples usando ruído
                                texture = np.ones((h, w, 3), dtype=np.uint8) * 240  # Base clara
                                
                                # Adiciona ruído para simular fibras de papel
                                noise = np.random.randint(0, 20, (h, w, 3), dtype=np.uint8)
                                texture = cv2.add(texture, noise)
                                
                                # Adiciona algumas linhas sutis para simular fibras
                                for _ in range(100):
                                    x1, y1 = np.random.randint(0, w), np.random.randint(0, h)
                                    x2, y2 = x1 + np.random.randint(-20, 20), y1 + np.random.randint(-20, 20)
                                    color = np.random.randint(200, 240)
                                    
                            # Adiciona efeito de brilho (sparkle) se solicitado
                            sparkle_effect = kwargs.get("sparkle_effect", params.get("sparkle_effect", False))
                            if sparkle_effect:
                                # Cria brilhos aleatórios na dobra da página
                                num_sparkles = int(30 * (1 - abs(2*actual_progress - 1)))  # Mais brilho no meio da transição
                                
                                # Cores vibrantes para os brilhos (adequadas para conteúdo infantil)
                                sparkle_colors = [
                                    (255, 255, 255),  # Branco
                                    (255, 255, 0),    # Amarelo
                                    (0, 255, 255),    # Ciano
                                    (255, 0, 255),    # Magenta
                                    (255, 215, 0),    # Dourado
                                    (255, 192, 203),  # Rosa claro
                                    (135, 206, 250)   # Azul claro
                                ]
                                
                                # Cria dois tipos de sparkles para um efeito mais rico
                                
                                # Tipo 1: Estrelas (para 60% dos sparkles)
                                for _ in range(int(num_sparkles * 0.6)):
                                    # Posição aleatória na área da dobra
                                    x = np.random.randint(fold_start, fold_end)
                                    y = np.random.randint(0, h)
                                    
                                    # Tamanho aleatório para o brilho
                                    size = np.random.randint(2, 6)
                                    
                                    # Cor aleatória para o brilho
                                    color = random.choice(sparkle_colors)
                                    # Converte para BGR para o OpenCV
                                    color_bgr = (color[2], color[1], color[0])
                                    
                                    # Desenha o brilho como uma estrela simples
                                    cv2.circle(result, (x, y), size, color_bgr, -1)
                                    
                                    # Adiciona raios para criar efeito de estrela
                                    for angle in range(0, 360, 45):
                                        rad = np.radians(angle)
                                        end_x = int(x + size * 2 * np.cos(rad))
                                        end_y = int(y + size * 2 * np.sin(rad))
                                        cv2.line(result, (x, y), (end_x, end_y), color_bgr, 1)
                                
                                # Tipo 2: Círculos com degradê (para 40% dos sparkles)
                                for _ in range(int(num_sparkles * 0.4)):
                                    # Posiciona os brilhos próximos à dobra
                                    sparkle_x = np.random.randint(fold_start, fold_end)
                                    sparkle_y = np.random.randint(0, h)
                                    
                                    # Tamanho do brilho
                                    sparkle_size = np.random.randint(3, 8)
                                    
                                    # Seleciona uma cor aleatória para o brilho
                                    color = random.choice(sparkle_colors)
                                    # Converte para BGR para o OpenCV
                                    color_bgr = (color[2], color[1], color[0])
                                    
                                    # Desenha o brilho como um círculo com degradê
                                    for r in range(sparkle_size, 0, -1):
                                        # Intensidade baseada na distância do centro
                                        intensity = 1.0 - (r / sparkle_size)
                                        
                                        # Cor com intensidade ajustada
                                        color_with_intensity = (int(color_bgr[0] * intensity),
                                                               int(color_bgr[1] * intensity),
                                                               int(color_bgr[2] * intensity))
                                        
                                        # Desenha o círculo
                                        cv2.circle(result, (sparkle_x, sparkle_y), r, color_with_intensity, 1)

                                
                                # Aplica a textura à área da dobra com blend
                                alpha = 0.3  # Intensidade da textura
                                mask = np.zeros((h, w), dtype=np.uint8)
                                cv2.rectangle(mask, (fold_start, 0), (fold_end, h), 255, -1)
                                mask = cv2.GaussianBlur(mask, (15, 15), 0)
                                mask = mask.reshape(h, w, 1) / 255.0
                                
                                # Aplica a textura apenas na área da dobra
                                result = result * (1 - mask * alpha) + texture * (mask * alpha)
                            
                            # Cria um gradiente para simular a dobra e sombra
                            for x in range(fold_start, fold_end):
                                # Distância normalizada do centro da dobra
                                dist = abs(x - fold_position) / fold_width
                                
                                # Fator de escurecimento baseado na distância e na intensidade da sombra
                                shadow_factor = 1.0 - shadow_intensity * (1.0 - dist * dist)
                                
                                # Aplica o escurecimento
                                if 0 <= x < w:
                                    result[:, x] = (result[:, x] * shadow_factor).astype(np.uint8)
                            
                            # Adiciona um efeito de distorção na dobra
                            if turn_direction == "left-to-right":
                                # Determina qual imagem usar para a dobra
                                fold_img = frame1 if actual_progress < 0.5 else frame2
                                
                                # Cria uma máscara para a área da dobra
                                mask = np.zeros((h, w), dtype=np.uint8)
                                cv2.rectangle(mask, (fold_start, 0), (fold_position, h), 255, -1)
                                
                                # Cria uma imagem com a cor da página personalizada para o verso
                                page_back = np.ones((h, w, 3), dtype=np.uint8)
                                # Converte a cor da página de RGB para BGR (formato do OpenCV)
                                page_back_color = page_color.copy()
                                if len(page_back_color) == 3:
                                    page_back_color[0], page_back_color[2] = page_back_color[2], page_back_color[0]  # Troca R e B
                                page_back[:] = page_back_color
                                
                                # Determina quando mostrar o verso da página (cor personalizada)
                                show_page_back = 0.2 < actual_progress < 0.8
                                
                                # Aplica uma leve distorção na área da dobra
                                for y in range(h):
                                    for x in range(fold_start, fold_position):
                                        # Distorção proporcional à distância da dobra
                                        dist_factor = (x - fold_start) / max(1, fold_position - fold_start)
                                        src_x = int(x - fold_width * 0.2 * dist_factor)
                                        
                                        # Decide se mostra o conteúdo da imagem ou o verso da página
                                        if show_page_back and dist_factor > 0.5:
                                            # Mostra o verso da página (cor personalizada)
                                            result[y, x] = page_back[y, x]
                                        elif 0 <= src_x < w:
                                            # Mostra o conteúdo da imagem com distorção
                                            result[y, x] = fold_img[y, src_x]
                            else:
                                # Implementação similar para right-to-left
                                fold_img = frame1 if actual_progress > 0.5 else frame2
                                
                                mask = np.zeros((h, w), dtype=np.uint8)
                                cv2.rectangle(mask, (fold_position, 0), (fold_end, h), 255, -1)
                                
                                # Cria uma imagem com a cor da página personalizada para o verso
                                page_back = np.ones((h, w, 3), dtype=np.uint8)
                                # Converte a cor da página de RGB para BGR (formato do OpenCV)
                                page_back_color = page_color.copy()
                                if len(page_back_color) == 3:
                                    page_back_color[0], page_back_color[2] = page_back_color[2], page_back_color[0]  # Troca R e B
                                page_back[:] = page_back_color
                                
                                # Determina quando mostrar o verso da página (cor personalizada)
                                show_page_back = 0.2 < actual_progress < 0.8
                                
                                for y in range(h):
                                    for x in range(fold_position, fold_end):
                                        dist_factor = (fold_end - x) / max(1, fold_end - fold_position)
                                        src_x = int(x + fold_width * 0.2 * dist_factor)
                                        
                                        # Decide se mostra o conteúdo da imagem ou o verso da página
                                        if show_page_back and dist_factor > 0.5:
                                            # Mostra o verso da página (cor personalizada)
                                            result[y, x] = page_back[y, x]
                                        elif 0 <= src_x < w:
                                            # Mostra o conteúdo da imagem com distorção
                                            result[y, x] = fold_img[y, src_x]
                        
                        # Aplica efeito de brilho gradual se solicitado
                        brightness_effect = kwargs.get("brightness_effect", params.get("brightness_effect", False))
                        if brightness_effect:
                            # Calcula a intensidade do brilho baseado no progresso da transição
                            # Mais brilho no meio da transição (efeito mágico)
                            brightness_factor = 1.0 + 0.5 * (1 - abs(2*progress - 1))
                            
                            # Cria uma máscara para aplicar o brilho apenas na área da dobra
                            brightness_mask = np.zeros_like(result)
                            
                            # Define a área da dobra para o brilho
                            mask_width = int(w * 0.3)  # Largura da área de brilho
                            mask_start = max(0, fold_position - mask_width//2)
                            mask_end = min(w, fold_position + mask_width//2)
                            
                            # Cria um gradiente suave para a máscara
                            for x in range(mask_start, mask_end):
                                # Calcula a intensidade baseada na distância do centro da dobra
                                intensity = 1.0 - abs(x - fold_position) / (mask_width/2)
                                intensity = intensity * intensity  # Suaviza o gradiente
                                
                                # Aplica a intensidade na máscara
                                brightness_mask[:, x] = np.array([255, 255, 255]) * intensity
                            
                            # Converte para float para evitar saturação durante os cálculos
                            result_float = result.astype(np.float32)
                            
                            # Aplica o brilho usando a máscara
                            bright_area = cv2.multiply(result_float, brightness_factor)
                            brightness_mask_norm = brightness_mask.astype(np.float32) / 255.0
                            
                            # Combina a imagem original com a área brilhante
                            result = result_float * (1 - brightness_mask_norm) + bright_area * brightness_mask_norm
                            
                            # Adiciona um brilho suave em toda a imagem
                            global_brightness = 1.0 + 0.2 * (1 - abs(2*progress - 1))
                            result = result * global_brightness
                            
                            # Converte de volta para uint8
                            result = np.clip(result, 0, 255).astype(np.uint8)
                        
                        # Salva o frame processado
                        frame_path = os.path.join(temp_dir, f"page_frame_{i:04d}.png")
                        cv2.imwrite(frame_path, result)
                        page_frames.append(frame_path)
                    
                    # Cria um clip com os frames da animação de página virando
                    page_clip = ImageSequenceClip(page_frames, fps=self.video_settings['fps'])
                    
                    # Ajusta a duração da transição
                    if page_clip.duration != transition_duration:
                        page_clip = page_clip.set_duration(transition_duration)
                    
                    # Combina os clips com a animação de página
                    clip1 = clip1.subclip(0, clip1.duration - transition_duration/2)
                    clip2 = clip2.subclip(transition_duration/2)
                    
                    # Atualiza o checkpoint
                    self._save_checkpoint(checkpoint_id, {
                        "transition_type": transition_type,
                        "transition_duration": transition_duration,
                        "status": "concluido",
                        "success": True,
                        "method": "page_turn",
                        "page_params": {
                            "direction": turn_direction,
                            "shadow": shadow_intensity,
                            "curve": page_curve,
                            "acceleration": acceleration,
                            "page_color": page_color,
                            "sparkle_effect": sparkle_effect,
                            "brightness_effect": brightness_effect,
                            "texture_effect": texture_effect
                        }
                    })
                    
                    return concatenate_videoclips([clip1, page_clip, clip2])
            except Exception as e:
                logger.warning(f"Erro ao criar transição de página virando: {str(e)}. Usando fade simples.")
                clip1 = clip1.crossfadeout(transition_duration)
                clip2 = clip2.crossfadein(transition_duration)
        
        else:
            # Para outros tipos, usa fade simples
            clip1 = clip1.crossfadeout(transition_duration)
            clip2 = clip2.crossfadein(transition_duration)
        
        # Ajusta o início do segundo clip
        clip2 = clip2.set_start(clip1.duration - transition_duration)
        
        # Atualiza o checkpoint final
        self._save_checkpoint(checkpoint_id, {
            "transition_type": transition_type,
            "transition_duration": transition_duration,
            "status": "concluido",
            "success": True,
            "method": "moviepy_fade_fallback",
            "fallback_params": {
                **params,
                **kwargs  # Inclui os parâmetros passados via kwargs
            }
        })
        
        # Concatena os clips
        return concatenate_videoclips([clip1, clip2], method="compose")
        
    def _cleanup_temp_files(self, directory: str, pattern: str = "*", max_age_hours: int = 24) -> None:
        """
        Limpa arquivos temporários antigos para liberar espaço em disco.
        
        Args:
            directory: Diretório onde os arquivos temporários estão armazenados
            pattern: Padrão para filtrar os arquivos (ex: "*.mp4")
            max_age_hours: Idade máxima dos arquivos em horas
        """
        try:
            import glob
            from datetime import datetime, timedelta
            
            # Verifica se o diretório existe
            if not os.path.exists(directory):
                logger.warning(f"Diretório não encontrado para limpeza: {directory}")
                return
            
            # Calcula o timestamp limite
            now = datetime.now()
            max_age = timedelta(hours=max_age_hours)
            cutoff_time = now - max_age
            
            # Encontra todos os arquivos que correspondem ao padrão
            file_pattern = os.path.join(directory, pattern)
            files = glob.glob(file_pattern)
            
            # Conta arquivos e espaço liberado
            files_removed = 0
            bytes_freed = 0
            
            for file_path in files:
                # Obtém a última modificação do arquivo
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # Verifica se o arquivo é mais antigo que o limite
                if file_modified < cutoff_time:
                    # Obtém o tamanho do arquivo antes de removê-lo
                    file_size = os.path.getsize(file_path)
                    
                    try:
                        # Remove o arquivo
                        os.remove(file_path)
                        files_removed += 1
                        bytes_freed += file_size
                    except Exception as e:
                        logger.warning(f"Erro ao remover arquivo temporário {file_path}: {str(e)}")
            
            # Converte bytes para MB para exibição
            mb_freed = bytes_freed / (1024 * 1024)
            
            if files_removed > 0:
                logger.info(f"Limpeza concluída: {files_removed} arquivos removidos, {mb_freed:.2f} MB liberados")
            else:
                logger.debug(f"Nenhum arquivo temporário antigo encontrado em {directory}")
                
        except Exception as e:
            logger.error(f"Erro durante a limpeza de arquivos temporários: {str(e)}")
    
    def _analyze_emotional_tone(self, scene_description: str) -> Dict[str, Any]:
        """
        Analisa o tom emocional de uma descrição de cena.
        
        Args:
            scene_description: Texto da descrição da cena
            
        Returns:
            Dict[str, Any]: Dicionário com informações sobre o tom emocional
        """
        # Palavras-chave para diferentes tons emocionais
        emotional_keywords = {
            "alegre": ["feliz", "alegre", "contente", "animado", "divertido", "riso", "sorriso", "celebração", "festa"],
            "triste": ["triste", "melancólico", "deprimido", "chorando", "lágrimas", "sombrio", "desolado", "luto"],
            "tenso": ["tenso", "nervoso", "ansioso", "preocupado", "estressado", "apreensivo", "alarmado", "assustado"],
            "calmo": ["calmo", "tranquilo", "sereno", "relaxado", "pacífico", "suave", "gentil", "harmonioso"],
            "raiva": ["raiva", "furia", "irritado", "zangado", "furioso", "enfurecido", "hostil", "agressivo"],
            "surpresa": ["surpresa", "choque", "espanto", "assombro", "perplexo", "atordoado", "maravilhado"],
            "medo": ["medo", "terror", "horror", "pânico", "apavorado", "assustado", "aterrorizado"],
            "amor": ["amor", "carinho", "afeto", "adoração", "paixão", "ternura", "compaixão", "amizade"],
            "aventura": ["aventura", "exploração", "descoberta", "jornada", "busca", "desafio", "emoção"],
            "mistério": ["mistério", "enigma", "intriga", "suspense", "desconhecido", "secreto", "oculto"],
            "mágico": ["mágico", "encantado", "feitiço", "mágica", "místico", "sobrenatural", "maravilhoso"]
        }
        
        # Inicializa o dicionário de resultados
        tone_results = {
            "primary_tone": None,
            "secondary_tone": None,
            "intensity": 0.5,  # Intensidade padrão (média)
            "tones": {}
        }
        
        # Converte a descrição para minúsculas para facilitar a comparação
        description_lower = scene_description.lower()
        
        # Conta as ocorrências de cada tom emocional
        for tone, keywords in emotional_keywords.items():
            count = sum(1 for keyword in keywords if keyword in description_lower)
            if count > 0:
                tone_results["tones"][tone] = count
        
        # Determina os tons primário e secundário
        sorted_tones = sorted(tone_results["tones"].items(), key=lambda x: x[1], reverse=True)
        
        if sorted_tones:
            tone_results["primary_tone"] = sorted_tones[0][0]
            if len(sorted_tones) > 1:
                tone_results["secondary_tone"] = sorted_tones[1][0]
        
        # Determina a intensidade com base em palavras intensificadoras
        intensifiers = ["muito", "extremamente", "completamente", "totalmente", "absolutamente", 
                       "intensamente", "profundamente", "fortemente", "super", "ultra"]
        
        intensity_count = sum(1 for word in intensifiers if word in description_lower)
        if intensity_count > 0:
            # Ajusta a intensidade com base no número de intensificadores (máximo 0.9)
            tone_results["intensity"] = min(0.5 + (intensity_count * 0.1), 0.9)
        
        # Verifica se há palavras de diminuição de intensidade
        diminishers = ["pouco", "levemente", "ligeiramente", "suavemente", "um pouco", "quase", "apenas"]
        diminish_count = sum(1 for word in diminishers if word in description_lower)
        if diminish_count > 0:
            # Reduz a intensidade com base no número de diminuidores (mínimo 0.1)
            tone_results["intensity"] = max(0.5 - (diminish_count * 0.1), 0.1)
        
        return tone_results
    
    def _select_transition_for_scenes(self, current_scene: Dict[str, Any], next_scene: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Seleciona automaticamente uma transição apropriada com base no contexto das cenas.
        
        Args:
            current_scene: Dados da cena atual
            next_scene: Dados da próxima cena
            
        Returns:
            Tuple[str, Dict[str, Any]]: Tipo de transição e parâmetros adicionais
        """
        # Parâmetros padrão para a transição
        params = {}
        
        # Extrai informações relevantes das cenas
        current_description = current_scene.get('description', '').lower()
        next_description = next_scene.get('description', '').lower()
        current_setting = current_scene.get('setting', {}).get('location', '').lower()
        next_setting = next_scene.get('setting', {}).get('location', '').lower()
        current_emotion = current_scene.get('emotion', '').lower()
        next_emotion = next_scene.get('emotion', '').lower()
        
        # Analisa o tom emocional das descrições das cenas
        current_tone = self._analyze_emotional_tone(current_description)
        next_tone = self._analyze_emotional_tone(next_description)
        
        # Palavras-chave para detectar mudanças de página ou capítulo
        page_turn_keywords = ['virar página', 'nova página', 'próxima página', 'capítulo', 'livro', 'conto', 'história']
        
        # Palavras-chave para detectar mudanças de foco ou zoom
        zoom_keywords = ['aproximar', 'afastar', 'zoom', 'foco', 'detalhe', 'perto', 'longe', 'close']
        
        # Palavras-chave para detectar rotação ou mudança de perspectiva
        rotate_keywords = ['girar', 'rotação', 'virar', 'perspectiva', 'lado', 'volta', 'mudar de ângulo']
        
        # Palavras-chave para detectar transformação ou morphing
        morph_keywords = ['transformar', 'mudar', 'metamorfose', 'evoluir', 'mágica', 'encanto', 'feitiço']
        
        # Verifica se há mudança drástica de emoção
        emotion_change = False
        
        # Verifica mudança de emoção usando a análise de tom emocional
        if current_tone["primary_tone"] and next_tone["primary_tone"] and current_tone["primary_tone"] != next_tone["primary_tone"]:
            # Pares de tons emocionais opostos
            opposite_tones = [
                ("alegre", "triste"), ("calmo", "tenso"), ("amor", "raiva"),
                ("calmo", "raiva"), ("alegre", "medo"), ("calmo", "surpresa")
            ]
            
            for t1, t2 in opposite_tones:
                if (current_tone["primary_tone"] == t1 and next_tone["primary_tone"] == t2) or \
                   (current_tone["primary_tone"] == t2 and next_tone["primary_tone"] == t1):
                    emotion_change = True
                    logger.debug(f"Detectada mudança emocional significativa: {current_tone['primary_tone']} -> {next_tone['primary_tone']}")
                    break
        
        # Também verifica usando os campos de emoção do roteiro, se disponíveis
        if not emotion_change and current_emotion and next_emotion and current_emotion != next_emotion:
            # Emoções opostas sugerem uma transição mais dramática
            opposite_emotions = [
                ('feliz', 'triste'), ('alegre', 'melancólico'), 
                ('calmo', 'agitado'), ('tranquilo', 'nervoso'),
                ('seguro', 'assustado'), ('confiante', 'temeroso')
            ]
            
            for e1, e2 in opposite_emotions:
                if (e1 in current_emotion and e2 in next_emotion) or (e2 in current_emotion and e1 in next_emotion):
                    emotion_change = True
                    logger.debug(f"Detectada mudança emocional significativa no roteiro: {current_emotion} -> {next_emotion}")
                    break
        
        # Verifica se há mudança de local/ambiente
        location_change = current_setting != next_setting and current_setting and next_setting
        
        # Lógica para selecionar a transição baseada no contexto
        
        # 1. Verifica transição de página virando (para histórias infantis)
        for keyword in page_turn_keywords:
            if keyword in current_description or keyword in next_description:
                # Determina a cor da página com base no contexto
                page_color = [255, 250, 240]  # Cor padrão (off-white)
                
                # Verifica se há menção a livros antigos ou páginas amareladas
                if any(word in current_description or word in next_description 
                       for word in ["antigo", "velho", "amarelado", "histórico", "medieval"]):
                    page_color = [245, 222, 179]  # Tom amarelado/envelhecido
                
                # Verifica se é um livro infantil colorido
                elif any(word in current_description or word in next_description 
                         for word in ["colorido", "infantil", "criança", "alegre"]):
                    # Escolhe uma cor pastel aleatória
                    pastel_colors = [
                        [255, 182, 193],  # Rosa claro
                        [173, 216, 230],  # Azul claro
                        [152, 251, 152],  # Verde claro
                        [255, 218, 185],  # Pêssego
                        [221, 160, 221]   # Lavanda
                    ]
                    page_color = random.choice(pastel_colors)
                
                # Determina se deve usar efeito de textura
                texture_effect = any(word in current_description or word in next_description 
                                   for word in ["textura", "papel", "pergaminho", "artesanal"])
                
                # Determina se deve usar efeito de sparkle (brilhos) baseado no contexto
                sparkle_effect = any(word in current_description or word in next_description 
                                   for word in ["mágico", "mágica", "magia", "encantado", "brilhante", "fada", "fantasia"])
                
                # Determina se deve usar efeito de brilho gradual baseado no contexto
                brightness_effect = any(word in current_description or word in next_description 
                                     for word in ["luz", "brilho", "iluminado", "radiante", "resplandecente", "sol"])
                
                # Para conteúdo infantil, podemos ativar esses efeitos por padrão se o tom for alegre
                if any(word in current_description or word in next_description for word in ["infantil", "criança", "crianças"]):
                    if current_tone.get("primary_tone") == "alegre" or next_tone.get("primary_tone") == "alegre":
                        sparkle_effect = True
                        brightness_effect = True
                
                return "page_turn", {
                    "turn_direction": "left-to-right",
                    "shadow_intensity": 0.6,
                    "page_curve": 0.3,
                    "acceleration": "ease-in-out",
                    "page_color": page_color,
                    "texture_effect": texture_effect,
                    "sparkle_effect": sparkle_effect,
                    "brightness_effect": brightness_effect
                }
        
        # 2. Verifica transição de zoom (para mudanças de foco)
        for keyword in zoom_keywords:
            if keyword in current_description or keyword in next_description:
                # Determina se é zoom in ou zoom out
                zoom_direction = "in" if any(w in current_description or w in next_description 
                                           for w in ["aproximar", "perto", "detalhe", "close"]) else "out"
                
                # Determina o ponto focal baseado no contexto
                focus_point = "center"  # padrão
                if "acima" in current_description or "acima" in next_description or "céu" in next_description:
                    focus_point = "top"
                elif "abaixo" in current_description or "abaixo" in next_description or "chão" in next_description:
                    focus_point = "bottom"
                elif "esquerda" in current_description or "esquerda" in next_description:
                    focus_point = "left"
                elif "direita" in current_description or "direita" in next_description:
                    focus_point = "right"
                
                return "zoom", {
                    "zoom_factor": 1.8,
                    "zoom_direction": zoom_direction,
                    "focus_point": focus_point,
                    "acceleration": "ease-in-out",
                    "use_advanced": True
                }
        
        # 3. Verifica transição de rotação 3D (para mudanças de perspectiva)
        for keyword in rotate_keywords:
            if keyword in current_description or keyword in next_description:
                # Determina o eixo de rotação baseado no contexto
                rotation_axis = "y"  # padrão (horizontal)
                if "vertical" in current_description or "vertical" in next_description:
                    rotation_axis = "x"
                elif "girar" in current_description or "girar" in next_description:
                    rotation_axis = "z"
                
                # Determina a cor de fundo com base no contexto
                background_color = [0, 0, 0]  # Preto padrão
                
                # Verifica o ambiente/cenário para escolher uma cor apropriada
                if any(word in current_description or word in next_description 
                       for word in ["céu", "nuvens", "ar", "voar"]):
                    background_color = [135, 206, 235]  # Azul céu
                elif any(word in current_description or word in next_description 
                         for word in ["mar", "oceano", "água", "rio", "lago"]):
                    background_color = [0, 105, 148]  # Azul marinho
                elif any(word in current_description or word in next_description 
                         for word in ["floresta", "jardim", "natureza", "campo"]):
                    background_color = [34, 139, 34]  # Verde floresta
                elif any(word in current_description or word in next_description 
                         for word in ["deserto", "areia", "quente", "sol"]):
                    background_color = [210, 180, 140]  # Bege/areia
                elif any(word in current_description or word in next_description 
                         for word in ["noite", "escuro", "estrelas", "lua"]):
                    background_color = [25, 25, 112]  # Azul escuro noturno
                
                return "rotate3d", {
                    "rotation_angle": 180,
                    "rotation_axis": rotation_axis,
                    "perspective": 0.0008,
                    "acceleration": "ease-in-out",
                    "background_color": background_color
                }
        
        # 4. Verifica transição de morphing (para transformações ou mudanças mágicas)
        for keyword in morph_keywords:
            if keyword in current_description or keyword in next_description:
                # Determina a qualidade do morph com base no contexto
                morph_quality = "high"  # Padrão para alta qualidade
                
                # Determina o número de frames de blend com base na complexidade
                blend_frames = 12  # Padrão
                
                # Se for uma transformação complexa ou detalhada, aumenta a qualidade
                if any(word in current_description or word in next_description 
                       for word in ["complexo", "detalhado", "elaborado", "sutil"]):
                    morph_quality = "ultra"
                    blend_frames = 16
                
                # Determina se deve usar suavização de bordas
                smooth_edges = any(word in current_description or word in next_description 
                                  for word in ["suave", "fluido", "líquido", "água", "névoa"])
                
                # Determina o método de fluxo com base no contexto
                flow_method = "farneback"  # Método padrão
                
                # Para transformações mais rápidas ou abruptas
                if any(word in current_description or word in next_description 
                       for word in ["rápido", "abrupto", "instantâneo", "explosão"]):
                    flow_method = "tvl1"
                    blend_frames = max(8, blend_frames - 4)  # Reduz um pouco os frames para parecer mais rápido
                
                return "morph", {
                    "morph_quality": morph_quality,
                    "blend_frames": blend_frames,
                    "smooth_edges": smooth_edges,
                    "flow_method": flow_method
                }
        
        # 5. Para mudanças drásticas de emoção, usa wipe
        if emotion_change:
            # Determina a direção do wipe baseado na mudança de emoção
            direction = "right"  # Direção padrão
            
            # Usa a análise de tom emocional para determinar a direção
            if current_tone["primary_tone"] and next_tone["primary_tone"]:
                # Mapeamento de direções baseado em mudanças de tom emocional
                emotion_direction_map = {
                    ("alegre", "triste"): "down",      # Felicidade para tristeza: movimento para baixo
                    ("triste", "alegre"): "up",        # Tristeza para felicidade: movimento para cima
                    ("calmo", "tenso"): "right",      # Calma para tensão: movimento para a direita (avanço)
                    ("tenso", "calmo"): "left",       # Tensão para calma: movimento para a esquerda (retorno)
                    ("amor", "raiva"): "right",       # Amor para raiva: movimento para a direita (avanço)
                    ("raiva", "amor"): "left",        # Raiva para amor: movimento para a esquerda (retorno)
                    ("medo", "coragem"): "up",        # Medo para coragem: movimento para cima
                    ("coragem", "medo"): "down",      # Coragem para medo: movimento para baixo
                    ("surpresa", "calmo"): "left",    # Surpresa para calma: movimento para a esquerda (retorno)
                    ("calmo", "surpresa"): "right",   # Calma para surpresa: movimento para a direita (avanço)
                }
                
                # Verifica se a combinação de emoções está no mapeamento
                emotion_pair = (current_tone["primary_tone"], next_tone["primary_tone"])
                if emotion_pair in emotion_direction_map:
                    direction = emotion_direction_map[emotion_pair]
                    logger.debug(f"Direção de wipe determinada pelo tom emocional: {direction}")
            
            # Caso não tenha encontrado uma direção pelo tom emocional, analisa o contexto
            if direction == "right":
                if any(word in current_description for word in ["esquerda", "oeste", "retornar", "voltar"]):
                    direction = "left"
                elif any(word in current_description for word in ["acima", "céu", "subir", "topo"]):
                    direction = "up"
                elif any(word in current_description for word in ["abaixo", "chão", "descer", "fundo"]):
                    direction = "down"
            
            # Determina a suavidade da borda com base no contexto e tom emocional
            edge_softness = 15  # Valor padrão
            
            # Usa a intensidade do tom emocional para ajustar a suavidade
            if current_tone["intensity"] > 0.7 or next_tone["intensity"] > 0.7:
                # Alta intensidade emocional = bordas mais nítidas
                edge_softness = max(5, int(15 - (max(current_tone["intensity"], next_tone["intensity"]) - 0.5) * 20))
                logger.debug(f"Borda ajustada para mais nítida devido à alta intensidade emocional: {edge_softness}")
            elif current_tone["intensity"] < 0.3 and next_tone["intensity"] < 0.3:
                # Baixa intensidade emocional = bordas mais suaves
                edge_softness = min(30, int(15 + (0.5 - min(current_tone["intensity"], next_tone["intensity"])) * 30))
                logger.debug(f"Borda ajustada para mais suave devido à baixa intensidade emocional: {edge_softness}")
            
            # Para transições mais duras ou abruptas (verificação adicional pelo tom emocional)
            if current_tone["primary_tone"] in ["raiva", "medo", "surpresa"] or next_tone["primary_tone"] in ["raiva", "medo", "surpresa"]:
                edge_softness = min(edge_softness, 10)  # Garante uma borda mais nítida para emoções intensas
            
            # Para transições mais suaves (verificação adicional pelo tom emocional)
            elif current_tone["primary_tone"] in ["calmo", "amor"] or next_tone["primary_tone"] in ["calmo", "amor"]:
                edge_softness = max(edge_softness, 20)  # Garante uma borda mais suave para emoções calmas
            
            # Determina a curva de aceleração com base na intensidade da mudança emocional
            acceleration = "linear"  # Padrão
            
            # Usa o tom emocional para determinar a aceleração
            if current_tone["primary_tone"] and next_tone["primary_tone"]:
                # Para mudanças de emoções positivas para negativas (desacelera no final)
                if current_tone["primary_tone"] in ["alegre", "calmo", "amor"] and \
                   next_tone["primary_tone"] in ["triste", "raiva", "medo"]:
                    acceleration = "ease-out"
                    logger.debug(f"Aceleração ajustada para ease-out (positivo->negativo)")
                
                # Para mudanças de emoções negativas para positivas (acelera no início)
                elif current_tone["primary_tone"] in ["triste", "raiva", "medo"] and \
                     next_tone["primary_tone"] in ["alegre", "calmo", "amor"]:
                    acceleration = "ease-in"
                    logger.debug(f"Aceleração ajustada para ease-in (negativo->positivo)")
                
                # Para mudanças drásticas ou surpresas (aceleração no início e desaceleração no final)
                elif "surpresa" in [current_tone["primary_tone"], next_tone["primary_tone"]] or \
                     (current_tone["intensity"] > 0.7 and next_tone["intensity"] > 0.7):
                    acceleration = "ease-in-out"
                    logger.debug(f"Aceleração ajustada para ease-in-out (mudança drástica)")
            
            # Verificação adicional usando os campos de emoção do roteiro
            if acceleration == "linear" and current_emotion and next_emotion:
                # Para mudanças de emoções positivas para negativas (desacelera no final)
                if any(word in current_emotion for word in ["feliz", "alegre", "contente"]) and \
                   any(word in next_emotion for word in ["triste", "melancólico", "deprimido"]):
                    acceleration = "ease-out"
                
                # Para mudanças de emoções negativas para positivas (acelera no início)
                elif any(word in current_emotion for word in ["triste", "melancólico", "deprimido"]) and \
                     any(word in next_emotion for word in ["feliz", "alegre", "contente"]):
                    acceleration = "ease-in"
            
            return f"wipe_{direction}", {
                "edge_softness": edge_softness,
                "acceleration": acceleration
            }
        
        # 6. Para mudanças de local, usa fade
        if location_change:
            # Determina a cor do fade com base no contexto dos locais e tom emocional
            fade_color = [0, 0, 0]  # Preto padrão
            
            # Primeiro, verifica o tom emocional da próxima cena para influenciar a cor
            if next_tone["primary_tone"]:
                # Mapeamento de cores emocionais
                emotion_color_map = {
                    "alegre": [255, 223, 0],      # Amarelo brilhante para alegria
                    "triste": [65, 105, 225],    # Azul royal para tristeza
                    "tenso": [139, 0, 0],        # Vermelho escuro para tensão
                    "calmo": [176, 224, 230],    # Azul claro para calma
                    "raiva": [178, 34, 34],      # Vermelho firebrick para raiva
                    "surpresa": [147, 112, 219],  # Roxo médio para surpresa
                    "medo": [47, 79, 79],        # Cinza ardosia escuro para medo
                    "amor": [255, 105, 180],     # Rosa quente para amor
                    "aventura": [255, 140, 0],    # Laranja escuro para aventura
                    "mistério": [72, 61, 139],    # Azul ardosia escuro para mistério
                    "mágico": [138, 43, 226]     # Violeta para mágico
                }
                
                # Se o tom emocional está no mapeamento, usa a cor correspondente
                if next_tone["primary_tone"] in emotion_color_map:
                    fade_color = emotion_color_map[next_tone["primary_tone"]]
                    logger.debug(f"Cor de fade baseada no tom emocional '{next_tone['primary_tone']}': {fade_color}")
            
            # Em seguida, verifica o ambiente para ajustar ou sobrescrever a cor emocional
            # Prioriza o ambiente sobre a emoção para mudanças de local
            
            # Analisa o ambiente para determinar uma cor contextual para o fade
            if any(word in next_setting for word in ["céu", "nuvens", "ar livre", "exterior", "dia"]):
                fade_color = [255, 255, 255]  # Branco para cenas externas/dia
                logger.debug("Cor de fade ajustada para branco (cena externa/dia)")
            
            elif any(word in next_setting for word in ["mar", "oceano", "praia", "lago", "rio"]):
                fade_color = [0, 105, 148]  # Azul para cenas aquáticas
                logger.debug("Cor de fade ajustada para azul (cena aquática)")
            
            elif any(word in next_setting for word in ["floresta", "selva", "bosque", "parque", "natureza"]):
                fade_color = [34, 139, 34]  # Verde para cenas na natureza
                logger.debug("Cor de fade ajustada para verde (cena de natureza)")
            
            elif any(word in next_setting for word in ["deserto", "areia", "savana", "quente"]):
                fade_color = [210, 180, 140]  # Bege/areia para cenas de deserto
                logger.debug("Cor de fade ajustada para bege (cena de deserto)")
            
            elif any(word in next_setting for word in ["noite", "escuro", "lua", "estrelas"]):
                fade_color = [25, 25, 112]  # Azul escuro para cenas noturnas
                logger.debug("Cor de fade ajustada para azul escuro (cena noturna)")
            
            elif any(word in next_setting for word in ["neve", "gelo", "frio", "inverno", "polar"]):
                fade_color = [240, 248, 255]  # Branco azulado para cenas de inverno
                logger.debug("Cor de fade ajustada para branco azulado (cena de inverno)")
            
            # Determina a curva de opacidade com base na intensidade emocional e mudança de local
            opacity_curve = "linear"  # Padrão
            
            # Usa a intensidade emocional para determinar a curva de opacidade
            if next_tone["intensity"] > 0.7:
                # Alta intensidade emocional = transição mais rápida no início
                opacity_curve = "ease-in"
                logger.debug("Curva de opacidade ajustada para ease-in (alta intensidade emocional)")
            elif next_tone["intensity"] < 0.3:
                # Baixa intensidade emocional = transição mais suave no final
                opacity_curve = "ease-out"
                logger.debug("Curva de opacidade ajustada para ease-out (baixa intensidade emocional)")
            
            # Para mudanças de local mais dramáticas ou abruptas
            if current_setting and next_setting:
                # Verifica se são ambientes muito diferentes (interior/exterior, etc)
                interior_keywords = ["casa", "sala", "quarto", "interior", "dentro"]
                exterior_keywords = ["rua", "exterior", "fora", "campo", "ar livre"]
                
                # Mudança de interior para exterior (acelera no início)
                if any(word in current_setting for word in interior_keywords) and \
                   any(word in next_setting for word in exterior_keywords):
                    opacity_curve = "ease-in"
                
                # Mudança de exterior para interior (desacelera no final)
                elif any(word in current_setting for word in exterior_keywords) and \
                     any(word in next_setting for word in interior_keywords):
                    opacity_curve = "ease-out"
            
            return "fade", {
                "fade_color": fade_color,
                "opacity_curve": opacity_curve
            }
        
        # 7. Caso padrão: escolhe aleatoriamente entre as transições disponíveis
        transition_types = ["fade", "wipe_right", "zoom", "morph", "rotate3d", "page_turn"]
        weights = [0.3, 0.2, 0.15, 0.15, 0.1, 0.1]  # Pesos para cada tipo de transição
        
        # Ajusta os pesos com base no contexto das cenas
        # Se houver menção a livros ou histórias, aumenta o peso da transição page_turn
        if any(word in current_description or word in next_description 
               for word in ["livro", "história", "conto", "fábula", "leitura"]):
            weights[5] = 0.3  # Aumenta o peso do page_turn
            weights[0] = 0.2  # Reduz o peso do fade
        
        # Se houver menção a magia ou transformação, aumenta o peso do morph
        if any(word in current_description or word in next_description 
               for word in ["magia", "feitiço", "transformação", "mudança"]):
            weights[3] = 0.3  # Aumenta o peso do morph
            weights[1] = 0.1  # Reduz o peso do wipe
        
        # Se houver menção a movimento ou foco, aumenta o peso do zoom
        if any(word in current_description or word in next_description 
               for word in ["foco", "detalhe", "aproximar", "afastar", "movimento"]):
            weights[2] = 0.3  # Aumenta o peso do zoom
            weights[4] = 0.05  # Reduz o peso do rotate3d
        
        selected_transition = random.choices(transition_types, weights=weights, k=1)[0]
        
        # Define parâmetros padrão para a transição selecionada
        if selected_transition == "fade":
            # Determina a cor do fade com base no contexto
            fade_color = [0, 0, 0]  # Preto padrão
            
            # Verifica o ambiente/cenário para escolher uma cor apropriada
            if any(word in current_description or word in next_description 
                   for word in ["céu", "nuvens", "dia", "luz", "brilho"]):
                fade_color = [255, 255, 255]  # Branco para cenas luminosas
            
            params = {
                "fade_color": fade_color,
                "opacity_curve": "linear"  # Curva de opacidade padrão
            }
            
        elif selected_transition.startswith("wipe"):
            # Determina a suavidade da borda com base no contexto
            edge_softness = 10  # Valor padrão
            
            # Para transições mais suaves
            if any(word in current_description or word in next_description 
                   for word in ["suave", "gentil", "delicado", "calmo"]):
                edge_softness = 20
            
            # Para transições mais abruptas
            elif any(word in current_description or word in next_description 
                     for word in ["abrupto", "rápido", "brusco", "repentino"]):
                edge_softness = 5
            
            params = {
                "edge_softness": edge_softness,
                "acceleration": "linear"  # Aceleração padrão
            }
            
        elif selected_transition == "zoom":
            # Determina a direção do zoom com base no contexto
            zoom_direction = "in"  # Padrão
            
            if any(word in current_description for word in ["afastar", "distante", "longe", "amplo"]) or \
               any(word in next_description for word in ["panorama", "paisagem", "vista", "amplo"]):
                zoom_direction = "out"
            
            # Determina o ponto focal com base no contexto
            focus_point = "center"  # Padrão
            
            if any(word in current_description or word in next_description 
                   for word in ["acima", "topo", "céu", "alto"]):
                focus_point = "top"
            elif any(word in current_description or word in next_description 
                     for word in ["abaixo", "chão", "baixo", "base"]):
                focus_point = "bottom"
            
            params = {
                "zoom_factor": 1.5,
                "zoom_direction": zoom_direction,
                "focus_point": focus_point,
                "acceleration": "ease-in-out",
                "use_advanced": True
            }
            
        elif selected_transition == "morph":
            # Determina a qualidade do morph com base no contexto
            morph_quality = "medium"  # Padrão
            
            # Para cenas mais importantes ou detalhadas
            if any(word in current_description or word in next_description 
                   for word in ["importante", "crucial", "detalhado", "complexo"]):
                morph_quality = "high"
            
            params = {
                "morph_quality": morph_quality, 
                "blend_frames": 8,
                "smooth_edges": False,
                "flow_method": "farneback"
            }
            
        elif selected_transition == "rotate3d":
            # Determina o eixo de rotação com base no contexto
            rotation_axis = "y"  # Padrão (horizontal)
            
            if any(word in current_description or word in next_description 
                   for word in ["vertical", "cima", "baixo", "altura"]):
                rotation_axis = "x"
            elif any(word in current_description or word in next_description 
                     for word in ["girar", "rotação", "espiral", "círculo"]):
                rotation_axis = "z"
            
            # Determina a cor de fundo com base no contexto
            background_color = [0, 0, 0]  # Preto padrão
            
            params = {
                "rotation_angle": 180,
                "rotation_axis": rotation_axis,
                "perspective": 0.0008,
                "acceleration": "ease-in-out",
                "background_color": background_color
            }
            
        elif selected_transition == "page_turn":
            # Determina a direção da virada de página com base no contexto
            turn_direction = "left-to-right"  # Padrão
            
            # Para idiomas que leem da direita para a esquerda ou menções a voltar página
            if any(word in current_description or word in next_description 
                   for word in ["voltar", "anterior", "retornar", "esquerda"]):
                turn_direction = "right-to-left"
            
            # Cor da página padrão (branco off-white)
            page_color = [255, 250, 240]
            
            params = {
                "turn_direction": turn_direction,
                "shadow_intensity": 0.5,
                "page_curve": 0.3,
                "acceleration": "ease-in-out",
                "page_color": page_color,
                "texture_effect": False
            }
        
        return selected_transition, params
    
    def create_final_video(self, animations_dir: str, audio_dir: str, output_dir: str) -> Optional[str]:
        """
        Cria o vídeo final combinando todas as cenas.
        
        Args:
            animations_dir: Diretório contendo as animações
            audio_dir: Diretório contendo os áudios
            output_dir: Diretório para salvar o vídeo final
            
        Returns:
            Caminho para o vídeo final ou None em caso de falha
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi carregado. Execute load_script() primeiro.")
        
        # Verifica se o FFmpeg está disponível
        import shutil
        ffmpeg_available = shutil.which('ffmpeg') is not None
        if not ffmpeg_available:
            try:
                # Tenta usar o ffmpeg do ambiente conda
                conda_ffmpeg = os.path.join(os.environ.get('CONDA_PREFIX', ''), 'bin', 'ffmpeg')
                ffmpeg_available = os.path.exists(conda_ffmpeg)
                if ffmpeg_available:
                    os.environ['PATH'] = os.environ['PATH'] + os.pathsep + os.path.dirname(conda_ffmpeg)
                    print(f"FFmpeg encontrado em {conda_ffmpeg}")
                else:
                    print("FFmpeg não encontrado no ambiente Conda")
            except Exception as e:
                print(f"Erro ao verificar FFmpeg no Conda: {str(e)}")
        
        if ffmpeg_available:
            print("FFmpeg disponível. Criando vídeos reais.")
        else:
            print("FFmpeg não disponível. Alguns vídeos podem ser simulados.")
        
        # Carrega os metadados das animações
        animation_metadata_path = os.path.join(animations_dir, 'extended', 'extended_animation_metadata.json')
        if os.path.exists(animation_metadata_path):
            animation_metadata = self.load_animation_metadata(animation_metadata_path)
        else:
            raise FileNotFoundError(f"Metadados de animações estendidas não encontrados em {animation_metadata_path}")
        
        # Carrega os metadados dos áudios
        audio_metadata_path = os.path.join(audio_dir, 'all_audio_metadata.json')
        if os.path.exists(audio_metadata_path):
            audio_metadata = self.load_audio_metadata(audio_metadata_path)
        else:
            raise FileNotFoundError(f"Metadados de áudios não encontrados em {audio_metadata_path}")
        
        print("Criando vídeos para cada cena...")
        
        # Cria o diretório para vídeos de cenas
        scenes_dir = os.path.join(output_dir, 'scenes')
        os.makedirs(scenes_dir, exist_ok=True)
        
        # Cria vídeos para cada cena
        scene_videos = {}
        for scene in self.script:
            scene_number = scene.get('scene_number')
            
            # Obtém o caminho da animação estendida
            animation_filename = animation_metadata.get('extended_animations', {}).get(str(scene_number))
            if not animation_filename:
                print(f"Animação estendida para Cena {scene_number} não encontrada nos metadados.")
                continue
            
            # Remove o prefixo "[Simulado] " se existir
            if animation_filename.startswith('[Simulado] '):
                animation_path = animation_filename
            else:
                animation_path = os.path.join(animations_dir, 'extended', animation_filename)
                if not os.path.exists(animation_path):
                    print(f"Arquivo de animação não encontrado: {animation_path}")
                    continue
            
            # Obtém os metadados de áudio para esta cena
            scene_audio_metadata = audio_metadata.get(str(scene_number), {})
            scene_audio_metadata['narration_dir'] = os.path.join(audio_dir, 'narration')
            
            # Cria o vídeo para esta cena
            scene_video_path = self._create_scene_video(scene_number, animation_path, scene_audio_metadata, scenes_dir)
            if scene_video_path:
                scene_videos[scene_number] = scene_video_path
        
        print(f"Vídeos criados para {len(scene_videos)} cenas. Combinando em vídeo final...")
        
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips, ImageClip
            
            # Verifica se temos pelo menos uma cena
            if not scene_videos:
                print("Nenhum vídeo de cena foi criado. Não é possível criar o vídeo final.")
                return None
            
            # Verifica se estamos em modo de simulação
            all_simulated = all(path.startswith('[Simulado]') for path in scene_videos.values())
            some_simulated = any(path.startswith('[Simulado]') for path in scene_videos.values())
            
            # Se todos os vídeos são simulados e o FFmpeg não está disponível
            if all_simulated and not ffmpeg_available:
                print("Todos os vídeos de cena são simulados e FFmpeg não disponível. Gerando vídeo final simulado.")
                return "[Simulado] video_final.mp4"
            
            # Se alguns vídeos são simulados mas o FFmpeg está disponível, podemos criar um vídeo real
            # usando imagens estáticas para as cenas simuladas
            if some_simulated and ffmpeg_available:
                print("Alguns vídeos são simulados, mas FFmpeg está disponível. Criando vídeo real com imagens estáticas.")
                
                # Substitui os vídeos simulados por clips de imagens estáticas
                for scene_number, path in list(scene_videos.items()):
                    if path.startswith('[Simulado]'):
                        # Procura por uma imagem estática correspondente
                        scene_image_path = os.path.join(os.path.dirname(os.path.dirname(output_dir)), 
                                                     'images', 'scenes', f'scene_{scene_number:03d}.png')
                        
                        if os.path.exists(scene_image_path):
                            # Cria um vídeo real a partir da imagem estática
                            temp_video_path = os.path.join(scenes_dir, f"temp_scene_{scene_number:03d}.mp4")
                            
                            # Cria um clip de imagem com duração fixa
                            img_clip = ImageClip(scene_image_path).set_duration(self.video_settings['scene_duration'])
                            
                            # Salva como vídeo
                            img_clip.write_videofile(
                                temp_video_path,
                                codec='libx264',
                                audio=None,
                                fps=self.video_settings['fps']
                            )
                            
                            # Atualiza o caminho no dicionário
                            scene_videos[scene_number] = temp_video_path
                            print(f"Criado vídeo real para cena {scene_number} a partir de imagem estática")
            
            # Se ainda temos vídeos simulados, retorna um vídeo final simulado
            if any(path.startswith('[Simulado]') for path in scene_videos.values()):
                print("Ainda existem vídeos de cena simulados. Gerando vídeo final simulado.")
                return "[Simulado] video_final.mp4"
            
            # Ordena as cenas por número
            sorted_scenes = sorted(scene_videos.items(), key=lambda x: x[0])
            
            # Carrega os clips de vídeo
            video_clips = []
            for scene_number, scene_path in sorted_scenes:
                clip = VideoFileClip(scene_path)
                video_clips.append(clip)
            
            # Combina os clips com transições
            final_clip = video_clips[0]
            transition_duration = self.video_settings['transition_duration']
            
            for i in range(1, len(video_clips)):
                # Obtém as cenas atual e próxima do script para análise contextual
                current_scene = self.script[i-1] if i-1 < len(self.script) else None
                next_scene = self.script[i] if i < len(self.script) else None
                
                # Se temos ambas as cenas, seleciona a transição com base no contexto
                if current_scene and next_scene:
                    # Seleciona automaticamente a transição mais apropriada
                    transition_type, transition_params = self._select_transition_for_scenes(current_scene, next_scene)
                    
                    # Verifica se é um conteúdo infantil para ajustar a transição
                    is_children_content = False
                    
                    # Verifica se há menção a conteúdo infantil nas cenas
                    children_keywords = ["criança", "infantil", "bebê", "menino", "menina", "escola", 
                                        "brinquedo", "desenho", "colorido", "fábula", "conto de fadas"]
                    
                    if any(keyword in str(current_scene).lower() or keyword in str(next_scene).lower() 
                           for keyword in children_keywords):
                        is_children_content = True
                    
                    # Ajusta a transição para conteúdo infantil
                    if is_children_content:
                        # Prefere transições mais suaves, coloridas e lúdicas para crianças
                        if transition_type == "fade":
                            # Usa cores mais vivas para fades em conteúdo infantil
                            bright_colors = [
                                [255, 192, 203],  # Rosa
                                [135, 206, 235],  # Azul céu
                                [152, 251, 152],  # Verde claro
                                [255, 215, 0],    # Amarelo ouro
                                [255, 165, 0],    # Laranja
                                [186, 85, 211],   # Roxo médio
                                [64, 224, 208],   # Turquesa
                                [240, 128, 128]   # Coral claro
                            ]
                            transition_params["fade_color"] = random.choice(bright_colors)
                            
                            # Curva de opacidade mais suave e divertida para crianças
                            transition_params["opacity_curve"] = "bounce"
                        
                        elif transition_type.startswith("wipe"):
                            # Bordas mais suaves para wipes em conteúdo infantil
                            transition_params["edge_softness"] = max(20, transition_params.get("edge_softness", 15))
                            
                            # Adiciona efeito de ondulação para wipes em conteúdo infantil
                            transition_params["wave_effect"] = True
                            transition_params["wave_amplitude"] = 10
                            transition_params["wave_frequency"] = 5
                        
                        elif transition_type == "page_turn":
                            # Ativa o efeito de textura para page_turn em conteúdo infantil
                            transition_params["texture_effect"] = True
                            
                            # Usa cores mais vivas para a página
                            bright_page_colors = [
                                [255, 182, 193],  # Rosa claro
                                [173, 216, 230],  # Azul claro
                                [152, 251, 152],  # Verde claro
                                [255, 218, 185],  # Pêssego
                                [221, 160, 221],  # Lavanda
                                [255, 250, 205],  # Amarelo claro
                                [175, 238, 238],  # Azul turquesa pálido
                                [255, 228, 225]   # Misty rose
                            ]
                            transition_params["page_color"] = random.choice(bright_page_colors)
                            
                            # Adiciona efeito de brilho para page_turn em conteúdo infantil
                            transition_params["sparkle_effect"] = True
                        
                        elif transition_type == "zoom":
                            # Torna o zoom mais divertido para conteúdo infantil
                            transition_params["bounce_effect"] = True
                            
                            # Adiciona um leve efeito de rotação durante o zoom para conteúdo infantil
                            if not transition_params.get("rotation_angle"):
                                transition_params["rotation_angle"] = random.choice([-10, 10])
                        
                        elif transition_type == "rotate3d":
                            # Adiciona cores de fundo mais vivas para rotate3d em conteúdo infantil
                            bright_bg_colors = [
                                [255, 192, 203],  # Rosa
                                [135, 206, 235],  # Azul céu
                                [152, 251, 152],  # Verde claro
                                [255, 215, 0],    # Amarelo ouro
                                [255, 165, 0]     # Laranja
                            ]
                            transition_params["background_color"] = random.choice(bright_bg_colors)
                            
                            # Adiciona efeito de confete para rotate3d em conteúdo infantil
                            transition_params["confetti_effect"] = True
                        
                        elif transition_type == "morph":
                            # Torna o morph mais suave e colorido para conteúdo infantil
                            transition_params["smooth_edges"] = True
                            transition_params["color_shift"] = True
                    
                    logger.info(f"Selecionada transição contextual '{transition_type}' entre cenas {i-1} e {i}")
                    logger.debug(f"Parâmetros da transição: {transition_params}")
                    
                    # Registra se é conteúdo infantil
                    if is_children_content:
                        logger.info(f"Transição otimizada para conteúdo infantil")
                else:
                    # Fallback para transição padrão se não temos informações de contexto
                    transition_type = "fade"
                    transition_params = {}
                    logger.info(f"Usando transição padrão 'fade' entre cenas {i-1} e {i}")
                
                # Salva o checkpoint antes de adicionar a transição
                self._save_checkpoint(f"adding_transition_{i}", {
                    "transition_type": transition_type,
                    "transition_params": transition_params,
                    "scene_index": i
                })
                
                # Aplica a transição com os parâmetros específicos
                final_clip = self._add_transition(
                    final_clip, 
                    video_clips[i], 
                    transition_duration, 
                    transition_type,
                    **transition_params  # Passa os parâmetros específicos para esta transição
                )
                
                # Salva checkpoint após adicionar a transição
                self._save_checkpoint(f"transition_added_{i}", {
                    "transition_type": transition_type,
                    "transition_params": transition_params,
                    "scene_index": i,
                    "completed": True
                })
            
            # Salva o vídeo final
            os.makedirs(output_dir, exist_ok=True)
            final_path = os.path.join(output_dir, "video_final.mp4")
            temp_final_path = os.path.join(output_dir, "temp_video_final.mp4")
            
            # Salva o checkpoint antes de renderizar o vídeo final
            self._save_checkpoint("final_video_rendering_started", {
                "output_path": final_path,
                "started_at": time.time()
            })
            
            # Primeiro passo: renderiza com MoviePy
            logger.info("Renderizando vídeo final (primeira passagem)...")
            final_clip.write_videofile(
                temp_final_path,
                codec='libx264',
                audio_codec='aac',
                fps=self.video_settings['fps']
            )
            
            # Segundo passo: otimiza com FFmpeg para melhor qualidade
            if ffmpeg_available:
                logger.info("Aplicando otimizações finais com FFmpeg...")
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_final_path,
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',  # Alta qualidade de vídeo
                    '-c:a', 'aac', '-b:a', '192k',  # Alta qualidade de áudio
                    '-pix_fmt', 'yuv420p',  # Compatível com a maioria dos players
                    '-movflags', '+faststart',  # Otimiza para streaming
                    '-metadata', f'title="{os.path.basename(final_path).split(".")[0]}"',
                    '-metadata', 'comment="Gerado automaticamente pelo sistema de animação"',
                    final_path
                ]
                
                try:
                    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                    # Remove o arquivo temporário
                    if os.path.exists(temp_final_path):
                        os.remove(temp_final_path)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Erro ao processar vídeo final com FFmpeg: {e.stderr.decode() if e.stderr else str(e)}")
                    # Se falhar, usa o arquivo temporário como saída
                    if os.path.exists(temp_final_path):
                        shutil.move(temp_final_path, final_path)
            else:
                # Se FFmpeg não estiver disponível, usa o arquivo temporário como final
                shutil.move(temp_final_path, final_path)
            
            # Fecha os clips para liberar recursos
            final_clip.close()
            for clip in video_clips:
                clip.close()
            
            # Salva o checkpoint após processar o vídeo final
            self._save_checkpoint("final_video_processed", {
                "output_path": final_path,
                "duration": final_clip.duration if hasattr(final_clip, 'duration') else None,
                "completed_at": time.time()
            })
            
            logger.info(f"Vídeo final salvo em: {final_path}")
            return final_path
            
        except Exception as e:
            logger.error(f"Erro ao criar vídeo final: {str(e)}")
            return None


# Exemplo de uso
if __name__ == "__main__":
    agent = VideoEditorAgent()
    
    # Carregar roteiro
    script_path = "../output/roteiro.json"
    if os.path.exists(script_path):
        agent.load_script(script_path)
        
        # Criar vídeo final
        animations_dir = "../output/animations"
        audio_dir = "../output/audio"
        output_dir = "../output/video"
        
        agent.create_final_video(animations_dir, audio_dir, output_dir)
    else:
        print(f"Erro: Roteiro não encontrado em {script_path}")
