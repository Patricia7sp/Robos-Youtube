#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Agente responsável pela geração de animações a partir de imagens estáticas.
Utiliza APIs de animação para criar movimentos fluidos e transições entre cenas.
"""

import os
import sys
import json
import time
import random
import requests
import logging
from typing import Dict, List, Tuple, Optional, Union, Any
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import numpy as np
import base64
from io import BytesIO
import tempfile
import shutil
import cv2
import math

# Bibliotecas para análise de imagens e detecção de objetos
try:
    import tensorflow as tf
    from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input, decode_predictions
    from tensorflow.keras.preprocessing import image as keras_image
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logging.warning("TensorFlow não disponível. Funcionalidades de análise de imagem serão limitadas.")

try:
    import torch
    import torchvision
    from torchvision.models import detection
    from torchvision.transforms import functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch não disponível. Funcionalidades de detecção de objetos serão limitadas.")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações das APIs de animação
STABILITY_API_BASE_URL = "https://api.stability.ai"
STABILITY_ANIMATION_ENDPOINT = "/v2beta/generation/image-to-animation"
RUNWAY_API_BASE_URL = "https://api.runwayml.com"
RUNWAY_ANIMATION_ENDPOINT = "/v1/animations"

class AnimationGeneratorAgent:
    """Agente responsável pela geração de animações a partir de imagens estáticas."""
    
    def __init__(self, api_key=None, api_provider="stability", cache_enabled=True):
        """Inicializa o agente de geração de animações.
        
        Args:
            api_key: Chave da API de animação
            api_provider: Provedor da API de animação (stability, runway, etc.)
            cache_enabled: Se o cache de animações deve ser habilitado
        """
        self.api_key = api_key
        self.api_provider = api_provider
        self.cache_enabled = cache_enabled
        
        # Diretório para cache de animações
        self.cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'cache', 'animations'
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Inicializa o cache
        self.animation_cache = {}
        self.animation_metadata = {}
        self._load_cache()
        
        logger.info(f"AnimationGeneratorAgent inicializado com provedor: {api_provider}")

    def _load_cache(self, output_dir=None):
        """Carrega o cache de animações do disco.
        
        Args:
            output_dir: Diretório opcional onde os metadados estão salvos. Se não for fornecido, usa self.cache_dir
            
        Returns:
            Dicionário com metadados de cache ou {} se não existir
        """
        # Se output_dir não for fornecido, usa o diretório de cache padrão
        cache_dir = output_dir if output_dir else self.cache_dir
        cache_path = os.path.join(cache_dir, 'animation_cache.json')
        metadata_path = os.path.join(cache_dir, 'animation_metadata.json')
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    self.animation_cache = json.load(f)
                logger.info(f"Cache de animações carregado: {len(self.animation_cache)} entradas")
            except Exception as e:
                logger.error(f"Erro ao carregar cache de animações: {str(e)}")
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.animation_metadata = json.load(f)
                logger.info(f"Metadados de animações carregados: {len(self.animation_metadata)} entradas")
            except Exception as e:
                logger.error(f"Erro ao carregar metadados de animações: {str(e)}")
    
    def _save_cache(self):
        """Salva o cache de animações no disco."""
        if not self.cache_enabled:
            return
            
        cache_path = os.path.join(self.cache_dir, 'animation_cache.json')
        metadata_path = os.path.join(self.cache_dir, 'animation_metadata.json')
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.animation_cache, f, ensure_ascii=False, indent=2)
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.animation_metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cache de animações salvo: {len(self.animation_cache)} entradas")
        except Exception as e:
            logger.error(f"Erro ao salvar cache de animações: {str(e)}")
    
    def analyze_image_content(self, image_path, analysis_type="all"):
        """Analisa o conteúdo de uma imagem para identificar objetos, pessoas, cenários, etc.
        
        Args:
            image_path: Caminho para a imagem a ser analisada
            analysis_type: Tipo de análise a ser realizada ("objects", "scene", "colors", "all")
            
        Returns:
            Dict: Dicionário com os resultados da análise
        """
        logger.info(f"Analisando conteúdo da imagem: {os.path.basename(image_path)}")
        results = {
            "objects": [],
            "scene": None,
            "colors": [],
            "faces": 0,
            "dominant_objects": [],
            "image_type": None,  # "photo", "drawing", "cartoon", etc.
            "complexity": None,  # "simple", "medium", "complex"
            "brightness": None,  # "dark", "medium", "bright"
            "motion_potential": []  # objetos com potencial de movimento
        }
        
        try:
            # Carrega a imagem
            img = Image.open(image_path)
            img_cv = cv2.imread(image_path)
            
            # Análise de cores dominantes
            if analysis_type in ["colors", "all"]:
                results["colors"] = self._analyze_colors(img)
                results["brightness"] = self._analyze_brightness(img_cv)
            
            # Detecção de objetos
            if analysis_type in ["objects", "all"]:
                # Usa OpenCV para detecção básica de características
                results["objects"] = self._detect_basic_features(img_cv)
                
                # Identifica objetos dominantes
                if results["objects"]:
                    # Seleciona os 3 objetos com maior confiança
                    results["dominant_objects"] = sorted(
                        results["objects"], 
                        key=lambda x: x.get("confidence", 0), 
                        reverse=True
                    )[:3]
                
                # Detecção de faces
                results["faces"] = self._detect_faces(img_cv)
            
            # Análise de complexidade da imagem
            results["complexity"] = self._analyze_complexity(img_cv)
            
            # Determina o tipo de imagem
            results["image_type"] = self._determine_image_type(img_cv)
            
            # Identifica objetos com potencial de movimento
            results["motion_potential"] = self._identify_motion_potential(results["objects"])
            
            logger.info(f"Análise de imagem concluída: {len(results['objects'])} objetos identificados")
            return results
            
        except Exception as e:
            logger.error(f"Erro ao analisar imagem: {str(e)}")
            return results
    
    def _analyze_colors(self, img):
        """Analisa as cores dominantes na imagem."""
        # Redimensiona para acelerar o processamento
        img_small = img.resize((100, 100))
        # Converte para array numpy e reshape
        pixels = np.array(img_small).reshape(-1, 3)
        
        # Usa K-means para encontrar as cores dominantes
        try:
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=5, random_state=42)
            kmeans.fit(pixels)
            colors = kmeans.cluster_centers_.astype(int)
            # Conta a proporção de cada cor
            labels = kmeans.labels_
            counts = np.bincount(labels)
            # Retorna as cores e suas proporções
            color_info = []
            for i, color in enumerate(colors):
                proportion = counts[i] / float(len(labels))
                color_info.append({
                    "rgb": color.tolist(),
                    "hex": '#{:02x}{:02x}{:02x}'.format(color[0], color[1], color[2]),
                    "proportion": float(proportion)
                })
            return sorted(color_info, key=lambda x: x["proportion"], reverse=True)
        except Exception as e:
            logger.warning(f"Erro ao analisar cores: {str(e)}")
            # Fallback simples se sklearn não estiver disponível
            # Calcula a cor média
            avg_color = np.mean(pixels, axis=0).astype(int)
            return [{
                "rgb": avg_color.tolist(),
                "hex": '#{:02x}{:02x}{:02x}'.format(avg_color[0], avg_color[1], avg_color[2]),
                "proportion": 1.0
            }]
    
    def _analyze_brightness(self, img_cv):
        """Analisa o brilho médio da imagem."""
        try:
            # Converte para escala de cinza
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            # Calcula o brilho médio
            brightness = np.mean(gray)
            
            # Categoriza o brilho
            if brightness < 80:
                return "dark"
            elif brightness < 160:
                return "medium"
            else:
                return "bright"
        except Exception as e:
            logger.warning(f"Erro ao analisar brilho: {str(e)}")
            return "medium"
    
    def _detect_basic_features(self, img_cv):
        """Detecta características básicas usando OpenCV."""
        try:
            # Converte para escala de cinza
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Detecta bordas
            edges = cv2.Canny(gray, 100, 200)
            
            # Detecta contornos
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filtra contornos por tamanho
            height, width = img_cv.shape[:2]
            min_area = (width * height) * 0.01  # 1% da área da imagem
            
            objects = []
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if area > min_area:
                    x, y, w, h = cv2.boundingRect(contour)
                    objects.append({
                        "name": f"object_{i+1}",
                        "confidence": float(area / (width * height)),  # normalizado pela área da imagem
                        "position": {
                            "x": float(x + w/2) / width,
                            "y": float(y + h/2) / height,
                            "width": float(w) / width,
                            "height": float(h) / height
                        }
                    })
            return objects
        except Exception as e:
            logger.warning(f"Erro na detecção básica de características: {str(e)}")
            return []
    
    def _detect_faces(self, img_cv):
        """Detecta faces na imagem usando OpenCV."""
        try:
            # Carrega o classificador Haar Cascade para faces
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            
            # Converte para escala de cinza
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Detecta faces
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            return len(faces)
        except Exception as e:
            logger.warning(f"Erro na detecção de faces: {str(e)}")
            return 0
    
    def _analyze_complexity(self, img_cv):
        """Analisa a complexidade visual da imagem."""
        try:
            # Converte para escala de cinza
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Calcula o gradiente
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            # Magnitude do gradiente
            magnitude = np.sqrt(sobelx**2 + sobely**2)
            
            # Média da magnitude como medida de complexidade
            complexity_score = np.mean(magnitude)
            
            # Categoriza a complexidade
            if complexity_score < 20:
                return "simple"
            elif complexity_score < 40:
                return "medium"
            else:
                return "complex"
        except Exception as e:
            logger.warning(f"Erro ao analisar complexidade: {str(e)}")
            return "medium"
    
    def _determine_image_type(self, img_cv):
        """Determina se a imagem é uma foto, desenho, cartoon, etc."""
        try:
            # Converte para escala de cinza
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Calcula o histograma
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist.flatten() / hist.sum()  # normaliza
            
            # Calcula a entropia
            non_zero = hist[hist > 0]
            entropy = -np.sum(non_zero * np.log2(non_zero))
            
            # Calcula bordas
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.count_nonzero(edges) / float(edges.size)
            
            # Heurística para classificação
            if entropy > 7.0 and edge_density < 0.05:
                return "photo"
            elif entropy < 6.0 and edge_density > 0.1:
                return "cartoon"
            elif edge_density > 0.05:
                return "drawing"
            else:
                return "photo"
        except Exception as e:
            logger.warning(f"Erro ao determinar tipo de imagem: {str(e)}")
            return "photo"
    
    def _identify_motion_potential(self, objects):
        """Identifica objetos com potencial de movimento para animação."""
        # Categorias de objetos que geralmente têm movimento
        movable_categories = [
            'person', 'animal', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 
            'zebra', 'giraffe', 'car', 'bicycle', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 
            'boat', 'fish', 'butterfly', 'insect', 'ball', 'kite', 'frisbee'
        ]
        
        motion_objects = []
        for obj in objects:
            obj_name = obj["name"].lower()
            # Verifica se o objeto pertence a uma categoria com potencial de movimento
            for category in movable_categories:
                if category in obj_name:
                    motion_objects.append({
                        "name": obj["name"],
                        "position": obj.get("position", {"x": 0.5, "y": 0.5}),
                        "motion_type": self._suggest_motion_type(obj_name)
                    })
                    break
        
        return motion_objects
    
    def _suggest_motion_type(self, object_name):
        """Sugere um tipo de movimento com base no objeto."""
        # Mapeamento de objetos para tipos de movimento
        motion_mapping = {
            'person': 'walk',
            'child': 'bounce',
            'baby': 'wiggle',
            'bird': 'fly',
            'butterfly': 'flutter',
            'fish': 'swim',
            'car': 'drive',
            'bicycle': 'cycle',
            'motorcycle': 'ride',
            'airplane': 'fly',
            'boat': 'float',
            'ball': 'bounce',
            'kite': 'flutter',
            'dog': 'run',
            'cat': 'pounce',
            'horse': 'gallop',
            'leaf': 'float',
            'cloud': 'drift',
            'water': 'flow',
            'tree': 'sway',
            'flower': 'sway'
        }
        
        # Verifica correspondências parciais
        for key, motion in motion_mapping.items():
            if key in object_name:
                return motion
        
        # Movimento padrão para objetos não mapeados
        return "move"
    
    def detect_objects_tensorflow(self, image_path, confidence_threshold=0.5):
        """Detecta objetos em uma imagem usando TensorFlow e o modelo ResNet50.
        
        Args:
            image_path: Caminho para a imagem a ser analisada
            confidence_threshold: Limiar de confiança para detecção (0-1)
            
        Returns:
            List: Lista de objetos detectados com suas posições e confiança
        """
        try:
            # Importa TensorFlow e Keras
            import tensorflow as tf
            from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input, decode_predictions
            from tensorflow.keras.preprocessing import image as keras_image
            import numpy as np
            
            logger.info(f"Detectando objetos com TensorFlow em: {os.path.basename(image_path)}")
            
            # Carrega o modelo ResNet50 pré-treinado
            model = ResNet50(weights='imagenet')
            
            # Carrega e pré-processa a imagem
            img = keras_image.load_img(image_path, target_size=(224, 224))
            x = keras_image.img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)
            
            # Faz a predição
            preds = model.predict(x)
            results = decode_predictions(preds, top=10)[0]
            
            # Filtra resultados com base no limiar de confiança
            objects = []
            for i, (imagenet_id, label, score) in enumerate(results):
                if score >= confidence_threshold:
                    objects.append({
                        "name": label,
                        "confidence": float(score),
                        "position": {"x": 0.5, "y": 0.5, "width": 1.0, "height": 1.0}  # Posição aproximada
                    })
            
            logger.info(f"TensorFlow detectou {len(objects)} objetos com confiança >= {confidence_threshold}")
            return objects
            
        except ImportError as e:
            logger.warning(f"TensorFlow não está disponível: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erro na detecção de objetos com TensorFlow: {str(e)}")
            return []
    
    def detect_objects_pytorch(self, image_path, confidence_threshold=0.5):
        """Detecta objetos em uma imagem usando PyTorch e o modelo Faster R-CNN.
        
        Args:
            image_path: Caminho para a imagem a ser analisada
            confidence_threshold: Limiar de confiança para detecção (0-1)
            
        Returns:
            List: Lista de objetos detectados com suas posições e confiança
        """
        try:
            # Importa PyTorch e torchvision
            import torch
            import torchvision
            from torchvision.models.detection import fasterrcnn_resnet50_fpn
            from torchvision import transforms
            from PIL import Image
            
            logger.info(f"Detectando objetos com PyTorch em: {os.path.basename(image_path)}")
            
            # Verifica se CUDA está disponível
            device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
            
            # Carrega o modelo Faster R-CNN pré-treinado
            model = fasterrcnn_resnet50_fpn(pretrained=True)
            model.eval().to(device)
            
            # Classes do COCO dataset
            COCO_INSTANCE_CATEGORY_NAMES = [
                '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
                'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'N/A', 'stop sign',
                'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
                'elephant', 'bear', 'zebra', 'giraffe', 'N/A', 'backpack', 'umbrella', 'N/A', 'N/A',
                'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
                'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
                'bottle', 'N/A', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
                'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
                'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'N/A', 'dining table',
                'N/A', 'N/A', 'toilet', 'N/A', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
                'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'N/A', 'book',
                'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
            ]
            
            # Carrega e transforma a imagem
            img = Image.open(image_path).convert("RGB")
            transform = transforms.Compose([
                transforms.ToTensor()
            ])
            img_tensor = transform(img).to(device)
            
            # Faz a predição
            with torch.no_grad():
                prediction = model([img_tensor])
            
            # Processa os resultados
            objects = []
            img_width, img_height = img.size
            
            for i in range(len(prediction[0]['boxes'])):
                score = prediction[0]['scores'][i].item()
                if score >= confidence_threshold:
                    box = prediction[0]['boxes'][i].cpu().numpy()
                    label_id = prediction[0]['labels'][i].item()
                    label = COCO_INSTANCE_CATEGORY_NAMES[label_id]
                    
                    # Normaliza as coordenadas da caixa
                    x1, y1, x2, y2 = box
                    x_center = (x1 + x2) / 2 / img_width
                    y_center = (y1 + y2) / 2 / img_height
                    width = (x2 - x1) / img_width
                    height = (y2 - y1) / img_height
                    
                    objects.append({
                        "name": label,
                        "confidence": float(score),
                        "position": {
                            "x": float(x_center),
                            "y": float(y_center),
                            "width": float(width),
                            "height": float(height)
                        }
                    })
            
            logger.info(f"PyTorch detectou {len(objects)} objetos com confiança >= {confidence_threshold}")
            return objects
            
        except ImportError as e:
            logger.warning(f"PyTorch não está disponível: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erro na detecção de objetos com PyTorch: {str(e)}")
            return []
    
    def analyze_scene(self, image_path, confidence_threshold=0.3):
        """Analisa a cena da imagem para identificar o ambiente ou contexto.
        
        Args:
            image_path: Caminho para a imagem a ser analisada
            confidence_threshold: Limiar de confiança para classificação (0-1)
            
        Returns:
            Dict: Informações sobre a cena identificada
        """
        try:
            # Tenta usar TensorFlow para classificação de cena
            import tensorflow as tf
            from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input, decode_predictions
            from tensorflow.keras.preprocessing import image as keras_image
            import numpy as np
            
            logger.info(f"Analisando cena em: {os.path.basename(image_path)}")
            
            # Carrega o modelo ResNet50 pré-treinado
            model = ResNet50(weights='imagenet')
            
            # Carrega e pré-processa a imagem
            img = keras_image.load_img(image_path, target_size=(224, 224))
            x = keras_image.img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)
            
            # Faz a predição
            preds = model.predict(x)
            results = decode_predictions(preds, top=5)[0]
            
            # Categorias de cenas comuns
            scene_categories = [
                'beach', 'coast', 'seashore', 'sea', 'ocean', 'lake', 'river', 'water',
                'mountain', 'hill', 'valley', 'cliff', 'rock', 'cave',
                'forest', 'woodland', 'jungle', 'rainforest', 'woods',
                'field', 'meadow', 'grassland', 'pasture', 'plain',
                'desert', 'sand', 'dune',
                'city', 'town', 'street', 'building', 'house', 'apartment', 'office', 'tower',
                'room', 'classroom', 'kitchen', 'bedroom', 'bathroom', 'living_room', 'dining_room',
                'park', 'garden', 'playground',
                'sky', 'cloud', 'sunset', 'sunrise', 'night', 'day'
            ]
            
            # Identifica a cena
            scene_info = None
            for _, label, score in results:
                # Verifica se o label corresponde a uma categoria de cena
                for category in scene_categories:
                    if category in label.lower():
                        if scene_info is None or score > scene_info["confidence"]:
                            scene_info = {
                                "type": category,
                                "confidence": float(score),
                                "description": label
                            }
            
            # Se não encontrou uma cena específica, usa a classificação de maior confiança
            if scene_info is None and results and results[0][2] >= confidence_threshold:
                _, label, score = results[0]
                scene_info = {
                    "type": "other",
                    "confidence": float(score),
                    "description": label
                }
            
            if scene_info:
                logger.info(f"Cena identificada: {scene_info['description']} com confiança {scene_info['confidence']}")
                return scene_info
            else:
                logger.info("Nenhuma cena identificada com confiança suficiente")
                return {"type": "unknown", "confidence": 0.0, "description": "unknown"}
            
        except ImportError as e:
            logger.warning(f"TensorFlow não está disponível para análise de cena: {str(e)}")
            # Fallback para análise básica
            return {"type": "unknown", "confidence": 0.0, "description": "unknown"}
        except Exception as e:
            logger.error(f"Erro na análise de cena: {str(e)}")
            return {"type": "unknown", "confidence": 0.0, "description": "unknown"}
    
    def _select_best_animation_type(self, image_analysis, source_images):
        """Seleciona o melhor tipo de animação com base na análise das imagens.
        
        Args:
            image_analysis: Dicionário com análises de cada imagem
            source_images: Lista de caminhos para as imagens de origem
            
        Returns:
            str: Tipo de animação recomendado
        """
        # Tipos de animação disponíveis
        animation_types = {
            "morph": 0,      # Transformação suave entre imagens
            "zoom": 0,       # Zoom in/out em partes da imagem
            "pan": 0,        # Movimento panorâmico
            "fade": 0,       # Fade in/out entre imagens
            "slide": 0,      # Deslizamento de uma imagem para outra
            "bounce": 0,     # Movimento de salto para objetos
            "rotate": 0,     # Rotação de elementos
            "float": 0      # Movimento flutuante para objetos leves
        }
        
        # Se temos apenas uma imagem, preferimos zoom ou pan
        if len(source_images) == 1:
            animation_types["zoom"] += 5
            animation_types["pan"] += 4
            animation_types["rotate"] += 2
        # Se temos duas ou mais imagens, morph e fade são boas opções
        else:
            animation_types["morph"] += 3
            animation_types["fade"] += 2
            animation_types["slide"] += 1
        
        # Analisa o conteúdo das imagens para ajustar as pontuações
        for img_key, analysis in image_analysis.items():
            # Verifica se há objetos com potencial de movimento
            if analysis.get("motion_potential"):
                motion_objects = analysis["motion_potential"]
                # Se temos objetos com potencial de movimento, favorece animações dinâmicas
                if any(obj["motion_type"] == "bounce" for obj in motion_objects):
                    animation_types["bounce"] += 3
                if any(obj["motion_type"] in ["float", "flutter"] for obj in motion_objects):
                    animation_types["float"] += 3
                if any(obj["motion_type"] in ["fly", "swim"] for obj in motion_objects):
                    animation_types["pan"] += 2
            
            # Considera o tipo de imagem
            image_type = analysis.get("image_type")
            if image_type == "photo":
                animation_types["morph"] += 1
                animation_types["fade"] += 1
            elif image_type == "cartoon":
                animation_types["bounce"] += 2
                animation_types["float"] += 1
            elif image_type == "drawing":
                animation_types["zoom"] += 1
                animation_types["pan"] += 1
            
            # Considera a complexidade da imagem
            complexity = analysis.get("complexity")
            if complexity == "simple":
                animation_types["bounce"] += 1
                animation_types["rotate"] += 1
            elif complexity == "complex":
                animation_types["morph"] += 1
                animation_types["pan"] += 1
            
            # Considera o brilho da imagem
            brightness = analysis.get("brightness")
            if brightness == "dark":
                animation_types["fade"] += 1
            elif brightness == "bright":
                animation_types["zoom"] += 1
            
            # Considera a cena da imagem
            scene = analysis.get("scene")
            if scene:
                scene_type = scene.get("type")
                if scene_type in ["water", "ocean", "sea", "lake", "river"]:
                    animation_types["float"] += 2
                    animation_types["fade"] += 1
                elif scene_type in ["sky", "cloud"]:
                    animation_types["float"] += 2
                    animation_types["pan"] += 1
                elif scene_type in ["forest", "jungle", "woods"]:
                    animation_types["pan"] += 2
                elif scene_type in ["city", "street", "building"]:
                    animation_types["zoom"] += 2
                    animation_types["pan"] += 1
        
        # Seleciona o tipo de animação com maior pontuação
        best_animation = max(animation_types.items(), key=lambda x: x[1])
        logger.info(f"Pontuações de tipos de animação: {animation_types}")
        
        # Se a pontuação for muito baixa, usa morph como padrão
        if best_animation[1] <= 1:
            return "morph"
        
        return best_animation[0]
    
    def _optimize_animation_parameters(self, animation_type, image_analysis, params):
        """Otimiza os parâmetros da animação com base na análise das imagens.
        
        Args:
            animation_type: Tipo de animação selecionado
            image_analysis: Dicionário com análises de cada imagem
            params: Parâmetros originais da animação
            
        Returns:
            dict: Parâmetros otimizados
        """
        # Cria uma cópia dos parâmetros para não modificar o original
        optimized_params = params.copy() if params else {}
        
        # Parâmetros padrão para cada tipo de animação
        default_params = {
            "morph": {"smoothness": 0.5, "transition_frames": 15},
            "zoom": {"zoom_factor": 1.5, "zoom_center": (0.5, 0.5), "easing": "ease-in-out"},
            "pan": {"direction": "left-to-right", "speed": 0.5, "easing": "linear"},
            "fade": {"fade_duration": 0.3, "overlap": 0.2, "easing": "ease-in-out"},
            "slide": {"direction": "left", "speed": 0.5, "easing": "ease-out"},
            "bounce": {"height": 0.2, "speed": 0.6, "easing": "bounce"},
            "rotate": {"angle": 15, "speed": 0.5, "easing": "ease-in-out"},
            "float": {"amplitude": 0.1, "speed": 0.3, "easing": "sine-wave"}
        }
        
        # Aplica parâmetros padrão se não estiverem definidos
        if animation_type in default_params:
            for key, value in default_params[animation_type].items():
                if key not in optimized_params:
                    optimized_params[key] = value
        
        # Otimizações específicas para cada tipo de animação com base na análise
        if animation_type == "zoom":
            # Tenta encontrar o objeto principal para centralizar o zoom
            main_objects = []
            for img_key, analysis in image_analysis.items():
                if analysis.get("dominant_objects"):
                    main_objects.extend(analysis["dominant_objects"])
            
            if main_objects:
                # Usa o objeto mais confiante como centro do zoom
                main_object = max(main_objects, key=lambda x: x.get("confidence", 0))
                if "position" in main_object:
                    pos = main_object["position"]
                    optimized_params["zoom_center"] = (pos["x"], pos["y"])
        
        elif animation_type == "pan":
            # Determina a direção do pan com base na posição dos objetos
            left_objects = 0
            right_objects = 0
            top_objects = 0
            bottom_objects = 0
            
            for img_key, analysis in image_analysis.items():
                for obj in analysis.get("objects", []):
                    if "position" in obj:
                        pos = obj["position"]
                        if pos["x"] < 0.4:
                            left_objects += 1
                        elif pos["x"] > 0.6:
                            right_objects += 1
                        if pos["y"] < 0.4:
                            top_objects += 1
                        elif pos["y"] > 0.6:
                            bottom_objects += 1
            
            # Determina a direção com base na concentração de objetos
            if left_objects > right_objects and abs(left_objects - right_objects) > 2:
                optimized_params["direction"] = "left-to-right"
            elif right_objects > left_objects and abs(right_objects - left_objects) > 2:
                optimized_params["direction"] = "right-to-left"
            elif top_objects > bottom_objects and abs(top_objects - bottom_objects) > 2:
                optimized_params["direction"] = "top-to-bottom"
            elif bottom_objects > top_objects and abs(bottom_objects - top_objects) > 2:
                optimized_params["direction"] = "bottom-to-top"
        
        elif animation_type == "bounce" or animation_type == "float":
            # Ajusta a velocidade com base na complexidade da imagem
            avg_complexity = "medium"
            complexity_scores = {"simple": 0, "medium": 0, "complex": 0}
            
            for img_key, analysis in image_analysis.items():
                complexity = analysis.get("complexity", "medium")
                complexity_scores[complexity] += 1
            
            # Determina a complexidade média
            if complexity_scores["simple"] > complexity_scores["medium"] and complexity_scores["simple"] > complexity_scores["complex"]:
                avg_complexity = "simple"
            elif complexity_scores["complex"] > complexity_scores["medium"] and complexity_scores["complex"] > complexity_scores["simple"]:
                avg_complexity = "complex"
            
            # Ajusta a velocidade com base na complexidade
            if avg_complexity == "simple":
                optimized_params["speed"] = 0.7  # Mais rápido para imagens simples
            elif avg_complexity == "complex":
                optimized_params["speed"] = 0.4  # Mais lento para imagens complexas
        
        # Adiciona informações de análise aos parâmetros para uso posterior
        optimized_params["content_analysis"] = {
            "has_faces": any(analysis.get("faces", 0) > 0 for img_key, analysis in image_analysis.items()),
            "has_motion_objects": any(len(analysis.get("motion_potential", [])) > 0 for img_key, analysis in image_analysis.items()),
            "dominant_colors": [analysis.get("colors", [])[0] if analysis.get("colors") else None for img_key, analysis in image_analysis.items()],
            "avg_brightness": self._get_average_property(image_analysis, "brightness"),
            "avg_complexity": self._get_average_property(image_analysis, "complexity")
        }
        
        logger.info(f"Parâmetros otimizados para animação do tipo {animation_type}: {optimized_params}")
        return optimized_params
    
    def _get_average_property(self, image_analysis, property_name):
        """Calcula a propriedade média de todas as imagens analisadas.
        
        Args:
            image_analysis: Dicionário com análises de cada imagem
            property_name: Nome da propriedade a ser calculada
            
        Returns:
            str ou None: Valor médio da propriedade
        """
        property_values = {"dark": 0, "medium": 0, "bright": 0, "simple": 0, "complex": 0}
        count = 0
        
        for img_key, analysis in image_analysis.items():
            if property_name in analysis and analysis[property_name] in property_values:
                property_values[analysis[property_name]] += 1
                count += 1
        
        if count == 0:
            return None
        
        # Retorna o valor mais comum
        return max(property_values.items(), key=lambda x: x[1])[0]
    
    def _get_cache_key(self, source_images, animation_type, parameters):
        """Gera uma chave de cache para uma animação.
        
        Args:
            source_images: Lista de caminhos para as imagens de origem
            animation_type: Tipo de animação (zoom, pan, morph, etc.)
            parameters: Parâmetros adicionais para a animação
            
        Returns:
            String representando a chave de cache
        """
        # Cria uma representação única das imagens de origem
        image_hash = "_".join([os.path.basename(img) for img in source_images])
        
        # Cria uma representação dos parâmetros
        param_str = json.dumps(parameters, sort_keys=True)
        
        # Combina tudo em uma chave única
        key = f"{image_hash}_{animation_type}_{hash(param_str)}"
        return key
    
    def _stability_generate_animation(self, source_images, output_path, animation_type="morph", 
                                      duration=3.0, fps=24, seed=None, image_analysis=None, **kwargs):
        """Gera uma animação usando a API da Stability AI.
        
        Args:
            source_images: Lista de caminhos para as imagens de origem
            output_path: Caminho para salvar a animação gerada
            animation_type: Tipo de animação (morph, zoom, pan, etc.)
            duration: Duração da animação em segundos
            fps: Frames por segundo
            seed: Seed para consistência na geração
            image_analysis: Dicionário com análises das imagens de origem
            **kwargs: Parâmetros adicionais para a API
            
        Returns:
            bool: True se a animação foi gerada com sucesso, False caso contrário
        """
        logger.info(f"Gerando animação com Stability AI: {animation_type}")
        
        # Verifica se a chave da API está disponível
        if not self.api_key:
            logger.error("Chave da API da Stability AI não configurada")
            return False
        
        try:
            # Verifica se devemos usar a API real ou gerar localmente
            use_api = kwargs.get("use_api", True)
            
            if use_api:
                # Configuração da chamada à API
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                
                # Prepara as imagens para envio
                encoded_images = []
                for img_path in source_images:
                    with open(img_path, "rb") as img_file:
                        encoded_img = base64.b64encode(img_file.read()).decode('utf-8')
                        encoded_images.append(encoded_img)
                
                # Mapeia o tipo de animação para o formato esperado pela API
                stability_animation_type = "INTERPOLATE"
                if animation_type == "morph":
                    stability_animation_type = "INTERPOLATE"
                elif animation_type == "zoom":
                    stability_animation_type = "ZOOM"
                elif animation_type == "pan":
                    stability_animation_type = "PAN"
                elif animation_type in ["bounce", "float"]:
                    stability_animation_type = "INTERPOLATE"  # Fallback para INTERPOLATE
                
                # Configura parâmetros adicionais baseados na análise de imagem
                animation_params = {
                    "animation_type": stability_animation_type,
                    "duration_seconds": duration,
                    "fps": fps,
                    "seed": seed if seed is not None else random.randint(0, 2147483647)
                }
                
                # Adiciona parâmetros específicos para cada tipo de animação
                if animation_type == "zoom" and "zoom_factor" in kwargs:
                    animation_params["zoom_factor"] = kwargs["zoom_factor"]
                if animation_type == "pan" and "direction" in kwargs:
                    animation_params["direction"] = kwargs["direction"]
                
                # Construção do payload para a API
                payload = {
                    "images": encoded_images,
                    "animation_params": animation_params,
                    "output_format": "mp4"
                }
                
                # Chamada à API
                response = requests.post(
                    f"{STABILITY_API_BASE_URL}{STABILITY_ANIMATION_ENDPOINT}",
                    headers=headers,
                    json=payload
                )
                
                # Verifica se a chamada foi bem-sucedida
                if response.status_code == 200:
                    # Salva o arquivo de vídeo retornado pela API
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    
                    logger.info(f"Animação gerada com sucesso via API: {output_path}")
                    
                    # Salva metadados da animação
                    animation_info = {
                        "type": animation_type,
                        "duration": duration,
                        "fps": fps,
                        "seed": seed,
                        "source_images": source_images,
                        "created_at": time.time(),
                        "parameters": kwargs,
                        "content_analysis": image_analysis is not None,
                        "api_provider": "stability",
                        "api_used": True
                    }
                    
                    # Atualiza o cache
                    cache_key = self._get_cache_key(source_images, animation_type, kwargs)
                    self.animation_cache[cache_key] = output_path
                    self.animation_metadata[cache_key] = animation_info
                    self._save_cache()
                    
                    return True
                else:
                    logger.error(f"Erro na chamada à API da Stability: {response.status_code} - {response.text}")
                    # Fallback para geração local se a API falhar
                    logger.info("Usando fallback para geração local de animação")
            
            # Se não estamos usando a API ou houve falha, gera localmente
            # Carrega as imagens de origem
            images = [Image.open(img) for img in source_images]
            
            # Cria um diretório temporário para os frames
            with tempfile.TemporaryDirectory() as temp_dir:
                # Simula a geração de frames intermediários
                num_frames = int(duration * fps)
                
                # Configurações específicas para cada tipo de animação
                # Usa as informações da análise de imagem para melhorar a animação
                if animation_type == "morph":
                    # Implementação melhorada de morphing usando análise de imagem
                    frames = self._generate_enhanced_morph_frames(images, num_frames, image_analysis, **kwargs)
                    
                elif animation_type == "zoom":
                    # Implementação de zoom inteligente focado em objetos importantes
                    zoom_center = kwargs.get("zoom_center", (0.5, 0.5))
                    zoom_factor = kwargs.get("zoom_factor", 1.5)
                    frames = self._generate_enhanced_zoom_frames(images, num_frames, zoom_center, zoom_factor, image_analysis, **kwargs)
                    
                elif animation_type == "pan":
                    # Implementação de pan inteligente baseado no conteúdo da imagem
                    direction = kwargs.get("direction", "left-to-right")
                    speed = kwargs.get("speed", 0.5)
                    frames = self._generate_enhanced_pan_frames(images, num_frames, direction, speed, image_analysis, **kwargs)
                    
                elif animation_type == "bounce" or animation_type == "float":
                    # Implementação de animação de objetos com movimento
                    amplitude = kwargs.get("amplitude", 0.1)
                    speed = kwargs.get("speed", 0.5)
                    frames = self._generate_enhanced_motion_frames(images, num_frames, animation_type, amplitude, speed, image_analysis, **kwargs)
                    
                else:
                    # Fallback para o método padrão se o tipo de animação não for reconhecido
                    frames = []
                    for i in range(num_frames):
                        # Calcula qual imagem de origem usar como base
                        if len(images) > 1:
                            progress = i / (num_frames - 1)
                            idx1 = int(progress * (len(images) - 1))
                            idx2 = min(idx1 + 1, len(images) - 1)
                            alpha = progress * (len(images) - 1) - idx1
                            
                            # Cria um blend simples entre as duas imagens
                            if idx1 == idx2:
                                frame = images[idx1].copy()
                            else:
                                # Garante que as imagens tenham o mesmo tamanho
                                if images[idx1].size != images[idx2].size:
                                    images[idx2] = images[idx2].resize(images[idx1].size)
                                
                                # Blend simples
                                frame = Image.blend(images[idx1].convert('RGBA'), 
                                                   images[idx2].convert('RGBA'), 
                                                   alpha)
                        else:
                            frame = images[0].copy()
                        frames.append(frame)
                
                # Salva os frames gerados
                for i, frame in enumerate(frames):
                    frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                    frame.save(frame_path)
                
                # Usa FFmpeg para combinar os frames em um vídeo
                frames_pattern = os.path.join(temp_dir, "frame_%04d.png")
                os.system(f"ffmpeg -y -r {fps} -i {frames_pattern} -c:v libx264 -pix_fmt yuv420p -crf 23 {output_path}")
                
                if os.path.exists(output_path):
                    logger.info(f"Animação gerada com sucesso: {output_path}")
                    
                    # Salva metadados da animação incluindo informações da análise de imagem
                    animation_info = {
                        "type": animation_type,
                        "duration": duration,
                        "fps": fps,
                        "seed": seed,
                        "source_images": source_images,
                        "created_at": time.time(),
                        "parameters": kwargs,
                        "content_analysis": image_analysis is not None
                    }
                    
                    # Atualiza o cache
                    cache_key = self._get_cache_key(source_images, animation_type, kwargs)
                    self.animation_cache[cache_key] = output_path
                    self.animation_metadata[cache_key] = animation_info
                    self._save_cache()
                    
                    return True
                else:
                    logger.error(f"Falha ao gerar animação: {output_path}")
                    return False
                
        except Exception as e:
            logger.error(f"Erro ao gerar animação com Stability AI: {str(e)}")
            return False
    
    def _runway_generate_animation(self, source_images, output_path, animation_type="morph", 
                                   duration=3.0, fps=24, seed=None, image_analysis=None, **kwargs):
        """Gera uma animação usando a API da Runway ML.
        
        Args:
            source_images: Lista de caminhos para as imagens de origem
            output_path: Caminho para salvar a animação gerada
            animation_type: Tipo de animação (morph, zoom, pan, etc.)
            duration: Duração da animação em segundos
            fps: Frames por segundo
            seed: Seed para consistência na geração
            image_analysis: Dicionário com análises das imagens de origem
            **kwargs: Parâmetros adicionais para a API
            
        Returns:
            bool: True se a animação foi gerada com sucesso, False caso contrário
        """
        logger.info(f"Gerando animação com Runway ML: {animation_type}")
        
        # Verifica se a chave da API está disponível
        if not self.api_key:
            logger.error("Chave da API da Runway ML não configurada")
            return False
        
        try:
            # Verifica se devemos usar a API real ou gerar localmente
            use_api = kwargs.get("use_api", True)
            
            if use_api:
                # Configuração da chamada à API
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                
                # Prepara as imagens para envio
                encoded_images = []
                for img_path in source_images:
                    with open(img_path, "rb") as img_file:
                        encoded_img = base64.b64encode(img_file.read()).decode('utf-8')
                        encoded_images.append(encoded_img)
                
                # Mapeia o tipo de animação para o formato esperado pela API da Runway
                runway_animation_type = "morph"
                if animation_type == "morph":
                    runway_animation_type = "morph"
                elif animation_type == "zoom":
                    runway_animation_type = "zoom"
                elif animation_type == "pan":
                    runway_animation_type = "pan"
                elif animation_type == "bounce":
                    runway_animation_type = "bounce"
                elif animation_type == "float":
                    runway_animation_type = "float"
                
                # Configura parâmetros adicionais baseados na análise de imagem
                animation_params = {
                    "type": runway_animation_type,
                    "duration": duration,
                    "fps": fps,
                    "seed": seed if seed is not None else random.randint(0, 2147483647)
                }
                
                # Adiciona parâmetros específicos para cada tipo de animação
                if animation_type == "zoom":
                    zoom_center = kwargs.get("zoom_center", (0.5, 0.5))
                    zoom_factor = kwargs.get("zoom_factor", 1.5)
                    animation_params["zoom_center"] = zoom_center
                    animation_params["zoom_factor"] = zoom_factor
                    
                    # Se temos análise de imagem, podemos ajustar o centro do zoom para focar em objetos importantes
                    if image_analysis and "objects" in image_analysis:
                        # Encontra o objeto mais importante (maior confiança ou maior área)
                        main_object = max(image_analysis["objects"], key=lambda obj: obj.get("confidence", 0))
                        if "bbox" in main_object:
                            # Calcula o centro do objeto como o centro do zoom
                            x1, y1, x2, y2 = main_object["bbox"]
                            center_x = (x1 + x2) / 2
                            center_y = (y1 + y2) / 2
                            animation_params["zoom_center"] = (center_x, center_y)
                
                elif animation_type == "pan":
                    direction = kwargs.get("direction", "left-to-right")
                    speed = kwargs.get("speed", 0.5)
                    animation_params["direction"] = direction
                    animation_params["speed"] = speed
                    
                    # Se temos análise de imagem, podemos ajustar a direção do pan baseado no conteúdo
                    if image_analysis and "composition" in image_analysis:
                        # Ajusta a direção do pan com base na composição da imagem
                        if image_analysis["composition"].get("focus_side") == "left":
                            animation_params["direction"] = "left-to-right"
                        elif image_analysis["composition"].get("focus_side") == "right":
                            animation_params["direction"] = "right-to-left"
                
                elif animation_type in ["bounce", "float"]:
                    amplitude = kwargs.get("amplitude", 0.1)
                    speed = kwargs.get("speed", 0.5)
                    animation_params["amplitude"] = amplitude
                    animation_params["speed"] = speed
                
                # Construção do payload para a API
                payload = {
                    "images": encoded_images,
                    "animation": animation_params,
                    "output_format": "mp4"
                }
                
                # Chamada à API
                response = requests.post(
                    f"{RUNWAY_API_BASE_URL}{RUNWAY_ANIMATION_ENDPOINT}",
                    headers=headers,
                    json=payload
                )
                
                # Verifica se a chamada foi bem-sucedida
                if response.status_code == 200:
                    # Salva o arquivo de vídeo retornado pela API
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    
                    logger.info(f"Animação gerada com sucesso via API Runway ML: {output_path}")
                    
                    # Salva metadados da animação
                    animation_info = {
                        "type": animation_type,
                        "duration": duration,
                        "fps": fps,
                        "seed": seed,
                        "source_images": source_images,
                        "created_at": time.time(),
                        "parameters": kwargs,
                        "content_analysis": image_analysis is not None,
                        "api_provider": "runway",
                        "api_used": True
                    }
                    
                    # Atualiza o cache
                    cache_key = self._get_cache_key(source_images, animation_type, kwargs)
                    self.animation_cache[cache_key] = output_path
                    self.animation_metadata[cache_key] = animation_info
                    self._save_cache()
                    
                    return True
                else:
                    logger.error(f"Erro na chamada à API da Runway ML: {response.status_code} - {response.text}")
                    # Fallback para geração local se a API falhar
                    logger.info("Usando fallback para geração local de animação")
            
            # Se não estamos usando a API ou houve falha, gera localmente
            # Carrega as imagens de origem
            images = [Image.open(img) for img in source_images]
            # Simula a geração de frames intermediários
            num_frames = int(duration * fps)
            
            # Configurações específicas para cada tipo de animação
            # Usa as informações da análise de imagem para melhorar a animação
            if animation_type == "morph":
                # Implementação melhorada de morphing usando análise de imagem
                frames = self._generate_enhanced_morph_frames(images, num_frames, image_analysis, **kwargs)
                
            elif animation_type == "zoom":
                # Implementação de zoom inteligente focado em objetos importantes
                zoom_center = kwargs.get("zoom_center", (0.5, 0.5))
                zoom_factor = kwargs.get("zoom_factor", 1.5)
                frames = self._generate_enhanced_zoom_frames(images, num_frames, zoom_center, zoom_factor, image_analysis, **kwargs)
                
            elif animation_type == "pan":
                # Implementação de pan inteligente baseado no conteúdo da imagem
                direction = kwargs.get("direction", "left-to-right")
                speed = kwargs.get("speed", 0.5)
                frames = self._generate_enhanced_pan_frames(images, num_frames, direction, speed, image_analysis, **kwargs)
                
            elif animation_type == "bounce" or animation_type == "float":
                # Implementação de animação de objetos com movimento
                amplitude = kwargs.get("amplitude", 0.1)
                speed = kwargs.get("speed", 0.5)
                frames = self._generate_enhanced_motion_frames(images, num_frames, animation_type, amplitude, speed, image_analysis, **kwargs)
                
            else:
                # Fallback para o método padrão se o tipo de animação não for reconhecido
                frames = []
                for i in range(num_frames):
                    # Calcula qual imagem de origem usar como base
                    if len(images) > 1:
                        progress = i / (num_frames - 1)
                        idx1 = int(progress * (len(images) - 1))
                        idx2 = min(idx1 + 1, len(images) - 1)
                        alpha = progress * (len(images) - 1) - idx1
                        
                        # Cria um blend simples entre as duas imagens
                        if idx1 == idx2:
                            frame = images[idx1].copy()
                        else:
                            # Garante que as imagens tenham o mesmo tamanho
                            if images[idx1].size != images[idx2].size:
                                images[idx2] = images[idx2].resize(images[idx1].size)
                            
                            # Blend simples
                            frame = Image.blend(images[idx1].convert('RGBA'), 
                                               images[idx2].convert('RGBA'), 
                                               alpha)
                    else:
                        frame = images[0].copy()
                    frames.append(frame)
            
            # Salva os frames gerados
            for i, frame in enumerate(frames):
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                frame.save(frame_path)
            
            # Usa FFmpeg para combinar os frames em um vídeo
            frames_pattern = os.path.join(temp_dir, "frame_%04d.png")
            os.system(f"ffmpeg -y -r {fps} -i {frames_pattern} -c:v libx264 -pix_fmt yuv420p -crf 23 {output_path}")
            
            if os.path.exists(output_path):
                logger.info(f"Animação gerada com sucesso: {output_path}")
                
                # Salva metadados da animação incluindo informações da análise de imagem
                animation_info = {
                    "type": animation_type,
                    "duration": duration,
                    "fps": fps,
                    "seed": seed,
                    "source_images": source_images,
                    "created_at": time.time(),
                    "parameters": kwargs,
                    "content_analysis": image_analysis is not None,
                    "api_provider": "runway"
                }
                
                # Atualiza o cache
                cache_key = self._get_cache_key(source_images, animation_type, kwargs)
                self.animation_cache[cache_key] = output_path
                self.animation_metadata[cache_key] = animation_info
                self._save_cache()
                
                return True
            else:
                logger.error(f"Falha ao gerar animação: {output_path}")
                return False
            
        except Exception as e:
            logger.error(f"Erro ao gerar animação com Runway ML: {str(e)}")
            return False
    
    def _generate_enhanced_morph_frames(self, images, num_frames, image_analysis=None, **kwargs):
        """Gera frames de morphing avançados entre imagens, utilizando análise de conteúdo.
        
        Args:
            images: Lista de imagens PIL
            num_frames: Número total de frames a serem gerados
            image_analysis: Dicionário com análises das imagens de origem
            **kwargs: Parâmetros adicionais para o morphing
            
        Returns:
            List[Image]: Lista de frames gerados
        """
        logger.info(f"Gerando {num_frames} frames de morphing avançado")
        
        frames = []
        
        try:
            # Se temos apenas uma imagem, retorna cópias dela
            if len(images) == 1:
                return [images[0].copy() for _ in range(num_frames)]
            
            # Para cada par de imagens consecutivas
            for i in range(len(images) - 1):
                img1 = images[i]
                img2 = images[i + 1]
                
                # Calcula quantos frames devem ser gerados entre este par
                pair_frames = num_frames // (len(images) - 1)
                if i == len(images) - 2:  # Último par
                    pair_frames = num_frames - len(frames)  # Garante o número exato de frames
                
                # Converte para arrays numpy
                img1_array = np.array(img1)
                img2_array = np.array(img2)
                
                # Verifica se temos análise de imagem disponível
                img1_analysis = image_analysis.get(f"image_{i+1}") if image_analysis else None
                img2_analysis = image_analysis.get(f"image_{i+2}") if image_analysis else None
                
                # Fallback: Morphing padrão com melhorias
                for j in range(pair_frames):
                    # Calcula o fator de interpolação
                    alpha = j / (pair_frames - 1) if pair_frames > 1 else 0.5
                    
                    # Aplica uma curva de aceleração para tornar o morphing mais natural
                    if kwargs.get("acceleration", "ease-in-out") == "ease-in-out":
                        alpha = 0.5 * (1 - np.cos(np.pi * alpha))
                    elif kwargs.get("acceleration", "") == "ease-in":
                        alpha = alpha * alpha
                    elif kwargs.get("acceleration", "") == "ease-out":
                        alpha = 1 - (1 - alpha) * (1 - alpha)
                    
                    # Blend entre as imagens
                    frame_array = (1 - alpha) * img1_array + alpha * img2_array
                    
                    # Adiciona alguma distorção para simular morphing
                    if 0.25 < alpha < 0.75 and kwargs.get("distortion_effect", True):
                        # Aplica uma distorção mais sofisticada
                        distortion = np.sin(alpha * np.pi) * 0.1
                        rows, cols = frame_array.shape[:2]
                        
                        # Cria uma grade de distorção
                        x = np.arange(cols)
                        y = np.arange(rows)
                        x_grid, y_grid = np.meshgrid(x, y)
                        
                        # Aplica distorção baseada em seno
                        if kwargs.get("morph_quality", "medium") == "high":
                            x_offset = distortion * np.sin(y_grid / rows * np.pi) * 20
                            y_offset = distortion * np.sin(x_grid / cols * np.pi) * 20
                            
                            # Aplica distorção mais complexa
                            for c in range(min(3, frame_array.shape[2])):
                                frame_array[:,:,c] = np.roll(frame_array[:,:,c], int(distortion * 10), axis=1)
                    
                    # Converte para imagem PIL
                    frame = Image.fromarray(frame_array.astype(np.uint8))
                    
                    # Adiciona efeitos especiais se solicitado
                    if kwargs.get("sparkle_effect", False):
                        frame = self._add_sparkle_effect(frame, alpha, **kwargs)
                    
                    frames.append(frame)
            
            return frames
            
        except Exception as e:
            logger.error(f"Erro ao gerar frames de morphing avançado: {str(e)}")
            # Fallback: retorna interpolação simples
            return self._simple_interpolation(images, num_frames)
    
    def _generate_enhanced_zoom_frames(self, images, num_frames, zoom_center=(0.5, 0.5), zoom_factor=1.5, image_analysis=None, **kwargs):
        """Gera frames de zoom avançados, focando em objetos importantes detectados na imagem.
        
        Args:
            images: Lista de imagens PIL
            num_frames: Número total de frames a serem gerados
            zoom_center: Centro do zoom (x, y) normalizado entre 0 e 1
            zoom_factor: Fator de zoom (1.0 = sem zoom)
            image_analysis: Dicionário com análises das imagens de origem
            **kwargs: Parâmetros adicionais para o zoom
            
        Returns:
            List[Image]: Lista de frames gerados
        """
        logger.info(f"Gerando {num_frames} frames de zoom avançado")
        
        frames = []
        
        try:
            # Se temos apenas uma imagem, aplica zoom nela
            if len(images) == 1:
                img = images[0]
                width, height = img.size
                
                # Se temos análise de imagem, ajusta o centro do zoom para focar no objeto principal
                if image_analysis and "image_1" in image_analysis:
                    objects = image_analysis["image_1"].get("objects", [])
                    if objects:
                        # Encontra o objeto mais importante (maior confiança ou tamanho)
                        main_object = max(objects, key=lambda obj: obj.get("confidence", 0) * obj.get("area", 0))
                        # Ajusta o centro do zoom para o centro do objeto
                        if "bbox" in main_object:
                            x1, y1, x2, y2 = main_object["bbox"]
                            zoom_center = ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height)
                
                # Calcula os parâmetros de zoom para cada frame
                for i in range(num_frames):
                    # Interpola o fator de zoom
                    progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                    current_zoom = 1.0 + progress * (zoom_factor - 1.0)
                    
                    # Calcula o crop box
                    crop_width = width / current_zoom
                    crop_height = height / current_zoom
                    crop_x = zoom_center[0] * width - crop_width / 2
                    crop_y = zoom_center[1] * height - crop_height / 2
                    
                    # Limita o crop box às dimensões da imagem
                    crop_x = max(0, min(width - crop_width, crop_x))
                    crop_y = max(0, min(height - crop_height, crop_y))
                    
                    # Aplica o crop e redimensiona para o tamanho original
                    crop_box = (int(crop_x), int(crop_y), int(crop_x + crop_width), int(crop_y + crop_height))
                    frame = img.crop(crop_box).resize((width, height), Image.LANCZOS)
                    frames.append(frame)
                
                return frames
            
            # Se temos múltiplas imagens, combina zoom com interpolação entre imagens
            else:
                # Para cada frame
                for i in range(num_frames):
                    # Calcula qual imagem de origem usar como base
                    progress = i / (num_frames - 1) if num_frames > 1 else 0
                    idx1 = min(int(progress * (len(images) - 1)), len(images) - 2)
                    idx2 = idx1 + 1
                    
                    # Calcula o fator de interpolação entre as duas imagens
                    alpha = progress * (len(images) - 1) - idx1
                    
                    # Garante que as imagens tenham o mesmo tamanho
                    if images[idx1].size != images[idx2].size:
                        images[idx2] = images[idx2].resize(images[idx1].size, Image.LANCZOS)
                    
                    # Blend simples
                    blended = Image.blend(images[idx1].convert('RGBA'), images[idx2].convert('RGBA'), alpha)
                    
                    # Aplica zoom no blend
                    width, height = blended.size
                    
                    # Interpola o fator de zoom
                    zoom_progress = abs(0.5 - progress) * 2  # Máximo no meio da animação
                    current_zoom = 1.0 + zoom_progress * (zoom_factor - 1.0)
                    
                    # Calcula o crop box
                    crop_width = width / current_zoom
                    crop_height = height / current_zoom
                    crop_x = zoom_center[0] * width - crop_width / 2
                    crop_y = zoom_center[1] * height - crop_height / 2
                    
                    # Limita o crop box às dimensões da imagem
                    crop_x = max(0, min(width - crop_width, crop_x))
                    crop_y = max(0, min(height - crop_height, crop_y))
                    
                    # Aplica o crop e redimensiona para o tamanho original
                    crop_box = (int(crop_x), int(crop_y), int(crop_x + crop_width), int(crop_y + crop_height))
                    frame = blended.crop(crop_box).resize((width, height), Image.LANCZOS)
                    frames.append(frame)
                
                return frames
                
        except Exception as e:
            logger.error(f"Erro ao gerar frames de zoom avançado: {str(e)}")
            # Fallback: retorna interpolação simples
            return self._simple_interpolation(images, num_frames)
    
    def _generate_enhanced_pan_frames(self, images, num_frames, direction="left-to-right", speed=0.5, image_analysis=None, **kwargs):
        """Gera frames de pan avançados, movendo a câmera de acordo com o conteúdo da imagem.
        
        Args:
            images: Lista de imagens PIL
            num_frames: Número total de frames a serem gerados
            direction: Direção do pan (left-to-right, right-to-left, top-to-bottom, bottom-to-top)
            speed: Velocidade do pan (0.0 a 1.0)
            image_analysis: Dicionário com análises das imagens de origem
            **kwargs: Parâmetros adicionais para o pan
            
        Returns:
            List[Image]: Lista de frames gerados
        """
        logger.info(f"Gerando {num_frames} frames de pan avançado na direção {direction}")
        
        frames = []
        
        try:
            # Se temos apenas uma imagem, aplica pan nela
            if len(images) == 1:
                img = images[0]
                width, height = img.size
                
                # Calcula os parâmetros de pan para cada frame
                for i in range(num_frames):
                    # Interpola a posição do pan
                    progress = i / (num_frames - 1) if num_frames > 1 else 0.5
                    
                    # Aplica uma curva de aceleração para tornar o pan mais natural
                    if kwargs.get("acceleration", "ease-in-out") == "ease-in-out":
                        progress = 0.5 * (1 - np.cos(np.pi * progress))
                    
                    # Calcula o deslocamento com base na direção
                    if direction == "left-to-right":
                        offset_x = int(width * speed * progress)
                        offset_y = 0
                    elif direction == "right-to-left":
                        offset_x = int(width * speed * (1 - progress))
                        offset_y = 0
                    elif direction == "top-to-bottom":
                        offset_x = 0
                        offset_y = int(height * speed * progress)
                    elif direction == "bottom-to-top":
                        offset_x = 0
                        offset_y = int(height * speed * (1 - progress))
                    else:  # diagonal ou personalizado
                        offset_x = int(width * speed * progress)
                        offset_y = int(height * speed * progress)
                    
                    # Cria uma nova imagem com o tamanho original
                    frame = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                    
                    # Calcula a posição para colar a imagem original
                    paste_x = -offset_x
                    paste_y = -offset_y
                    
                    # Cola a imagem original na nova imagem
                    frame.paste(img, (paste_x, paste_y))
                    
                    frames.append(frame)
                
                return frames
            
            # Se temos múltiplas imagens, combina pan com interpolação entre imagens
            else:
                return self._simple_interpolation(images, num_frames)  # Por enquanto, usamos interpolação simples
                
        except Exception as e:
            logger.error(f"Erro ao gerar frames de pan avançado: {str(e)}")
            # Fallback: retorna interpolação simples
            return self._simple_interpolation(images, num_frames)
    
    def _generate_enhanced_motion_frames(self, images, num_frames, motion_type="bounce", amplitude=0.1, speed=0.5, image_analysis=None, **kwargs):
        """Gera frames com efeitos de movimento como bounce ou float.
        
        Args:
            images: Lista de imagens PIL
            num_frames: Número total de frames a serem gerados
            motion_type: Tipo de movimento (bounce, float)
            amplitude: Amplitude do movimento (0.0 a 1.0)
            speed: Velocidade do movimento (0.0 a 1.0)
            image_analysis: Dicionário com análises das imagens de origem
            **kwargs: Parâmetros adicionais para o movimento
            
        Returns:
            List[Image]: Lista de frames gerados
        """
        logger.info(f"Gerando {num_frames} frames com movimento {motion_type}")
        
        frames = []
        
        try:
            # Se temos apenas uma imagem, aplica movimento nela
            if len(images) == 1:
                img = images[0]
                width, height = img.size
                
                # Calcula os parâmetros de movimento para cada frame
                for i in range(num_frames):
                    # Calcula a fase do movimento
                    phase = i / num_frames * speed * 2 * np.pi
                    
                    # Calcula o deslocamento com base no tipo de movimento
                    if motion_type == "bounce":
                        # Movimento de quique (bounce) - apenas vertical
                        offset_y = int(height * amplitude * abs(np.sin(phase)))
                        offset_x = 0
                    elif motion_type == "float":
                        # Movimento flutuante - combinação de horizontal e vertical
                        offset_y = int(height * amplitude * np.sin(phase))
                        offset_x = int(width * amplitude * 0.5 * np.sin(phase * 0.7))
                    else:
                        # Movimento padrão
                        offset_y = int(height * amplitude * np.sin(phase))
                        offset_x = 0
                    
                    # Cria uma nova imagem com o tamanho original
                    frame = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                    
                    # Calcula a posição para colar a imagem original
                    paste_x = offset_x
                    paste_y = offset_y
                    
                    # Cola a imagem original na nova imagem
                    frame.paste(img, (paste_x, paste_y))
                    
                    frames.append(frame)
                
                return frames
            
            # Se temos múltiplas imagens, combina movimento com interpolação entre imagens
            else:
                return self._simple_interpolation(images, num_frames)  # Por enquanto, usamos interpolação simples
                
        except Exception as e:
            logger.error(f"Erro ao gerar frames com movimento: {str(e)}")
            # Fallback: retorna interpolação simples
            return self._simple_interpolation(images, num_frames)
    
    def _simple_interpolation(self, images, num_frames):
        """Realiza interpolação simples entre imagens.
        
        Args:
            images: Lista de imagens PIL
            num_frames: Número total de frames a gerar
            
        Returns:
            List[Image]: Lista de frames gerados
        """
        frames = []
        
        # Se temos apenas uma imagem, retorna cópias dela
        if len(images) == 1:
            return [images[0].copy() for _ in range(num_frames)]
        
        # Para cada frame
        for i in range(num_frames):
            # Calcula qual imagem de origem usar como base
            progress = i / (num_frames - 1) if num_frames > 1 else 0
            idx1 = min(int(progress * (len(images) - 1)), len(images) - 2)
            idx2 = idx1 + 1
            
            # Calcula o fator de interpolação entre as duas imagens
            alpha = progress * (len(images) - 1) - idx1
            
            # Garante que as imagens tenham o mesmo tamanho
            if images[idx1].size != images[idx2].size:
                images[idx2] = images[idx2].resize(images[idx1].size, Image.LANCZOS)
            
            # Blend simples
            frame = Image.blend(images[idx1].convert('RGBA'), images[idx2].convert('RGBA'), alpha)
            frames.append(frame)
        
        return frames
    
    def _add_sparkle_effect(self, image, alpha, **kwargs):
        """Adiciona efeito de brilho/sparkle a uma imagem.
        
        Args:
            image: Imagem PIL
            alpha: Fator de interpolação (0.0 a 1.0)
            **kwargs: Parâmetros adicionais para o efeito
            
        Returns:
            Image: Imagem com efeito aplicado
        """
        # Implementação básica de efeito de brilho
        try:
            # Cria uma cópia da imagem
            result = image.copy()
            
            # Intensidade do efeito (máxima no meio da transição)
            intensity = 1.0 - abs(2.0 * alpha - 1.0)
            
            if intensity > 0.2:  # Aplica apenas quando a intensidade é significativa
                # Aumenta o brilho e contraste
                enhancer = ImageEnhance.Brightness(result)
                result = enhancer.enhance(1.0 + 0.2 * intensity)
                
                enhancer = ImageEnhance.Contrast(result)
                result = enhancer.enhance(1.0 + 0.1 * intensity)
                
                # Adiciona pontos de brilho aleatórios se solicitado
                if kwargs.get("sparkle_points", False):
                    width, height = result.size
                    draw = ImageDraw.Draw(result)
                    
                    # Número de pontos de brilho baseado no tamanho da imagem
                    num_points = int(width * height * 0.0001 * intensity)
                    
                    for _ in range(num_points):
                        x = random.randint(0, width - 1)
                        y = random.randint(0, height - 1)
                        size = random.randint(1, 3)
                        brightness = random.randint(200, 255)
                        draw.ellipse((x-size, y-size, x+size, y+size), 
                                    fill=(brightness, brightness, brightness, 200))
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao adicionar efeito de brilho: {str(e)}")
            return image  # Retorna a imagem original em caso de erro
    
    def generate_animation(self, source_images, output_path, animation_type="morph", 
                          duration=3.0, fps=24, seed=None, force_regenerate=False, 
                          analyze_content=True, smart_animation=True, **kwargs):
        """Gera uma animação a partir de imagens estáticas.
        
        Args:
            source_images: Lista de caminhos para as imagens de origem
            output_path: Caminho para salvar a animação gerada
            animation_type: Tipo de animação (morph, zoom, pan, etc.)
            duration: Duração da animação em segundos
            fps: Frames por segundo
            seed: Seed para consistência na geração
            force_regenerate: Se True, força a regeneração mesmo se existir no cache
            analyze_content: Se True, analisa o conteúdo das imagens para melhorar a animação
            smart_animation: Se True, seleciona automaticamente o melhor tipo de animação com base no conteúdo
            **kwargs: Parâmetros adicionais para a API
            
        Returns:
            bool: True se a animação foi gerada com sucesso, False caso contrário
        """
        # Verifica se as imagens de origem existem
        for img_path in source_images:
            if not os.path.exists(img_path):
                logger.error(f"Imagem de origem não encontrada: {img_path}")
                return False
        
        # Cria o diretório de saída se não existir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Verifica se a animação já existe no cache
        if self.cache_enabled and not force_regenerate:
            cache_key = self._get_cache_key(source_images, animation_type, kwargs)
            if cache_key in self.animation_cache:
                cached_path = self.animation_cache[cache_key]
                if os.path.exists(cached_path):
                    logger.info(f"Usando animação em cache: {cached_path}")
                    # Copia a animação em cache para o caminho de saída
                    shutil.copy2(cached_path, output_path)
                    return True
        
        # Analisa o conteúdo das imagens se solicitado
        image_analysis = {}
        if analyze_content:
            logger.info("Analisando conteúdo das imagens para otimizar a animação...")
            for i, img_path in enumerate(source_images):
                # Analisa o conteúdo básico da imagem
                basic_analysis = self.analyze_image_content(img_path)
                
                # Tenta detecção avançada de objetos com TensorFlow ou PyTorch
                try:
                    # Tenta primeiro com PyTorch (mais preciso para detecção de objetos)
                    advanced_objects = self.detect_objects_pytorch(img_path, confidence_threshold=0.4)
                    if not advanced_objects:
                        # Se PyTorch falhar ou não encontrar objetos, tenta com TensorFlow
                        advanced_objects = self.detect_objects_tensorflow(img_path, confidence_threshold=0.4)
                    
                    if advanced_objects:
                        basic_analysis["objects"] = advanced_objects
                        # Atualiza objetos dominantes
                        basic_analysis["dominant_objects"] = sorted(
                            advanced_objects, 
                            key=lambda x: x.get("confidence", 0), 
                            reverse=True
                        )[:3]
                        # Atualiza objetos com potencial de movimento
                        basic_analysis["motion_potential"] = self._identify_motion_potential(advanced_objects)
                except Exception as e:
                    logger.warning(f"Erro na detecção avançada de objetos: {str(e)}")
                
                # Analisa a cena da imagem
                try:
                    scene_info = self.analyze_scene(img_path)
                    if scene_info and scene_info["type"] != "unknown":
                        basic_analysis["scene"] = scene_info
                except Exception as e:
                    logger.warning(f"Erro na análise de cena: {str(e)}")
                
                image_analysis[f"image_{i+1}"] = basic_analysis
            
            # Registra os resultados da análise
            logger.info(f"Análise de imagens concluída: {len(image_analysis)} imagens analisadas")
            
            # Seleciona o melhor tipo de animação com base na análise
            if smart_animation and animation_type == "auto":
                animation_type = self._select_best_animation_type(image_analysis, source_images)
                logger.info(f"Tipo de animação selecionado automaticamente: {animation_type}")
            
            # Ajusta parâmetros da animação com base na análise
            kwargs = self._optimize_animation_parameters(animation_type, image_analysis, kwargs)
        
        # Gera a animação usando o provedor configurado
        if self.api_provider.lower() == "stability":
            return self._stability_generate_animation(source_images, output_path, animation_type, 
                                                    duration, fps, seed, image_analysis=image_analysis, **kwargs)
        elif self.api_provider.lower() == "runway":
            return self._runway_generate_animation(source_images, output_path, animation_type, 
                                                 duration, fps, seed, image_analysis=image_analysis, **kwargs)
        else:
            logger.error(f"Provedor de API não suportado: {self.api_provider}")
            return False
    

    def generate_morph_frames(self, source_image1, source_image2, num_frames=24, quality="high", seed=None, **kwargs):
        """Gera frames intermediários para uma transição de morphing entre duas imagens.
        
        Args:
            source_image1: Caminho para a primeira imagem
            source_image2: Caminho para a segunda imagem
            num_frames: Número de frames intermediários a serem gerados
            quality: Qualidade do morphing ('low', 'medium', 'high')
            seed: Seed para consistência na geração
            **kwargs: Parâmetros adicionais para o algoritmo de morphing
            
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        logger.info(f"Gerando {num_frames} frames de morphing entre duas imagens")
        
        # Cria uma chave de cache única para esta operação
        cache_key = f"morph_{os.path.basename(source_image1)}_{os.path.basename(source_image2)}_{num_frames}_{quality}"
        
        # Verifica se já existe no cache
        if self.cache_enabled and cache_key in self.animation_cache:
            logger.info(f"Usando frames de morphing do cache: {cache_key}")
            return self.animation_cache[cache_key]
        
        # Cria um diretório temporário para os frames
        output_frames = []
        
        try:
            # Carrega as imagens de origem
            img1 = Image.open(source_image1)
            img2 = Image.open(source_image2)
            
            # Redimensiona as imagens para o mesmo tamanho se necessário
            if img1.size != img2.size:
                # Usa o maior tamanho para manter qualidade
                target_size = (max(img1.width, img2.width), max(img1.height, img2.height))
                img1 = img1.resize(target_size, Image.LANCZOS)
                img2 = img2.resize(target_size, Image.LANCZOS)
            
            # Converte para arrays numpy
            img1_array = np.array(img1)
            img2_array = np.array(img2)
            
            # Cria um diretório temporário para os frames
            with tempfile.TemporaryDirectory() as temp_dir:
                # Gera os frames intermediários
                frame_paths = []
                
                # Dependendo do provedor de API configurado, usa diferentes métodos
                if self.api_provider == "stability" and self.api_key:
                    # Usa a API da Stability para morphing de alta qualidade
                    frame_paths = self._stability_generate_morph_frames(
                        source_image1, source_image2, temp_dir, num_frames, quality, seed, **kwargs
                    )
                else:
                    # Fallback: Usa interpolação linear simples
                    for i in range(num_frames):
                        # Calcula o fator de interpolação
                        alpha = i / (num_frames - 1) if num_frames > 1 else 0.5
                        
                        # Aplica suavização para tornar a transição mais natural
                        if quality == "high":
                            # Usa uma curva suave (ease-in-out)
                            alpha = 0.5 * (1 - np.cos(np.pi * alpha))
                        
                        # Interpola entre as duas imagens
                        blended = (1 - alpha) * img1_array + alpha * img2_array
                        
                        # Converte para imagem PIL e salva
                        frame = Image.fromarray(blended.astype(np.uint8))
                        frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                        frame.save(frame_path)
                        frame_paths.append(frame_path)
                
                # Copia os frames para um local permanente
                morph_cache_dir = os.path.join(self.cache_dir, "morphs", cache_key)
                os.makedirs(morph_cache_dir, exist_ok=True)
                
                for i, frame_path in enumerate(frame_paths):
                    perm_path = os.path.join(morph_cache_dir, f"frame_{i:04d}.png")
                    shutil.copy2(frame_path, perm_path)
                    output_frames.append(perm_path)
                
                # Salva no cache
                if self.cache_enabled:
                    self.animation_cache[cache_key] = output_frames
                    self.animation_metadata[cache_key] = {
                        "source_images": [source_image1, source_image2],
                        "num_frames": num_frames,
                        "quality": quality,
                        "timestamp": time.time()
                    }
                    self._save_cache()
                
                logger.info(f"Gerados {len(output_frames)} frames de morphing")
                return output_frames
                
        except Exception as e:
            logger.error(f"Erro ao gerar frames de morphing: {str(e)}")
            # Retorna listas vazias em caso de erro
            return []
    
    def _add_sparkle_effect(self, image, progress, **kwargs):
        """Adiciona efeito de sparkle/estrelas à imagem.
        
        Args:
            image: Imagem PIL para adicionar o efeito
            progress: Progresso da transição (0.0 a 1.0)
            **kwargs: Parâmetros adicionais para o efeito
                - color_theme: Tema de cores ("rainbow", "pastel", "vibrant")
                - sparkle_density: Densidade de sparkles (0.0 a 1.0)
                - sparkle_size: Tamanho máximo dos sparkles
                - sparkle_variation: Variação no tamanho dos sparkles
        
        Returns:
            Image: Imagem com efeito de sparkle aplicado
        """
        # Cria uma cópia da imagem para não modificar a original
        result = image.copy()
        
        # Parâmetros do efeito
        width, height = image.size
        sparkle_density = kwargs.get("sparkle_density", 0.05)  # Densidade padrão
        sparkle_size_max = kwargs.get("sparkle_size", 15)  # Tamanho máximo
        sparkle_variation = kwargs.get("sparkle_variation", 0.7)  # Variação no tamanho
        color_theme = kwargs.get("color_theme", "rainbow")  # Tema de cores
        
        # Ajusta a intensidade do efeito com base no progresso
        # Mais intenso no meio da transição
        intensity = 1.0 - abs(2.0 * progress - 1.0)  # 0->1->0 durante a transição
        
        # Número de sparkles baseado na densidade e tamanho da imagem
        num_sparkles = int(width * height * sparkle_density * intensity / 1000)
        
        # Define as cores dos sparkles com base no tema
        if color_theme == "rainbow":
            colors = [
                (255, 0, 0, 200),      # Vermelho
                (255, 165, 0, 200),    # Laranja
                (255, 255, 0, 200),    # Amarelo
                (0, 255, 0, 200),      # Verde
                (0, 0, 255, 200),      # Azul
                (75, 0, 130, 200),     # Índigo
                (238, 130, 238, 200)   # Violeta
            ]
        elif color_theme == "pastel":
            colors = [
                (255, 209, 220, 200),  # Rosa pastel
                (230, 230, 250, 200),  # Lavanda
                (173, 216, 230, 200),  # Azul claro
                (152, 251, 152, 200),  # Verde pastel
                (255, 250, 205, 200),  # Amarelo claro
                (255, 218, 185, 200),  # Pêssego
                (221, 160, 221, 200)   # Plum
            ]
        else:  # "vibrant" ou padrão
            colors = [
                (255, 0, 0, 200),      # Vermelho
                (255, 215, 0, 200),    # Ouro
                (0, 255, 127, 200),    # Verde primavera
                (0, 191, 255, 200),    # Azul céu profundo
                (138, 43, 226, 200),   # Violeta azulado
                (255, 20, 147, 200),   # Rosa profundo
                (255, 255, 255, 200)   # Branco
            ]
        
        # Cria um objeto de desenho
        draw = ImageDraw.Draw(result)
        
        # Adiciona os sparkles
        for _ in range(num_sparkles):
            # Posição aleatória
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            
            # Tamanho aleatório com base na variação
            size = random.randint(
                int(sparkle_size_max * (1 - sparkle_variation)), 
                sparkle_size_max
            )
            
            # Cor aleatória da paleta
            color = random.choice(colors)
            
            # Tipo de sparkle (estrela ou círculo com gradiente)
            sparkle_type = random.random()
            
            if sparkle_type < 0.6:  # 60% chance de ser uma estrela
                # Desenha uma estrela
                self._draw_star(draw, x, y, size, color)
            else:  # 40% chance de ser um círculo com gradiente
                # Desenha um círculo com gradiente
                self._draw_gradient_circle(draw, x, y, size, color)
        
        return result
    
    def _draw_star(self, draw, x, y, size, color):
        """Desenha uma estrela na imagem.
        
        Args:
            draw: Objeto ImageDraw
            x, y: Coordenadas do centro da estrela
            size: Tamanho da estrela
            color: Cor da estrela (R, G, B, A)
        """
        # Número de pontas da estrela
        n_points = 5
        
        # Raio externo e interno
        outer_radius = size
        inner_radius = size // 2
        
        # Calcula os pontos da estrela
        points = []
        for i in range(n_points * 2):
            # Alterna entre raio externo e interno
            radius = outer_radius if i % 2 == 0 else inner_radius
            # Calcula ângulo
            angle = math.pi * i / n_points
            # Adiciona ponto
            points.append((
                x + radius * math.sin(angle),
                y + radius * math.cos(angle)
            ))
        
        # Desenha a estrela
        draw.polygon(points, fill=color)
    
    def _draw_gradient_circle(self, draw, x, y, size, color):
        """Desenha um círculo com gradiente na imagem.
        
        Args:
            draw: Objeto ImageDraw
            x, y: Coordenadas do centro do círculo
            size: Tamanho do círculo
            color: Cor do círculo (R, G, B, A)
        """
        # Cria um círculo com gradiente
        for r in range(size, 0, -1):
            # Ajusta a transparência com base no raio
            alpha = int(color[3] * (r / size))
            # Cria a cor com nova transparência
            circle_color = (color[0], color[1], color[2], alpha)
            # Desenha o círculo
            draw.ellipse((x-r, y-r, x+r, y+r), fill=circle_color)
    
    def _generate_page_turn_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição de página virando entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - turn_direction: Direção da virada ("left-to-right" ou "right-to-left")
                - shadow_intensity: Intensidade da sombra (0.0 a 1.0)
                - page_curve: Curvatura da página (0.0 a 1.0)
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        logger.info("Gerando transição de página virando")
        
        # Parâmetros da transição
        turn_direction = kwargs.get("turn_direction", "left-to-right")
        shadow_intensity = kwargs.get("shadow_intensity", 0.5)
        page_curve = kwargs.get("page_curve", 0.3)
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Converte para arrays numpy para manipulação
        img1_array = np.array(img1).astype(np.float32) / 255.0
        img2_array = np.array(img2).astype(np.float32) / 255.0
        
        # Dimensões da imagem
        height, width = img1_array.shape[:2]
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Aplica uma curva de aceleração para tornar a transição mais natural
            ease_progress = 0.5 * (1 - np.cos(np.pi * progress))
            
            # Cria uma nova imagem para o frame atual
            frame_array = np.zeros_like(img1_array)
            
            # Calcula a posição da dobra da página
            if turn_direction == "left-to-right":
                fold_position = int(width * ease_progress)
                # Área visível da primeira imagem (lado esquerdo)
                visible_width1 = fold_position
                # Área visível da segunda imagem (lado direito)
                visible_width2 = width - fold_position
            else:  # "right-to-left"
                fold_position = int(width * (1 - ease_progress))
                # Área visível da primeira imagem (lado direito)
                visible_width1 = width - fold_position
                # Área visível da segunda imagem (lado esquerdo)
                visible_width2 = fold_position
            
            # Cria máscaras para as áreas visíveis
            mask1 = np.zeros((height, width))
            mask2 = np.zeros((height, width))
            
            if turn_direction == "left-to-right":
                # Primeira imagem visível à esquerda da dobra
                mask1[:, :fold_position] = 1.0
                # Segunda imagem visível à direita da dobra
                mask2[:, fold_position:] = 1.0
            else:  # "right-to-left"
                # Primeira imagem visível à direita da dobra
                mask1[:, fold_position:] = 1.0
                # Segunda imagem visível à esquerda da dobra
                mask2[:, :fold_position] = 1.0
            
            # Expande as máscaras para corresponder ao número de canais da imagem
            if img1_array.shape[2] == 3:  # RGB
                mask1 = np.stack([mask1, mask1, mask1], axis=2)
                mask2 = np.stack([mask2, mask2, mask2], axis=2)
            else:  # RGBA
                mask1 = np.stack([mask1, mask1, mask1, mask1], axis=2)
                mask2 = np.stack([mask2, mask2, mask2, mask2], axis=2)
            
            # Aplica as máscaras para combinar as imagens
            frame_array = img1_array * mask1 + img2_array * mask2
            
            # Aplica efeito de curvatura na dobra
            if page_curve > 0:
                # Largura da área afetada pela curvatura
                curve_width = int(width * page_curve * 0.2)
                
                # Aplica distorção na área da dobra
                for x_offset in range(-curve_width, curve_width + 1):
                    # Posição relativa à dobra
                    x = fold_position + x_offset
                    
                    # Verifica se a posição está dentro da imagem
                    if 0 <= x < width:
                        # Fator de distorção baseado na distância da dobra
                        distortion = 1.0 - abs(x_offset) / curve_width
                        distortion = distortion * distortion * page_curve
                        
                        # Aplica distorção vertical
                        for y in range(height):
                            # Calcula o deslocamento vertical
                            y_offset = int(distortion * np.sin(y / height * np.pi) * curve_width)
                            
                            # Aplica o deslocamento se estiver dentro dos limites
                            y_src = y + y_offset
                            if 0 <= y_src < height:
                                frame_array[y, x] = frame_array[y_src, x]
            
            # Aplica sombra na área da dobra
            if shadow_intensity > 0:
                # Largura da sombra
                shadow_width = int(width * 0.1)
                
                # Cria máscara de sombra
                shadow_mask = np.zeros((height, width))
                
                # Aplica sombra gradual
                for x_offset in range(-shadow_width, shadow_width + 1):
                    x = fold_position + x_offset
                    if 0 <= x < width:
                        # Intensidade da sombra baseada na distância da dobra
                        intensity = (1.0 - abs(x_offset) / shadow_width) * shadow_intensity
                        shadow_mask[:, x] = intensity
                
                # Expande a máscara de sombra para corresponder ao número de canais
                if img1_array.shape[2] == 3:  # RGB
                    shadow_mask = np.stack([shadow_mask, shadow_mask, shadow_mask], axis=2)
                else:  # RGBA
                    shadow_mask = np.stack([shadow_mask, shadow_mask, shadow_mask, np.zeros_like(shadow_mask)], axis=2)
                
                # Aplica a sombra
                frame_array = frame_array * (1.0 - shadow_mask)
            
            # Aplica efeito de brilho na área da dobra
            if brightness_effect:
                # Largura do brilho
                brightness_width = int(width * 0.05)
                
                # Cria máscara de brilho
                brightness_mask = np.zeros((height, width))
                
                # Aplica brilho gradual
                for x_offset in range(-brightness_width, brightness_width + 1):
                    x = fold_position + x_offset
                    if 0 <= x < width:
                        # Intensidade do brilho baseada na distância da dobra
                        intensity = (1.0 - abs(x_offset) / brightness_width) * ease_progress
                        brightness_mask[:, x] = intensity
                
                # Expande a máscara de brilho para corresponder ao número de canais
                if img1_array.shape[2] == 3:  # RGB
                    brightness_mask = np.stack([brightness_mask, brightness_mask, brightness_mask], axis=2)
                else:  # RGBA
                    brightness_mask = np.stack([brightness_mask, brightness_mask, brightness_mask, np.zeros_like(brightness_mask)], axis=2)
                
                # Aplica o brilho
                frame_array = frame_array + brightness_mask * (1.0 - frame_array)
            
            # Converte de volta para uint8 e depois para imagem PIL
            frame_array_uint8 = (frame_array * 255).astype(np.uint8)
            frame = Image.fromarray(frame_array_uint8)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.03 * ease_progress,
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_rotate3d_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição de rotação 3D entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - rotation_axis: Eixo de rotação ("horizontal" ou "vertical")
                - rotation_direction: Direção da rotação ("clockwise" ou "counterclockwise")
                - perspective_strength: Força da perspectiva (0.0 a 1.0)
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        logger.info("Gerando transição de rotação 3D")
        
        # Parâmetros da transição
        rotation_axis = kwargs.get("rotation_axis", "vertical")
        rotation_direction = kwargs.get("rotation_direction", "clockwise")
        perspective_strength = kwargs.get("perspective_strength", 0.5)
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Converte para arrays numpy para manipulação
        img1_np = np.array(img1)
        img2_np = np.array(img2)
        
        # Dimensões da imagem
        height, width = img1_np.shape[:2]
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Aplica uma curva de aceleração para tornar a transição mais natural
            ease_progress = 0.5 * (1 - np.cos(np.pi * progress))
            
            # Ajusta a direção da rotação
            if rotation_direction == "counterclockwise":
                angle = ease_progress * 180  # 0 a 180 graus
            else:  # "clockwise"
                angle = -ease_progress * 180  # 0 a -180 graus
            
            # Prepara a matriz de transformação
            if rotation_axis == "horizontal":
                # Rotação em torno do eixo horizontal (X)
                # Calcula os pontos de origem e destino para a transformação de perspectiva
                src_points = np.array([
                    [0, 0],           # Canto superior esquerdo
                    [width - 1, 0],   # Canto superior direito
                    [width - 1, height - 1],  # Canto inferior direito
                    [0, height - 1]   # Canto inferior esquerdo
                ], dtype=np.float32)
                
                # Calcula a escala baseada no ângulo
                scale_y = abs(np.cos(np.radians(angle)))
                
                # Calcula os pontos de destino com distorção de perspectiva
                if angle > 0:  # Rotacionando para cima
                    dst_points = np.array([
                        [0, height * (1 - scale_y) / 2],
                        [width - 1, height * (1 - scale_y) / 2],
                        [width - 1, height - height * (1 - scale_y) / 2],
                        [0, height - height * (1 - scale_y) / 2]
                    ], dtype=np.float32)
                else:  # Rotacionando para baixo
                    dst_points = np.array([
                        [0, height * (1 - scale_y) / 2],
                        [width - 1, height * (1 - scale_y) / 2],
                        [width - 1, height - height * (1 - scale_y) / 2],
                        [0, height - height * (1 - scale_y) / 2]
                    ], dtype=np.float32)
            else:  # "vertical"
                # Rotação em torno do eixo vertical (Y)
                # Calcula os pontos de origem e destino para a transformação de perspectiva
                src_points = np.array([
                    [0, 0],           # Canto superior esquerdo
                    [width - 1, 0],   # Canto superior direito
                    [width - 1, height - 1],  # Canto inferior direito
                    [0, height - 1]   # Canto inferior esquerdo
                ], dtype=np.float32)
                
                # Calcula a escala baseada no ângulo
                scale_x = abs(np.cos(np.radians(angle)))
                
                # Calcula os pontos de destino com distorção de perspectiva
                if angle > 0:  # Rotacionando para a esquerda
                    dst_points = np.array([
                        [width * (1 - scale_x) / 2, 0],
                        [width - width * (1 - scale_x) / 2, 0],
                        [width - width * (1 - scale_x) / 2, height - 1],
                        [width * (1 - scale_x) / 2, height - 1]
                    ], dtype=np.float32)
                else:  # Rotacionando para a direita
                    dst_points = np.array([
                        [width * (1 - scale_x) / 2, 0],
                        [width - width * (1 - scale_x) / 2, 0],
                        [width - width * (1 - scale_x) / 2, height - 1],
                        [width * (1 - scale_x) / 2, height - 1]
                    ], dtype=np.float32)
            
            # Ajusta a força da perspectiva
            dst_points = src_points + (dst_points - src_points) * perspective_strength
            
            # Escolhe a imagem a ser exibida com base no progresso
            if progress < 0.5:
                # Primeira metade da transição: mostra a primeira imagem rotacionando
                img_to_transform = img1_np.copy()
                # Ajusta o progresso para ir de 0 a 1 durante a primeira metade
                transform_progress = progress * 2
            else:
                # Segunda metade da transição: mostra a segunda imagem rotacionando de volta
                img_to_transform = img2_np.copy()
                # Ajusta o progresso para ir de 1 a 0 durante a segunda metade
                transform_progress = 2 - progress * 2
            
            # Calcula a matriz de transformação de perspectiva
            if progress < 0.5:
                # Para a primeira imagem
                transform_matrix = cv2.getPerspectiveTransform(src_points, dst_points)
            else:
                # Para a segunda imagem, inverte a transformação
                transform_matrix = cv2.getPerspectiveTransform(dst_points, src_points)
            
            # Aplica a transformação de perspectiva
            warped_img = cv2.warpPerspective(img_to_transform, transform_matrix, (width, height))
            
            # Converte para imagem PIL
            frame = Image.fromarray(warped_img)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.5 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.03 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_special_transition(self, img1, img2, output_dir, num_frames, transition_type, **kwargs):
        """Gera transições especiais como bounce, spin, flip, glitch e pixelate.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            transition_type: Tipo de transição ("bounce", "spin", "flip", "glitch", "pixelate", "blur")
            **kwargs: Parâmetros adicionais para o efeito
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
                - direction: Direção do efeito ("horizontal", "vertical", "diagonal")
                - bounce_height: Altura do salto para o efeito bounce (0.0 a 1.0)
                - spin_rotations: Número de rotações para o efeito spin
                - glitch_intensity: Intensidade do efeito glitch (0.0 a 1.0)
                - pixelate_max: Tamanho máximo dos pixels para o efeito pixelate
                - blur_max: Intensidade máxima do desfoque para o efeito blur
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        logger.info(f"Gerando transição especial: {transition_type}")
        
        # Parâmetros comuns
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        direction = kwargs.get("direction", "horizontal")
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Seleciona o tipo de transição
        if transition_type == "bounce":
            frame_paths = self._generate_bounce_transition(img1, img2, output_dir, num_frames, **kwargs)
        elif transition_type == "spin":
            frame_paths = self._generate_spin_transition(img1, img2, output_dir, num_frames, **kwargs)
        elif transition_type == "flip":
            frame_paths = self._generate_flip_transition(img1, img2, output_dir, num_frames, **kwargs)
        elif transition_type == "glitch":
            frame_paths = self._generate_glitch_transition(img1, img2, output_dir, num_frames, **kwargs)
        elif transition_type == "pixelate":
            frame_paths = self._generate_pixelate_transition(img1, img2, output_dir, num_frames, **kwargs)
        elif transition_type == "blur":
            frame_paths = self._generate_blur_transition(img1, img2, output_dir, num_frames, **kwargs)
        else:
            logger.warning(f"Tipo de transição especial desconhecido: {transition_type}. Usando fade como fallback.")
            # Usa uma transição de fade como fallback
            return self._generate_fade_transition(img1, img2, output_dir, num_frames, **kwargs)
        
        return frame_paths
    
    def _generate_fade_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição de fade entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
                - is_children_content: Se True, adapta efeitos para conteúdo infantil
                - acceleration: Tipo de aceleração ("ease-in-out", "ease-in", "ease-out")
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        logger.info("Gerando transição de fade")
        
        # Parâmetros do efeito
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Aplica uma curva de aceleração para tornar a transição mais natural
            if kwargs.get("acceleration", "ease-in-out") == "ease-in-out":
                progress = 0.5 * (1 - np.cos(np.pi * progress))
            elif kwargs.get("acceleration", "") == "ease-in":
                progress = progress * progress
            elif kwargs.get("acceleration", "") == "ease-out":
                progress = 1 - (1 - progress) * (1 - progress)
            
            # Mistura as imagens com base no progresso
            frame = Image.blend(img1, img2, progress)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.02 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_slide_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição de slide entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - direction: Direção do slide ("left", "right", "up", "down")
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
                - is_children_content: Se True, adapta efeitos para conteúdo infantil
                - acceleration: Tipo de aceleração ("ease-in-out", "ease-in", "ease-out")
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        direction = kwargs.get("direction", "left")  # Direção do slide
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        logger.info(f"Gerando transição de slide na direção: {direction}")
        
        # Dimensões da imagem
        width, height = img1.size
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Aplica uma curva de aceleração para tornar a transição mais natural
            if kwargs.get("acceleration", "ease-in-out") == "ease-in-out":
                progress = 0.5 * (1 - np.cos(np.pi * progress))
            elif kwargs.get("acceleration", "") == "ease-in":
                progress = progress * progress
            elif kwargs.get("acceleration", "") == "ease-out":
                progress = 1 - (1 - progress) * (1 - progress)
            
            # Cria uma nova imagem para o frame
            frame = Image.new("RGB", (width, height))
            
            # Calcula as posições das imagens com base na direção
            if direction == "left":
                # Primeira imagem desliza para a esquerda, segunda vem da direita
                x1 = int(-width * progress)
                x2 = int(width * (1 - progress))
                frame.paste(img1, (x1, 0))
                frame.paste(img2, (x2, 0))
            elif direction == "right":
                # Primeira imagem desliza para a direita, segunda vem da esquerda
                x1 = int(width * progress)
                x2 = int(-width * (1 - progress))
                frame.paste(img1, (x1, 0))
                frame.paste(img2, (x2, 0))
            elif direction == "up":
                # Primeira imagem desliza para cima, segunda vem de baixo
                y1 = int(-height * progress)
                y2 = int(height * (1 - progress))
                frame.paste(img1, (0, y1))
                frame.paste(img2, (0, y2))
            elif direction == "down":
                # Primeira imagem desliza para baixo, segunda vem de cima
                y1 = int(height * progress)
                y2 = int(-height * (1 - progress))
                frame.paste(img1, (0, y1))
                frame.paste(img2, (0, y2))
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.02 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_bounce_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição com efeito de salto (bounce) entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - bounce_height: Altura máxima do salto (0.0 a 1.0)
                - direction: Direção do salto ("up", "down", "left", "right")
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        bounce_height = kwargs.get("bounce_height", 0.3)  # Altura máxima do salto
        direction = kwargs.get("direction", "up")  # Direção do salto
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Converte para arrays numpy para manipulação
        img1_np = np.array(img1)
        img2_np = np.array(img2)
        
        # Dimensões da imagem
        height, width = img1_np.shape[:2]
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Primeira metade: primeira imagem sai
            # Segunda metade: segunda imagem entra
            if progress < 0.5:
                # Normaliza o progresso para a primeira metade (0 a 1)
                norm_progress = progress * 2
                
                # Aplica uma curva para o efeito de salto (parábola)
                # y = 4 * h * x * (1-x) onde h é a altura máxima
                bounce_offset = 4 * bounce_height * norm_progress * (1 - norm_progress)
                
                # Cria uma cópia da primeira imagem para manipulação
                frame_np = img1_np.copy()
                
                # Aplica a transformação de acordo com a direção
                transform_matrix = np.eye(2, 3, dtype=np.float32)  # Matriz identidade
                
                if direction == "up" or direction == "down":
                    # Movimento vertical
                    offset_y = int(height * bounce_offset) * (-1 if direction == "up" else 1)
                    transform_matrix[1, 2] = offset_y  # Translada verticalmente
                else:  # "left" ou "right"
                    # Movimento horizontal
                    offset_x = int(width * bounce_offset) * (-1 if direction == "left" else 1)
                    transform_matrix[0, 2] = offset_x  # Translada horizontalmente
                
                # Aplica a transformação
                frame_np = cv2.warpAffine(frame_np, transform_matrix, (width, height))
                
                # Aplica fade-out gradual
                alpha = 1.0 - norm_progress
                frame_np = cv2.addWeighted(frame_np, alpha, np.zeros_like(frame_np), 0, 0)
            else:
                # Normaliza o progresso para a segunda metade (0 a 1)
                norm_progress = (progress - 0.5) * 2
                
                # Aplica uma curva para o efeito de salto (parábola invertida)
                # y = 4 * h * (1-x) * x onde h é a altura máxima
                bounce_offset = 4 * bounce_height * (1 - norm_progress) * norm_progress
                
                # Cria uma cópia da segunda imagem para manipulação
                frame_np = img2_np.copy()
                
                # Aplica a transformação de acordo com a direção
                transform_matrix = np.eye(2, 3, dtype=np.float32)  # Matriz identidade
                
                if direction == "up" or direction == "down":
                    # Movimento vertical
                    offset_y = int(height * bounce_offset) * (1 if direction == "up" else -1)
                    transform_matrix[1, 2] = offset_y  # Translada verticalmente
                else:  # "left" ou "right"
                    # Movimento horizontal
                    offset_x = int(width * bounce_offset) * (1 if direction == "left" else -1)
                    transform_matrix[0, 2] = offset_x  # Translada horizontalmente
                
                # Aplica a transformação
                frame_np = cv2.warpAffine(frame_np, transform_matrix, (width, height))
                
                # Aplica fade-in gradual
                alpha = norm_progress
                frame_np = cv2.addWeighted(frame_np, alpha, np.zeros_like(frame_np), 0, 0)
            
            # Converte para imagem PIL
            frame = Image.fromarray(frame_np)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * bounce_offset
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.02 * bounce_offset,
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_spin_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição com efeito de rotação (spin) entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - spin_rotations: Número de rotações completas
                - direction: Direção da rotação ("clockwise" ou "counterclockwise")
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        spin_rotations = kwargs.get("spin_rotations", 1.0)  # Número de rotações completas
        direction = kwargs.get("direction", "clockwise")  # Direção da rotação
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Converte para arrays numpy para manipulação
        img1_np = np.array(img1)
        img2_np = np.array(img2)
        
        # Dimensões da imagem
        height, width = img1_np.shape[:2]
        
        # Centro da imagem
        center = (width // 2, height // 2)
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Calcula o ângulo de rotação
            angle = progress * spin_rotations * 360.0
            if direction == "counterclockwise":
                angle = -angle
            
            # Primeira metade: primeira imagem roda e desaparece
            # Segunda metade: segunda imagem aparece e roda
            if progress < 0.5:
                # Normaliza o progresso para a primeira metade (0 a 1)
                norm_progress = progress * 2
                
                # Cria uma cópia da primeira imagem para manipulação
                frame_np = img1_np.copy()
                
                # Cria a matriz de rotação
                rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0 - norm_progress * 0.5)
                
                # Aplica a rotação
                frame_np = cv2.warpAffine(frame_np, rotation_matrix, (width, height))
                
                # Aplica fade-out gradual
                alpha = 1.0 - norm_progress
                frame_np = cv2.addWeighted(frame_np, alpha, np.zeros_like(frame_np), 0, 0)
            else:
                # Normaliza o progresso para a segunda metade (0 a 1)
                norm_progress = (progress - 0.5) * 2
                
                # Cria uma cópia da segunda imagem para manipulação
                frame_np = img2_np.copy()
                
                # Calcula o ângulo para a segunda imagem
                # Continua a partir do ângulo da primeira imagem
                second_angle = angle - (spin_rotations * 360.0 / 2)
                
                # Cria a matriz de rotação
                rotation_matrix = cv2.getRotationMatrix2D(center, second_angle, 0.5 + norm_progress * 0.5)
                
                # Aplica a rotação
                frame_np = cv2.warpAffine(frame_np, rotation_matrix, (width, height))
                
                # Aplica fade-in gradual
                alpha = norm_progress
                frame_np = cv2.addWeighted(frame_np, alpha, np.zeros_like(frame_np), 0, 0)
            
            # Converte para imagem PIL
            frame = Image.fromarray(frame_np)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.03 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_flip_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição com efeito de virada (flip) entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - direction: Direção da virada ("horizontal" ou "vertical")
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        direction = kwargs.get("direction", "horizontal")  # Direção da virada
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Converte para arrays numpy para manipulação
        img1_np = np.array(img1)
        img2_np = np.array(img2)
        
        # Dimensões da imagem
        height, width = img1_np.shape[:2]
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Aplica uma curva de aceleração para tornar a transição mais natural
            ease_progress = 0.5 * (1 - np.cos(np.pi * progress))
            
            # Prepara a matriz de transformação
            if direction == "horizontal":
                # Virada horizontal
                # Escala no eixo X vai de 1 a 0 e depois de 0 a 1
                if progress < 0.5:
                    # Primeira metade: primeira imagem diminui até desaparecer
                    scale_x = 1.0 - 2.0 * progress
                    img_to_transform = img1_np.copy()
                else:
                    # Segunda metade: segunda imagem aparece e cresce
                    scale_x = 2.0 * progress - 1.0
                    img_to_transform = img2_np.copy()
                
                # Cria a matriz de transformação
                transform_matrix = np.array([
                    [scale_x, 0, width * (1.0 - scale_x) / 2],
                    [0, 1, 0]
                ], dtype=np.float32)
            else:  # "vertical"
                # Virada vertical
                # Escala no eixo Y vai de 1 a 0 e depois de 0 a 1
                if progress < 0.5:
                    # Primeira metade: primeira imagem diminui até desaparecer
                    scale_y = 1.0 - 2.0 * progress
                    img_to_transform = img1_np.copy()
                else:
                    # Segunda metade: segunda imagem aparece e cresce
                    scale_y = 2.0 * progress - 1.0
                    img_to_transform = img2_np.copy()
                
                # Cria a matriz de transformação
                transform_matrix = np.array([
                    [1, 0, 0],
                    [0, scale_y, height * (1.0 - scale_y) / 2]
                ], dtype=np.float32)
            
            # Aplica a transformação
            frame_np = cv2.warpAffine(img_to_transform, transform_matrix, (width, height))
            
            # Converte para imagem PIL
            frame = Image.fromarray(frame_np)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.03 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_glitch_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição com efeito de glitch entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - glitch_intensity: Intensidade do efeito glitch (0.0 a 1.0)
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        glitch_intensity = kwargs.get("glitch_intensity", 0.5)  # Intensidade do glitch
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Converte para arrays numpy para manipulação
        img1_np = np.array(img1)
        img2_np = np.array(img2)
        
        # Dimensões da imagem
        height, width = img1_np.shape[:2]
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Intensidade do glitch varia durante a transição
            # Máxima no meio da transição
            current_intensity = glitch_intensity * (1.0 - abs(2.0 * progress - 1.0))
            
            # Mistura as imagens com base no progresso
            alpha = progress
            frame_np = cv2.addWeighted(img1_np, 1.0 - alpha, img2_np, alpha, 0)
            
            # Aplica o efeito de glitch
            if current_intensity > 0:
                # Número de distorções baseado na intensidade
                num_glitches = int(10 * current_intensity)
                
                # Aplica várias distorções aleatórias
                for _ in range(num_glitches):
                    # Seleciona um canal de cor aleatório para distorcer
                    channel = random.randint(0, 2)  # R, G ou B
                    
                    # Seleciona uma linha aleatória para distorcer
                    y = random.randint(0, height - 1)
                    
                    # Altura da faixa de distorção
                    glitch_height = random.randint(1, int(10 * current_intensity))
                    
                    # Limita a altura para não ultrapassar a imagem
                    if y + glitch_height >= height:
                        glitch_height = height - y - 1
                    
                    # Deslocamento horizontal aleatório
                    shift = random.randint(-int(width * current_intensity / 3), 
                                          int(width * current_intensity / 3))
                    
                    # Aplica o deslocamento
                    if shift > 0:
                        # Desloca para a direita
                        frame_np[y:y+glitch_height, shift:, channel] = \
                            frame_np[y:y+glitch_height, :-shift, channel]
                    elif shift < 0:
                        # Desloca para a esquerda
                        frame_np[y:y+glitch_height, :shift, channel] = \
                            frame_np[y:y+glitch_height, -shift:, channel]
                
                # Adiciona ruído aleatório
                noise = np.random.normal(0, 20 * current_intensity, frame_np.shape).astype(np.int8)
                frame_np = np.clip(frame_np.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            
            # Converte para imagem PIL
            frame = Image.fromarray(frame_np)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.2 * current_intensity
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.02 * current_intensity,
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_pixelate_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição com efeito de pixelização entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - pixelate_max: Tamanho máximo dos pixels (maior = mais pixelizado)
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        pixelate_max = kwargs.get("pixelate_max", 30)  # Tamanho máximo dos pixels
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Dimensões da imagem
        width, height = img1.size
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Curva de pixelização: aumenta até o meio, depois diminui
            if progress < 0.5:
                # Primeira metade: aumenta a pixelização
                pixelate_size = int(pixelate_max * (progress * 2))
                # Usa a primeira imagem
                img_to_pixelate = img1
            else:
                # Segunda metade: diminui a pixelização
                pixelate_size = int(pixelate_max * (2 - progress * 2))
                # Usa a segunda imagem
                img_to_pixelate = img2
            
            # Garante que o tamanho mínimo é 1
            pixelate_size = max(1, pixelate_size)
            
            # Aplica o efeito de pixelização
            # Redimensiona para baixo e depois para cima para criar o efeito
            small = img_to_pixelate.resize(
                (width // pixelate_size, height // pixelate_size),
                resample=Image.BILINEAR
            )
            frame = small.resize((width, height), resample=Image.NEAREST)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.02 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _generate_blur_transition(self, img1, img2, output_dir, num_frames, **kwargs):
        """Gera uma transição com efeito de desfoque entre duas imagens.
        
        Args:
            img1: Imagem PIL da primeira cena
            img2: Imagem PIL da segunda cena
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            **kwargs: Parâmetros adicionais para o efeito
                - blur_max: Raio máximo do desfoque
                - sparkle_effect: Se True, adiciona sparkles à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
        
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        # Parâmetros do efeito
        blur_max = kwargs.get("blur_max", 20)  # Raio máximo do desfoque
        sparkle_effect = kwargs.get("sparkle_effect", False)
        brightness_effect = kwargs.get("brightness_effect", False)
        is_children_content = kwargs.get("is_children_content", False)
        
        # Lista para armazenar os caminhos dos frames
        frame_paths = []
        
        # Gera os frames da transição
        for i in range(num_frames):
            # Calcula o progresso da transição
            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
            
            # Curva de desfoque: aumenta até o meio, depois diminui
            if progress < 0.5:
                # Primeira metade: aumenta o desfoque na primeira imagem
                blur_radius = int(blur_max * (progress * 2))
                # Usa a primeira imagem
                img_to_blur = img1.copy()
                # Aplica o desfoque
                frame = img_to_blur.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                # Mistura com a imagem original para um efeito mais suave
                alpha = progress * 2
                frame = Image.blend(img_to_blur, frame, alpha)
            else:
                # Segunda metade: diminui o desfoque na segunda imagem
                blur_radius = int(blur_max * (2 - progress * 2))
                # Usa a segunda imagem
                img_to_blur = img2.copy()
                # Aplica o desfoque
                blurred = img_to_blur.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                # Mistura com a imagem original para um efeito mais suave
                alpha = 2 - progress * 2
                frame = Image.blend(img_to_blur, blurred, alpha)
            
            # Aplica efeito de brilho se solicitado
            if brightness_effect:
                # Cria um enhancer de brilho
                enhancer = ImageEnhance.Brightness(frame)
                # Calcula o fator de brilho (mais brilhante no meio da transição)
                brightness_factor = 1.0 + 0.3 * (1.0 - abs(2.0 * progress - 1.0))
                # Aplica o brilho
                frame = enhancer.enhance(brightness_factor)
            
            # Aplica efeito de sparkle se solicitado
            if sparkle_effect:
                frame = self._add_sparkle_effect(
                    frame, 
                    progress,
                    sparkle_density=0.02 * (1.0 - abs(2.0 * progress - 1.0)),
                    color_theme="rainbow" if is_children_content else "vibrant",
                    **kwargs
                )
            
            # Salva o frame
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)
            frame_paths.append(frame_path)
        
        return frame_paths
    
    def _stability_generate_morph_frames(self, source_image1, source_image2, output_dir, num_frames, quality, seed=None, **kwargs):
        """Gera frames de morphing usando a API da Stability AI.
        
        Args:
            source_image1: Caminho para a primeira imagem
            source_image2: Caminho para a segunda imagem
            output_dir: Diretório para salvar os frames
            num_frames: Número de frames a gerar
            quality: Qualidade do morphing
            seed: Seed para consistência
            
        Returns:
            List[str]: Lista de caminhos para os frames gerados
        """
        try:
            # Configuração da API da Stability
            api_host = kwargs.get('api_host', 'https://api.stability.ai')
            api_endpoint = f"{api_host}/v1/generation/image-to-image/morph"
            
            # Prepara as imagens para envio
            with open(source_image1, "rb") as f1, open(source_image2, "rb") as f2:
                source_image1_data = base64.b64encode(f1.read()).decode('utf-8')
                source_image2_data = base64.b64encode(f2.read()).decode('utf-8')
            
            # Mapeia a qualidade para os parâmetros da API
            quality_map = {
                "low": {"steps": 15, "cfg_scale": 7.0},
                "medium": {"steps": 30, "cfg_scale": 7.5},
                "high": {"steps": 50, "cfg_scale": 8.0}
            }
            
            api_params = quality_map.get(quality, quality_map["medium"])
            
            # Adiciona parâmetros adicionais
            if seed is not None:
                api_params["seed"] = seed
            
            # Prepara o payload da requisição
            payload = {
                "source_image_1": source_image1_data,
                "source_image_2": source_image2_data,
                "num_frames": num_frames,
                **api_params,
                **kwargs
            }
            
            # Cabeçalhos da requisição
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Faz a requisição à API
            logger.info(f"Enviando requisição para a API da Stability AI")
            response = requests.post(api_endpoint, headers=headers, json=payload)
            
            # Verifica se a requisição foi bem-sucedida
            if response.status_code == 200:
                # Processa a resposta
                result = response.json()
                frame_paths = []
                
                # Salva os frames recebidos
                for i, frame_data in enumerate(result.get("frames", [])):
                    # Decodifica a imagem de base64
                    image_data = base64.b64decode(frame_data)
                    frame = Image.open(BytesIO(image_data))
                    
                    # Salva o frame
                    frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
                    frame.save(frame_path)
                    frame_paths.append(frame_path)
                
                return frame_paths
            else:
                logger.error(f"Erro na API da Stability: {response.status_code} - {response.text}")
                # Fallback para interpolação simples
                return []
                
        except Exception as e:
            logger.error(f"Erro ao usar API da Stability para morphing: {str(e)}")
            return []
    def generate_scene_transition(self, scene1_image, scene2_image, output_path, 
                                  transition_type="fade", duration=1.5, fps=24, **kwargs):
        """Gera uma transição entre duas cenas.
        
        Args:
            scene1_image: Caminho para a imagem da primeira cena
            scene2_image: Caminho para a imagem da segunda cena
            output_path: Caminho para salvar a transição gerada
            transition_type: Tipo de transição (fade, dissolve, wipe, etc.)
            duration: Duração da transição em segundos
            fps: Frames por segundo
            **kwargs: Parâmetros adicionais para a API
                - is_children_content: Se True, aplica efeitos especiais para conteúdo infantil
                - sparkle_effect: Se True, adiciona efeito de brilhos/estrelas à transição
                - brightness_effect: Se True, adiciona efeito de brilho à transição
                - color_theme: Tema de cores para os efeitos ("rainbow", "pastel", "vibrant")
                - character_focus: Nome do personagem em foco para efeitos personalizados
            
        Returns:
            bool: True se a transição foi gerada com sucesso, False caso contrário
        """
        logger.info(f"Gerando transição entre cenas: {transition_type}")
        
        # Verifica se as imagens de origem existem
        if not os.path.exists(scene1_image) or not os.path.exists(scene2_image):
            logger.error(f"Imagens de origem não encontradas: {scene1_image} ou {scene2_image}")
            return False
        
        # Cria o diretório de saída se não existir
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Verifica se a transição já existe no cache
        if self.cache_enabled:
            cache_key = self._get_cache_key([scene1_image, scene2_image], f"transition_{transition_type}", kwargs)
            if cache_key in self.animation_cache:
                cached_path = self.animation_cache[cache_key]
                if os.path.exists(cached_path):
                    logger.info(f"Usando transição em cache: {cached_path}")
                    # Copia a transição em cache para o caminho de saída
                    shutil.copy2(cached_path, output_path)
                    return True
        
        # Tipos de transição avançada que requerem processamento especial
        advanced_transitions = [
            "wipe_right", "wipe_left", "wipe_up", "wipe_down", 
            "zoom", "morph", "rotate3d", "page_turn", "dissolve", 
            "slide_right", "slide_left", "slide_up", "slide_down",
            "bounce", "spin", "flip", "glitch", "pixelate", "blur"
        ]
        
        # Se for um tipo avançado, usa processamento especial
        if transition_type.lower() in advanced_transitions:
            try:
                # Carrega as imagens de origem
                img1 = Image.open(scene1_image).convert('RGBA')
                img2 = Image.open(scene2_image).convert('RGBA')
                
                # Garante que ambas as imagens tenham o mesmo tamanho
                if img1.size != img2.size:
                    # Redimensiona a segunda imagem para corresponder à primeira
                    img2 = img2.resize(img1.size, Image.LANCZOS)
                
                # Cria um diretório temporário para os frames
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Calcula o número total de frames
                    num_frames = int(duration * fps)
                    
                    # Gera os frames da transição com base no tipo selecionado
                    if transition_type.lower() == "wipe_right":
                        # Transição de wipe da esquerda para a direita
                        width, height = img1.size
                        for i in range(num_frames):
                            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                            # Calcula a posição do corte
                            cut_pos = int(width * progress)
                            
                            # Cria uma nova imagem
                            frame = Image.new('RGBA', img1.size)
                            # Cola a parte da primeira imagem
                            frame.paste(img1.crop((0, 0, cut_pos, height)), (0, 0))
                            # Cola a parte da segunda imagem
                            frame.paste(img2.crop((cut_pos, 0, width, height)), (cut_pos, 0))
                            
                            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                            frame.save(frame_path)
                    
                    elif transition_type.lower() == "wipe_left":
                        # Transição de wipe da direita para a esquerda
                        width, height = img1.size
                        for i in range(num_frames):
                            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                            # Calcula a posição do corte
                            cut_pos = int(width * (1 - progress))
                            
                            # Cria uma nova imagem
                            frame = Image.new('RGBA', img1.size)
                            # Cola a parte da primeira imagem
                            frame.paste(img1.crop((cut_pos, 0, width, height)), (cut_pos, 0))
                            # Cola a parte da segunda imagem
                            frame.paste(img2.crop((0, 0, cut_pos, height)), (0, 0))
                            
                            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                            frame.save(frame_path)
                    
                    elif transition_type.lower() == "wipe_up":
                        # Transição de wipe de baixo para cima
                        width, height = img1.size
                        for i in range(num_frames):
                            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                            # Calcula a posição do corte
                            cut_pos = int(height * (1 - progress))
                            
                            # Cria uma nova imagem
                            frame = Image.new('RGBA', img1.size)
                            # Cola a parte da primeira imagem
                            frame.paste(img1.crop((0, cut_pos, width, height)), (0, cut_pos))
                            # Cola a parte da segunda imagem
                            frame.paste(img2.crop((0, 0, width, cut_pos)), (0, 0))
                            
                            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                            frame.save(frame_path)
                    
                    elif transition_type.lower() == "wipe_down":
                        # Transição de wipe de cima para baixo
                        width, height = img1.size
                        for i in range(num_frames):
                            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                            # Calcula a posição do corte
                            cut_pos = int(height * progress)
                            
                            # Cria uma nova imagem
                            frame = Image.new('RGBA', img1.size)
                            # Cola a parte da primeira imagem
                            frame.paste(img1.crop((0, 0, width, cut_pos)), (0, 0))
                            # Cola a parte da segunda imagem
                            frame.paste(img2.crop((0, cut_pos, width, height)), (0, cut_pos))
                            
                            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                            frame.save(frame_path)
                    
                    elif transition_type.lower() == "zoom":
                        # Transição de zoom out da primeira imagem e zoom in na segunda
                        width, height = img1.size
                        for i in range(num_frames):
                            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                            
                            if progress < 0.5:
                                # Primeira metade: zoom out da primeira imagem
                                zoom_progress = 1.0 - (progress * 2)  # 1.0 -> 0.0
                                zoom_size = (int(width * zoom_progress), int(height * zoom_progress))
                                
                                # Redimensiona a imagem
                                zoomed = img1.resize(zoom_size, Image.LANCZOS)
                                
                                # Cria uma nova imagem e centraliza a imagem redimensionada
                                frame = Image.new('RGBA', img1.size, (0, 0, 0, 255))
                                paste_x = (width - zoom_size[0]) // 2
                                paste_y = (height - zoom_size[1]) // 2
                                frame.paste(zoomed, (paste_x, paste_y))
                            else:
                                # Segunda metade: zoom in da segunda imagem
                                zoom_progress = (progress - 0.5) * 2  # 0.0 -> 1.0
                                zoom_size = (int(width * zoom_progress), int(height * zoom_progress))
                                
                                # Redimensiona a imagem
                                zoomed = img2.resize(zoom_size, Image.LANCZOS)
                                
                                # Cria uma nova imagem e centraliza a imagem redimensionada
                                frame = Image.new('RGBA', img1.size, (0, 0, 0, 255))
                                paste_x = (width - zoom_size[0]) // 2
                                paste_y = (height - zoom_size[1]) // 2
                                frame.paste(zoomed, (paste_x, paste_y))
                            
                            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                            frame.save(frame_path)
                    
                    elif transition_type.lower() == "morph":
                        # Verifica se temos acesso à API para morphing de alta qualidade
                        if self.api_key and kwargs.get("use_api", True):
                            # Em uma implementação real, aqui chamaria a API
                            # Por enquanto, vamos usar o método de morphing local avançado
                            morph_frames = self.generate_morph_frames(
                                scene1_image, 
                                scene2_image, 
                                num_frames=num_frames, 
                                quality=kwargs.get("morph_quality", "high"),
                                seed=kwargs.get("seed", None),
                                **kwargs
                            )
                            
                            # Se temos frames gerados, vamos usá-los
                            if morph_frames:
                                for i, frame_path in enumerate(morph_frames):
                                    dest_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                                    shutil.copy2(frame_path, dest_path)
                        
                        # Fallback: Morphing local básico
                        for i in range(num_frames):
                            progress = i / (num_frames - 1) if num_frames > 1 else 1.0
                            
                            # Aplica uma curva de aceleração para tornar o morphing mais natural
                            if kwargs.get("acceleration", "ease-in-out") == "ease-in-out":
                                progress = 0.5 * (1 - np.cos(np.pi * progress))
                            elif kwargs.get("acceleration", "") == "ease-in":
                                progress = progress * progress
                            elif kwargs.get("acceleration", "") == "ease-out":
                                progress = 1 - (1 - progress) * (1 - progress)
                            
                            # Blend entre as imagens
                            frame = Image.blend(img1, img2, progress)
                            
                            # Adiciona alguma distorção para simular morphing
                            if 0.25 < progress < 0.75:
                                # Converte para array numpy para manipulação
                                frame_array = np.array(frame)
                                
                                # Aplica uma distorção mais sofisticada
                                distortion = np.sin(progress * np.pi) * 0.1
                                rows, cols = frame_array.shape[:2]
                                
                                # Cria uma grade de distorção
                                x = np.arange(cols)
                                y = np.arange(rows)
                                x_grid, y_grid = np.meshgrid(x, y)
                                
                                # Aplica distorção baseada em seno
                                if kwargs.get("morph_quality", "medium") == "high":
                                    x_offset = distortion * np.sin(y_grid / rows * np.pi) * 20
                                    y_offset = distortion * np.sin(x_grid / cols * np.pi) * 20
                                    
                                    # Aplica distorção mais complexa
                                    for c in range(min(3, frame_array.shape[2])):
                                        frame_array[:,:,c] = np.roll(frame_array[:,:,c], int(distortion * 10), axis=1)
                                else:
                                    # Distorção simples
                                    frame_array = np.roll(frame_array, int(distortion * 10), axis=1)
                                
                                # Adiciona efeito de cor para conteúdo infantil
                                if kwargs.get("is_children_content", False) and kwargs.get("color_shift", False):
                                    # Ajusta as cores para tornar mais vibrante
                                    hsv = cv2.cvtColor(frame_array, cv2.COLOR_RGB2HSV).astype(np.float32)
                                    # Aumenta a saturação
                                    hsv[:,:,1] = hsv[:,:,1] * (1.0 + 0.3 * np.sin(progress * np.pi))
                                    # Ajusta o matiz sutilmente
                                    hsv[:,:,0] = (hsv[:,:,0] + 10 * np.sin(progress * np.pi)) % 180
                                    # Converte de volta para RGB
                                    frame_array = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
                                
                                # Converte de volta para imagem
                                frame = Image.fromarray(frame_array)
                            
                            # Adiciona efeitos especiais para conteúdo infantil
                            if kwargs.get("is_children_content", False) and kwargs.get("sparkle_effect", False):
                                # Adiciona sparkles/estrelas
                                frame = self._add_sparkle_effect(frame, progress, **kwargs)
                            
                            frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                            frame.save(frame_path)
                    
                    # Usa FFmpeg para combinar os frames em um vídeo
                    frames_pattern = os.path.join(temp_dir, "frame_%04d.png")
                    import subprocess
                    ffmpeg_cmd = [
                        'ffmpeg', '-y',
                        '-r', str(fps),
                        '-i', frames_pattern,
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        '-crf', '23',
                        output_path
                    ]
                    
                    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                    
                    if os.path.exists(output_path):
                        logger.info(f"Transição avançada gerada com sucesso: {output_path}")
                        
                        # Salva metadados da transição
                        transition_info = {
                            "type": transition_type,
                            "duration": duration,
                            "fps": fps,
                            "source_images": [scene1_image, scene2_image],
                            "created_at": time.time(),
                            "parameters": kwargs
                        }
                        
                        # Atualiza o cache
                        if self.cache_enabled:
                            cache_key = self._get_cache_key([scene1_image, scene2_image], 
                                                          f"transition_{transition_type}", kwargs)
                            cache_path = os.path.join(self.cache_dir, f"transition_{hash(cache_key)}.mp4")
                            shutil.copy2(output_path, cache_path)
                            
                            self.animation_cache[cache_key] = cache_path
                            self.animation_metadata[cache_key] = transition_info
                            self._save_cache()
                        
                        return True
                    else:
                        logger.error(f"Falha ao gerar transição avançada: {output_path}")
                        return False
                    
            except Exception as e:
                logger.error(f"Erro ao gerar transição avançada: {str(e)}")
                logger.warning("Tentando gerar transição simples como fallback...")
                # Continua para o método padrão abaixo
        
        # Implementa transições adicionais
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Carrega as imagens
                img1 = Image.open(scene1_image).convert('RGBA')
                img2 = Image.open(scene2_image).convert('RGBA')
                
                # Garante que ambas as imagens tenham o mesmo tamanho
                if img1.size != img2.size:
                    img2 = img2.resize(img1.size, Image.LANCZOS)
                
                # Número de frames
                num_frames = int(duration * fps)
                frame_paths = []
                
                # Implementa transições específicas para conteúdo infantil
                if transition_type.lower() == "page_turn":
                    # Implementa transição de página virando
                    frame_paths = self._generate_page_turn_transition(
                        img1, img2, temp_dir, num_frames, 
                        turn_direction=kwargs.get("turn_direction", "left-to-right"),
                        shadow_intensity=kwargs.get("shadow_intensity", 0.5),
                        page_curve=kwargs.get("page_curve", 0.3),
                        sparkle_effect=kwargs.get("sparkle_effect", False),
                        brightness_effect=kwargs.get("brightness_effect", False),
                        is_children_content=kwargs.get("is_children_content", False),
                        **kwargs
                    )
                elif transition_type.lower() == "rotate3d":
                    # Implementa transição de rotação 3D
                    frame_paths = self._generate_rotate3d_transition(
                        img1, img2, temp_dir, num_frames,
                        rotation_angle=kwargs.get("rotation_angle", 180),
                        rotation_axis=kwargs.get("rotation_axis", "y"),
                        perspective=kwargs.get("perspective", 0.0008),
                        **kwargs
                    )
                elif transition_type.lower() in ["bounce", "spin", "flip", "glitch", "pixelate", "blur"]:
                    # Implementa transições especiais para conteúdo infantil
                    frame_paths = self._generate_special_transition(
                        img1, img2, temp_dir, num_frames, transition_type.lower(), **kwargs
                    )
                elif transition_type.lower() == "fade" or transition_type.lower() == "dissolve":
                    # Implementa transição de fade/dissolve
                    frame_paths = self._generate_fade_transition(
                        img1, img2, temp_dir, num_frames,
                        sparkle_effect=kwargs.get("sparkle_effect", False),
                        brightness_effect=kwargs.get("brightness_effect", False),
                        is_children_content=kwargs.get("is_children_content", False),
                        **kwargs
                    )
                elif transition_type.lower().startswith("slide"):
                    # Extrai a direção do tipo de transição (slide_right, slide_left, etc.)
                    direction = transition_type.lower().split("_")[1] if "_" in transition_type.lower() else kwargs.get("direction", "left")
                    
                    # Implementa transição de slide
                    frame_paths = self._generate_slide_transition(
                        img1, img2, temp_dir, num_frames,
                        direction=direction,
                        sparkle_effect=kwargs.get("sparkle_effect", False),
                        brightness_effect=kwargs.get("brightness_effect", False),
                        is_children_content=kwargs.get("is_children_content", False),
                        **kwargs
                    )
                
                # Se temos frames gerados, combina-os em um vídeo
                if frame_paths:
                    # Usa FFmpeg para combinar os frames em um vídeo
                    frames_pattern = os.path.join(temp_dir, "frame_%04d.png")
                    import subprocess
                    ffmpeg_cmd = [
                        'ffmpeg', '-y',
                        '-r', str(fps),
                        '-i', frames_pattern,
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        '-crf', '23',
                        output_path
                    ]
                    
                    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                    
                    if os.path.exists(output_path):
                        logger.info(f"Transição {transition_type} gerada com sucesso: {output_path}")
                        
                        # Salva no cache
                        if self.cache_enabled:
                            cache_key = self._get_cache_key([scene1_image, scene2_image], 
                                                          f"transition_{transition_type}", kwargs)
                            cache_path = os.path.join(self.cache_dir, f"transition_{hash(cache_key)}.mp4")
                            shutil.copy2(output_path, cache_path)
                            
                            self.animation_cache[cache_key] = cache_path
                            self.animation_metadata[cache_key] = {
                                "type": transition_type,
                                "duration": duration,
                                "fps": fps,
                                "source_images": [scene1_image, scene2_image],
                                "created_at": time.time(),
                                "parameters": kwargs
                            }
                            self._save_cache()
                        
                        return True
        except Exception as e:
            logger.error(f"Erro ao gerar transição {transition_type}: {str(e)}")
            logger.warning("Tentando método padrão como fallback...")
        
        # Método padrão: usa a API para gerar a transição
        return self.generate_animation(
            [scene1_image, scene2_image], 
            output_path, 
            animation_type=transition_type, 
            duration=duration, 
            fps=fps, 
            **kwargs
        )
    
    def generate_character_animation(self, character_image, output_path, 
                                    animation_type="talk", duration=2.0, fps=24, **kwargs):
        """Gera uma animação para um personagem (ex: falar, piscar, etc.).
        
        Args:
            character_image: Caminho para a imagem do personagem
            output_path: Caminho para salvar a animação gerada
            animation_type: Tipo de animação (talk, blink, move, etc.)
            duration: Duração da animação em segundos
            fps: Frames por segundo
            **kwargs: Parâmetros adicionais para a API
            
        Returns:
            bool: True se a animação foi gerada com sucesso, False caso contrário
        """
        logger.info(f"Gerando animação de personagem: {animation_type}")
        
        # Para animações de personagem, usamos técnicas específicas
        # Em uma implementação real, isso seria integrado com uma API especializada
        
        # Por enquanto, vamos usar uma abordagem simplificada
        return self.generate_animation(
            [character_image], 
            output_path, 
            animation_type=animation_type, 
            duration=duration, 
            fps=fps, 
            **kwargs
        )
    
    def animate_story_scene(self, scene_images, character_images, background_image, 
                           output_path, duration=5.0, fps=24, **kwargs):
        """Cria uma animação completa para uma cena de história.
        
        Args:
            scene_images: Lista de imagens da cena
            character_images: Dicionário com imagens dos personagens
            background_image: Imagem de fundo
            output_path: Caminho para salvar a animação gerada
            duration: Duração da animação em segundos
            fps: Frames por segundo
            **kwargs: Parâmetros adicionais
            
        Returns:
            bool: True se a animação foi gerada com sucesso, False caso contrário
        """
        logger.info(f"Gerando animação completa para cena de história")
        
        # Em uma implementação real, isso combinaria várias técnicas de animação
        # para criar uma cena completa com personagens animados sobre um fundo
        
        # Por enquanto, vamos usar uma abordagem simplificada
        all_images = [background_image] + list(scene_images)
        return self.generate_animation(
            all_images, 
            output_path, 
            animation_type="scene", 
            duration=duration, 
            fps=fps, 
            **kwargs
        )
    
    def test_animation_generation(self, test_images, output_dir):
        """Testa a geração de animações com diferentes configurações.
        
        Args:
            test_images: Lista de imagens para teste
            output_dir: Diretório para salvar as animações de teste
            
        Returns:
            Dict: Resultados do teste com caminhos para as animações geradas
        """
        logger.info("Iniciando teste de geração de animações")
        
        os.makedirs(output_dir, exist_ok=True)
        results = {
            "morph_animations": [],
            "zoom_animations": [],
            "character_animations": []
        }
        
        # Testa animação de morphing entre imagens
        if len(test_images) >= 2:
            morph_output = os.path.join(output_dir, "morph_test.mp4")
            success = self.generate_animation(
                test_images[:2],
                morph_output,
                animation_type="morph",
                duration=3.0,
                fps=24,
                force_regenerate=True
            )
            if success:
                results["morph_animations"].append(morph_output)
        
        # Testa animação de zoom
        if test_images:
            zoom_output = os.path.join(output_dir, "zoom_test.mp4")
            success = self.generate_animation(
                [test_images[0]],
                zoom_output,
                animation_type="zoom",
                duration=2.0,
                fps=24,
                force_regenerate=True
            )
            if success:
                results["zoom_animations"].append(zoom_output)
        
        # Testa animação de personagem
        if test_images:
            character_output = os.path.join(output_dir, "character_test.mp4")
            success = self.generate_character_animation(
                test_images[0],
                character_output,
                animation_type="talk",
                duration=2.5,
                fps=24,
                force_regenerate=True
            )
            if success:
                results["character_animations"].append(character_output)
        
        logger.info(f"Teste de animação concluído. Resultados: {results}")
        return results

# Exemplo de uso
if __name__ == "__main__":
    # Configurações de teste
    test_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'test'
    )
    os.makedirs(test_dir, exist_ok=True)
    
    # Cria o agente de animação
    agent = AnimationGeneratorAgent(api_provider="stability")
    
    # Encontra imagens para teste
    import glob
    test_images = glob.glob(os.path.join(test_dir, "*.png"))
    
    if not test_images:
        print("Nenhuma imagem de teste encontrada. Criando imagens de placeholder...")
        
        # Cria imagens de placeholder para teste
        from PIL import Image, ImageDraw, ImageFont
        
        for i in range(3):
            img = Image.new('RGB', (512, 512), color=(240, 240, 240))
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("Arial", 24)
            except IOError:
                font = ImageFont.load_default()
            
            text = f"Imagem de Teste {i+1}"
            text_width = draw.textlength(text, font=font)
            draw.text(
                ((512 - text_width) // 2, 256),
                text,
                font=font,
                fill=(0, 0, 0)
            )
            
            img_path = os.path.join(test_dir, f"test_image_{i+1}.png")
            img.save(img_path)
            test_images.append(img_path)
        
        print(f"Criadas {len(test_images)} imagens de teste")
    
    # Testa a geração de animações
    output_dir = os.path.join(test_dir, "animations")
    results = agent.test_animation_generation(test_images, output_dir)
    
    print("\n=== Resultados do Teste de Animação ===")
    for anim_type, paths in results.items():
        print(f"{anim_type}: {len(paths)} animações geradas")
        for path in paths:
            print(f"  - {path}")
        

