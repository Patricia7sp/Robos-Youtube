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
