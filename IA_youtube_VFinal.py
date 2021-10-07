

# Instalando bibliotecas básicas como numpy, selenium e webdriver

import bs4
from skimage.io import imread, imsave
from bs4 import NavigableString, Comment
import requests
import os 
import selenium
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.utils import ChromeType
import sys
from bs4 import BeautifulSoup
from collections import Counter  
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.error import URLError
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from PIL import Image
import wikipedia_histories
import wikipedia
#from kora.selenium import wd


# Bibliotecas para processamento de NLP e criação do audio

import string
import pyttsx3
import speake3
from gtts import gTTS
from gtts_token import gtts_token
from voxpopuli import Voice
from playsound import playsound
import nltk
from nltk import sent_tokenize
from nltk import word_tokenize
from nltk.corpus import stopwords
from string import punctuation
from nltk.probability import FreqDist
from collections import defaultdict
import random
from tensorflow.keras.preprocessing.text import Tokenizer
from heapq import nlargest
nltk.download('stopwords')
nltk.download('punkt')

# Bibliotecas para criação de video e processamento de imagens

from google_images_search import GoogleImagesSearch
from io import BytesIO
import time
import cv2 as cv
import glob
from PIL.ImageFilter import (BLUR, CONTOUR, DETAIL, EDGE_ENHANCE, EDGE_ENHANCE_MORE,EMBOSS, FIND_EDGES, SMOOTH, SMOOTH_MORE, SHARPEN, GaussianBlur)
import moviepy.editor as mpy
import gizeh
from moviepy.editor import *
from moviepy.video.fx.all import crop
import argparse
import subprocess
import ffmpeg
import heapq

# Bibliotecas para upload do video para youtube

import http.client as httplib
import httplib2
import random
import google.oauth2.credentials
import argparse
import time
import datetime
import socket
def main(*args):
  import argparse

from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request
from oauth2client import client
from oauth2client import tools

#criação do app
from tkinter import *
from tkinter import ttk










# Cria o dataframe para receber os dados
wikipedia = pd.DataFrame(columns = ["Assunto"])

driver = webdriver.Chrome(ChromeDriverManager().install())



def pesquisar_wiki():
    
    driver.get('https://en.wikipedia.org/wiki')
    driver.implicitly_wait(20)

    # pesquisando o assunto desejado
    pesquisa= input("O Que deseja pesquisar?")
    driver.find_element(By.XPATH, '//*[@id="searchInput"]').send_keys(pesquisa)
    driver.find_element(By.XPATH, '//*[@id="searchButton"]').click()
    mc= driver.find_element(By.CLASS_NAME, "mw-parser-output").text
    
    #fazendo uma limpeza na base 
    def ignorar_caracteres_cercados(ignorar, char_abertura, char_fechamento):
        profundidade = 0
        novo_texto = ''

        for c in ignorar:
            if c == char_abertura:
                profundidade += 1
            elif c == char_fechamento:
                profundidade -= 1
                if profundidade < 0:
                    raise Exception('[] não balanceado')
            elif profundidade == 0:
                novo_texto += c

        if profundidade > 0:
            raise Exception('[] não balanceado')

        return novo_texto
    
    texto_novo = ignorar_caracteres_cercados(mc, '[',']') # Limpar a base com dados com chaves.
   
    texto = texto_novo.replace('(', ' ').replace(')', ' ') # limpadar os dados com parenteses
    print(texto)

    #Fazendo resumo da história 
    sentenca_texto = sent_tokenize(texto)
    sentenca_texto

    #quebrando  em sentenças
    words = word_tokenize(texto)
    print(words)
    
    # precisamos definir o idioma que queremos recuperar as stopswords
    not_relevant= stopwords.words('english')  
    print(not_relevant)
    
   
   # Transformando pontuação em uma lista e inserindo na lista das stops_words

    pontuacao = list(punctuation)
    print(pontuacao)

   # Juntando as duas listas em uma só

    not_relevant.extend(pontuacao)
    print(not_relevant)

    #vamos remover as stopwords e pontuação de nosso documento
    ajuste= [word for word in words if word not in not_relevant]

    print(ajuste)

    #Gerando contagem da frequência das palavras

    freq= FreqDist(ajuste)
    print(freq)

    # Vamos agora separar quais são as sentenças mais importantes do nosso texto. Criaremos um “score” para cada sentença baseado 
#no número de vezes que uma palavra importante se repete dentro dela

    sentencas_importantes = defaultdict(int)
    print(sentencas_importantes)

    
    #inserindo as informações no dicionario
    for i, sentenca in enumerate(sentenca_texto):
        for words in word_tokenize(sentenca.lower()):
            if words in freq:
              sentencas_importantes[i] += freq[words]


    #fazendo o resumo, escolhendo a quantidade de sentenças

    quant_sentencas=nlargest(15, sentencas_importantes, sentencas_importantes.get)
    print(quant_sentencas)
    
    # pegando as melhores frases

    lista_frases= nltk.sent_tokenize(texto)
    lista_frases


    #vamos dar uma nota para cada frase, sentenças
    novas_frases = {}

    for frases in lista_frases:
        for palavras in nltk.word_tokenize(frases.lower()):
            if palavras in freq.keys():
                if frases not in novas_frases.keys():
                    novas_frases[frases]= freq[palavras]
                else:
                    novas_frases[frases]+= freq[palavras]
    
    
    
    #ordernando as melhores frases

    melhores_frases=heapq.nlargest(20, novas_frases, key=novas_frases.get)
    melhores_frases


   # Primeira opção para fazer o resumo

    resumo=''.join(melhores_frases)
    resumo

    # Segunda opção para fazer o resumo
    for i in sorted(quant_sentencas):
        print(sentenca_texto[i]) 


    # Para forçar a gravação do resumo em aúdio mp3 e posteriormente sua leitura pela IA.
    # Obs. Eu precisei forçar a gravação porque estou  usando o windows.

    try:
                audio = gTTS(resumo, lang='en')
                audio.save('audio.mp3')
                print ('Tina Turner:\n    ' + resumo)
                playsound ('audio.mp3')   #windows
                os.remove('audio.mp3')

            #Permission para Windows 10 
    except PermissionError:
                numero = random.randint(0,1000000000000)
                audio = gTTS(resumo, lang='en')
                audio.save('audio'+ str(numero) +'.mp3')
                print ('Tina Turner:\n    ' + resumo)
                playsound ('audio'+ str(numero) +'.mp3')   #windows
                os.remove('audio'+ str(numero) +'.mp3')



pesquisar_wiki()



def imagens_google():
    # inserindo os dados de acesso para google search
    search = GoogleImagesSearch('sua chave api_key', 'sua project_cx')

    # define search params:
    _search_params = {
        'q': 'Tina turner',
        'imgsize': 'HUGE',
        'num': 10
    }



    #definindo a busca e baixando as imagens
    my_bytes_io = BytesIO()

    search.search(_search_params)

    for image in search.results():
        # chamando objeto BytesIO para retornar address 0
        my_bytes_io.seek(0)

        # pegando raw image data
        image_data = image.get_raw_data()

        # esta funcao escreve o raw image data para o objeto
        image.copy_to(my_bytes_io, image_data)

        # a  raw data  com automatico token
        # faz uma copia do método
        image.copy_to(my_bytes_io)

        #  retornamos o address novamente faz a leitura 
        my_bytes_io.seek(0)

        # criando uma imagem temporaria 
        temp_img = Image.open(my_bytes_io)
        # visualizando as imagens criadas
        temp_img.show()


    #this will only search for images:
    search.search(search_params=_search_params)

    # this will search and download:
    search.search(search_params=_search_params, path_to_dir='/path/')

    # this will search, download and resize:
    search.search(search_params=_search_params, path_to_dir='/path/', width=500, height=500)

    # search first, then download and resize afterwards:
    search.search(search_params=_search_params)
    for image in search.results():
        image.download(r'C:\Users\Qintess\anaconda3\envs\Data_Science\Data_Science\projeto\modelagem\ProjetoIntegrador\Webscraping_youtube/')
        image.resize(500, 500)

imagens_google()

# Buscando as imagens com Selenium
def imagens_selenium():
    #carregando a página desejada
    driver.get('https://www.google.com.br/imghp?hl=en&authuser=0&ogbl')
    driver.implicitly_wait(20)


    # Inserir a palavra chave''

    foto= input("O Que deseja pesquisar?")
    driver.find_element(By.XPATH, '//*[@id="sbtc"]/div/div[2]/input').send_keys(foto)
    # fazendo a busca
    driver.find_element(By.XPATH, '//*[@id="sbtc"]/button').click()


    #definindo o tamanho da foto 
    driver.find_element(By.XPATH, '//*[@id="yDmH0d"]/div[2]/c-wiz/div[1]/div/div[1]/div[2]/div').click()
    driver.find_element(By.XPATH, '//*[@id="yDmH0d"]/div[2]/c-wiz/div[2]/div[2]/c-wiz[1]/div/div/div[1]/div/div[1]/div/div[2]').click()
    driver.find_element(By.XPATH, '//*[@id="yDmH0d"]/div[2]/c-wiz/div[2]/div[2]/c-wiz[1]/div/div/div[3]/div/a[2]/div/span').click()


    # fazedo a rolagem da página até o final- não é obrigatório, só um complemento
    last_height = driver.execute_script('return document.body.scrollHeight')
    while True:
        driver.execute_script('window.scrollTo(0,document.body.scrollHeight)')
        time.sleep(2)
        new_height = driver.execute_script('return document.body.scrollHeight')
        try:
            driver.find_element_by_xpath('//*[@id="islmp"]/div/div/div/div/div[5]/input').click()
            time.sleep(2)
        except:
            pass
        if new_height == last_height:
            break
        last_height = new_height


    #lendo as imagens

    for i in range(1,50):
        try:
            driver.find_element_by_xpath('//*[@id="islrg"]/div[1]/div['+str(i)+']/a[1]/div[1]/img')
        except:
            pass


    #Salvando as imagens
    for i in range(1, 50):
        try:
            driver.find_element_by_xpath('//*[@id="islrg"]/div[1]/div['+str(i)+']/a[1]/div[1]/img').screenshot(r'C:\Users\Qintess\anaconda3\envs\Data_Science\Data_Science\projeto\modelagem\ProjetoIntegrador\Bryan Adams\Tina Turner ('+str(i)+').png')
        except:
            pass
   
imagens_selenium()

#Convertendo as imagens e dimencionando com Pillow 


def imagens_tratamento():
    #aplicando o tratamento uma a uma
    foto_1 = Image.open("Tina.jpg").convert('RGB')
    foto_2 = Image.open("Tina_1.jpg").convert('RGB')
    foto_3 = Image.open("Tina_2.jpg").convert('RGB')
    foto_4 = Image.open("Tina_3.jpg").convert('RGB')
    foto_5 = Image.open("Tina_4.jpg").convert('RGB')
    foto_6 = Image.open("Tina_5.jpg").convert('RGB')
    foto_7 = Image.open("Tina_6.jpg").convert('RGB')



    # convertando o filtro da imagem, deixando a imagem borrada.
    conversao_1 = foto_1.filter(GaussianBlur (radius=10))
    conversao_2 = foto_2.filter(GaussianBlur (radius=10))
    conversao_3 = foto_3.filter(GaussianBlur (radius=10))
    conversao_4 = foto_4.filter(GaussianBlur (radius=10))
    conversao_5 = foto_5.filter(GaussianBlur (radius=10))
    conversao_6 = foto_6.filter(GaussianBlur (radius=10))
    conversao_7 = foto_7.filter(GaussianBlur (radius=10))




    # criando uma segunda foto redimensionada para fazer a moldura
    size= (400,450)
    art_1= foto_1.resize(size, Image.BICUBIC)
    art_2= foto_2.resize(size)
    art_3= foto_3.resize(size)
    art_4= foto_4.resize(size)
    art_5= foto_5.resize(size)
    art_6= foto_6.resize(size)
    art_7= foto_7.resize(size)




    conversao_1.save("tratamento.jpg")
    conversao_2.save("tratamento_1.jpg")
    conversao_3.save("tratamento_3.jpg")
    conversao_4.save("tratamento_4.jpg")
    conversao_5.save("tratamento_5.jpg")
    conversao_6.save("tratamento_6.jpg")
    conversao_7.save("tratamento_7.jpg")


# ##   Colando uma imagem em outra e criando a moldura



    conversao_1.paste(art_1, (5,5))
    conversao_2.paste(art_2, (5,5))
    conversao_3.paste(art_3, (5,5))
    conversao_4.paste(art_4, (5,5))
    conversao_5.paste(art_5, (5,5))
    conversao_6.paste(art_6, (5,5))
    conversao_7.paste(art_7, (5,5))




    #Salvando as imagens
    conversao_1.save("Tina_moldura_1.jpg")
    conversao_2.save("Tina_moldura_2.jpg")
    conversao_3.save("Tina_moldura_3.jpg")
    conversao_4.save("Tina_moldura_4.jpg")
    conversao_5.save("Tina_moldura_5.jpg")
    conversao_6.save("Tina_moldura_6.jpg")
    conversao_7.save("Tina_moldura_7.jpg")

imagens_tratamento()


# ##Transformando os aúdios e <font color=blue> imagens <font color=red> em vídeo clip <font color=black> usando <font color=gre>Moviepy e  <font color=red>ImageMagick

def video_youtube():
    #salvando o caminho da pasta em uma variavel
    fotos = r'C:\Users\Qintess\anaconda3\envs\Data_Science\Data_Science\projeto\modelagem\ProjetoIntegrador\Webscraping_youtube'


    #interando pelas imagens que contenham formato JPG
    arquivos = os.listdir(fotos)




    #salvando somente as imagens dentro de uma lista
    arquivos = [
                'Tina_moldura_1.jpg',
                'Tina_moldura_2.jpg',
                'Tina_moldura_3.jpg',
                'Tina_moldura_4.jpg',
                'Tina_moldura_5.jpg',
                'Tina_moldura_6.jpg',
                'Tina_moldura_7.jpg'
                ]


    #Criando um video clip das imagens.
    clip = ImageSequenceClip(arquivos, fps=0.021)

    # Salvando o video_clip
    clip= clip.write_videofile("video_2.mp4", fps = 70)


    #Abrindo o arquivo de audio
    audio_t= os.path.join('audio.mp3')

    #Criando o audioclip
    audioclip = AudioFileClip(audio_t)
    audioclip = audioclip.set_duration('05:25.35')
    audioclip = audioclip.set_fps(audioclip.fps)


    #Salvando o audio clip
    audioclip.write_audiofile('audio_.mp3')



    #criando gif

    clip.write_gif("teste.gif", fps=7)



    #Criando uma sequencia de imagens
    clip.write_images_sequence(os.path.join("frame%04d.jpeg"))


# ###  Fazendo a união do <font color= red> video <font color=grey> com o <font color= blue> aúdio 


    #abrindo os arquivos de audio e video
    audio= os.path.join('audio_.mp3')
    video= os.path.join('video_2.mp4')

    #criando um video clip
    video_clip= VideoFileClip(video)

    #criando um audio clip
    audio_clip = AudioFileClip(audio)



    #concatenando o video com o audio
    final_clip= video_clip.set_audio(audio_clip)



    final_clip.save_frame()




    #salvando o novo video clip criado
    final_clip.write_videofile("video_tina.mp4", codec='libx264', audio_codec="aac")

video_youtube()

# ## 8° Upload do video para o Youtube Usando  Data API V3


def  upload_video():
    #tempo limite para conexão com o servidor
    socket.setdefaulttimeout(30000)

    # A CLIENT_SECRETS_FILE- informação a qual vai conter seu client_id e sua chave_secreta do seu OAuth 2.0

    CLIENT_SECRET_FILE = 'client_secret_1.json'

    # Antenticação do  canal do usuario para fazer upload.

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_console()
    youtube = build('youtube', 'v3', credentials=credentials)



    upload_date_time = datetime.datetime(2021, 9, 8, 12, 30, 0).isoformat() + '.000Z'

    # inserindo as informaçoes de categoria do video, titulo, tags, descrição.

    request_body = {
        'snippet': {
            'categoryI': 19,
            'title': ' Tina Turner ',
            'description': ' Life History of Tina Turner',
            'tags': ['Python', 'Youtube API', 'Google', 'Education', 'AI']
        },
        'status': {
            'privacyStatus': 'private',
            'publishAt': upload_date_time,
            'selfDeclaredMadeForKids': False       
        },
        'notifySubscribers': False
    }

    # inserindo o video a qual será feito o upload e executando  a chamada. 

    media = MediaFileUpload('video_tina.mp4')

    response_upload = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media
    ).execute()


    """
    youtube.thumbnails().set(
        videoId=response_upload.get('id'),
        media_body=MediaFileUpload('thumbnail.png')
    ).execute()
    """

upload_video()
    







programa = Tk()

programa.title("IA Para Criação de Vídeos - Youtube")
programa.configure(background='#000')

pesquisar = pesquisar_wiki

# texto_wikipedia = Label(programa, text="Clique no botão", background='#FF0000', foreground='#FFFAFA')
# texto_wikipedia.pack(ipadx=3, ipady=3, padx=20, pady=20, side='top', fill=Y, expand=False)
botao = Button(programa, text="Pesquisar", background='#FF0000', foreground='#FFFAFA', command=pesquisar)
botao.pack(ipadx=6, ipady=6, padx=20, pady=20, side='top', fill=Y, expand=False)
input_texto= Label(programa, text=" ")
input_texto.pack(ipadx=2, ipady=2, padx=20, pady=20, side='top', fill=Y, expand=False)

texto_wikipedia_2 = Label(programa, text="Clique para fazer a consulta", background='#FF0000', foreground='#FFFAFA')
texto_wikipedia_2.pack(ipadx=5, ipady=5, padx=20, pady=20, side='top', fill=Y, expand=False)



programa.mainloop()


