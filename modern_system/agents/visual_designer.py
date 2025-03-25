# -*- coding: utf-8 -*-
"""
Visual Designer Agent
--------------------
Este agente é responsável por gerar imagens para cada cena do roteiro,
incluindo personagens, cenários e elementos visuais.
"""

import os
import json
import time
import base64
import sys
import io
import datetime
import random

# Tentar importar requests, mas continuar mesmo se falhar
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("AVISO: Módulo 'requests' não encontrado. Funcionando em modo simulado.")
    REQUESTS_AVAILABLE = False

# Tentar importar PIL, mas continuar mesmo se falhar
try:
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:

    print("AVISO: Módulo 'PIL' não encontrado. Funcionando em modo simulado.")
    PIL_AVAILABLE = False

# Adiciona o diretório raiz ao path para importar módulos do projeto
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.append(sys_path)
from config.settings import API_KEYS, ANIMATION_STYLE, IMAGE_STYLE, IMAGE_STYLES


class VisualDesignerAgent:
    def __init__(self, api_key=None, api_provider=None, image_style=None):
        """Inicializa o VisualDesignerAgent.
        
        Args:
            api_key: Chave da API para geração de imagens (opcional, se não fornecida, usará as chaves do settings.py)
            api_provider: Provedor da API preferido ('qwen', 'ia_studio', 'deepseek' ou 'openai')
            image_style: Estilo de imagem desejado ('Disney_3.0', '3D_cartoon', 'Epic', 'Realistic', 'Animals')
        """
        self.image_style = image_style or IMAGE_STYLE
        self.target_width = 1920
        self.target_height = 1080
        self.cache_enabled = True  # Habilita o sistema de cache por padrão

        # Carrega as chaves de API de todos os provedores disponíveis
        self.api_keys = {
            'stability': API_KEYS.get('STABILITY_API_KEY') or os.environ.get('STABILITY_API_KEY'),
            'qwen': API_KEYS.get('QWEN_IMAGE_API_KEY') or os.environ.get('QWEN_API_KEY'),
            'ia_studio': API_KEYS.get('IA_STUDIO_IMAGE_API_KEY') or os.environ.get('IA_STUDIO_API_KEY'),
            'deepseek': API_KEYS.get('DEEPSEEK_IMAGE_API_KEY') or os.environ.get('DEEPSEEK_API_KEY'),
            'openai': API_KEYS.get('DALLE_API_KEY') or os.environ.get('OPENAI_API_KEY')
        }

        # Se uma chave de API específica foi fornecida, sobrescreve a correspondente
        if api_key and api_provider:
            self.api_keys[api_provider] = api_key

        # Define a ordem padrão de preferência para os provedores de API
        # Usando exclusivamente Stability AI como provedor
        default_order = ['stability']

        # Filtra apenas os provedores que têm chaves válidas
        self.api_providers = [provider for provider in default_order if self.api_keys.get(provider)]

        # Se um provedor específico foi solicitado e tem chave válida, coloca-o em primeiro lugar
        if api_provider and api_provider in self.api_keys and self.api_keys[api_provider]:
            if api_provider in self.api_providers:
                self.api_providers.remove(api_provider)
            self.api_providers.insert(0, api_provider)

        # Se não há provedores com chaves válidas, usa o modo simulado
        if not self.api_providers:
            print("AVISO: Nenhuma chave de API válida encontrada. Usando modo simulado.")
            self.api_provider = None
            self.api_key = None
        else:
            # Define o provedor principal (o primeiro da lista)
            self.api_provider = self.api_providers[0]
            self.api_key = self.api_keys.get(self.api_provider)
            print("Usando {} como provedor principal de imagens.".format(self.api_provider))

        # Verifica se há pelo menos uma chave de API disponível
        if not any(self.api_keys.values()):
            print("AVISO: Nenhuma chave de API fornecida. O agente funcionará em modo simulado.")
        else:
            print("Usando provedor de API: {0}".format(self.api_provider))

        self.style = ANIMATION_STYLE
        self.script = None
        self.character_designs = {}
        self.scene_images = {}

        # Inicializa o sistema de cache para imagens
        self.cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'cache', 'images'
        )
        # Verifica se o diretório existe antes de criar (compatibilidade com Python < 3.2)
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
            except OSError as e:
                # Ignora erro se o diretório já existir (race condition)
                if e.errno != os.errno.EEXIST:
                    raise
        self.image_cache = {}
        self._load_cache()
        print("Sistema de cache de imagens inicializado: {}".format(self.cache_dir))

    def _load_cache(self, output_dir=None):
        """Carrega o cache de imagens do disco.
        
        Args:
            output_dir: Diretório opcional onde os metadados estão salvos. Se não for fornecido, usa self.cache_dir
            
        Returns:
            Dicionário com metadados de cache ou {} se não existir
        """
        if not self.cache_enabled:
            return {}
            
        # Se output_dir não for fornecido, usa o diretório de cache padrão
        cache_dir = output_dir if output_dir else self.cache_dir
        
        # Tenta carregar o cache padrão
        cache_index_path = os.path.join(cache_dir, 'cache_index.json')
        
        # Tenta carregar o cache de metadados de imagens se estiver no formato novo
        metadata_path = os.path.join(cache_dir, 'image_metadata.json')
        
        # Primeiro tenta o cache de metadados, depois o cache_index
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                print(f"Cache de imagens carregado de {metadata_path} com {len(cache_data.get('images', {}))} imagens")
                
                # Verifica se o cache tem a estrutura esperada
                if 'character_seeds' not in cache_data:
                    cache_data['character_seeds'] = {}
                if 'scene_seeds' not in cache_data:
                    cache_data['scene_seeds'] = {}
                if 'location_seeds' not in cache_data:
                    cache_data['location_seeds'] = {}
                if 'images' not in cache_data:
                    cache_data['images'] = {}
                    
                return cache_data
            except Exception as e:
                print(f"Erro ao carregar cache de metadados: {e}")
                # Tenta o cache_index como fallback
        
        # Tenta o cache_index se o metadata não existir ou falhar
        if os.path.exists(cache_index_path):
            try:
                with open(cache_index_path, 'r', encoding='utf-8') as f:
                    self.image_cache = json.load(f)
                print("Cache de imagens carregado: {} entradas".format(len(self.image_cache)))
            except Exception as e:
                print("Erro ao carregar cache de imagens: {}".format(str(e)))
                self.image_cache = {}

    def _save_cache(self):
        """Salva o cache de imagens no disco."""
        cache_index_path = os.path.join(self.cache_dir, 'cache_index.json')
        try:
            with open(cache_index_path, 'w', encoding='utf-8') as f:
                json.dump(self.image_cache, f, ensure_ascii=False, indent=2)
            print("Cache de imagens salvo: {} entradas".format(len(self.image_cache)))
        except Exception as e:
            print("Erro ao salvar cache de imagens: {}".format(str(e)))

    def _get_cache_key(self, prompt, style, provider, model=None):
        """Gera uma chave única para o cache baseada no prompt, estilo e provedor.
        
        Args:
            prompt: O prompt usado para gerar a imagem
            style: O estilo de imagem usado
            provider: O provedor de API usado
            model: O modelo usado (opcional)
            
        Returns:
            Uma string única para usar como chave de cache
        """
        # Cria uma chave baseada no prompt, estilo, provedor e modelo
        # Usa apenas os primeiros 100 caracteres do prompt para manter a chave curta
        import hashlib
        prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:10]
        model_str = "_{}".format(model) if model else ""
        return "{}_{}{}_{}".format(provider, style, model_str, prompt_hash)

    def _get_from_cache(self, prompt, style, provider, model=None):
        """Tenta obter uma imagem do cache.
        
        Args:
            prompt: O prompt usado para gerar a imagem
            style: O estilo de imagem usado
            provider: O provedor de API usado
            model: O modelo usado (opcional)
            
        Returns:
            Os bytes da imagem se encontrada no cache, ou None caso contrário
        """
        cache_key = self._get_cache_key(prompt, style, provider, model)

        if cache_key in self.image_cache:
            cache_file_path = os.path.join(self.cache_dir, self.image_cache[cache_key])
            if os.path.exists(cache_file_path):
                try:
                    with open(cache_file_path, 'rb') as f:
                        print("Imagem encontrada no cache: {}".format(cache_key))
                        return f.read()
                except Exception as e:
                    print("Erro ao ler imagem do cache: {}".format(str(e)))

        return None

    def _save_to_cache(self, prompt, style, provider, image_data, model=None):
        """Salva uma imagem no cache.
        
        Args:
            prompt: O prompt usado para gerar a imagem
            style: O estilo de imagem usado
            provider: O provedor de API usado
            image_data: Os bytes da imagem a ser salva
            model: O modelo usado (opcional)
            
        Returns:
            True se a imagem foi salva com sucesso, False caso contrário
        """
        if not image_data:
            return False

        cache_key = self._get_cache_key(prompt, style, provider, model)
        timestamp = int(time.time())
        filename = "{}_{}.png".format(provider, timestamp)
        file_path = os.path.join(self.cache_dir, filename)

        try:
            with open(file_path, 'wb') as f:
                f.write(image_data)

            # Atualiza o índice do cache
            self.image_cache[cache_key] = filename
            self._save_cache()
            print("Imagem salva no cache: {}".format(cache_key))
            return True
        except Exception as e:
            print("Erro ao salvar imagem no cache: {}".format(str(e)))
            return False

    def load_script(self, script_data):
        """
        Carrega o roteiro processado a partir de um arquivo JSON ou de uma lista de cenas.
        
        Args:
            script_data: Caminho para o arquivo JSON do roteiro ou lista de cenas
        """
        if isinstance(script_data, str):
            # Se for um caminho de arquivo
            with open(script_data, 'r', encoding='utf-8') as file:
                self.script = json.load(file)
        else:
            # Se for uma lista de cenas
            self.script = script_data

        print("Roteiro carregado: {0} cenas".format(len(self.script)))

    def _generate_character_prompt(self, character):
        """
        Gera um prompt para criar um personagem consistente.
        
        Args:
            character: Nome do personagem
            
        Returns:
            Prompt detalhado para geração de imagem do personagem
        """
        character_descriptions = {
            "Alice": "Uma menina de 8 anos com cabelos loiros compridos até a cintura, vestido azul claro com avental branco, meias brancas e sapatos pretos. Olhos azuis grandes e expressivos, pele clara, bochechas levemente rosadas. Expressão curiosa, determinada e sonhadora. Postura confiante mas infantil. Estilo de animação 3D infantil com traços suaves e cores vibrantes. A mesma Alice em todas as cenas, com consistência visual total.",
            
            "Professor Ludovico": "Homem de meia-idade (45-50 anos) com cabelos grisalhos despenteados, bigode fino, óculos redondos pequenos na ponta do nariz. Veste terno vintage marrom com colete, gravata borboleta azul, relógio de bolso dourado no bolso do colete. Expressão distraída, gentil e sonhadora. Postura ligeiramente curvada, como se sempre estivesse pensando em algo importante. Estilo de animação 3D infantil com detalhes precisos em suas roupas da era vitoriana. O mesmo Professor Ludovico em todas as cenas.",
            
            "Coelho": "Coelho branco de tamanho médio com olhos vermelhos brilhantes, orelhas longas e alertas, usando colete vermelho com botões dourados e segurando um relógio de bolso dourado. Bigodes longos e trêmulos, patas delicadas. Sempre com expressão apressada e ansiosa, olhando constantemente para o relógio. Movimentos rápidos e nervosos. Estilo de animação 3D infantil com pelo branco detalhado e texturizado. O mesmo Coelho em todas as cenas.",
            
            "Gato": "Filhote de gato cinza com listras pretas sutis, olhos grandes e verdes, orelhas pontudas e alertas. Aparência fofa e inocente, com pelo macio e brilhante. Expressão curiosa e brincalhona. Estilo de animação 3D infantil com detalhes realistas no pelo. O mesmo filhote em todas as cenas.",
            
            "Gata mãe": "Gata adulta cinza com manchas brancas no peito e patas, olhos amarelos protetores. Pelo longo e bem cuidado. Expressão vigilante e maternal. Estilo de animação 3D infantil com detalhes realistas. A mesma gata em todas as cenas.",
            
            "Estudante": "Jovem universitário da era vitoriana (18-22 anos) com cabelos castanhos arrumados, vestindo terno simples escuro com gravata, carregando livros. Expressão séria e concentrada. Estilo de animação 3D infantil. O mesmo estudante em todas as cenas.",
            
            "Lóri": "Uma adolescente elegante de 15 anos, mais velha que Alice, cabelos castanhos em penteado elaborado da era vitoriana, vestido formal azul-escuro com babados e fitas. Postura refinada com movimentos delicados, expressões faciais sutis mas marcantes. Personagem em estilo de animação 3D com detalhes nos tecidos e acessórios. A mesma Lóri em todas as cenas.",
            
            "Edith": "Uma menina pequena e espirituosa de 6 anos, mais nova que Alice, cabelos cacheados ruivos volumosos e indomáveis, vestido verde da era vitoriana com detalhes infantis. Movimentos rápidos e brincalhões, expressões faciais exóticas e divertidas. Animação 3D com ênfase em movimentos bouncy e expressões exageradas. A mesma Edith em todas as cenas.",
            
            "Mia": "Uma gata adulta elegante com pelagem malhada em tons de cinza, olhos verdes brilhantes e expressivos. Movimentos fluidos e graciosos, personalidade maternal com seus filhotes. Animação 3D com atenção especial à textura do pelo e movimentação felina realista. A mesma Mia em todas as cenas.",
            
            "mamãe": "Uma mulher elegante da era vitoriana de 40 anos, cabelos escuros presos em coque elaborado, vestido longo roxo formal com detalhes delicados. Postura nobre com movimentos precisos, expressões faciais que alternam entre severidade e afeto. Animação 3D com detalhes nos tecidos e acessórios da época. A mesma mãe em todas as cenas.",
            
            "papai": "Um homem imponente da era vitoriana de 45 anos, barba curta bem aparada, roupas formais de reitor com detalhes dourados. Postura rígida mas digna, movimentos calculados, expressões que revelam autoridade e ocasional gentileza. Animação 3D com ênfase na textura dos tecidos e detalhes faciais. O mesmo pai em todas as cenas."
        }

        # Descrição padrão para personagens não especificados
        description = character_descriptions.get(
            character,
            "Personagem {} em estilo de animação 3D infantil, era vitoriana, com movimentos fluidos e expressões faciais marcantes".format(character)
        )

        style_desc = {
            'children_storybook': "estilo de livro infantil clássico, ilustração delicada e detalhada",
            'anime': "estilo anime suave apropriado para crianças",
            'realistic': "estilo realista mas adequado para crianças",
            'cartoon': "estilo de desenho animado colorido e expressivo"
        }

        art_style = {
            'watercolor': "aquarela suave com contornos delicados",
            'digital': "arte digital limpa e vibrante",
            'pencil': "desenho a lápis colorido com textura",
            'oil_painting': "pintura a óleo com textura e profundidade"
        }

        prompt = "Retrato de {0}: {1}. Em {2} e técnica de {3}. Fundo simples e neutro, foco no personagem, iluminação suave, cores {4}.".format(
            character,
            description,
            style_desc[self.style['style']],
            art_style[self.style['art_style']],
            self.style['color_palette']
        )

        return prompt

    def _generate_scene_prompt(self, scene):
        """
        Gera um prompt para criar uma cena.
        
        Args:
            scene: Dicionário contendo informações da cena
            
        Returns:
            Prompt detalhado para geração de imagem da cena
        """
        location = scene.get('location', 'Indefinido')
        characters = scene.get('characters', [])
        visual_elements = scene.get('visual_elements', [])

        location_descriptions = {
            "jardim": "Jardim vitoriano da Universidade de Oxford, com árvores antigas de troncos grossos e copas frondosas, canteiros geométricos de flores coloridas bem cuidadas, caminhos de pedra sinuosos, bancos de madeira ornamentados. Ao fundo, imponentes prédios góticos da universidade com torres, vitrais e detalhes arquitetônicos clássicos. Iluminação natural com raios de sol atravessando as folhas. Atmosfera mágica e serena da era vitoriana. Cores vivas mas harmônicas. O mesmo jardim em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "sala de jantar": "Sala de jantar vitoriana elegante com mesa grande de madeira escura polida, cadeiras estofadas em veludo verde, talheres de prata, louça fina, cristais reluzentes. Paredes com papel de parede floral em tom verde-escuro, quadros emoldurados em dourado, lustre de cristal pendente sobre a mesa. Cortinas pesadas de veludo verde com cordões dourados. Lareira de mármore acesa em um canto. Atmosfera aconchegante e refinada da era vitoriana. A mesma sala em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "toca do coelho": "Entrada de uma toca de coelho no jardim da universidade, escondida entre raízes de uma árvore antiga. Abertura circular perfeitamente formada, com pequenos degraus de terra descendo para a escuridão. Algumas flores silvestres e cogumelos coloridos crescem ao redor da entrada. Raios de sol filtrados pelas folhas iluminam parcialmente a entrada. Atmosfera misteriosa e convidativa. A mesma toca em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "universidade": "Fachada imponente da Universidade de Oxford na era vitoriana, com arquitetura gótica detalhada: torres altas, arcos pontiagudos, vitrais coloridos, gralhas voando entre os pináculos, bandeiras tremulando. Escadaria de pedra larga na entrada, portas de madeira maciça com detalhes em ferro. Estudantes com roupas da época vitoriana caminhando com livros. Céu azul com algumas nuvens. A mesma universidade em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "sala de aula": "Sala de aula vitoriana da Universidade de Oxford com carteiras de madeira escura enfileiradas, quadro-negro grande na parede frontal, globo terrestre em um pedestal, mapas e diagramas matemáticos pendurados nas paredes. Janelas altas que permitem a entrada de luz natural, estante com livros antigos, mesa do professor em patamar elevado. Atmosfera acadêmica e formal. A mesma sala em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "rio Tâmisa": "Rio Tâmisa na era vitoriana, águas calmas refletindo o céu, margens verdejantes com árvores frondosas. Pequeno barco a remo de madeira navegando suavemente. Ao fundo, silhueta de Oxford com torres e pináculos. Luz dourada de fim de tarde criando reflexos na água. Atmosfera serena e poética. O mesmo rio em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "escritório": "Escritório vitoriano aconchegante com escrivaninha de madeira escura entulhada de livros, papéis e instrumentos matemáticos. Estantes até o teto repletas de livros antigos. Poltrona de couro marrom gasto, candeeiro a óleo, tinteiro e penas. Janela com vista para o jardim da universidade. Globo terrestre antigo em um canto. Atmosfera acadêmica e acolhedora. O mesmo escritório em todas as cenas, mantendo consistência de ângulo e elementos.",
            
            "mesa": "Mesa de chá vitoriana elegante no jardim da universidade, coberta com toalha de renda branca, bule de porcelana azul e branca, xícaras delicadas combinando, pratinhos com biscoitos e bolinhos. Cadeiras de ferro forjado pintadas de branco com almofadas. Flores frescas em um pequeno vaso central. Luz natural filtrada pelas folhas das árvores. A mesma mesa em todas as cenas, mantendo consistência de ângulo e elementos."
        }

        # Descrição padrão para locais não especificados
        location_desc = location_descriptions.get(
            location,
            "Cenário mágico de {0} na era vitoriana, com elementos animados e detalhes em movimento que criam uma atmosfera encantadora".format(location)
        )

        # Adiciona personagens à descrição
        characters_desc = ""
        if characters:
            characters_desc = " Com {0} presentes na cena.".format(", ".join(characters))

        # Adiciona elementos visuais à descrição
        elements_desc = ""
        if visual_elements:
            elements_desc = " Incluindo {0} como elementos visuais importantes.".format(", ".join(visual_elements))

        style_desc = {
            'children_storybook': "estilo de livro infantil clássico, ilustração delicada e detalhada",
            'anime': "estilo anime suave apropriado para crianças",
            'realistic': "estilo realista mas adequado para crianças",
            'cartoon': "estilo de desenho animado colorido e expressivo"
        }

        art_style = {
            'watercolor': "aquarela suave com contornos delicados",
            'digital': "arte digital limpa e vibrante",
            'pencil': "desenho a lápis colorido com textura",
            'oil_painting': "pintura a óleo com textura e profundidade"
        }

        # Adiciona instruções específicas para manter consistência visual
        consistency_instructions = "Manter absoluta consistência visual com as outras cenas. Os personagens devem ter exatamente a mesma aparência em todas as cenas, sem variações de roupa, cabelo ou características físicas. Os cenários devem manter o mesmo estilo, ângulo de visão e elementos arquitetônicos."
        
        # Adiciona instruções sobre a paleta de cores
        color_instructions = {
            'vibrant': "cores vivas e vibrantes, mas harmônicas, apropriadas para histórias infantis",
            'pastel': "paleta de cores pastel suaves e acolhedoras, criando uma atmosfera serena e delicada",
            'muted': "cores suavizadas e sutis que criam uma atmosfera clássica da era vitoriana",
            'dark': "cores ricas e profundas com bom contraste, mantendo a legibilidade e adequação para crianças"
        }
        
        prompt = "{0}.{1}{2} Em {3} e técnica de {4}. Iluminação suave, {5}. Composição equilibrada, perspectiva correta. {6}".format(
            location_desc,
            characters_desc,
            elements_desc,
            style_desc[self.style['style']],
            art_style[self.style['art_style']],
            color_instructions.get(self.style['color_palette'], f"cores {self.style['color_palette']}"),
            consistency_instructions
        )

        return prompt

    def _resize_to_16_9(self, image):
        """Redimensiona a imagem para proporção 16:9 (1920x1080).
        
        Args:
            image: Objeto PIL.Image
            
        Returns:
            Objeto PIL.Image redimensionado
        """
        # Calcula as dimensões atuais
        width, height = image.size

        # Calcula a proporção atual
        current_ratio = width / height
        target_ratio = self.target_width / self.target_height

        if current_ratio > target_ratio:
            # Imagem é mais larga que 16:9
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            image = image.crop((left, 0, left + new_width, height))
        else:
            # Imagem é mais alta que 16:9
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            image = image.crop((0, top, width, top + new_height))

        # Redimensiona para 1920x1080
        return image.resize((self.target_width, self.target_height), Image.Resampling.LANCZOS)

    def generate_placeholder_image(self, prompt_text):
        """
        Gera uma imagem de placeholder com o texto do prompt e elementos visuais
        quando a API de geração de imagens não está disponível.
        
        Args:
            prompt_text: Texto do prompt para incluir na imagem
            
        Returns:
            Dados da imagem em bytes
        """
        if not PIL_AVAILABLE:
            print("Não é possível gerar imagem de placeholder: PIL não está disponível")
            return b"imagem_simulada_fallback"

        try:
            # Cria uma imagem com fundo preto
            width, height = 1280, 720  # 16:9 aspect ratio
            img = Image.new('RGB', (width, height), color=(0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Tenta carregar uma fonte, ou usa a fonte padrão
            try:
                # Tenta encontrar uma fonte no sistema
                font_path = "/System/Library/Fonts/Helvetica.ttc"
                title_font = ImageFont.truetype(font_path, 36)
                body_font = ImageFont.truetype(font_path, 24)
            except IOError:
                # Usa a fonte padrão se não encontrar a fonte específica
                title_font = ImageFont.load_default()
                body_font = ImageFont.load_default()

            # Adiciona um título simulado
            sim_text = "Imagem Simulada"
            sim_width = 300  # Largura estimada do texto

            # Desenha um retângulo semi-transparente para o título
            draw.rectangle((0, 30, width, 130), fill=(0, 0, 0, 128))
            draw.text(((width - sim_width) // 2, 80), sim_text, font=title_font, fill=(255, 255, 255))

            # Adiciona uma borda à imagem
            border_width = 10
            draw.rectangle((0, 0, width - 1, height - 1), outline="white", width=border_width)

            # Converte a imagem para bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()

        except Exception as e:
            print("Erro ao gerar imagem de placeholder: {0}".format(str(e)))
            # Retorna um placeholder mínimo em caso de falha
            return b"imagem_simulada_fallback"

    def _try_generate_with_apis(self, styled_prompt, character_name=None, scene_number=None, location_name=None, consistency_seed=None):
        """
        Tenta gerar uma imagem usando as APIs disponíveis na ordem definida,
        com suporte para consistência visual entre imagens relacionadas.
        
        Args:
            styled_prompt: Prompt formatado com estilo para geração da imagem
            character_name: Nome do personagem (se for uma imagem de personagem)
            scene_number: Número da cena (se for uma imagem de cena)
            location_name: Nome do local (se for uma imagem de local)
            consistency_seed: Semente para manter consistência visual (opcional)
            
        Returns:
            Conteúdo da imagem em bytes ou None se todas as APIs falharem
        """
        # Determina informações de contexto para o cache e consistência
        context_type = None
        context_id = None
        style_preset = None
        seed = consistency_seed
        
        if character_name:
            context_type = "character"
            context_id = character_name
            # Para personagens, usar um preset que favorece personagens
            if self.image_style == 'Disney_3.0':
                style_preset = "animation"
            elif self.image_style == '3D_cartoon':
                style_preset = "animation-3d"
            else:
                style_preset = "digital-art"
                
        elif scene_number is not None:
            context_type = "scene"
            context_id = f"scene_{scene_number}"
            # Para cenas, usar um preset que favorece ambientes
            if self.image_style == 'Disney_3.0':
                style_preset = "animation"
            elif self.image_style == '3D_cartoon':
                style_preset = "animation-3d"
            elif self.image_style == 'Epic':
                style_preset = "cinematic"
            elif self.image_style == 'Realistic':
                style_preset = "photographic"
            else:
                style_preset = "digital-art"
                
        elif location_name is not None:
            context_type = "location"
            context_id = location_name
            # Para locais, usar presets que favorecem ambientes
            if self.image_style == 'Disney_3.0':
                style_preset = "animation"
            elif self.image_style == 'Epic':
                style_preset = "cinematic"
            elif self.image_style == 'Realistic':
                style_preset = "photographic"
            else:
                style_preset = "digital-art"
        
        # Carrega o cache para gerenciamento de seeds
        cache = None
        if hasattr(self, 'cache_dir') and self.cache_dir:
            cache_dir = os.path.dirname(os.path.join(self.cache_dir, 'dummy.txt'))
            cache = self._load_cache(cache_dir)
            
        # Obtém uma seed consistente se não fornecida
        if seed is None and context_id and cache is not None:
            if context_type == "character":
                seed = self._get_character_seed(character_name, cache)
            elif context_type == "scene":
                seed = self._get_scene_seed(scene_number, cache)
            elif context_type == "location":
                seed = self._get_location_seed(location_name, cache)
            else:
                # Fallback para o método antigo se não for personagem, cena ou local
                seed = abs(hash(context_id)) % 2147483647  # Valor máximo para int32
                print(f"Usando seed gerada {seed} para {context_type} {context_id}")
                
            # Salva o cache atualizado
            if hasattr(self, 'cache_dir') and self.cache_dir:
                self._save_cache(cache_dir, cache)
        
        # Tenta usar cada provedor de API na ordem definida
        for provider in self.api_providers:
            # Verifica se temos uma chave válida para este provedor
            api_key = self.api_keys.get(provider)
            if not api_key:
                print(f"Provedor {provider} não possui chave de API configurada, pulando...")
                continue  # Pula para o próximo provedor se não houver chave

            # Verifica se a imagem está no cache para este provedor
            cache_key = f"{styled_prompt}_{context_type}_{context_id}" if context_id else styled_prompt
            cached_image = self._get_from_cache(cache_key, self.image_style, provider)
            if cached_image:
                print(f"Usando imagem do cache para {context_type or 'prompt'} {context_id or styled_prompt[:50]}...")
                return cached_image

            try:
                print(f"Tentando gerar imagem com provedor {provider}...")
                # Tenta gerar a imagem com o provedor atual
                if provider == 'stability':
                    print(f"Gerando com Stability AI: {context_type or 'imagem'} {context_id or ''}")
                    result = self._generate_with_stability(styled_prompt, seed=seed, style_preset=style_preset)
                    if result:
                        return result
                # Adicionar outros provedores conforme necessário
            except Exception as e:
                print(f"Erro ao gerar imagem com provedor {provider}: {str(e)}")
                # Registra o erro em um log para análise posterior
                self._log_error(f"Erro na geração de imagem com {provider}", {
                    "error": str(e),
                    "context_type": context_type,
                    "context_id": context_id,
                    "prompt": styled_prompt[:200] + ("..." if len(styled_prompt) > 200 else ""),
                    "timestamp": datetime.datetime.now().isoformat()
                })
                # Continua para o próximo provedor
        
        # Se chegou aqui, todas as APIs falharam
        print(f"Falha em todos os provedores de API para {context_type or 'imagem'} {context_id or ''}")
        return None
        
    def _log_error(self, error_type, error_data):
        """Registra erros em um arquivo de log para análise posterior.
        
        Args:
            error_type: Tipo/descrição do erro
            error_data: Dicionário com dados relacionados ao erro
        """
        try:
            # Garante que o diretório de logs existe
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Nome do arquivo de log com data
            log_file = os.path.join(log_dir, f"image_generation_errors_{datetime.datetime.now().strftime('%Y%m%d')}.log")
            
            # Formata os dados do erro
            log_entry = f"[{datetime.datetime.now().isoformat()}] {error_type}\n"
            for key, value in error_data.items():
                log_entry += f"  {key}: {value}\n"
            log_entry += "\n"
            
            # Escreve no arquivo de log
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
        except Exception as e:
            print(f"Erro ao registrar log: {e}")
            # Não levanta exceção para não interromper o fluxo principal
    
    def _generate_with_stability(self, styled_prompt, seed=None, style_preset=None):
        """
        Gera uma imagem usando a API do Stability AI com parâmetros avançados
        para garantir maior qualidade e consistência visual.
        
        Args:
            styled_prompt: Prompt formatado com estilo para geração da imagem
            seed: Semente para geração determinista (opcional)
            style_preset: Preset de estilo para a geração (opcional)
            
        Returns:
            Conteúdo da imagem em bytes ou None em caso de falha
        """
        try:
            print(f"Gerando imagem com Stability AI: {styled_prompt[:100]}...")
            
            # Obter modelo e configurações
            stability_model = API_KEYS.get('STABILITY_MODEL') or os.environ.get(
                'STABILITY_MODEL', 'stable-diffusion-xl-1024-v1-0')
            
            # Configurações dos modelos disponíveis com parâmetros otimizados
            stability_models = {
                'stable-diffusion-xl-1024-v1-0': {
                    'name': 'Stable Diffusion XL 1.0',
                    'width': 1024,
                    'height': 1024,
                    'steps': 40,  # Aumentado para melhor qualidade
                    'cfg_scale': 8.0,  # Aumentado para melhor aderência ao prompt
                    'sampler': 'K_DPMPP_2M'
                },
                'stable-diffusion-xl-1024-v1-0-turbo': {
                    'name': 'Stable Diffusion XL Turbo',
                    'width': 1024,
                    'height': 1024,
                    'steps': 25,
                    'cfg_scale': 7.5,
                    'sampler': 'K_DPMPP_SDE'
                },
                'stable-diffusion-v1-6': {
                    'name': 'Stable Diffusion 1.6',
                    'width': 768,  # Aumentado para melhor qualidade
                    'height': 768,  # Aumentado para melhor qualidade
                    'steps': 35,    # Aumentado para melhor qualidade
                    'cfg_scale': 7.5,
                    'sampler': 'K_DPMPP_2M'
                }
            }
            
            # Obter configuração do modelo
            model_config = stability_models.get(
                stability_model, stability_models['stable-diffusion-xl-1024-v1-0'])
            
            # Configuração da API
            api_url = f"https://api.stability.ai/v1/generation/{stability_model}/text-to-image"
            api_url_alt = f"https://api.stability.ai/v2/generation/{stability_model}/text-to-image"
            
            headers = {
                'Authorization': f'Bearer {self.api_keys["stability"]}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Preparar payload com parâmetros avançados
            payload = {
                "text_prompts": [
                    {
                        "text": styled_prompt,
                        "weight": 1.0
                    }
                ],
                "cfg_scale": model_config['cfg_scale'],
                "height": model_config['height'],
                "width": model_config['width'],
                "samples": 1,
                "steps": model_config['steps'],
                "sampler": model_config['sampler']
            }
            
            # Adicionar seed se fornecida para consistência entre imagens
            if seed is not None:
                payload["seed"] = seed
                print(f"Usando seed {seed} para consistência visual")
            
            # Adicionar style preset se fornecido
            if style_preset:
                payload["style_preset"] = style_preset
                print(f"Usando style preset: {style_preset}")
            elif 'xl' in stability_model.lower():
                # Para modelos XL, usar presets específicos baseados no estilo desejado
                style_presets = {
                    'Disney_3.0': 'animation',
                    '3D_cartoon': 'animation-3d',
                    'Epic': 'cinematic',
                    'Realistic': 'photographic',
                    'Animals': 'digital-art'
                }
                preset = style_presets.get(self.image_style, 'digital-art')
                payload["style_preset"] = preset
                print(f"Usando style preset automático: {preset} para estilo {self.image_style}")
            
            # Adicionar prompt negativo aprimorado para evitar problemas comuns
            negative_prompt = "deformed, distorted, disfigured, poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, mutated hands and fingers, disconnected limbs, mutation, mutated, ugly, disgusting, blurry, amputation, bad proportions, watermark, signature, text, uneven eyes, asymmetric features, double image, duplicate"
            payload["text_prompts"].append({"text": negative_prompt, "weight": -1.0})
            
            # Fazer a requisição com retry embutido
            max_retries = 3
            retry_delay = 5
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # Tentar a primeira URL
                    response = requests.post(
                        api_url,
                        headers=headers,
                        json=payload,
                        timeout=90  # Aumentado para lidar com modelos mais pesados
                    )
                    
                    # Se falhar, tentar a URL alternativa
                    if response.status_code != 200:
                        print(f"Tentativa {attempt+1}: API primária falhou com código {response.status_code}, tentando API alternativa...")
                        response = requests.post(
                            api_url_alt,
                            headers=headers,
                            json=payload,
                            timeout=90
                        )
                    
                    # Processar resposta
                    if response.status_code == 200:
                        result = response.json()
                        if 'artifacts' in result and len(result['artifacts']) > 0:
                            image_data = base64.b64decode(result['artifacts'][0]['base64'])
                            # Salvar no cache com informações adicionais
                            cache_metadata = {
                                'model': stability_model,
                                'style': self.image_style,
                                'seed': seed,
                                'style_preset': payload.get('style_preset'),
                                'timestamp': datetime.datetime.now().isoformat()
                            }
                            self._save_to_cache(styled_prompt, self.image_style, 'stability', image_data, stability_model, cache_metadata)
                            print(f"Imagem gerada com sucesso usando Stability AI ({model_config['name']})")
                            return image_data
                        else:
                            print("Resposta da API não contém artefatos de imagem")
                    else:
                        print(f"Erro na API: {response.status_code} - {response.text}")
                        
                    # Se chegou aqui, a tentativa falhou
                    last_error = f"Código de status: {response.status_code}, Resposta: {response.text if len(response.text) < 500 else response.text[:500] + '...'}"
                        
                except Exception as e:
                    last_error = str(e)
                    print(f"Erro na tentativa {attempt+1}: {last_error}")
                
                # Se não for a última tentativa, esperar antes de tentar novamente
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)  # Backoff exponencial
                    print(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
                    time.sleep(wait_time)
            
            print(f"Todas as tentativas falharam ao gerar imagem com Stability AI. Último erro: {last_error}")
            return None
            
        except Exception as e:
            print(f"Erro ao usar a API do Stability AI: {str(e)}")
            return None
    
    def _generate_image(self, prompt, character_name=None, scene_number=None, location_name=None, consistency_seed=None, max_retries=3, retry_delay=5):
        """
        Gera uma imagem usando a API selecionada com suporte para consistência visual.
        Implementa um sistema de retry para lidar com falhas temporárias da API.
        Se todas as tentativas falharem, gera uma imagem de placeholder.
        
        Args:
            prompt: Prompt detalhado para geração da imagem
            character_name: Nome do personagem (se for uma imagem de personagem)
            scene_number: Número da cena (se for uma imagem de cena)
            location_name: Nome do local (se for uma imagem de local)
            consistency_seed: Semente para manter consistência visual (opcional)
            max_retries: Número máximo de tentativas em caso de falha
            retry_delay: Tempo de espera entre tentativas (em segundos)
            
        Returns:
            Conteúdo da imagem em bytes ou None em caso de falha
        """
        # Se o módulo requests não estiver disponível, sempre gere imagens simuladas
        if not REQUESTS_AVAILABLE:
            print("Modo simulado obrigatório: Módulo 'requests' não disponível")
            return self._generate_placeholder_image(prompt)

        # Se o módulo PIL não estiver disponível, retorne dados simulados
        if not PIL_AVAILABLE:
            print("Modo simulado obrigatório: Módulo 'PIL' não disponível")
            # Não podemos gerar um placeholder sem PIL, então retornamos bytes vazios
            return b"imagem_simulada_fallback"
            
        # Adiciona o estilo ao prompt
        style_description = IMAGE_STYLES.get(self.image_style, "Disney style")
        styled_prompt = f"Create a {style_description} image of {prompt}"
        
        # Registra informações sobre o tipo de imagem sendo gerada
        context_info = ""
        if character_name:
            context_info = f"personagem '{character_name}'"
        elif scene_number is not None:
            context_info = f"cena {scene_number}"
        elif location_name:
            context_info = f"local '{location_name}'"
        
        print(f"Gerando imagem para {context_info if context_info else 'prompt genérico'}: {prompt[:100]}...")

        # Verifica se estamos em modo simulado (sem chaves de API configuradas)
        simulate_mode = all(not key for key in self.api_keys.values())
        if simulate_mode:
            print("Modo simulado: Nenhuma API configurada. Gerando imagem placeholder.")
            return self._generate_placeholder_image(
                text=f"MODO SIMULADO: {prompt[:150]}...",
                width=1344 if not character_name else 768,
                height=768
            )
        
        # Implementação do sistema de retry para todo o processo de geração de imagem
        for attempt in range(max_retries):
            try:
                # Se não é a primeira tentativa, aguarda antes de tentar novamente
                if attempt > 0:
                    retry_wait = retry_delay * (2 ** (attempt - 1))  # Backoff exponencial
                    print(f"Tentativa {attempt+1}/{max_retries} após {retry_wait} segundos...")
                    time.sleep(retry_wait)
                
                # Tenta gerar a imagem com as APIs disponíveis, passando os parâmetros de consistência
                result = self._try_generate_with_apis(
                    styled_prompt, 
                    character_name=character_name, 
                    scene_number=scene_number, 
                    location_name=location_name,
                    consistency_seed=consistency_seed
                )
                
                if result:
                    print(f"Imagem gerada com sucesso para {context_info if context_info else 'prompt genérico'}")
                    return result
                    
            except Exception as e:
                print(f"Erro na tentativa {attempt+1}: {str(e)}")
                if attempt == max_retries - 1:  # Última tentativa
                    print("Todas as tentativas falharam. Gerando imagem de placeholder.")
                    break
        
        # Se todas as tentativas falharam ou estamos em modo simulado, gera uma imagem de placeholder
        # Usa o novo método _generate_placeholder_image
        placeholder_text = f"Imagem para {context_info if context_info else 'prompt genérico'}: {prompt[:150]}..."
        
        # Determina o tamanho da imagem baseado no tipo (personagem ou cena)
        if character_name:
            width, height = 768, 768  # Quadrado para personagens
        else:
            width, height = 1344, 768  # Widescreen para cenas (16:9)
            
        # Determina as cores baseadas no contexto
        if character_name:
            # Cores mais vibrantes para personagens
            bg_color = (220, 230, 240)
            text_color = (50, 50, 100)
        else:
            # Cores mais suaves para cenas
            bg_color = (200, 210, 220)
            text_color = (80, 80, 80)
            
        # Gera a imagem de placeholder usando o método dedicado
        placeholder_image = self._generate_placeholder_image(
            text=placeholder_text,
            width=width,
            height=height,
            bg_color=bg_color,
            text_color=text_color
        )
        
        # Registra a falha no log
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'image_generation_errors.log')
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] Falha na geração de imagem para {context_info if context_info else 'prompt genérico'}\n")
            f.write(f"Prompt: {prompt[:200]}...\n")
            f.write(f"Usando imagem de placeholder como fallback.\n\n")
            
        print(f"Gerada imagem de placeholder para {context_info if context_info else 'prompt genérico'}")
        return placeholder_image

        if simulate_mode:
            print("Modo simulado: Gerando imagem para prompt: {0}...".format(prompt[:100]))
            # Simula o tempo de geração
            time.sleep(1)
            # Usa o novo método _generate_placeholder_image
            return self._generate_placeholder_image(prompt)

        try:
            # Obtém o estilo de imagem a ser usado
            style_description = IMAGE_STYLES.get(self.image_style, IMAGE_STYLES['Disney_3.0'])
            styled_prompt = "Create a {} image of {}".format(style_description, prompt)

            # Tenta usar cada provedor de API na ordem definida
            for provider in self.api_providers:
                # Verifica se temos uma chave válida para este provedor
                api_key = self.api_keys.get(provider)
                if not api_key:
                    continue  # Pula para o próximo provedor se não houver chave

                # Verifica se a imagem está no cache para este provedor
                cached_image = self._get_from_cache(prompt, self.image_style, provider)
                if cached_image:
                    print("Usando imagem do cache para provedor {}: {}...".format(provider, prompt[:50]))
                    return cached_image

                # 1. Tenta usar a API do Stability AI (Stable Diffusion)
                if provider == 'stability':
                    # Sistema de retry com delay
                    max_retries = 3
                    retry_delay = 2  # segundos

                    for retry_attempt in range(max_retries):
                        try:
                            if retry_attempt > 0:
                                print("Tentativa {} de {} para Stability AI após {} segundos...".format(
                                    retry_attempt + 1, max_retries, retry_delay))
                                time.sleep(retry_delay)
                                # Aumenta o delay exponencialmente para cada nova tentativa
                                retry_delay *= 2

                            # Obtém o modelo configurado ou usa o padrão
                            stability_model = API_KEYS.get('STABILITY_MODEL') or os.environ.get(
                                'STABILITY_MODEL', 'stable-diffusion-xl-1024-v1-0')

                            # Modelos disponíveis do Stability AI
                            stability_models = {
                                'stable-diffusion-xl-1024-v1-0': {
                                    'name': 'SDXL 1.0',
                                    'cfg_scale': 7,
                                    'steps': 30,
                                    'width': 1344,  # Dimensão permitida para SDXL 1.0
                                    'height': 768   # Dimensão permitida para SDXL 1.0 (mantém proporção 16:9)
                                },
                                'stable-diffusion-v1-5': {
                                    'name': 'SD 1.5',
                                    'cfg_scale': 7,
                                    'steps': 50,  # Mais steps para melhor qualidade
                                    'width': 768,
                                    'height': 432  # Proporção 16:9 para formato widescreen
                                },
                                'stable-diffusion-512-v2-1': {
                                    'name': 'SD 2.1',
                                    'cfg_scale': 8,  # Mais guidance para melhor aderência ao prompt
                                    'steps': 40,
                                    'width': 768,
                                    'height': 432  # Proporção 16:9 para formato widescreen
                                }
                            }

                            # Obtém as configurações do modelo selecionado ou usa o padrão
                            model_config = stability_models.get(
                                stability_model, stability_models['stable-diffusion-xl-1024-v1-0'])
                            print("Usando modelo Stability AI: {} ({})".format(stability_model, model_config['name']))

                            # URL da API do Stability AI (usando o endpoint mais recente)
                            api_url_stability = "https://api.stability.ai/v1/generation/{}/text-to-image".format(
                                stability_model)
                                
                            # URL alternativa caso a primeira falhe
                            api_url_stability_alt = "https://api.stability.ai/v2/generation/{}/text-to-image".format(
                                stability_model)

                            # Cabeçalho para API do Stability AI
                            headers_stability = {
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                                "Authorization": "Bearer {}".format(api_key)
                            }

                            # Configuração para API do Stability AI
                            # Dicionário de prompts em inglês para cada cena com elementos visuais ricos
                            scene_prompts = {
                                # Cenas da história de Alice (inspiração em Alice no País das Maravilhas)
                                'O Dilema dos Gatinhos': "A young girl named Alice with long blonde hair and a worried expression, holding three mischievous kittens in a Victorian university garden. One kitten is trying to escape. Magical atmosphere with flowers that seem to have faces. Golden afternoon light filtering through ancient oak trees. Disney style illustration with vibrant colors, magical atmosphere, expressive characters, children's book style.",
                                'A Busca no Jardim': "Alice searching for hiding places for kittens in a magical Victorian university garden. Ancient trees with twisted trunks and vibrant flowers that seem to watch her. A stone bench covered with moss, perfect for hiding kittens. Butterflies with unusual patterns flutter nearby. Perspective showing both Alice and the vastness of the garden. Disney style illustration with magical atmosphere and rich details.",
                                'Ludovico e as Formigas': "Professor Ludovico (resembling Lewis Carroll with distinctive features) kneeling in the garden observing ants through a golden magnifying glass, with Alice watching curiously over his shoulder. The ants are forming mathematical patterns. Ludovico has a pocket watch visible in his waistcoat. Dappled sunlight through leaves creates patterns on the ground. Disney style illustration with detailed nature elements and Victorian-era clothing details.",
                                'O Chá com o Professor': "Alice and Professor Ludovico having tea in a Victorian garden gazebo. A whimsical tea set with mismatched cups. Mathematics books, papers with equations, and a chess set with unusual pieces on the table. A dormouse sleeping in a teapot. Pocket watch prominently displayed. Warm golden afternoon lighting. Disney style illustration with warm colors and intricate details on the tea service.",
                                'O Coelho Apressado': "Alice spotting a white rabbit in a hurry running through the university garden, checking his golden pocket watch with a panicked expression. The rabbit is wearing a red waistcoat with ornate buttons. Alice's expression shows wonder and curiosity. Garden path winding through flowering bushes. Magical atmosphere with subtle glowing elements. Disney style illustration with dynamic movement and sense of urgency.",
                                'O Passeio de Barco': "Alice and Professor Ludovico on a wooden boat ride on the Thames river. Golden afternoon sun creating sparkles on the water. Ludovico is telling a story with animated hand gestures while Alice listens with wonder. Willow trees draping over the water's edge. Water lilies and curious fish visible in the clear water. Disney style illustration with vibrant colors, flowing water, and dreamy atmosphere reminiscent of the origin of Alice in Wonderland.",
                                'A Mágica do Açucareiro': "Alice watching in wonder as a sugar bowl performs magical movements on a tea table in the garden. The sugar bowl has a face-like pattern and is spinning while sugar crystals float in the air, sparkling in the sunlight. Other tea items seem to be subtly animated. A dormouse peeks from behind a teapot. Disney style illustration with magical elements, sparkling effects, and whimsical animation.",
                                'A Descoberta da Toca': "Alice discovering a large rabbit hole under a gnarled tree in the university garden. She's kneeling at the edge, peering down with a curious expression. The hole has an unusual glow coming from within. Pocket watch and playing cards scattered near the entrance. Unusual mushrooms growing around the hole. Disney style illustration with magical atmosphere and a sense of mystery and adventure.",
                                # Personagens da história com detalhes visuais ricos
                                'Alice': "Young girl with long blonde hair cascading past her shoulders, bright curious blue eyes, and an inquisitive expression. Wearing a blue Victorian-style dress with puffed sleeves, white pinafore with pockets, striped stockings, and black Mary Jane shoes. A small golden key on a ribbon around her neck. Disney style character design with expressive features, bright eyes, and fluid movement poses.",
                                'Ludovico': "Middle-aged mathematics professor resembling Lewis Carroll, with kind eyes behind wire-rimmed spectacles, neatly trimmed mustache, and slightly disheveled hair. Wearing formal Victorian-era clothing including a brown tweed waistcoat with watch chain, bow tie, and tailored jacket with elbow patches. Carries a notebook filled with mathematical equations and sketches. Disney style character design with scholarly appearance and gentle, thoughtful expression.",
                                'Coelho': "White rabbit with long ears and pink eyes, wearing an ornate red waistcoat with gold embroidery, checkered bow tie, and tiny spectacles perched on his nose. Constantly checking a golden pocket watch with intricate engravings. Expression shows perpetual worry about being late. Disney style character design with expressive features, detailed clothing, and dynamic rushing poses.",
                                'Gato': "Adorable kitten with soft striped fur in orange and cream colors, bright green eyes with a mischievous gleam, and unusually expressive face. Pink nose, whiskers that seem to twitch with curiosity, and a wide grin. Wearing a tiny blue ribbon around its neck. Disney style character design with vibrant colors, adorable features, and playful, fluid movement.",
                                'Gatos': "Group of playful kittens with different colors and patterns - one black with white paws, one calico with patches of orange and black, one grey tabby with blue eyes, and one pure white with unusual purple eyes. Each with unique personality traits shown through their expressions and poses. All wearing tiny different colored ribbons. Disney style character design with expressive features, dynamic poses, and harmonious color palette."
                            }

                            # Prompt padrão em inglês para casos não cobertos pelo dicionário
                            default_prompt = "Disney style illustration with vibrant colors, magical atmosphere, expressive characters. Children's book style, detailed, high quality."

                            # Verifica se o prompt corresponde a uma cena ou personagem conhecido
                            final_prompt = default_prompt

                            # Primeiro, tenta encontrar uma correspondência exata
                            for known_prompt_key, known_prompt_value in scene_prompts.items():
                                if known_prompt_key == prompt:
                                    final_prompt = known_prompt_value
                                    break

                            # Se não encontrou correspondência exata, procura por palavras-chave
                            if final_prompt == default_prompt:
                                for known_prompt_key, known_prompt_value in scene_prompts.items():
                                    if known_prompt_key in prompt:
                                        final_prompt = known_prompt_value
                                        break
                            print("Prompt traduzido para Stability AI: {}".format(final_prompt))

                            # Configuração do payload com base no modelo selecionado
                            payload_stability = {
                                "text_prompts": [
                                    {
                                        "text": final_prompt + ", full body shot, wide angle view, full scene composition, widescreen format, cinematic framing, nothing cropped out of frame",
                                        "weight": 1.0
                                    }
                                ],
                                "cfg_scale": model_config['cfg_scale'],
                                "height": model_config['height'],
                                "width": model_config['width'],
                                "samples": 1,
                                "steps": model_config['steps']
                            }

                            # Adiciona prompts negativos para melhorar a qualidade
                            negative_prompt = "poor quality, low resolution, bad anatomy, worst quality, low quality, blurry, distorted, deformed, disfigured, text, watermark, cropped, cut off, zoomed in, close-up, out of frame, body parts missing, incomplete scene, truncated"
                            payload_stability["text_prompts"].append({"text": negative_prompt, "weight": -1.0})

                            print("Tentando gerar imagem com Stability AI para: {}...".format(final_prompt[:50]))
                            try:
                                # Tenta verificar a conexão com a API antes de enviar o prompt completo
                                try:
                                    test_response = requests.get(
                                        "https://api.stability.ai/v1/engines/list",
                                        headers={"Authorization": "Bearer {}".format(api_key)},
                                        timeout=10
                                    )
                                    
                                    print("Resposta da API (engines/list): Status {}".format(test_response.status_code))
                                    print("Conteúdo da resposta: {}".format(test_response.text))
                                    
                                    if test_response.status_code != 200:
                                        # Tenta endpoint alternativo
                                        print("Tentando endpoint alternativo v2/engines/list...")
                                        test_response = requests.get(
                                            "https://api.stability.ai/v2/engines/list",
                                            headers={"Authorization": "Bearer {}".format(api_key)},
                                            timeout=10
                                        )
                                        print("Resposta da API v2: Status {}".format(test_response.status_code))
                                        print("Conteúdo da resposta v2: {}".format(test_response.text))
                                except Exception as e:
                                    print("Erro ao verificar conexão com a API: {}".format(str(e)))
                                    test_response = type('obj', (object,), {'status_code': 500})

                                if test_response.status_code == 200:
                                    print("Conexão com Stability AI estabelecida com sucesso")
                                else:
                                    print("Aviso: Conexão com Stability AI retornou status {}".format(test_response.status_code))
                                    print("Continuando mesmo com erro de conexão para tentar gerar imagem...")

                                # Envia o prompt para geração de imagem
                                try:
                                    print("Enviando requisição para: {}".format(api_url_stability))
                                    print("Payload: {}".format(json.dumps(payload_stability, indent=2)))
                                    
                                    response_stability = requests.post(
                                        api_url_stability,
                                        headers=headers_stability,
                                        json=payload_stability,
                                        timeout=90  # Aumenta o timeout para 90 segundos
                                    )
                                    
                                    print("Resposta da API de geração: Status {}".format(response_stability.status_code))
                                    print("Conteúdo da resposta: {}".format(response_stability.text[:500])) # Limita a 500 caracteres
                                    
                                    # Se falhar com a primeira URL, tenta a URL alternativa
                                    if response_stability.status_code != 200:
                                        print("Tentando URL alternativa para Stability AI...")
                                        print("Enviando requisição para: {}".format(api_url_stability_alt))
                                        
                                        response_stability = requests.post(
                                            api_url_stability_alt,
                                            headers=headers_stability,
                                            json=payload_stability,
                                            timeout=90
                                        )
                                        
                                        print("Resposta da API alternativa: Status {}".format(response_stability.status_code))
                                        print("Conteúdo da resposta alternativa: {}".format(response_stability.text[:500]))
                                except Exception as e:
                                    print("Erro ao enviar prompt para Stability AI: {}".format(str(e)))
                                    # Cria um objeto de resposta simulado para continuar o fluxo
                                    response_stability = type('obj', (object,), {'status_code': 500, 'text': str(e)})
                            except requests.exceptions.ConnectionError as conn_err:
                                print("Erro de conexão com Stability AI: {}".format(str(conn_err)))
                                # Tenta novamente com um proxy diferente ou configuração alternativa
                                try:
                                    print("Tentando conexão alternativa com Stability AI...")
                                    response_stability = requests.post(
                                        api_url_stability,
                                        headers=headers_stability,
                                        json=payload_stability,
                                        timeout=90,
                                        verify=False  # Desativa verificação SSL para teste
                                    )
                                except Exception as retry_err:
                                    print("Falha na segunda tentativa: {}".format(str(retry_err)))
                                    raise

                            if response_stability.status_code == 200:
                                result = response_stability.json()
                                # Processa a resposta do Stability AI
                                if 'artifacts' in result and len(result['artifacts']) > 0:
                                    # Obtém a primeira imagem gerada
                                    image_data = base64.b64decode(result['artifacts'][0]['base64'])

                                    print("Imagem gerada com sucesso usando a API do Stability AI")
                                    if PIL_AVAILABLE:
                                        # Converte para objeto PIL
                                        image = Image.open(BytesIO(image_data))

                                        # Redimensiona para 16:9
                                        image = self._resize_to_16_9(image)

                                        # Converte de volta para bytes
                                        output = BytesIO()
                                        image.save(output, format='PNG', quality=95)
                                        processed_image_data = output.getvalue()

                                        # Salva a imagem no cache
                                        self._save_to_cache(prompt, self.image_style, provider, processed_image_data, stability_model)

                                        return processed_image_data
                                    else:
                                        # Se PIL não estiver disponível, salva o conteúdo bruto no cache
                                        self._save_to_cache(prompt, self.image_style, provider, image_data, stability_model)
                                        return image_data

                                print("Erro ao gerar imagem com Stability AI: {}".format(response_stability.status_code))
                                print("Resposta da API: {}".format(response_stability.text))
                                
                                # Tenta extrair mais detalhes do erro
                                try:
                                    error_json = response_stability.json()
                                    if 'message' in error_json:
                                        print("Mensagem de erro: {}".format(error_json['message']))
                                    if 'name' in error_json:
                                        print("Tipo de erro: {}".format(error_json['name']))
                                except Exception as json_err:
                                    print("Não foi possível analisar a resposta JSON: {}".format(str(json_err)))

                                # Se for erro 429 (limite de taxa) ou 500 (erro de servidor), tenta novamente
                                if response_stability.status_code in [429, 500, 502, 503, 504]:
                                    if retry_attempt < max_retries - 1:  # Se não for a última tentativa
                                        continue  # Tenta novamente

                                # Se for outro tipo de erro ou a última tentativa, interrompe o loop
                                break
                            #except Exception as stability_error:
                                print("Erro ao usar a API do Stability AI: {}".format(str(stability_error)))

                                # Tenta novamente se não for a última tentativa
                                if retry_attempt < max_retries - 1:
                                    continue
                                else:
                                    break
                        except Exception as e:
                            print("Erro interno durante a tentativa de geração com Stability AI: {}".format(str(e)))
                    # Fim do bloco para Stability AI

                # Não usamos mais Qwen
                if False and provider == 'qwen':
                    try:
                        # Cabeçalho para API do Qwen2.5 (DashScope)
                        headers_qwen = {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer {0}".format(api_key)
                        }

                        # Configuração para API do Qwen2.5 (DashScope)
                        payload_qwen = {
                            "model": "qwen-vl-plus",
                            "input": {
                                "prompt": "Create a {0} style image of {1}".format(style_description, prompt)
                            },
                            "parameters": {
                                "style": "photo",  # Ou 'cartoon', 'flat', 'comics', etc.
                                "size": "1024*1024",
                                "n": 1
                            }
                        }

                        # URL da API de imagem do Qwen2.5 (DashScope)
                        api_url_qwen = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"

                        print("Tentando gerar imagem com QWEN para: {0}...".format(styled_prompt[:50]))
                        response_qwen = requests.post(
                            api_url_qwen,
                            headers=headers_qwen,
                            json=payload_qwen,
                            timeout=30  # Timeout de 30 segundos
                        )

                        if response_qwen.status_code == 200:
                            result = response_qwen.json()
                            # Formato da resposta do DashScope
                            output = result.get("output", {})
                            results = output.get("results", [])
                            if results and len(results) > 0:
                                image_url = results[0].get("url")
                                if image_url:
                                    # Baixa a imagem
                                    image_response = requests.get(image_url)
                                    if image_response.status_code == 200:
                                        print("Imagem gerada com sucesso usando a API do Qwen2.5")
                                        if PIL_AVAILABLE:
                                            # Converte para objeto PIL
                                            image = Image.open(BytesIO(image_response.content))

                                            # Redimensiona para 16:9
                                            image = self._resize_to_16_9(image)

                                            # Converte de volta para bytes
                                            output = BytesIO()
                                            image.save(output, format='JPEG', quality=95)
                                            processed_image_data = output.getvalue()

                                            # Salva a imagem no cache
                                            self._save_to_cache(prompt, self.image_style, provider, processed_image_data)

                                            return processed_image_data
                                        else:
                                            # Salva a imagem no cache
                                            self._save_to_cache(prompt, self.image_style, provider, image_response.content)
                                            return image_response.content

                        print("Erro ao gerar imagem com Qwen: {0}".format(response_qwen.status_code))
                        print(response_qwen.text)
                    except Exception as qwen_error:
                        print("Erro ao usar a API do Qwen2.5: {0}".format(str(qwen_error)))

                # Não usamos mais IA Studio
                elif False and provider == 'ia_studio':
                    try:
                        # Obtém o modelo configurado ou usa o padrão
                        gemini_model = API_KEYS.get('IA_STUDIO_MODEL') or os.environ.get('IA_STUDIO_MODEL', 'gemini-1.5-flash')
                        print("Usando modelo Gemini: {}".format(gemini_model))

                        # URL da API do Gemini
                        api_url_gemini = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(gemini_model)

                        # Adiciona a chave de API como parâmetro de consulta
                        api_url_with_key = "{}?key={}".format(api_url_gemini, api_key)

                        # Configuração para API do Gemini
                        payload_gemini = {
                            "contents": [{
                                "parts": [{
                                    "text": "Generate an image in {} style. The image should show: {}".format(style_description, prompt)
                                }]
                            }],
                            "generationConfig": {
                                "temperature": 0.4,
                                "topK": 32,
                                "topP": 1,
                                "maxOutputTokens": 2048
                            }
                        }

                        # URL da API de imagem do Gemini
                        api_url_gemini = "https://api.openai.com/v1/images/generations"

                        print("Tentando gerar imagem com IA Studio (Gemini) para: {0}...".format(styled_prompt[:50]))
                        response_gemini = requests.post(
                            api_url_gemini,
                            json=payload_gemini,
                            timeout=30  # Timeout de 30 segundos
                        )

                        if response_gemini.status_code == 200:
                            result = response_gemini.json()
                            # Processa a resposta do Gemini (ajuste conforme a estrutura real da resposta)
                            if 'candidates' in result and len(result['candidates']) > 0:
                                candidate = result['candidates'][0]
                                if 'content' in candidate and 'parts' in candidate['content']:
                                    for part in candidate['content']['parts']:
                                        if 'inlineData' in part and 'data' in part['inlineData']:
                                            # Decodifica a imagem de base64
                                            image_data = base64.b64decode(part['inlineData']['data'])
                                            print("Imagem gerada com sucesso usando a API do IA Studio (Gemini)")
                                            if PIL_AVAILABLE:
                                                # Converte para objeto PIL
                                                image = Image.open(BytesIO(image_data))

                                                # Redimensiona para 16:9
                                                image = self._resize_to_16_9(image)

                                                # Converte de volta para bytes
                                                output = BytesIO()
                                                image.save(output, format='JPEG', quality=95)
                                                processed_image_data = output.getvalue()

                                                # Salva a imagem no cache
                                                self._save_to_cache(prompt, self.image_style, provider, processed_image_data, gemini_model)

                                                return processed_image_data
                                            else:
                                                # Salva a imagem no cache
                                                self._save_to_cache(prompt, self.image_style, provider, image_data, gemini_model)
                                                return image_data

                        print("Erro ao gerar imagem com IA Studio (Gemini): {0}".format(response_gemini.status_code))
                        print(response_gemini.text)
                    except Exception as gemini_error:
                        print("Erro ao usar a API do IA Studio (Gemini): {0}".format(str(gemini_error)))

                # Não usamos mais Deepseek
                elif False and provider == 'deepseek':
                    try:
                        # Obtém o modelo configurado ou usa o padrão
                        deepseek_model = API_KEYS.get('DEEPSEEK_MODEL') or os.environ.get('DEEPSEEK_MODEL', 'deepseek-image')
                        print("Usando modelo Deepseek: {}".format(deepseek_model))

                        # Cabeçalho para API do Deepseek
                        headers_deepseek = {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer {0}".format(api_key)
                        }

                        # Configuração para API do Deepseek
                        payload_deepseek = {
                            "model": deepseek_model,
                            "prompt": "Create a detailed {} image showing {}".format(style_description, prompt),
                            "n": 1,
                            "size": "1024x1024",
                            "response_format": "url"
                        }

                        # URL da API de imagem do Deepseek
                        api_url_deepseek = "https://api.deepseek.com/v1/images/generations"

                        print("Tentando gerar imagem com Deepseek para: {0}...".format(styled_prompt[:50]))
                        response_deepseek = requests.post(
                            api_url_deepseek,
                            headers=headers_deepseek,
                            json=payload_deepseek,
                            timeout=30  # Timeout de 30 segundos
                        )

                        if response_deepseek.status_code == 200:
                            result = response_deepseek.json()
                            # Formato da resposta do Deepseek (ajuste conforme a estrutura real da resposta)
                            if "data" in result and len(result["data"]) > 0 and "url" in result["data"][0]:
                                image_url = result["data"][0]["url"]
                                # Baixa a imagem
                                image_response = requests.get(image_url)
                                if image_response.status_code == 200:
                                    print("Imagem gerada com sucesso usando a API do Deepseek")
                                    if PIL_AVAILABLE:
                                        # Converte para objeto PIL
                                        image = Image.open(BytesIO(image_response.content))

                                        # Redimensiona para 16:9
                                        image = self._resize_to_16_9(image)

                                        # Converte de volta para bytes
                                        output = BytesIO()
                                        image.save(output, format='JPEG', quality=95)
                                        processed_image_data = output.getvalue()

                                        # Salva a imagem no cache
                                        self._save_to_cache(prompt, self.image_style, provider, processed_image_data, deepseek_model)

                                        return processed_image_data
                                    else:
                                        # Salva a imagem no cache
                                        self._save_to_cache(prompt, self.image_style, provider, image_response.content, deepseek_model)
                                        return image_response.content

                        print("Erro ao gerar imagem com Deepseek: {0}".format(response_deepseek.status_code))
                        print(response_deepseek.text)
                    except Exception as deepseek_error:
                        print("Erro ao usar a API do Deepseek: {0}".format(str(deepseek_error)))

                # Não usamos mais OpenAI
                elif False and provider == 'openai':
                    try:
                        # Cabeçalho para API da OpenAI
                        headers_openai = {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer {0}".format(api_key)
                        }

                        # Verifica se há um modelo específico configurado para a OpenAI
                        openai_model = API_KEYS.get('OPENAI_MODEL') or os.environ.get('OPENAI_MODEL', 'dall-e-3')
                        print("Usando modelo OpenAI: {0}".format(openai_model))

                        # Configuração para API DALL-E da OpenAI
                        payload_openai = {
                            "model": openai_model if openai_model != 'gpt-4o-mini' else "dall-e-3",
                            "prompt": styled_prompt,
                            "n": 1,
                            "size": "1024x1024",
                            "quality": "standard"
                        }

                        api_url_openai = "https://api.openai.com/v1/images/generations"

                        print("Gerando imagem com OpenAI para: {0}...".format(styled_prompt[:50]))
                        response_openai = requests.post(
                            api_url_openai,
                            headers=headers_openai,
                            json=payload_openai,
                            timeout=30  # Timeout de 30 segundos
                        )

                        # Processamento da resposta da API da OpenAI
                        if response_openai.status_code == 200:
                            result = response_openai.json()
                            # Formato da resposta da OpenAI
                            if "data" in result and len(result["data"]) > 0 and "url" in result["data"][0]:
                                image_url = result["data"][0]["url"]
                                # Baixa a imagem
                                try:
                                    image_response = requests.get(image_url, timeout=30)
                                    if image_response.status_code == 200:
                                        print("Imagem gerada com sucesso usando a API da OpenAI")
                                        if PIL_AVAILABLE:
                                            # Converte para objeto PIL
                                            image = Image.open(BytesIO(image_response.content))

                                            # Redimensiona para 16:9
                                            image = self._resize_to_16_9(image)

                                            # Converte de volta para bytes
                                            output = BytesIO()
                                            image.save(output, format='JPEG', quality=95)
                                            processed_image_data = output.getvalue()

                                            # Salva a imagem no cache
                                            self._save_to_cache(prompt, self.image_style, provider, processed_image_data, openai_model)

                                            return processed_image_data
                                        else:
                                            # Salva a imagem no cache
                                            self._save_to_cache(prompt, self.image_style, provider, image_response.content, openai_model)
                                            return image_response.content
                                except Exception as download_error:
                                    print("Erro ao baixar a imagem: {0}".format(str(download_error)))

                        print("Erro ao gerar imagem com OpenAI: {0}".format(response_openai.status_code))
                        print(response_openai.text)
                    except Exception as openai_error:
                        print("Erro ao usar a API da OpenAI: {0}".format(str(openai_error)))
            # Se chegamos aqui, nenhuma API funcionou
            print("Todas as APIs falharam. Gerando imagem de placeholder avançado como fallback final...")
            # Usa a função de placeholder existente, que já é bastante avançada
            return self.generate_placeholder_image(prompt)

        except Exception as e:
            print("Erro ao gerar imagem: {0}".format(str(e)))
            print("Gerando imagem de placeholder avançado como fallback final...")
            return self.generate_placeholder_image(prompt)

    def _save_image(self, image_data, filename, output_dir):
        """
        Salva os dados da imagem em um arquivo.
        
        Args:
            image_data: Dados binários da imagem ou objeto PIL.Image
            filename: Nome do arquivo
            output_dir: Diretório de saída
            
        Returns:
            Caminho completo para a imagem salva
        """
        # Cria o diretório se não existir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        image_path = os.path.join(output_dir, filename)

        # Verifica se os dados da imagem são bytes ou um objeto PIL.Image
        if isinstance(image_data, bytes):
            with open(image_path, 'wb') as f:
                f.write(image_data)
        else:
            # Assume que é um objeto PIL.Image
            image_data.save(image_path)

        return image_path
        
    def _generate_placeholder_image(self, text, width=512, height=512, bg_color=(240, 240, 240), text_color=(100, 100, 100)):
        """
        Gera uma imagem de placeholder com texto e elementos visuais quando a geração de imagem falha.
        
        Args:
            text: Texto a ser exibido na imagem
            width: Largura da imagem
            height: Altura da imagem
            bg_color: Cor de fundo (R,G,B)
            text_color: Cor do texto (R,G,B)
            
        Returns:
            Bytes da imagem de placeholder em formato PNG
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
            import random
            import re
            import io
            import numpy as np
            import os
            
            # Extrai palavras-chave do texto para determinar elementos visuais
            keywords = re.findall(r'\b\w{3,}\b', text.lower())
            common_objects = [
                'gato', 'coelho', 'personagem', 'jardim', 'livro', 'universidade', 'professor',
                'matemática', 'xadrez', 'barco', 'rio', 'história', 'relógio', 'rosa', 'flor', 
                'criança', 'escola', 'aventura', 'magia', 'floresta', 'castelo', 'príncipe', 'princesa'
            ]
            
            # Cria uma imagem com fundo sólido e um gradiente suave
            image = Image.new('RGB', (width, height), color=bg_color)
            draw = ImageDraw.Draw(image)
            
            # Adiciona um gradiente suave ao fundo
            for y in range(height):
                # Calcula a intensidade do gradiente baseado na posição vertical
                factor = y / height
                # Cria uma cor ligeiramente diferente para cada linha
                r = int(bg_color[0] * (1 - factor * 0.3))
                g = int(bg_color[1] * (1 - factor * 0.2))
                b = int(bg_color[2] * (1 - factor * 0.1))
                # Desenha uma linha horizontal com a cor calculada
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # Tenta carregar fontes, ou usa a fonte padrão se não conseguir
            try:
                # Tenta encontrar fontes no sistema
                font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"  # Caminho para Mac
                if not os.path.exists(font_path):
                    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux
                
                title_font = ImageFont.truetype(font_path, 40)
                font = ImageFont.truetype(font_path, 24)
                small_font = ImageFont.truetype(font_path, 18)
            except IOError:
                # Se não encontrar, usa a fonte padrão
                font = ImageFont.load_default()
                title_font = font
                small_font = font
            
            # Adiciona elementos visuais baseados nas palavras-chave
            detected_objects = [obj for obj in common_objects if obj in text.lower()]
            if not detected_objects:
                # Se não detectou nenhum objeto conhecido, seleciona aleatoriamente
                detected_objects = random.sample(common_objects, min(3, len(common_objects)))
            
            # Desenha formas simples baseadas nos objetos detectados
            for obj in detected_objects[:3]:  # Limita a 3 objetos
                if obj in ['personagem', 'criança', 'príncipe', 'princesa']:
                    # Desenha uma figura humana simples
                    x, y = random.randint(width//4, 3*width//4), random.randint(height//4, 3*height//4)
                    # Cabeça
                    head_color = (random.randint(200, 240), random.randint(180, 220), random.randint(160, 200))
                    draw.ellipse((x-20, y-20, x+20, y+20), fill=head_color, outline=(0, 0, 0))
                    # Corpo
                    body_color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
                    draw.line((x, y+20, x, y+60), fill=(0, 0, 0), width=2)
                    # Braços
                    draw.line((x, y+30, x-30, y+50), fill=(0, 0, 0), width=2)
                    draw.line((x, y+30, x+30, y+50), fill=(0, 0, 0), width=2)
                    # Pernas
                    draw.line((x, y+60, x-20, y+100), fill=(0, 0, 0), width=2)
                    draw.line((x, y+60, x+20, y+100), fill=(0, 0, 0), width=2)
                    # Olhos
                    draw.ellipse((x-10, y-10, x-5, y-5), fill=(255, 255, 255), outline=(0, 0, 0))
                    draw.ellipse((x+5, y-10, x+10, y-5), fill=(255, 255, 255), outline=(0, 0, 0))
                    # Boca
                    draw.arc((x-10, y, x+10, y+10), 0, 180, fill=(0, 0, 0), width=1)
                
                elif obj in ['jardim', 'rosa', 'flor', 'floresta']:
                    # Desenha flores e plantas
                    for _ in range(5):
                        flower_x = random.randint(width//10, 9*width//10)
                        flower_y = random.randint(2*height//3, 9*height//10)
                        # Caule
                        draw.line((flower_x, flower_y, flower_x, flower_y+50), fill=(20, 120, 20), width=2)
                        # Pétalas
                        petal_color = (random.randint(200, 255), random.randint(100, 200), random.randint(100, 200))
                        for angle in range(0, 360, 45):
                            rad = np.radians(angle)
                            x1 = flower_x + 15 * np.cos(rad)
                            y1 = flower_y + 15 * np.sin(rad)
                            draw.ellipse((x1-8, y1-8, x1+8, y1+8), fill=petal_color)
                        # Centro
                        draw.ellipse((flower_x-5, flower_y-5, flower_x+5, flower_y+5), fill=(255, 220, 0))
                
                elif obj in ['castelo', 'universidade']:
                    # Desenha um castelo/edifício simples
                    castle_x = random.randint(width//4, 3*width//4)
                    castle_y = height - 150
                    castle_width = 120
                    castle_height = 100
                    # Corpo principal
                    draw.rectangle((castle_x, castle_y, castle_x+castle_width, castle_y+castle_height), 
                                  fill=(180, 180, 180), outline=(100, 100, 100))
                    # Torres
                    tower_width = 20
                    draw.rectangle((castle_x-tower_width, castle_y, castle_x, castle_y+castle_height+20),
                                 fill=(160, 160, 160), outline=(100, 100, 100))
                    draw.rectangle((castle_x+castle_width, castle_y, castle_x+castle_width+tower_width, castle_y+castle_height+20),
                                 fill=(160, 160, 160), outline=(100, 100, 100))
                    # Porta
                    draw.rectangle((castle_x+castle_width//2-15, castle_y+castle_height-40, castle_x+castle_width//2+15, castle_y+castle_height),
                                 fill=(120, 80, 40), outline=(0, 0, 0))
                    # Janelas
                    for i in range(3):
                        draw.rectangle((castle_x+20+i*30, castle_y+20, castle_x+40+i*30, castle_y+40),
                                     fill=(200, 200, 255), outline=(0, 0, 0))
            
            # Prepara o texto (quebra em linhas)
            wrapper = textwrap.TextWrapper(width=min(40, width//10))
            word_list = wrapper.wrap(text=text)
            # Limita o número de linhas para não sobrecarregar a imagem
            if len(word_list) > 8:
                word_list = word_list[:7] + ['...']
            caption_text = '\n'.join(word_list)
            
            # Cria um fundo semi-transparente para o texto
            text_box_margin = 20
            text_box_padding = 10
            text_box_height = len(word_list) * 30 + 2 * text_box_padding
            text_box_y = height - text_box_height - text_box_margin
            
            # Desenha um retângulo semi-transparente para o texto
            draw.rectangle([(text_box_margin, text_box_y), 
                           (width - text_box_margin, text_box_y + text_box_height)], 
                          fill=(50, 50, 50, 128), outline=(200, 200, 200))
            
            # Desenha o texto
            text_y = text_box_y + text_box_padding
            for line in word_list:
                # Calcula a largura do texto para centralizá-lo
                try:
                    text_width = draw.textlength(line, font=font)
                except AttributeError:
                    # Fallback para versões mais antigas do PIL
                    text_width, _ = draw.textsize(line, font=font)
                
                text_x = (width - text_width) // 2
                draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255))
                text_y += 30
            
            # Adiciona um aviso de placeholder no topo
            header_text = "IMAGEM SIMULADA"
            try:
                header_width = draw.textlength(header_text, font=title_font)
            except AttributeError:
                # Fallback para versões mais antigas do PIL
                header_width, _ = draw.textsize(header_text, font=title_font)
                
            # Desenha um retângulo para o título
            draw.rectangle([(0, 10), (width, 60)], fill=(200, 50, 50, 180))
            draw.text(((width - header_width) // 2, 15), header_text, font=title_font, fill=(255, 255, 255))
            
            # Adiciona uma borda à imagem
            border_width = 4
            draw.rectangle([(0, 0), (width-1, height-1)], outline=(180, 180, 180), width=border_width)
            
            # Converte a imagem para bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            print(f"Erro ao gerar imagem de placeholder: {e}")
            # Cria uma imagem extremamente simples como fallback
            try:
                from PIL import Image
                import io
                # Cria uma imagem simples com texto indicando erro
                img = Image.new('RGB', (width, height), color=(255, 200, 200))
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue()
            except Exception:
                # Se tudo falhar, retorna bytes vazios
                return b"PLACEHOLDER_IMAGE_ERROR"
                
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
        
    def test_seed_consistency(self, output_dir):
        """Testa a consistência visual nas imagens geradas usando o sistema de seeds.
        
        Gera múltiplas imagens para o mesmo personagem, cena e local para verificar
        se a consistência visual é mantida.
        
        Args:
            output_dir: Diretório para salvar as imagens de teste
        
        Returns:
            Dict com resultados do teste e caminhos das imagens geradas
        """
        print("\n=== Iniciando teste de consistência visual com seeds ===\n")
        
        # Cria diretório de teste se não existir
        test_dir = os.path.join(output_dir, 'seed_consistency_test')
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
        
        # Carrega o cache para o teste
        cache = self._load_cache(test_dir)
        
        # Gera múltiplas imagens do mesmo personagem para testar consistência
        print(f"\n--- Testando consistência para o personagem '{character_name}' ---")
        for i in range(3):
            output_path = os.path.join(test_dir, f"{character_name}_test_{i+1}.png")
            print(f"Gerando imagem {i+1} para o personagem {character_name}...")
            
            # Usa o mesmo personagem mas varia ligeiramente o prompt para testar consistência
            variation_prompt = f"{character_prompt}, {['smiling', 'serious face', 'looking surprised'][i]}"
            
            # Gera a imagem com o seed consistente para o personagem
            image_data = self._generate_image(
                prompt=variation_prompt,
                character_name=character_name,
                max_retries=2
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
            
            # Gera a imagem com o seed consistente para a cena
            image_data = self._generate_image(
                prompt=variation_prompt,
                scene_number=scene_number,
                max_retries=2
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
            
            # Gera a imagem com o seed consistente para o local
            image_data = self._generate_image(
                prompt=variation_prompt,
                location_name=location_name,
                max_retries=2
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
        self._save_cache(test_dir, cache)
        
        # Gera relatório de resultados
        print("\n=== Resultados do teste de consistência visual ===\n")
        print(f"Imagens de personagem geradas: {len(test_results['character_images'])}")
        print(f"Imagens de cena geradas: {len(test_results['scene_images'])}")
        print(f"Imagens de local geradas: {len(test_results['location_images'])}")
        print(f"\nTodas as imagens foram salvas em: {test_dir}")
        print("\nVerifique visualmente as imagens para confirmar a consistência visual.")
        print("Os personagens, cenas e locais devem manter características visuais consistentes entre as imagens.")
        
        return test_results

    def generate_character_designs(self, output_dir):
        """
        Gera designs para todos os personagens no roteiro.
        
        Args:
            output_dir: Diretório para salvar as imagens
            
        Returns:
            Dicionário mapeando personagens para caminhos de imagens
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi carregado. Execute load_script() primeiro.")

        # Coleta todos os personagens únicos do roteiro
        all_characters = set()
        for scene in self.script:
            all_characters.update(scene.get('characters', []))

        print("Gerando designs para {0} personagens...".format(len(all_characters)))

        # Cria o diretório de saída para personagens
        character_dir = os.path.join(output_dir, 'characters')
        if not os.path.exists(character_dir):
            os.makedirs(character_dir)

        # Gera imagens para cada personagem (apenas os que não estão no cache)
        characters_to_generate = [c for c in all_characters if c not in self.character_designs]
        if characters_to_generate:
            print(f"Gerando {len(characters_to_generate)} novos designs de personagens...")
        else:
            print("Todos os designs de personagens já estão em cache.")
            
        for character in characters_to_generate:
            print("Gerando design para: {0}".format(character))
            prompt = self._generate_character_prompt(character)

            # Em modo de simulação ou desenvolvimento, apenas registra o prompt
            if not self.api_key:
                print("Prompt para {0}: {1}".format(character, prompt))
                self.character_designs[character] = "[Simulado] {0}.png".format(character)
                continue

            try:
                # Adiciona instruções específicas para consistência visual
                consistency_note = "\nEste personagem deve manter exatamente a mesma aparência em todas as cenas. Garantir consistência absoluta em roupas, cabelo, características físicas e expressões."
                enhanced_prompt = prompt + consistency_note
                
                print(f"Gerando imagem para {character} com consistência visual aprimorada...")
                
                # Gera uma seed consistente baseada no nome do personagem
                # Isso garante que o mesmo personagem tenha uma aparência consistente mesmo se regenerado
                character_seed = abs(hash(character)) % 2147483647  # Valor máximo para int32
                
                # Gera a imagem com o provedor selecionado e sistema de retry
                # Passa o nome do personagem e a seed para garantir consistência visual
                image_data = self._generate_image(
                    enhanced_prompt, 
                    character_name=character,
                    consistency_seed=character_seed,
                    max_retries=5, 
                    retry_delay=3
                )

                if image_data:
                    # Salva a imagem
                    filename = "{0}.png".format(character.lower().replace(' ', '_'))
                    image_path = self._save_image(image_data, filename, character_dir)
                    self.character_designs[character] = image_path
                    print("Design para {0} salvo em: {1}".format(character, image_path))
                    
                    # Registra o prompt usado para referência futura
                    prompt_file = os.path.join(character_dir, "{0}_prompt.txt".format(character.lower().replace(' ', '_')))
                    with open(prompt_file, 'w', encoding='utf-8') as f:
                        f.write(enhanced_prompt)
                    
                    # Salva o cache após cada personagem gerado com sucesso
                    metadata = {
                        'characters': {k: os.path.basename(v) for k, v in self.character_designs.items()},
                        'scenes': {str(k): os.path.basename(v) for k, v in self.scene_images.items()},
                        'prompts': {character: enhanced_prompt},  # Armazena o prompt usado para referência
                        'seeds': {character: character_seed},  # Armazena a seed para consistência
                        'timestamp': datetime.datetime.now().isoformat(),
                        'style': self.image_style
                    }
                    self._save_cache(output_dir, metadata)
                    print(f"Cache atualizado para {character}")
                else:
                    print(f"Falha ao gerar design para {character} após múltiplas tentativas")
                    # Tenta gerar uma imagem de placeholder como fallback
                    placeholder_image = self.generate_placeholder_image(enhanced_prompt)
                    if placeholder_image:
                        filename = "{0}_placeholder.png".format(character.lower().replace(' ', '_'))
                        image_path = self._save_image(placeholder_image, filename, character_dir)
                        self.character_designs[character] = image_path
                        print(f"Imagem placeholder gerada para {character} em: {image_path}")
            except Exception as e:
                print(f"Erro ao gerar design para {character}: {e}")
                # Registra o erro no log
                error_log = os.path.join(output_dir, 'error_log.txt')
                with open(error_log, 'a', encoding='utf-8') as f:
                    f.write(f"\n[{datetime.datetime.now()}] Erro ao gerar {character}: {str(e)}")
                # Continua com o próximo personagem

        return self.character_designs

    def generate_scene_images(self, output_dir):
        """
        Gera imagens para todas as cenas no roteiro.
        
        Args:
            output_dir: Diretório para salvar as imagens
            
        Returns:
            Dicionário mapeando números de cenas para caminhos de imagens
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi carregado. Execute load_script() primeiro.")

        print("Processando {0} cenas...".format(len(self.script)))

        # Cria o diretório de saída para cenas
        scene_dir = os.path.join(output_dir, 'scenes')
        if not os.path.exists(scene_dir):
            os.makedirs(scene_dir)

        # Identifica cenas que precisam ser geradas (não estão no cache)
        scenes_to_generate = []
        for i, scene in enumerate(self.script):
            scene_number = scene.get('scene_number', i + 1)
            if scene_number not in self.scene_images:
                scenes_to_generate.append((i, scene, scene_number))

        if scenes_to_generate:
            print(f"Gerando {len(scenes_to_generate)} novas imagens de cenas...")
        else:
            print("Todas as imagens de cenas já estão em cache.")
            return self.scene_images

        # Gera imagens para cada cena que não está no cache
        for i, scene, scene_number in scenes_to_generate:
            print("Gerando imagem para Cena {0}: {1}".format(scene_number, scene.get('title', '')))
            prompt = self._generate_scene_prompt(scene)

            # Em modo de simulação ou desenvolvimento, apenas registra o prompt
            if not self.api_key:
                print("Prompt para Cena {0}: {1}".format(scene_number, prompt))
                self.scene_images[scene_number] = "[Simulado] scene_{0}.png".format(scene_number)
                continue

            try:
                # Adiciona instruções específicas para consistência visual
                # Verifica se há personagens na cena para garantir sua consistência
                characters_in_scene = scene.get('characters', [])
                character_consistency = ""
                
                if characters_in_scene:
                    character_consistency = "\nPersonagens presentes devem manter exatamente a mesma aparência que em suas imagens de referência. "
                    for character in characters_in_scene:
                        if character in self.character_designs:
                            character_consistency += f"O personagem {character} deve ser consistente com sua imagem de referência. "
                
                # Verifica se há uma localização na cena para garantir consistência do ambiente
                location = scene.get('location', '')
                location_consistency = ""
                
                if location:
                    # Verifica se já geramos alguma cena com essa localização antes
                    location_scenes = [s for i, s in enumerate(self.script[:i]) if s.get('location') == location]
                    if location_scenes:
                        location_consistency = f"\nO ambiente {location} deve ser visualmente idêntico em todas as cenas, mantendo a mesma arquitetura, ângulo, iluminação e elementos decorativos."
                
                # Combina as instruções de consistência
                consistency_note = f"\nManter absoluta consistência visual com as outras cenas.{character_consistency}{location_consistency}"
                enhanced_prompt = prompt + consistency_note
                
                print(f"Gerando imagem para Cena {scene_number} com consistência visual aprimorada...")
                
                # Gera uma seed para a cena baseada no número da cena e localização
                # Isso garante consistência visual entre cenas com a mesma localização
                scene_seed = None
                
                # Se a localização já foi usada em cenas anteriores, tenta usar a mesma seed
                # para manter consistência do ambiente
                if location:
                    # Verifica no cache se já temos uma seed para esta localização
                    cache = self._load_cache(output_dir)
                    location_seeds = cache.get('location_seeds', {})
                    
                    if location in location_seeds:
                        scene_seed = location_seeds[location]
                        print(f"Usando seed {scene_seed} da localização '{location}' para manter consistência visual")
                    else:
                        # Cria uma nova seed para esta localização
                        scene_seed = abs(hash(f"location_{location}")) % 2147483647
                        print(f"Criando nova seed {scene_seed} para localização '{location}'")
                else:
                    # Se não há localização específica, usa o número da cena para a seed
                    scene_seed = abs(hash(f"scene_{scene_number}")) % 2147483647
                
                # Gera a imagem com o provedor selecionado e sistema de retry
                # Passa o número da cena e a seed para garantir consistência visual
                image_data = self._generate_image(
                    enhanced_prompt, 
                    scene_number=scene_number,
                    consistency_seed=scene_seed,
                    max_retries=5, 
                    retry_delay=3
                )

                if image_data:
                    # Salva a imagem
                    filename = "scene_{0:03d}.png".format(scene_number)
                    image_path = self._save_image(image_data, filename, scene_dir)
                    self.scene_images[scene_number] = image_path
                    print("Imagem para Cena {0} salva em: {1}".format(scene_number, image_path))
                    
                    # Registra o prompt usado para referência futura
                    prompt_file = os.path.join(scene_dir, "scene_{0:03d}_prompt.txt".format(scene_number))
                    with open(prompt_file, 'w', encoding='utf-8') as f:
                        f.write(enhanced_prompt)
                    
                    # Atualiza o cache de seeds de localização se aplicável
                    cache = self._load_cache(output_dir)
                    location_seeds = cache.get('location_seeds', {})
                    
                    if location and location not in location_seeds:
                        location_seeds[location] = scene_seed
                        cache['location_seeds'] = location_seeds
                    
                    # Salva o cache após cada cena gerada com sucesso
                    metadata = {
                        'characters': {k: os.path.basename(v) for k, v in self.character_designs.items()},
                        'scenes': {str(k): os.path.basename(v) for k, v in self.scene_images.items()},
                        'scene_prompts': {str(scene_number): enhanced_prompt},  # Armazena o prompt usado
                        'location_seeds': location_seeds,  # Armazena seeds por localização
                        'scene_seeds': {str(scene_number): scene_seed},  # Armazena a seed da cena
                        'timestamp': datetime.datetime.now().isoformat(),
                        'style': self.image_style
                    }
                    self._save_cache(output_dir, metadata)
                    print(f"Cache atualizado para Cena {scene_number}")
                else:
                    print(f"Falha ao gerar imagem para Cena {scene_number} após múltiplas tentativas")
                    # Tenta gerar uma imagem de placeholder como fallback
                    placeholder_image = self.generate_placeholder_image(enhanced_prompt)
                    if placeholder_image:
                        filename = "scene_{0:03d}_placeholder.png".format(scene_number)
                        image_path = self._save_image(placeholder_image, filename, scene_dir)
                        self.scene_images[scene_number] = image_path
                        print(f"Imagem placeholder gerada para Cena {scene_number} em: {image_path}")
            except Exception as e:
                print(f"Erro ao gerar imagem para Cena {scene_number}: {e}")
                # Registra o erro no log
                error_log = os.path.join(output_dir, 'error_log.txt')
                with open(error_log, 'a', encoding='utf-8') as f:
                    f.write(f"\n[{datetime.datetime.now()}] Erro ao gerar Cena {scene_number}: {str(e)}")
                # Continua com a próxima cena

        return self.scene_images

    # Método _load_cache foi movido para a parte superior da classe para evitar duplicação
        
    def _save_cache(self, output_dir, metadata):
        """Salva o cache de metadados de imagens com sistema de backup.
        
        Args:
            output_dir: Diretório para salvar os metadados
            metadata: Dicionário com metadados a serem salvos
            
        Returns:
            Boolean indicando se o cache foi salvo com sucesso
        """
        if not self.cache_enabled:
            return False
            
        # Carrega o cache existente para fazer merge
        existing_cache = self._load_cache(output_dir)
        
        # Prepara o diretório para backups
        backup_dir = os.path.join(output_dir, 'cache_backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Cria timestamp para o arquivo
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Faz o merge do cache existente com os novos metadados
        merged_cache = existing_cache.copy()
        
        # Atualiza cada seção do cache com os novos dados
        for key, value in metadata.items():
            if isinstance(value, dict) and key in existing_cache and isinstance(existing_cache[key], dict):
                # Para dicionários aninhados, faz um merge recursivo
                merged_cache[key] = {**existing_cache[key], **value}
            else:
                # Para outros tipos de dados, substitui completamente
                merged_cache[key] = value
        
        # Adiciona informações de timestamp
        if 'metadata' not in merged_cache:
            merged_cache['metadata'] = {}
        
        merged_cache['metadata']['last_updated'] = timestamp
        merged_cache['metadata']['version'] = merged_cache.get('metadata', {}).get('version', 0) + 1
        
        try:
            # Caminho para o arquivo de cache
            metadata_path = os.path.join(output_dir, 'image_metadata.json')
            
            # Cria um backup do cache atual antes de sobrescrever
            if os.path.exists(metadata_path):
                backup_path = os.path.join(backup_dir, f'image_metadata_{timestamp}.json')
                import shutil
                shutil.copy(metadata_path, backup_path)
                print(f"Backup do cache criado em: {backup_path}")
                
                # Limita o número de backups para economizar espaço
                backup_files = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) 
                                       if f.startswith('image_metadata_') and f.endswith('.json')])
                if len(backup_files) > 5:  # Mantém apenas os 5 backups mais recentes
                    for old_backup in backup_files[:-5]:
                        try:
                            os.remove(old_backup)
                        except Exception:
                            pass
            
            # Salva o cache atualizado
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(merged_cache, f, ensure_ascii=False, indent=2)
                
            print(f"Cache de imagens atualizado e salvo em {metadata_path}")
            print(f"Total de {len(merged_cache.get('images', {}))} imagens no cache")
            
            # Registra informações sobre seeds para personagens e cenas
            num_characters = len(merged_cache.get('character_seeds', {}))
            num_scenes = len(merged_cache.get('scene_seeds', {}))
            num_locations = len(merged_cache.get('location_seeds', {}))
            
            print(f"Cache contém seeds para {num_characters} personagens, {num_scenes} cenas e {num_locations} locais")
            return True
            
        except Exception as e:
            print(f"Erro ao salvar cache: {e}")
            # Tenta salvar em um arquivo alternativo em caso de erro
            try:
                emergency_path = os.path.join(output_dir, f'image_metadata_emergency_{timestamp}.json')
                with open(emergency_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_cache, f, ensure_ascii=False, indent=2)
                print(f"Cache de emergência salvo em {emergency_path}")
            except Exception as emergency_error:
                print(f"Erro ao salvar cache de emergência: {emergency_error}")
            
            return False
            
    def generate_placeholder_image(self, prompt, width=1024, height=1024):
        """Gera uma imagem de placeholder com texto quando as APIs de geração falham.
        
        Args:
            prompt: O prompt que seria usado para gerar a imagem
            width: Largura da imagem (padrão: 1024)
            height: Altura da imagem (padrão: 1024)
            
        Returns:
            Dados da imagem em bytes ou None se PIL não estiver disponível
        """
        if not PIL_AVAILABLE:
            print("Não é possível gerar imagem de placeholder: PIL não está instalado")
            return None
            
        try:
            # Cria uma imagem com fundo colorido
            background_colors = [
                (230, 230, 250),  # Lavender
                (240, 248, 255),  # Alice Blue
                (245, 245, 245),  # White Smoke
                (240, 255, 240),  # Honeydew
                (255, 240, 245),  # Lavender Blush
                (255, 250, 240),  # Floral White
                (240, 255, 255),  # Azure
                (250, 235, 215)   # Antique White
            ]
            
            # Seleciona uma cor de fundo aleatória
            bg_color = random.choice(background_colors)
            
            # Cria a imagem
            image = Image.new('RGB', (width, height), color=bg_color)
            draw = ImageDraw.Draw(image)
            
            # Tenta carregar uma fonte, ou usa a fonte padrão
            try:
                # Tenta encontrar uma fonte no sistema
                font_paths = [
                    '/System/Library/Fonts/Supplemental/Arial.ttf',  # macOS
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
                    'C:\\Windows\\Fonts\\arial.ttf'  # Windows
                ]
                
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, 40)
                        break
                        
                if font is None:
                    font = ImageFont.load_default()
                    
            except Exception:
                # Se falhar, usa a fonte padrão
                font = ImageFont.load_default()
            
            # Adiciona um título
            title = "Imagem Placeholder"
            title_width = draw.textlength(title, font=font) if hasattr(draw, 'textlength') else font.getsize(title)[0]
            draw.text(((width - title_width) // 2, 50), title, fill=(0, 0, 0), font=font)
            
            # Adiciona uma borda
            border_width = 10
            draw.rectangle([(border_width, border_width), (width - border_width, height - border_width)], 
                          outline=(100, 100, 100), width=5)
            
            # Adiciona o prompt (resumido)
            max_prompt_length = 200
            prompt_text = prompt[:max_prompt_length] + '...' if len(prompt) > max_prompt_length else prompt
            
            # Quebra o texto em linhas
            lines = []
            words = prompt_text.split()
            current_line = ""
            
            for word in words:
                test_line = current_line + " " + word if current_line else word
                line_width = draw.textlength(test_line, font=font) if hasattr(draw, 'textlength') else font.getsize(test_line)[0]
                
                if line_width < width - 100:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
                    
            if current_line:
                lines.append(current_line)
            
            # Desenha as linhas de texto
            y_position = height // 3
            for line in lines[:10]:  # Limita a 10 linhas
                line_width = draw.textlength(line, font=font) if hasattr(draw, 'textlength') else font.getsize(line)[0]
                draw.text(((width - line_width) // 2, y_position), line, fill=(50, 50, 50), font=font)
                y_position += 50
            
            # Adiciona uma mensagem de erro
            error_msg = "Falha na geração de imagem - Usando placeholder"
            error_width = draw.textlength(error_msg, font=font) if hasattr(draw, 'textlength') else font.getsize(error_msg)[0]
            draw.text(((width - error_width) // 2, height - 100), error_msg, fill=(255, 0, 0), font=font)
            
            # Adiciona data e hora
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            draw.text((20, height - 50), timestamp, fill=(100, 100, 100), font=font)
            
            # Converte a imagem para bytes
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            print(f"Erro ao gerar imagem placeholder: {e}")
            return None
    
    def generate_all_images(self, output_dir):
        """
        Gera todas as imagens necessárias para o roteiro.
        Implementa um sistema robusto de cache e retry para garantir a geração
        bem-sucedida de todas as imagens, com foco na consistência visual.
        
        Args:
            output_dir: Diretório para salvar as imagens
            
        Returns:
            Tupla com dicionários de personagens e cenas
        """
        print("\n=== Iniciando geração de todas as imagens ===\n")
        start_time = datetime.datetime.now()
        
        # Cria diretórios necessários se não existirem
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'characters'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'scenes'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'logs'), exist_ok=True)
        
        # Tenta carregar o cache existente
        cache = self._load_cache(output_dir)
        print(f"Status do cache: {'Encontrado' if cache else 'Não encontrado ou vazio'}")
        
        # Inicializa os dicionários de personagens e cenas a partir do cache, se disponível
        if cache and 'characters' in cache:
            self.character_designs = {k: os.path.join(output_dir, 'characters', v) 
                                     for k, v in cache['characters'].items()}
            print(f"Carregados {len(self.character_designs)} designs de personagens do cache")
            
            # Verifica se os arquivos realmente existem
            missing_characters = [k for k, v in self.character_designs.items() if not os.path.exists(v)]
            if missing_characters:
                print(f"Aviso: {len(missing_characters)} imagens de personagens estão no cache mas não foram encontradas no disco")
                for char in missing_characters:
                    print(f"  - Personagem ausente: {char}")
                    # Remove do cache para forçar a regeneração
                    del self.character_designs[char]
        else:
            self.character_designs = {}
            
        if cache and 'scenes' in cache:
            self.scene_images = {int(k): os.path.join(output_dir, 'scenes', v) 
                               for k, v in cache['scenes'].items()}
            print(f"Carregadas {len(self.scene_images)} imagens de cenas do cache")
            
            # Verifica se os arquivos realmente existem
            missing_scenes = [k for k, v in self.scene_images.items() if not os.path.exists(v)]
            if missing_scenes:
                print(f"Aviso: {len(missing_scenes)} imagens de cenas estão no cache mas não foram encontradas no disco")
                for scene_num in missing_scenes:
                    print(f"  - Cena ausente: {scene_num}")
                    # Remove do cache para forçar a regeneração
                    del self.scene_images[scene_num]
        else:
            self.scene_images = {}

        # Carrega informações de seeds e prompts para garantir consistência visual
        character_prompts = {}
        scene_prompts = {}
        character_seeds = {}
        scene_seeds = {}
        location_seeds = {}
        
        if cache and 'prompts' in cache:
            character_prompts = cache['prompts']
            print(f"Carregados {len(character_prompts)} prompts de personagens para consistência visual")
            
        if cache and 'scene_prompts' in cache:
            scene_prompts = cache['scene_prompts']
            print(f"Carregados {len(scene_prompts)} prompts de cenas para consistência visual")
            
        if cache and 'seeds' in cache:
            character_seeds = cache['seeds']
            print(f"Carregadas {len(character_seeds)} seeds de personagens para consistência visual")
            
        if cache and 'scene_seeds' in cache:
            scene_seeds = cache['scene_seeds']
            print(f"Carregadas {len(scene_seeds)} seeds de cenas para consistência visual")
            
        if cache and 'location_seeds' in cache:
            location_seeds = cache['location_seeds']
            print(f"Carregadas {len(location_seeds)} seeds de localizações para consistência visual")

        # Registra o estilo de imagem sendo usado
        print(f"\nEstilo de imagem selecionado: {self.image_style}")
        print(f"Provedores de API configurados: {', '.join(self.api_providers) if self.api_providers else 'Nenhum'}")
        
        # Gera designs de personagens (apenas os que não estão no cache)
        print("\n=== Gerando designs de personagens ===\n")
        character_designs = self.generate_character_designs(output_dir)

        # Gera imagens de cenas (apenas as que não estão no cache)
        print("\n=== Gerando imagens de cenas ===\n")
        scene_images = self.generate_scene_images(output_dir)

        # Verifica se todas as imagens foram geradas corretamente
        all_characters = set()
        for scene in self.script:
            all_characters.update(scene.get('characters', []))
            
        missing_characters = [c for c in all_characters if c not in self.character_designs]
        if missing_characters:
            print(f"\nAtenção: {len(missing_characters)} personagens não puderam ser gerados:")
            for char in missing_characters:
                print(f"  - {char}")
        
        missing_scenes = [i+1 for i in range(len(self.script)) if i+1 not in self.scene_images]
        if missing_scenes:
            print(f"\nAtenção: {len(missing_scenes)} cenas não puderam ser geradas:")
            for scene_num in missing_scenes:
                print(f"  - Cena {scene_num}")

        # Recarrega o cache para obter todas as informações atualizadas
        cache = self._load_cache(output_dir)
        
        # Atualiza as informações de seeds e prompts do cache
        if cache and 'seeds' in cache:
            character_seeds = cache['seeds']
        if cache and 'scene_seeds' in cache:
            scene_seeds = cache['scene_seeds']
        if cache and 'location_seeds' in cache:
            location_seeds = cache['location_seeds']
        if cache and 'prompts' in cache:
            character_prompts = cache['prompts']
        if cache and 'scene_prompts' in cache:
            scene_prompts = cache['scene_prompts']

        # Salva os metadados das imagens com informações adicionais
        metadata = {
            'characters': {k: os.path.basename(v) for k, v in self.character_designs.items()},
            'scenes': {str(k): os.path.basename(v) for k, v in self.scene_images.items()},
            'generation_info': {
                'start_time': start_time.isoformat(),
                'end_time': datetime.datetime.now().isoformat(),
                'total_characters': len(all_characters),
                'total_scenes': len(self.script),
                'generated_characters': len(self.character_designs),
                'generated_scenes': len(self.scene_images),
                'style': self.style,
                'image_style': self.image_style,
                'api_providers': self.api_providers
            },
            'prompts': character_prompts,
            'scene_prompts': scene_prompts,
            'seeds': character_seeds,
            'scene_seeds': scene_seeds,
            'location_seeds': location_seeds,
            'timestamp': datetime.datetime.now().isoformat()
        }

        # Salva o cache atualizado
        self._save_cache(output_dir, metadata)

        # Salva os metadados em um arquivo JSON legível
        metadata_path = os.path.join(output_dir, 'image_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Cria um arquivo de resumo com estatísticas e informações úteis
        summary_path = os.path.join(output_dir, 'generation_summary.txt')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=== RESUMO DA GERAÇÃO DE IMAGENS ===\n\n")
            f.write(f"Data e hora: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Estilo de imagem: {self.image_style}\n")
            f.write(f"Provedores de API: {', '.join(self.api_providers) if self.api_providers else 'Nenhum'}\n\n")
            
            f.write(f"Total de personagens: {len(all_characters)}\n")
            f.write(f"Personagens gerados: {len(self.character_designs)}\n")
            f.write(f"Personagens não gerados: {len(missing_characters)}\n\n")
            
            f.write(f"Total de cenas: {len(self.script)}\n")
            f.write(f"Cenas geradas: {len(self.scene_images)}\n")
            f.write(f"Cenas não geradas: {len(missing_scenes)}\n\n")
            
            # Calcula o tempo total de execução
            end_time = datetime.datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            hours, remainder = divmod(execution_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            f.write(f"Tempo total de execução: {int(hours)}h {int(minutes)}m {int(seconds)}s\n")

        # Calcula o tempo total de execução
        end_time = datetime.datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        hours, remainder = divmod(execution_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print(f"\n=== Geração de imagens concluída em {int(hours)}h {int(minutes)}m {int(seconds)}s ===\n")
        print(f"Gerados {len(self.character_designs)}/{len(all_characters)} personagens e {len(self.scene_images)}/{len(self.script)} cenas")
        print(f"Metadados salvos em: {metadata_path}")
        print(f"Resumo da geração salvo em: {summary_path}")

        return character_designs, scene_images


# Exemplo de uso
if __name__ == "__main__":
    agent = VisualDesignerAgent()

    # Carregar roteiro
    script_path = "../output/roteiro.json"
    if os.path.exists(script_path):
        agent.load_script(script_path)

        # Gerar todas as imagens
        output_dir = "../output/images"
        agent.generate_all_images(output_dir)
    else:
        print("Erro: Roteiro não encontrado em {0}".format(script_path))
