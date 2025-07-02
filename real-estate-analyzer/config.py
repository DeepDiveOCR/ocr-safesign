import os
import cv2
import easyocr
import google.generativeai as genai
import firebase_admin # type: ignore
from firebase_admin import credentials, firestore # type: ignore
from flask import Flask # type: ignore
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore", message="Could not initialize NNPACK")

# --- 1. 환경변수 및 기본 설정 ---
load_dotenv()
confm_key = os.getenv("CONFIRM_KEY")
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# --- 2. Flask 앱 초기화 ---
app = Flask(__name__)
app.secret_key = 'safesign_robust'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- 3. 외부 서비스 클라이언트 초기화 ---

# EasyOCR 리더 초기화
print("EasyOCR 리더를 초기화합니다...")
try:
    reader = easyocr.Reader(
        ['ko'],
        model_storage_directory='.EasyOCR/model',
        user_network_directory='.EasyOCR/user_network',
        recog_network='finetuned',
        download_enabled=False,
        gpu=False
    )
    print("✅ EasyOCR 리더 초기화 완료 (커스텀 모델: finetuned).")
except Exception as e:
    print(f"🚨 EasyOCR 초기화 실패: {e}")
    reader = None

# Gemini 모델 초기화
model = None
if not GOOGLE_API_KEY:
    print("🚨 환경 변수에서 GOOGLE_API_KEY를 찾을 수 없습니다. .env 파일을 확인해주세요.")
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini API 설정 완료.")
    except Exception as e:
        print(f"🚨 Gemini API 설정 오류: {e}")

# Firebase Admin SDK 초기화
db = None
SERVICE_ACCOUNT_KEY_PATH = 'firebase-credentials.json'
if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
    print(f"🚨 Firebase 서비스 계정 키 파일을 찾을 수 없습니다: {SERVICE_ACCOUNT_KEY_PATH}.")
else:
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Admin SDK 및 Firestore 클라이언트 초기화 완료.")
    except Exception as e:
        print(f"🚨 Firebase 초기화 실패: {e}")