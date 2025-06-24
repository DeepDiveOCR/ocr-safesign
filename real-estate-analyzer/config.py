import os
from flask import Flask
from dotenv import load_dotenv
import easyocr
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. 환경변수 및 Flask 앱 설정 ---
load_dotenv()
app = Flask(__name__)
app.secret_key = 'safesign_robust'

# 파일 업로드 폴더 설정
if not os.path.exists('uploads'):
    os.makedirs('uploads')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- 2. 외부 서비스 클라이언트 초기화 ---
db = None
model = None
reader = None

try:
    # EasyOCR 리더 초기화
    print("EasyOCR 리더를 초기화합니다...")
    reader = easyocr.Reader(['ko','en'])
    print("✅ EasyOCR 리더 초기화 완료.")

    # Gemini API 설정
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    if not GOOGLE_API_KEY:
        raise ValueError("환경 변수에서 GOOGLE_API_KEY를 찾을 수 없습니다.")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini API 설정 완료.")

    # Firebase Admin SDK 초기화
    SERVICE_ACCOUNT_KEY_PATH = 'firebase-credentials.json'
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        raise FileNotFoundError(f"Firebase 서비스 계정 키 파일을 찾을 수 없습니다: {SERVICE_ACCOUNT_KEY_PATH}")
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK 초기화 완료.")

    # Firestore 클라이언트 초기화
    db = firestore.client()
    print("✅ Firestore 클라이언트 초기화 완료.")

except Exception as e:
    print(f"🚨 설정 초기화 중 오류 발생: {e}")
