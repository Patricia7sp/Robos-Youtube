import http.client as httplib
import httplib2
import random
import google.oauth2.credentials
import os
import time
import datetime
import socket

from apikey import apikey
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

socket.setdefaulttimeout(30000)

CLIENT_SECRET_FILE = 'client_secret_1.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
credentials = flow.run_console()
youtube = build('youtube', 'v3', credentials=credentials)



upload_date_time = datetime.datetime(2021, 9, 8, 12, 30, 0).isoformat() + '.000Z'

request_body = {
    'snippet': {
        'categoryI': 19,
        'title': 'Upload Testing This is Private Video ',
        'description': 'Upload TEsting This is Private Video',
        'tags': ['Python', 'Youtube API', 'Google']
    },
    'status': {
        'privacyStatus': 'private',
        'publishAt': upload_date_time,
        'selfDeclaredMadeForKids': False, 
    },
    'notifySubscribers': False
}

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
