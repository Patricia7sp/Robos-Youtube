#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YouTube Publisher Agent
---------------------
Este agente é responsável por otimizar e fazer upload do vídeo final para o YouTube,
incluindo geração de metadados otimizados para SEO.
"""

import os
import json
import time
import random
import http.client
import httplib2
import requests
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path para importar módulos do projeto
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import API_KEYS, YOUTUBE_SETTINGS

# Importações do Google API Client
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("AVISO: Bibliotecas do Google API Client não encontradas. Execute 'pip install google-api-python-client google-auth-oauthlib google-auth-httplib2'")

class YouTubePublisherAgent:
    def __init__(self, client_secrets_file: Optional[str] = None):
        """
        Inicializa o agente de publicação no YouTube.
        
        Args:
            client_secrets_file: Caminho para o arquivo client_secrets.json do OAuth (opcional)
        """
        self.api_key = API_KEYS.get('YOUTUBE_API_KEY') or os.environ.get('YOUTUBE_API_KEY')
        self.client_secrets_file = client_secrets_file
        self.youtube_settings = YOUTUBE_SETTINGS
        self.credentials = None
        self.youtube = None
        self.script = None
        
    def load_script(self, script_path: str) -> None:
        """
        Carrega o roteiro processado a partir de um arquivo JSON.
        
        Args:
            script_path: Caminho para o arquivo JSON do roteiro
        """
        with open(script_path, 'r', encoding='utf-8') as file:
            self.script = json.load(file)
        print(f"Roteiro carregado: {len(self.script)} cenas")
    
    def _get_authenticated_service(self) -> Optional[Any]:
        """
        Autentica o usuário e cria o serviço YouTube.
        
        Returns:
            Objeto de serviço YouTube ou None em caso de falha
        """
        # Se não temos o arquivo de segredos do cliente, não podemos autenticar
        if not self.client_secrets_file:
            print("AVISO: Arquivo client_secrets.json não fornecido. Funcionando em modo simulado.")
            return None
        
        # Escopos necessários para o upload de vídeos
        SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        
        # Arquivo para armazenar as credenciais do usuário
        token_file = 'token.json'
        
        # Carrega as credenciais do arquivo token.json, se existir
        if os.path.exists(token_file):
            try:
                self.credentials = Credentials.from_authorized_user_info(
                    json.load(open(token_file)), SCOPES)
            except Exception as e:
                print(f"Erro ao carregar credenciais: {str(e)}")
        
        # Se não há credenciais válidas, solicita ao usuário que faça login
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    print(f"Erro ao atualizar credenciais: {str(e)}")
                    self.credentials = None
            
            if not self.credentials:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file, SCOPES)
                    self.credentials = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Erro ao obter novas credenciais: {str(e)}")
                    return None
                
                # Salva as credenciais para a próxima execução
                with open(token_file, 'w') as token:
                    token.write(self.credentials.to_json())
        
        try:
            # Cria o serviço YouTube
            return build('youtube', 'v3', credentials=self.credentials)
        except Exception as e:
            print(f"Erro ao criar serviço YouTube: {str(e)}")
            return None
    
    def _generate_title(self) -> str:
        """
        Gera um título otimizado para SEO com base no roteiro.
        
        Returns:
            Título otimizado para o vídeo
        """
        if not self.script:
            return "História Animada para Crianças"
        
        # Extrai informações relevantes do roteiro
        main_characters = set()
        locations = set()
        
        for scene in self.script:
            main_characters.update(scene.get('characters', []))
            location = scene.get('location')
            if location:
                locations.add(location)
        
        # Identifica personagens principais (que aparecem em mais cenas)
        character_counts = {}
        for scene in self.script:
            for character in scene.get('characters', []):
                character_counts[character] = character_counts.get(character, 0) + 1
        
        # Ordena personagens por frequência
        sorted_characters = sorted(character_counts.items(), key=lambda x: x[1], reverse=True)
        main_character = sorted_characters[0][0] if sorted_characters else "Personagem"
        
        # Obtém o título da primeira cena como possível título da história
        story_title = self.script[0].get('title', '') if self.script else ''
        
        # Gera algumas opções de título
        title_options = [
            f"{main_character} e a Aventura no {next(iter(locations), 'Mundo Mágico')}",
            f"A História de {main_character} - Conto Infantil Animado",
            f"{story_title} - História Animada para Crianças",
            f"Aventuras de {main_character} - Desenho Animado Infantil",
            f"O Professor de Matemática - Uma História Mágica para Crianças"
        ]
        
        # Escolhe um título aleatório
        title = random.choice(title_options)
        
        # Limita o tamanho do título (YouTube permite até 100 caracteres)
        return title[:100]
    
    def _generate_description(self) -> str:
        """
        Gera uma descrição otimizada para SEO com base no roteiro.
        
        Returns:
            Descrição otimizada para o vídeo
        """
        if not self.script:
            return "Uma história animada encantadora para crianças. Assista e divirta-se!"
        
        # Extrai informações relevantes do roteiro
        characters = set()
        locations = set()
        themes = set()
        
        for scene in self.script:
            characters.update(scene.get('characters', []))
            location = scene.get('location')
            if location:
                locations.add(location)
            
            # Extrai possíveis temas da narração
            narration = scene.get('narration', '')
            if 'amizade' in narration.lower():
                themes.add('amizade')
            if 'aventura' in narration.lower():
                themes.add('aventura')
            if 'magia' in narration.lower():
                themes.add('magia')
            if 'aprendizado' in narration.lower() or 'lição' in narration.lower():
                themes.add('aprendizado')
            if 'família' in narration.lower():
                themes.add('família')
        
        # Cria um resumo da história
        first_scene = self.script[0].get('narration', '')
        last_scene = self.script[-1].get('narration', '')
        
        summary = first_scene[:200] + "..." if first_scene else ""
        
        # Constrói a descrição
        description = f"""🎬 O Professor de Matemática - Uma História Mágica para Crianças 🎬

Uma encantadora história animada sobre {', '.join(themes) if themes else 'aventura e imaginação'}.

📖 SINOPSE:
{summary}

🌟 PERSONAGENS:
{', '.join(characters)}

🔔 INSCREVA-SE no canal para mais histórias animadas para crianças!
👍 Deixe seu LIKE se você gostou desta história!
💬 COMENTE qual foi sua parte favorita!

#HistóriasInfantis #DesenhosAnimados #ContosParaCrianças #HistóriasParaDormir #AnimaçãoInfantil #HistóriasAnimadas #CriançasYouTube

© Todos os direitos reservados."""
        
        # Limita o tamanho da descrição (YouTube permite até 5000 caracteres)
        return description[:5000]
    
    def _generate_tags(self) -> List[str]:
        """
        Gera tags otimizadas para SEO com base no roteiro.
        
        Returns:
            Lista de tags para o vídeo
        """
        # Tags base
        base_tags = self.youtube_settings.get('tags', [])
        
        if not self.script:
            return base_tags
        
        # Extrai informações relevantes do roteiro
        characters = set()
        locations = set()
        themes = set()
        
        for scene in self.script:
            characters.update(scene.get('characters', []))
            location = scene.get('location')
            if location:
                locations.add(location)
            
            # Extrai possíveis temas da narração
            narration = scene.get('narration', '')
            if 'amizade' in narration.lower():
                themes.add('amizade')
            if 'aventura' in narration.lower():
                themes.add('aventura')
            if 'magia' in narration.lower():
                themes.add('magia')
            if 'aprendizado' in narration.lower() or 'lição' in narration.lower():
                themes.add('aprendizado')
            if 'família' in narration.lower():
                themes.add('família')
        
        # Cria tags específicas da história
        story_tags = [
            "O Professor de Matemática",
            "histórias infantis",
            "contos para crianças",
            "desenhos animados infantis",
            "histórias animadas",
            "histórias para dormir",
            "contos de fadas",
            "animação infantil",
        ]
        
        # Adiciona personagens e locais como tags
        for character in characters:
            story_tags.append(f"{character}")
            story_tags.append(f"história de {character}")
        
        for location in locations:
            story_tags.append(f"{location}")
        
        for theme in themes:
            story_tags.append(f"{theme}")
            story_tags.append(f"histórias sobre {theme}")
        
        # Combina todas as tags e remove duplicatas
        all_tags = list(set(base_tags + story_tags))
        
        # Limita o número de tags (YouTube permite até 500 caracteres no total)
        total_length = 0
        final_tags = []
        
        for tag in all_tags:
            # Cada tag consome seu comprimento + 1 (para o separador)
            if total_length + len(tag) + 1 <= 500:
                final_tags.append(tag)
                total_length += len(tag) + 1
            else:
                break
        
        return final_tags
    
    def generate_metadata(self) -> Dict[str, Any]:
        """
        Gera metadados otimizados para SEO para o vídeo.
        
        Returns:
            Dicionário com metadados do vídeo
        """
        title = self._generate_title()
        description = self._generate_description()
        tags = self._generate_tags()
        
        metadata = {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': self.youtube_settings.get('category', '22'),  # 22 = People & Blogs
            'privacyStatus': self.youtube_settings.get('privacy_status', 'private'),
            'defaultLanguage': self.youtube_settings.get('default_language', 'pt-BR'),
            'defaultAudioLanguage': self.youtube_settings.get('default_language', 'pt-BR')
        }
        
        print(f"Metadados gerados para o vídeo:")
        print(f"Título: {title}")
        print(f"Tags: {', '.join(tags[:5])}... (total: {len(tags)})")
        
        return metadata
    
    def upload_video(self, video_path: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Faz upload do vídeo para o YouTube com metadados otimizados.
        
        Args:
            video_path: Caminho para o arquivo de vídeo
            metadata: Metadados do vídeo (opcional)
            
        Returns:
            ID do vídeo no YouTube ou None em caso de falha
        """
        # Verifica se o vídeo existe
        if not os.path.exists(video_path) and not video_path.startswith('[Simulado]'):
            print(f"Erro: Arquivo de vídeo não encontrado: {video_path}")
            return None
        
        # Gera metadados se não foram fornecidos
        if not metadata:
            metadata = self.generate_metadata()
        
        # Verifica se estamos em modo de simulação
        if video_path.startswith('[Simulado]') or not self.client_secrets_file:
            print("Modo simulado: Simulando upload para o YouTube...")
            print(f"Título: {metadata['title']}")
            print(f"Descrição: {metadata['description'][:100]}...")
            print(f"Tags: {', '.join(metadata['tags'][:5])}...")
            print(f"Categoria: {metadata['categoryId']}")
            print(f"Status de privacidade: {metadata['privacyStatus']}")
            
            # Simula o tempo de upload
            print("Fazendo upload do vídeo... (simulado)")
            time.sleep(3)
            
            # Retorna um ID simulado
            return "SIMULATED_VIDEO_ID_12345"
        
        # Autentica e cria o serviço YouTube
        self.youtube = self._get_authenticated_service()
        if not self.youtube:
            print("Erro: Não foi possível autenticar com o YouTube API.")
            return None
        
        # Prepara o corpo da requisição
        body = {
            'snippet': {
                'title': metadata['title'],
                'description': metadata['description'],
                'tags': metadata['tags'],
                'categoryId': metadata['categoryId'],
                'defaultLanguage': metadata.get('defaultLanguage'),
                'defaultAudioLanguage': metadata.get('defaultAudioLanguage')
            },
            'status': {
                'privacyStatus': metadata['privacyStatus'],
                'selfDeclaredMadeForKids': True  # Conteúdo para crianças
            }
        }
        
        # Configura o upload
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True
        )
        
        try:
            # Cria a requisição de inserção
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Executa o upload
            print("Fazendo upload do vídeo para o YouTube...")
            response = self._resumable_upload(insert_request)
            
            if response:
                print(f"Upload concluído! ID do vídeo: {response['id']}")
                print(f"URL do vídeo: https://www.youtube.com/watch?v={response['id']}")
                return response['id']
            else:
                print("Erro: Upload falhou.")
                return None
                
        except HttpError as e:
            print(f"Erro HTTP durante o upload: {e.resp.status} {e.content}")
            return None
        except Exception as e:
            print(f"Erro durante o upload: {str(e)}")
            return None
    
    def _resumable_upload(self, request) -> Optional[Dict[str, Any]]:
        """
        Executa um upload retomável para o YouTube.
        
        Args:
            request: Objeto de requisição do YouTube
            
        Returns:
            Resposta do YouTube ou None em caso de falha
        """
        response = None
        error = None
        retry = 0
        max_retries = 10
        
        while response is None:
            try:
                print("Fazendo upload do arquivo...")
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"Upload em andamento: {progress}%")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    if retry > max_retries:
                        print(f"Número máximo de tentativas excedido.")
                        raise
                    
                    retry += 1
                    sleep_time = 2 ** retry
                    print(f"Erro {e.resp.status}. Tentando novamente em {sleep_time} segundos.")
                    time.sleep(sleep_time)
                else:
                    print(f"Erro HTTP: {e.resp.status} {e.content}")
                    raise
            except (httplib2.HttpLib2Error, http.client.ResponseNotReady) as e:
                if retry > max_retries:
                    print(f"Número máximo de tentativas excedido.")
                    raise
                
                retry += 1
                sleep_time = 2 ** retry
                print(f"Erro de conexão: {str(e)}. Tentando novamente em {sleep_time} segundos.")
                time.sleep(sleep_time)
        
        return response
    
    def save_metadata(self, metadata: Dict[str, Any], output_dir: str) -> str:
        """
        Salva os metadados gerados em um arquivo JSON.
        
        Args:
            metadata: Metadados do vídeo
            output_dir: Diretório para salvar o arquivo
            
        Returns:
            Caminho para o arquivo de metadados
        """
        os.makedirs(output_dir, exist_ok=True)
        metadata_path = os.path.join(output_dir, 'youtube_metadata.json')
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Metadados salvos em: {metadata_path}")
        return metadata_path


# Exemplo de uso
if __name__ == "__main__":
    agent = YouTubePublisherAgent()
    
    # Carregar roteiro
    script_path = "../output/roteiro.json"
    if os.path.exists(script_path):
        agent.load_script(script_path)
        
        # Gerar metadados
        metadata = agent.generate_metadata()
        
        # Salvar metadados
        output_dir = "../output/youtube"
        agent.save_metadata(metadata, output_dir)
        
        # Upload do vídeo (simulado)
        video_path = "../output/video/video_final.mp4"
        if os.path.exists(video_path):
            agent.upload_video(video_path, metadata)
        else:
            print(f"Erro: Vídeo final não encontrado em {video_path}")
    else:
        print(f"Erro: Roteiro não encontrado em {script_path}")
