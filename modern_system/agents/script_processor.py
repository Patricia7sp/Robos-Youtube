# -*- coding: utf-8 -*-
"""
Script Processor Agent
---------------------
Este agente é responsável por analisar o texto da história e transformá-lo em um roteiro estruturado
para animação, identificando cenas, personagens, narrações e direções para animação.
"""

import os
import sys
import json
import re
import requests
from typing import List, Dict, Any, Optional

# Importa as configurações do sistema
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    import sys
    sys.path.append(sys_path)
from config.settings import API_KEYS

# Implementação com suporte à API do Qwen2.5
class ScriptProcessorAgent:
    def __init__(self, api_key=None):
        """
        Inicializa o agente de processamento de roteiro.
        
        Args:
            api_key: Chave da API Qwen2.5 (opcional, pode ser definida como variável de ambiente)
        """
        self.api_key = api_key or API_KEYS.get('QWEN_API_KEY') or os.environ.get("QWEN_API_KEY")
        self.story = ""
        self.script = []
        
    def load_story(self, story_text):
        """
        Carrega o texto da história para processamento.
        
        Args:
            story_text: Texto completo da história
        """
        self.story = story_text
        print("História carregada: {} caracteres".format(len(story_text)))
        
    def load_story_from_file(self, file_path):
        """
        Carrega o texto da história a partir de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo de texto
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            self.story = file.read()
        print("História carregada do arquivo: {}".format(file_path))
    
    def _split_into_paragraphs(self):
        """
        Divide a história em parágrafos para processamento.
        
        Returns:
            Lista de parágrafos
        """
        paragraphs = self.story.split('\n')
        # Remove parágrafos vazios
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _identify_scenes(self, paragraphs):
        """
        Identifica as cenas na história com base em mudanças de cenário, tempo ou foco.
        
        Args:
            paragraphs: Lista de parágrafos da história
            
        Returns:
            Lista de dicionários representando cenas
        """
        # Implementação simplificada - na versão final, usaremos LLMs para esta análise
        scenes = []
        current_scene = {"paragraphs": [], "location": None, "characters": []}
        
        for paragraph in paragraphs:
            # Detecta mudanças de cena com base em indicadores de tempo/local
            location_indicators = ["jardim", "sala de jantar", "toca", "universidade", "mesa", "barco"]
            time_indicators = ["primeira vez", "muitas tardes", "amanhã", "quando chegou"]
            
            # Verifica se este parágrafo indica uma nova cena
            new_scene = False
            
            # Se já temos uma cena e encontramos indicadores de nova cena
            if current_scene["paragraphs"] and any(indicator in paragraph.lower() for indicator in location_indicators + time_indicators):
                new_scene = True
            
            if new_scene:
                # Finaliza a cena atual
                scenes.append(current_scene)
                # Inicia uma nova cena
                current_scene = {"paragraphs": [], "location": None, "characters": []}
            
            # Adiciona o parágrafo à cena atual
            current_scene["paragraphs"].append(paragraph)
            
            # Tenta identificar o local da cena
            for location in location_indicators:
                if location in paragraph.lower() and not current_scene["location"]:
                    current_scene["location"] = location
            
            # Identifica personagens mencionados
            character_names = ["Alice", "Ludovico", "Lóri", "Edith", "mamãe", "papai", "professor", "Mia"]
            for character in character_names:
                if character in paragraph and character not in current_scene["characters"]:
                    current_scene["characters"].append(character)
        
        # Adiciona a última cena
        if current_scene["paragraphs"]:
            scenes.append(current_scene)
            
        return scenes
    
    def _create_script_from_scenes(self, scenes):
        """
        Transforma as cenas identificadas em um roteiro estruturado para animação.
        
        Args:
            scenes: Lista de cenas identificadas
            
        Returns:
            Roteiro estruturado para animação
        """
        script = []
        
        for i, scene in enumerate(scenes):
            scene_script = {
                "scene_number": i + 1,
                "title": "Cena {}".format(i + 1),
                "location": scene.get("location", "Indefinido"),
                "characters": scene.get("characters", []),
                "narration": "\n".join(scene["paragraphs"]),
                "dialogues": [],
                "animation_directions": [],
                "visual_elements": []
            }
            
            # Extrai diálogos (texto entre travessões)
            combined_text = " ".join(scene["paragraphs"])
            dialogue_matches = re.findall(r'[-–]([^-–]+?)[-–]', combined_text)
            
            for dialogue in dialogue_matches:
                # Tenta identificar o personagem que fala
                speaker = "Desconhecido"
                for character in scene["characters"]:
                    if combined_text.find("{}".format(character)) < combined_text.find("- {}".format(dialogue)) and \
                       combined_text.find("{}".format(character)) > combined_text.rfind(".", 0, combined_text.find("- {}".format(dialogue))):
                        speaker = character
                        break
                
                scene_script["dialogues"].append({
                    "speaker": speaker,
                    "text": dialogue.strip()
                })
            
            # Adiciona direções básicas para animação
            scene_script["animation_directions"].append(
                "Mostrar o cenário: {}".format(scene.get('location', 'local indefinido'))
            )
            
            for character in scene["characters"]:
                scene_script["animation_directions"].append(
                    "Introduzir personagem: {}".format(character)
                )
            
            # Identifica elementos visuais importantes
            visual_elements = ["gatos", "filhotes", "jardim", "toca", "coelho", "açucareiro", 
                              "ratinho", "xadrez", "peças", "baralho", "dama de copas"]
            
            for element in visual_elements:
                if element in combined_text.lower():
                    scene_script["visual_elements"].append(element)
            
            script.append(scene_script)
        
        return script
    
    def _process_with_qwen(self, text, instruction):
        """
        Processa texto usando a API do Qwen2.5 com fallback para OpenAI
        
        Args:
            text: Texto a ser processado
            instruction: Instrução para o modelo
            
        Returns:
            Resposta do modelo em formato JSON
        """
        if not self.api_key:
            print("AVISO: Sem chave de API Qwen2.5. Tentando usar OpenAI como fallback.")
            return self._process_with_openai(text, instruction)
            
        try:
            print("Tentando processar texto com a API do Qwen2.5...")
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.api_key)
            }
            
            payload = {
                "model": "qwen2.5-72b-instruct",  # Ou outro modelo Qwen disponível
                "messages": [
                    {"role": "system", "content": "Você é um assistente especializado em roteirização e narrativas para crianças."},
                    {"role": "user", "content": "{}\n\nHISTÓRIA:\n{}".format(instruction, text)}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # URL correta da API do Qwen
            response = requests.post(
                "https://api.qwen.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30  # Timeout de 30 segundos
            )
            
            if response.status_code == 200:
                print("Processamento com Qwen2.5 concluído com sucesso.")
                return response.json()["choices"][0]["message"]["content"]
            else:
                print("Erro na API Qwen: {}".format(response.status_code))
                print(response.text)
                print("Tentando fallback para OpenAI...")
                return self._process_with_openai(text, instruction)
                
        except Exception as e:
            print("Erro ao processar com Qwen: {}".format(str(e)))
            print("Tentando fallback para OpenAI...")
            return self._process_with_openai(text, instruction)
            
    def _process_with_openai(self, text, instruction):
        """
        Processa texto usando a API da OpenAI como fallback
        
        Args:
            text: Texto a ser processado
            instruction: Instrução para o modelo
            
        Returns:
            Resposta do modelo em formato JSON
        """
        # Verifica se temos uma chave da OpenAI
        openai_key = API_KEYS.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
        if not openai_key:
            print("AVISO: Sem chave de API OpenAI. Usando processamento local simulado.")
            return self._simulate_processing(text, instruction)
            
        try:
            # Verifica se há um modelo específico configurado para a OpenAI
            openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4')
            print("Processando texto com OpenAI usando modelo: {}".format(openai_model))
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(openai_key)
            }
            
            payload = {
                "model": openai_model,
                "messages": [
                    {"role": "system", "content": "Você é um assistente especializado em roteirização e narrativas para crianças."},
                    {"role": "user", "content": "{}\n\nHISTÓRIA:\n{}".format(instruction, text)}
                ],
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30  # Timeout de 30 segundos
            )
            
            if response.status_code == 200:
                print("Processamento com OpenAI concluído com sucesso.")
                return response.json()["choices"][0]["message"]["content"]
            else:
                print("Erro na API OpenAI: {}".format(response.status_code))
                print(response.text)
                print("Usando processamento local simulado como fallback final.")
                return self._simulate_processing(text, instruction)
                
        except Exception as e:
            print("Erro ao processar com OpenAI: {}".format(str(e)))
            print("Usando processamento local simulado como fallback final.")
            return self._simulate_processing(text, instruction)
            
    def _simulate_processing(self, text, instruction):
        """
        Simula o processamento de texto quando as APIs não estão disponíveis
        
        Args:
            text: Texto a ser processado
            instruction: Instrução para o modelo
            
        Returns:
            Resposta simulada em formato JSON
        """
        print("MODO SIMULADO: Processando texto localmente...")
        
        # Simula o tempo de processamento
        import time
        import random
        import json
        
        # Extrai alguns elementos básicos do texto para usar na simulação
        paragraphs = text.split('\n\n')
        sentences = []
        for p in paragraphs:
            sentences.extend([s.strip() for s in p.split('.') if s.strip()])
        
        # Identifica possíveis personagens (palavras capitalizadas que não iniciam frases)
        import re
        potential_characters = set()
        for sentence in sentences:
            words = sentence.split()
            for word in words[1:]:  # Ignora a primeira palavra de cada frase
                if re.match(r'^[A-Z][a-z]+$', word) and len(word) > 2:
                    potential_characters.add(word)
        
        characters = list(potential_characters)[:5]  # Limita a 5 personagens
        if not characters or len(characters) < 2:
            characters = ["Alice", "Coelho", "Gato"]
        
        # Cria uma resposta simulada baseada no conteúdo do texto
        time.sleep(2)  # Simula o tempo de processamento
        
        # Determina o número de cenas com base no tamanho do texto
        num_scenes = max(3, min(10, len(sentences) // 3))
        
        # Cria uma resposta simulada em formato JSON
        simulated_response = {
            "title": "Aventuras no Jardim Mágico",
            "characters": [
                {"name": char, "description": "Personagem importante na história"} 
                for char in characters
            ],
            "scenes": []
        }
        
        # Adiciona cenas simuladas
        for i in range(num_scenes):
            scene_index = i * len(sentences) // num_scenes
            if scene_index < len(sentences):
                scene_text = sentences[scene_index]
            else:
                scene_text = "Cena final da história."
                
            scene = {
                "scene_number": i + 1,
                "title": "Cena {}".format(i + 1),
                "setting": random.choice(["Jardim", "Universidade", "Sala de Aula", "Margem do Rio", "Bosque"]),
                "description": scene_text,
                "characters": random.sample(characters, min(len(characters), random.randint(1, 3))),
                "dialogue": [],
                "narration": scene_text,
                "visual_elements": ["jardim", "gatos", "livros"] if i % 2 == 0 else ["coelho", "relógio", "chá"]
            }
            
            # Adiciona diálogos simulados
            if random.random() > 0.3:  # 70% de chance de ter diálogo
                num_dialogues = random.randint(1, 2)
                for j in range(num_dialogues):
                    character = random.choice(characters)
                    dialogue = {
                        "character": character,
                        "text": f"{'Olá! ' if j == 0 else ''}Esta é uma fala simulada para a cena {i+1}."
                    }
                    scene["dialogue"].append(dialogue)
            
            simulated_response["scenes"].append(scene)
        
        # Converte para string JSON e depois de volta para dict para garantir o formato correto
        return json.loads(json.dumps(simulated_response))
    
    def process_story(self) -> List[Dict[str, Any]]:
        """
        Processa a história completa e gera um roteiro estruturado.
        
        Returns:
            Roteiro estruturado para animação
        """
        if not self.story:
            raise ValueError("Nenhuma história foi carregada para processamento")
        
        # Se temos uma chave de API válida, tentamos usar o Qwen2.5 para análise avançada
        if self.api_key:
            try:
                instruction = """
                Analise esta história infantil e crie um roteiro estruturado para animação com os seguintes elementos:
                1. Divida a história em cenas lógicas (momentos distintos da narrativa)
                2. Para cada cena, identifique:
                   - Número e título da cena
                   - Local onde ocorre
                   - Personagens presentes
                   - Narração (texto descritivo)
                   - Diálogos (falas dos personagens)
                   - Direções para animação (instruções visuais)
                   - Elementos visuais importantes
                
                Retorne o resultado como um objeto JSON com uma lista de cenas.
                """
                
                result = self._process_with_qwen(self.story, instruction)
                if result and isinstance(result, list) and len(result) > 0:
                    self.script = result
                    print(f"Processamento avançado com Qwen2.5: {len(self.script)} cenas identificadas")
                    return self.script
            except Exception as e:
                print(f"Erro no processamento avançado: {str(e)}. Usando método alternativo.")
        
        # Método alternativo (original) caso o Qwen2.5 não esteja disponível
        paragraphs = self._split_into_paragraphs()
        scenes = self._identify_scenes(paragraphs)
        self.script = self._create_script_from_scenes(scenes)
        
        print(f"Processamento concluído: {len(self.script)} cenas identificadas")
        return self.script
    
    def save_script(self, output_path: str) -> None:
        """
        Salva o roteiro processado em formato JSON.
        
        Args:
            output_path: Caminho para salvar o arquivo JSON
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi gerado ainda. Execute process_story() primeiro.")
        
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(self.script, file, ensure_ascii=False, indent=2)
        
        print(f"Roteiro salvo em: {output_path}")
    
    def get_formatted_script(self) -> str:
        """
        Retorna uma versão formatada do roteiro para visualização.
        
        Returns:
            String formatada do roteiro
        """
        if not self.script:
            raise ValueError("Nenhum roteiro foi gerado ainda. Execute process_story() primeiro.")
        
        formatted_script = ""
        
        for scene in self.script:
            formatted_script += f"\n\n{'=' * 50}\n"
            formatted_script += f"CENA {scene['scene_number']}: {scene['title']}\n"
            formatted_script += f"{'=' * 50}\n\n"
            
            formatted_script += f"LOCAL: {scene['location']}\n"
            formatted_script += f"PERSONAGENS: {', '.join(scene['characters'])}\n\n"
            
            formatted_script += "NARRAÇÃO:\n"
            formatted_script += f"{scene['narration']}\n\n"
            
            if scene['dialogues']:
                formatted_script += "DIÁLOGOS:\n"
                for dialogue in scene['dialogues']:
                    formatted_script += f"{dialogue['speaker']}: \"{dialogue['text']}\"\n"
                formatted_script += "\n"
            
            formatted_script += "DIREÇÕES PARA ANIMAÇÃO:\n"
            for direction in scene['animation_directions']:
                formatted_script += f"- {direction}\n"
            formatted_script += "\n"
            
            formatted_script += "ELEMENTOS VISUAIS:\n"
            for element in scene['visual_elements']:
                formatted_script += f"- {element}\n"
        
        return formatted_script


# Exemplo de uso
if __name__ == "__main__":
    agent = ScriptProcessorAgent()
    
    # Carregar história de um arquivo
    story_path = "../data/historia.txt"
    if os.path.exists(story_path):
        agent.load_story_from_file(story_path)
    else:
        # História de exemplo para teste
        example_story = """
        O Professor de Matemática
        
        Eu preciso arrumar um jeito de esconder esses gatinhos. Já é a segunda vez que Mia dá cria, mas desta vez ela exagerou e vieram logo oito. Mamãe disse que só suportaria três de cada vez, pois as nossas já são muito levadas e gostam de se enredar nas meadas de lã quando estamos tentando tricotar.
        """
        agent.load_story(example_story)
    
    # Processar a história
    script = agent.process_story()
    
    # Salvar o roteiro
    os.makedirs("../output", exist_ok=True)
    agent.save_script("../output/roteiro.json")
    
    # Exibir o roteiro formatado
    print(agent.get_formatted_script())
