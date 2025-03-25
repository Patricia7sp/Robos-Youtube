#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agente de geração de voz para o sistema de animação automatizada.
Este módulo é responsável por converter texto em áudio usando a API ElevenLabs.
"""

import os
import time
import json
import requests
import tempfile
import base64
import random
import sys

# Adiciona o diretório raiz ao path para importar módulos do projeto
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.append(sys_path)
from config.settings import API_KEYS, OUTPUT_DIR

class VoiceActorAgent:
    """
    Agente responsável pela geração de vozes para os personagens e narração.
    Utiliza a API ElevenLabs para converter texto em áudio.
    """
    
    def __init__(self, api_key=None):
        """
        Inicializa o agente de geração de voz.
        
        Args:
            api_key: Chave da API ElevenLabs (opcional, pode ser carregada das configurações)
        """
        self.api_key = api_key or API_KEYS.get('ELEVENLABS_API_KEY', '')
        self.script = []
        self.character_voices = {}
        self.narrator_voice = None
        
        # Vozes disponíveis na ElevenLabs (IDs de exemplo)
        self.available_voices = {
            "narrador": "21m00Tcm4TlvDq8ikWAM",  # Voz masculina para narrador
            "narradora": "EXAVITQu4vr4xnSDxMaL",  # Voz feminina para narradora
            "homem_adulto": "pNInz6obpgDQGcFmaJgB",  # Voz masculina adulta
            "mulher_adulta": "AZnzlk1XvdvUeBnXmlld",  # Voz feminina adulta
            "menino": "yoZ06aMxZJJ28mfd3POQ",  # Voz de menino
            "menina": "jsCqWAovK2LkecY7zXl4"   # Voz de menina
        }
    
    def load_script(self, script_path):
        """
        Carrega o roteiro processado de um arquivo JSON.
        
        Args:
            script_path: Caminho para o arquivo JSON do roteiro
        """
        # Verifica se o script_path é uma string (caminho de arquivo)
        if isinstance(script_path, str):
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    self.script = json.load(f)
            except Exception as e:
                print(f"Erro ao carregar o roteiro: {e}")
                self.script = []
        else:
            # Se não for uma string, assume que é a lista de cenas já carregada
            self.script = script_path
        
        # Extrai personagens do roteiro
        characters = set()
        for scene in self.script:
            if "characters" in scene:
                for character in scene["characters"]:
                    if isinstance(character, str):
                        characters.add(character)
                    elif isinstance(character, dict) and "name" in character:
                        characters.add(character["name"])
        
        # Atribui vozes aos personagens
        self._assign_voices(list(characters))
    
    def _assign_voices(self, characters):
        """
        Atribui vozes aos personagens com base em seus nomes.
        
        Args:
            characters: Lista de nomes de personagens
        """
        # Atribui o narrador
        self.narrator_voice = self.available_voices["narrador"]
        
        # Atribui vozes aos personagens
        for character in characters:
            character_lower = character.lower()
            
            # Tenta identificar o tipo de personagem pelo nome
            if any(female_name in character_lower for female_name in ["alice", "maria", "ana", "menina"]):
                if "menina" in character_lower or len(character) < 6:
                    voice_id = self.available_voices["menina"]
                else:
                    voice_id = self.available_voices["mulher_adulta"]
            elif any(male_name in character_lower for male_name in ["joão", "pedro", "menino", "professor", "ludovico"]):
                if "menino" in character_lower:
                    voice_id = self.available_voices["menino"]
                else:
                    voice_id = self.available_voices["homem_adulto"]
            elif any(animal in character_lower for animal in ["gato", "coelho", "animal"]):
                # Para animais, escolhe aleatoriamente entre vozes infantis
                voice_id = random.choice([self.available_voices["menino"], self.available_voices["menina"]])
            else:
                # Para outros personagens, escolhe aleatoriamente
                voice_id = random.choice(list(self.available_voices.values()))
            
            self.character_voices[character] = voice_id
    
    def _generate_audio_with_elevenlabs(self, text, voice_id):
        """
        Gera áudio usando a API ElevenLabs.
        
        Args:
            text: Texto a ser convertido em áudio
            voice_id: ID da voz a ser usada
            
        Returns:
            Dados binários do áudio ou None em caso de falha
        """
        if not self.api_key:
            print("AVISO: Chave da API ElevenLabs não configurada. Usando modo simulado.")
            return self._generate_placeholder_audio(text)
        
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                print(f"Áudio gerado com sucesso para: {text[:30]}...")
                return response.content
            else:
                print(f"Erro ao gerar áudio: {response.status_code}")
                print(response.text)
                return self._generate_placeholder_audio(text)
                
        except Exception as e:
            print(f"Erro ao gerar áudio: {str(e)}")
            return self._generate_placeholder_audio(text)
    
    def _generate_placeholder_audio(self, text):
        """
        Gera um arquivo de áudio placeholder quando a API não está disponível.
        
        Args:
            text: Texto que seria convertido em áudio
            
        Returns:
            Dados binários do áudio placeholder
        """
        print(f"Gerando áudio placeholder para: {text[:30]}...")
        
        # Cria um arquivo de áudio vazio
        # Em uma implementação real, poderíamos usar uma biblioteca TTS local
        # como gTTS ou pyttsx3 para gerar áudio offline
        
        # Simula o tempo de geração
        time.sleep(0.5)
        
        # Retorna dados binários mínimos para simular um arquivo MP3
        return b"AUDIO_PLACEHOLDER"
    
    def generate_scene_audio(self, scene, output_dir):
        """
        Gera o áudio para uma cena, incluindo narração e diálogos.
        
        Args:
            scene: Dicionário com informações da cena
            output_dir: Diretório de saída para os arquivos de áudio
            
        Returns:
            Caminho para o arquivo de áudio combinado da cena
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        scene_number = scene.get("scene_number", 0)
        scene_audio_path = os.path.join(output_dir, f"cena_{scene_number}.mp3")
        
        # Modo simplificado sem FFmpeg
        # Apenas gera arquivos de placeholder para cada cena
        print(f"Gerando áudio placeholder para cena {scene_number}")
        
        # Cria um arquivo de áudio placeholder simples
        with open(scene_audio_path, "wb") as f:
            f.write(b"AUDIO_PLACEHOLDER")
            
        return scene_audio_path
        
        narration = scene.get("narration", "")
        audio_segments = []
        temp_files = []
        
        if narration:
            print(f"Gerando narração para cena {scene_number}: {narration[:50]}...")
            narration_audio = self._generate_audio_with_elevenlabs(narration, self.narrator_voice)
            
            if narration_audio and can_combine_audio:
                # Salva em arquivo temporário para combinar depois
                narration_path = os.path.join(output_dir, f"temp_narration_{scene_number}.mp3")
                with open(narration_path, "wb") as f:
                    f.write(narration_audio)
                
                audio_segments.append(AudioSegment.from_file(narration_path, format="mp3"))
                temp_files.append(narration_path)
            elif narration_audio:
                # Se não podemos combinar, usamos apenas a narração
                with open(scene_audio_path, "wb") as f:
                    f.write(narration_audio)
                return scene_audio_path
        
        # Gera áudio para diálogos, se houver
        dialogues = scene.get("dialogues", [])
        if dialogues and can_combine_audio:
            # Adiciona uma pequena pausa após a narração
            if audio_segments:
                silence = AudioSegment.silent(duration=1000)  # 1 segundo de silêncio
                audio_segments.append(silence)
            
            for i, dialogue in enumerate(dialogues):
                character = dialogue.get("character", "")
                text = dialogue.get("text", "")
                
                if character and text:
                    print(f"Gerando diálogo para {character}: {text[:30]}...")
                    
                    # Obtém a voz do personagem ou usa uma voz padrão
                    voice_id = self.character_voices.get(character, self.narrator_voice)
                    
                    # Gera o áudio para este diálogo
                    dialogue_audio = self._generate_audio_with_elevenlabs(text, voice_id)
                    
                    if dialogue_audio:
                        # Salva em arquivo temporário
                        dialogue_path = os.path.join(output_dir, f"temp_dialogue_{scene_number}_{i}.mp3")
                        with open(dialogue_path, "wb") as f:
                            f.write(dialogue_audio)
                        
                        # Adiciona ao segmento de áudio
                        audio_segments.append(AudioSegment.from_file(dialogue_path, format="mp3"))
                        
                        # Adiciona uma pequena pausa entre diálogos
                        audio_segments.append(AudioSegment.silent(duration=500))  # 0.5 segundos
                        
                        temp_files.append(dialogue_path)
        
        # Combina todos os segmentos de áudio
        if audio_segments and can_combine_audio:
            try:
                # Combina todos os segmentos
                combined_audio = audio_segments[0]
                for segment in audio_segments[1:]:
                    combined_audio += segment
                
                # Exporta o áudio combinado
                combined_audio.export(scene_audio_path, format="mp3")
                
                # Remove arquivos temporários
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                
                print(f"Áudio combinado para cena {scene_number} salvo em: {scene_audio_path}")
            except Exception as e:
                print(f"Erro ao combinar áudios: {str(e)}")
                
                # Fallback: usa apenas a narração se disponível
                if narration_audio:
                    with open(scene_audio_path, "wb") as f:
                        f.write(narration_audio)
        elif not os.path.exists(scene_audio_path):
            # Se não temos áudio, cria um arquivo vazio
            with open(scene_audio_path, "wb") as f:
                f.write(b"AUDIO_PLACEHOLDER")
            print(f"Arquivo de áudio placeholder criado para cena {scene_number}")
        
        return scene_audio_path
    
    def _generate_local_tts_audio(self, text):
        """
        Gera áudio usando uma biblioteca TTS local quando a API não está disponível.
        
        Args:
            text: Texto a ser convertido em áudio
            
        Returns:
            Dados binários do áudio ou None em caso de falha
        """
        try:
            # Tenta usar gTTS (Google Text-to-Speech)
            from gtts import gTTS
            import io
            
            print(f"Usando gTTS para gerar áudio local para: {text[:30]}...")
            
            # Cria um objeto BytesIO para armazenar o áudio
            audio_bytes = io.BytesIO()
            
            # Gera o áudio
            tts = gTTS(text=text, lang='pt', slow=False)
            tts.write_to_fp(audio_bytes)
            
            # Retorna os dados binários
            audio_bytes.seek(0)
            return audio_bytes.read()
            
        except ImportError:
            print("AVISO: gTTS não encontrado. Tentando pyttsx3...")
            
            try:
                # Tenta usar pyttsx3 como segunda opção
                import pyttsx3
                import io
                import tempfile
                
                print(f"Usando pyttsx3 para gerar áudio local para: {text[:30]}...")
                
                # Inicializa o motor TTS
                engine = pyttsx3.init()
                
                # Configura a voz
                voices = engine.getProperty('voices')
                for voice in voices:
                    if 'pt' in voice.id.lower() or 'br' in voice.id.lower():
                        engine.setProperty('voice', voice.id)
                        break
                
                # Configura a taxa de fala
                engine.setProperty('rate', 150)  # 150 palavras por minuto
                
                # Cria um arquivo temporário para salvar o áudio
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Salva o áudio no arquivo temporário
                engine.save_to_file(text, temp_path)
                engine.runAndWait()
                
                # Lê o arquivo e retorna os dados
                with open(temp_path, 'rb') as f:
                    audio_data = f.read()
                
                # Remove o arquivo temporário
                os.remove(temp_path)
                
                return audio_data
                
            except Exception as e:
                print(f"Erro ao gerar áudio local: {str(e)}")
                return self._generate_placeholder_audio(text)
    
    def generate_all_audio(self, output_dir: str):
        """
        Gera áudio para todas as cenas do roteiro.
        
        Args:
            output_dir: Diretório de saída para os arquivos de áudio
            
        Returns:
            Dicionário mapeando número da cena para caminho do arquivo de áudio
        """
        audio_paths = {}
        audio_metadata = {}
        
        for scene in self.script:
            scene_number = scene.get("scene_number", 0)
            audio_path = self.generate_scene_audio(scene, output_dir)
            audio_paths[scene_number] = audio_path
            
            # Adiciona metadados para cada cena
            audio_metadata[str(scene_number)] = {
                "path": audio_path,
                "duration": 15.0,  # Duração padrão em segundos
                "scene_number": scene_number
            }
        
        # Salva os metadados em um arquivo JSON
        metadata_path = os.path.join(output_dir, "all_audio_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(audio_metadata, f, ensure_ascii=False, indent=2)
            
        print(f"\nMetadados de áudio salvos em: {metadata_path}")
        
        return audio_paths
