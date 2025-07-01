
import os
import cv2
import re # ★★★[기능 추가] 텍스트 파싱을 위한 정규표현식 라이브러리
import numpy as np
import easyocr
import google.generativeai as genai
import requests # ★★★[기능 추가] 외부 API 호출을 위한 라이브러리 (시세 조회용)
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import datetime

# ★★★[기능 추가] Firebase 서버 연동을 위한 Admin SDK ★★★
import firebase_admin
from firebase_admin import credentials, auth, firestore # ★★★[수정] firestore 임포트
from estimator.median_price import estimate_median_trade

#======================================================================
# # ★★★[기능 추가] 위험 판단 로직을 app.py에 연동하기 위한 import 구문
#======================================================================
from rule.rules import (
    check_owner_match,
    check_mortgage_risk,
    check_deposit_over_market,
    check_mortgage_vs_deposit,
    compare_address,
    # determine_overall_risk,
)


# ======================================================================
# 1. Flask 앱 설정 및 환경 변수 로드
# ======================================================================

# .env 파일에서 환경 변수를 로드합니다.
# 이 함수는 app.py와 같은 위치에 있는 .env 파일을 찾아서 그 안의 값들을 환경 변수로 설정합니다.
# .env 파일에서 환경 변수를 로드합니다.
# 이 함수는 app.py와 같은 위치에 있는 .env 파일을 찾아서 그 안의 값들을 환경 변수로 설정합니다.

import warnings
warnings.filterwarnings("ignore", message="Could not initialize NNPACK")
load_dotenv() 
confm_key = os.getenv("CONFIRM_KEY") #주소 검색용 공공 API 인증키
confm_key = os.getenv("CONFIRM_KEY") #주소 검색용 공공 API 인증키

app = Flask(__name__)
# 세션 쿠키는 이제 사용하지 않으므로 secret_key가 필수적이지 않지만, 다른 확장을 위해 유지합니다.
app.secret_key = 'safesign_robust' 
    
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# EasyOCR 리더 전역 변수로 초기화 (매번 로드하지 않도록)
# EasyOCR 리더 전역 변수로 초기화 (매번 로드하지 않도록)
print("EasyOCR 리더를 초기화합니다...")
home_dir = os.path.expanduser("~")
reader = easyocr.Reader(['ko', 'en'], gpu=False, model_storage_directory=f"{home_dir}/.EasyOCR")
print("✅ EasyOCR 리더 초기화 완료.")

# Gemini 모델 설정
# Gemini 모델 설정
try:
    # os.environ.get()을 사용하여 .env 파일에서 로드된 API 키를 가져옵니다.
    # os.environ.get()을 사용하여 .env 파일에서 로드된 API 키를 가져옵니다.
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') 
    if not GOOGLE_API_KEY:
        # .env 파일에 키가 없는 경우 에러를 발생시켜 서버가 실행되지 않도록 합니다.
        # .env 파일에 키가 없는 경우 에러를 발생시켜 서버가 실행되지 않도록 합니다.
        raise ValueError("환경 변수에서 GOOGLE_API_KEY를 찾을 수 없습니다. .env 파일을 확인해주세요.")
    
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini API 설정 완료.")

    # ★★★[기능 추가] Firebase Admin SDK 초기화 ★★★
    SERVICE_ACCOUNT_KEY_PATH = 'firebase-credentials.json' # 서비스 계정 키 파일 이름
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        raise FileNotFoundError(f"Firebase 서비스 계정 키 파일을 찾을 수 없습니다: {SERVICE_ACCOUNT_KEY_PATH}. Firebase 콘솔에서 다운로드하여 경로를 지정해주세요.")
    
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK 초기화 완료.")

    # ★★★[기능 추가] Firestore 클라이언트 초기화 ★★★
    db = firestore.client()
    print("✅ Firestore 클라이언트 초기화 완료.")


except Exception as e:
    print(f"🚨 Gemini API 설정 오류: {e}")
    model = None

# Colab 코드에 있던 이미지 처리 함수들
# Colab 코드에 있던 이미지 처리 함수들
def enhance_image_for_ocr(image_path, output_path="enhanced_image.png"):
    """이미지 비율을 먼저 확인하여 90도 회전 여부를 결정하는 최종 로직"""
    print(f"--- '{os.path.basename(image_path)}' 이미지 전처리 시작 ---")
    img = cv2.imread(image_path)
    
    if img is None: 
        print(f"⚠️ 파일을 읽을 수 없습니다: {image_path}")
        return None, None

    # === 1단계: 이미지 비율로 큰 방향 잡기 ===
    (h, w) = img.shape[:2]
    
    # 가로(w)가 세로(h)보다 길면, 90도 회전이 필요한 문서로 간주합니다.
    if w > h:
        print(f"✅ 가로로 긴 이미지(w:{w}, h:{h}) 감지. 90도 회전 실행.")
        # 원본 이미지를 시계 방향으로 90도 회전시켜 세웁니다.
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    else:
        print(f"✅ 세로로 긴 이미지(w:{w}, h:{h}) 감지. 90도 회전 안함.")

    # 이제 img 변수에는 무조건 세로 방향으로 정렬된 이미지가 들어있습니다.
    # === 2단계: 세로로 정렬된 이미지에서 미세 기울기 보정 ===
    
    # 2단계의 나머지 로직은 이전과 거의 동일합니다.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    rotated = img.copy() # 최종 결과물을 담을 변수 초기화

    try:
        gray_inv = cv2.bitwise_not(gray)
        _, thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # 미세조정 각도가 너무 크면 (보통 0에 가까움) 건너뛰는 안전장치는 유지합니다.
        if abs(angle) > 45:
            print(f"⚠️ 미세조정 각도({angle:.2f}°)가 너무 커서 추가 회전은 건너뜁니다.")
            rotated = img.copy()
        else:
            print(f"✅ 미세 기울기 보정 시작 (감지된 각도: {angle:.2f}°)")
            
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            cos = np.abs(M[0, 0])
            sin = np.abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]
            
            rotated = cv2.warpAffine(img, M, (new_w, new_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            print(f"✅ 미세 기울기 보정 완료.")
            
    except Exception as e:
        print(f"⚠️ 미세 기울기 보정 중 오류 발생 (90도 회전 원본만 사용): {e}")
        rotated = img.copy() 

    # 최종적으로 노이즈 제거 및 이진화 처리
    final_gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(final_gray, None, 10, 7, 21)
    final_img = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    filename, ext = os.path.splitext(output_path)
    if not ext:
        output_path = filename + '.png'

    cv2.imwrite(output_path, final_img)
    print(f"✅ 전처리 완료, 결과 저장: '{output_path}'")
    return output_path, rotated

# ======================================================================
# ★★★ [구조 변경] 백엔드에서 텍스트를 파싱하는 핵심 함수 ★★★
# ======================================================================
def parse_summary_from_text(text):
    """입력된 요약 텍스트 전체를 파싱하여 딕셔너리로 반환합니다."""
    summary = {}
    
    def extract_value(pattern, txt):
        match = re.search(pattern, txt, re.MULTILINE)
        return match.group(1).strip() if match else None

    patterns = {
        "owner_name": r"현재 소유자:\s*(.*)",
        "has_mortgage": r"근저당권:\s*(.*)",
        "mortgage_amount": r"채권최고액:\s*([\d,]+)원",
        "is_mortgage_cleared": r"말소 여부:\s*(.*)",
        "other_register_info": r"기타 등기사항:\s*(.*)",
        "contract_date": r"계약일:\s*(\d{4}-\d{2}-\d{2})",
        "lease_period": r"임대차 기간:\s*(.*)",
        "handover_date": r"명도일:\s*(\d{4}-\d{2}-\d{2})",
        "contract_addr": r"계약주소:\s*(.*)",
        "register_addr": r"등기부등본 주소:\s*(.*)",
        "register_addr": r"등기부등본 주소:\s*(.*)",
        "deposit": r"보증금:\s*([\d,]+)원",
        "monthly_rent": r"월세:\s*([\d,]+)원",
        "maintenance_fee": r"관리비:\s*([\d,]+)원",
        "included_fees": r"관리비 포함항목:\s*\[(.*)\]",
        "lessor_name": r"임대인:\s*(?!계좌정보)(.*)",
        "lessee_name": r"임차인:\s*(.*)",
        "lessor_account": r"임대인 계좌정보:\s*(.*)",
        "lessee_account": r"임차인 계좌정보:\s*(.*)",
        "building_type": r"건물유형:\s*(.*)" #[추가] 
    }

    for key, pattern in patterns.items():
        summary[key] = extract_value(pattern, text)

    # 데이터 후처리 (문자열 -> 숫자/bool/리스트 등)
    if summary.get("has_mortgage"):
        summary["has_mortgage"] = "있음" in summary["has_mortgage"]
    if summary.get("is_mortgage_cleared"):
        summary["is_mortgage_cleared"] = "말소됨" in summary["is_mortgage_cleared"]
    for key in ["mortgage_amount", "deposit", "monthly_rent", "maintenance_fee"]:
        if summary.get(key):
            try:
                summary[key] = int(summary[key].replace(',', ''))
            except (ValueError, TypeError):
                summary[key] = 0 # 숫자로 변환 실패 시 0으로 처리
    if summary.get("lease_period"):
        parts = summary["lease_period"].split('~')
        if len(parts) == 2:
            summary["lease_period"] = (parts[0].strip(), parts[1].strip())
    if summary.get("included_fees"):
        summary["included_fees"] = [fee.strip() for fee in summary["included_fees"].split(',')]
    
    # === 특약사항(clauses) 블록 추출 ===
    clause_block_match = re.search(r"(특약사항)\s*[:-]?\s*([\s\S]+)", text)
    if clause_block_match:
        clause_text = clause_block_match.group(2).strip()
        if len(clause_text) > 5:  # 실질적인 내용 있는 경우에만 반영
            summary["clauses_raw"] = clause_text
            summary["clauses"] = clause_text
            summary["clauses_cleaned"] = clause_text.strip()
        else:
            summary["clauses_raw"] = "특약사항 없음"
            summary["clauses"] = "특약사항 없음"
    else:
        summary["clauses_raw"] = "특약사항 없음"
        summary["clauses"] = "특약사항 없음"
    return summary

# ======================================================================
# 2. Flask 라우트(경로) 정의
# ======================================================================

# 메인 페이지를 보여주는 라우트
# 메인 페이지를 보여주는 라우트
@app.route('/')
def index():
    return render_template('index.html')

# OCR 처리를 담당하는 API 라우트
# OCR 처리를 담당하는 API 라우트
@app.route('/ocr', methods=['POST'])
def ocr_process():
    if 'registerFile' not in request.files or 'contractFile' not in request.files:
        return jsonify({'error': '두 개의 파일(등기부등본, 계약서)이 모두 필요합니다.'}), 400

    register_file = request.files['registerFile']
    contract_file = request.files['contractFile']
    
    # 파일 임시 저장
    # 파일 임시 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    register_filename = f"{timestamp}_register_{secure_filename(register_file.filename)}"
    contract_filename = f"{timestamp}_contract_{secure_filename(contract_file.filename)}"
    register_path = os.path.join(app.config['UPLOAD_FOLDER'], register_filename)
    contract_path = os.path.join(app.config['UPLOAD_FOLDER'], contract_filename)
    register_file.save(register_path)
    contract_file.save(contract_path)

    try:
        # --- 등기부등본 처리 ---
        # --- 등기부등본 처리 ---
        enhanced_reg_path, _ = enhance_image_for_ocr(register_path, f"enhanced_{register_filename}")
        if not enhanced_reg_path: raise Exception("등기부등본 이미지 처리 실패")
        reg_results = reader.readtext(enhanced_reg_path)
        reg_text = "\n".join([res[1] for res in reg_results])

        # --- 계약서 처리 ---
        # --- 계약서 처리 ---
        enhanced_con_path, _ = enhance_image_for_ocr(contract_path, f"enhanced_{contract_filename}")
        if not enhanced_con_path: raise Exception("계약서 이미지 처리 실패")
        con_results = reader.readtext(enhanced_con_path)
        con_text = "\n".join([res[1] for res in con_results])
        
        if not model: return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
            
        full_ocr_text = f"[등기부등본 OCR 결과]\n{reg_text}\n\n[계약서 OCR 결과]\n{con_text}"
        # 프롬프트
        prompt = f"""
당신은 대한민국 부동산 임대차 계약서와 등기부등본을 분석해 **요약 정보**와 **특약사항**을 구분하여 제공하는 AI 전문가입니다.
아래 OCR 텍스트를 바탕으로, 지정된 형식에 맞춰 **요약 정보**와 **특약사항**을 정확히 추출해주세요.

요약 형식:
--- 등기부등본 요약 ---
- 등기부등본 주소: (도로명 또는 지번 주소)
- 현재 소유자: OOO
- 근저당권: [설정 있음 / 없음]
- 채권최고액: XX,XXX,XXX원
- 말소 여부: [말소됨 / 유지]
- 기타 등기사항: (간략 요약)

--- 계약서 요약 ---
계약 기본정보
- 계약일: YYYY-MM-DD
- 임대차 기간: YYYY-MM-DD ~ YYYY-MM-DD
- 명도일: YYYY-MM-DD
- 계약주소: (도로명 또는 지번 주소)

금전 조건
- 보증금: X,XXX,XXX원
- 월세: XX,XXX원
- 관리비: XX,XXX원
- 관리비 포함항목: [인터넷, 전기, 수도 등]

임차인/임대인 정보
- 임대인: 성명 
- 임차인: 성명 
- 임대인 계좌정보: 은행명 / 계좌번호
- 비상 연락처: 성명 / 전화번호

특약사항
- (모든 특약 조항을 그대로 나열, 없으면 '특약사항 없음'으로 표기)

--- OCR 텍스트 ---
등기부등본 텍스트: {reg_text}
계약서 텍스트: {con_text}
---

[최종 분석]
- 아래 문단은 최종 분석을 포함하는 매우 중요한 항목입니다.
- 이 항목은 절대 생략하지 말고 반드시 작성해야 합니다.
- 누락되면 전체 응답이 무효 처리됩니다.
- 아래의 지시를 반드시 따르세요.
- 점수 기준에 따라 '위험', '주의', '안전' 중 하나로 최종 등급을 판단하세요.
- 등급 판단 사유를 자연스럽고 신뢰도 있게 설명하는 문장으로 서술해 주세요.
- 최종 분석 항목으로, 전체 계약서를 종합적으로 평가한 결과를 서술해 주세요.
"""
        response = model.generate_content(prompt)
        # 🔍 Gemini 응답 전체 확인
        print("🔍 Gemini 응답 전체:\n", response.text)
        full_corrected_text = response.text

        # ★★★ [구조 변경] Gemini가 생성한 텍스트를 '요약'과 '특약사항'과 '최종 분석 '으로 분리
        summary_part = ""
        clauses_part = "특약사항 없음" # 기본값
        
        # 3. clauses_part: "특약사항" 이후 전체
        split_keyword = "특약사항"
        if split_keyword in full_corrected_text:
            parts = full_corrected_text.split(split_keyword, 1)
            # clauses_part는 "특약사항" + 나머지
            clauses_part = (split_keyword + parts[1]).strip()
        else:
            clauses_part = "특약사항 없음"

        # 분리된 텍스트를 각각 JSON으로 반환
        return jsonify({
            'summary_text': summary_part,
            'clauses_text': clauses_part
        })

    except Exception as e:
        print(f"OCR 처리 중 심각한 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500
    
    finally:
        # try/except 블록이 끝나면 항상 임시 파일들을 삭제합니다.
        # try/except 블록이 끝나면 항상 임시 파일들을 삭제합니다.
        if os.path.exists(register_path): os.remove(register_path)
        if os.path.exists(contract_path): os.remove(contract_path)
        # 전처리된 파일들도 삭제
        # 전처리된 파일들도 삭제
        if 'enhanced_reg_path' in locals() and os.path.exists(enhanced_reg_path): os.remove(enhanced_reg_path)
        if 'enhanced_con_path' in locals() and os.path.exists(enhanced_con_path): os.remove(enhanced_con_path)

# ======================================================================
# ★★★ [구조 변경] 모든 분석을 처리하는 새로운 단일 종합 엔드포인트 ★★★
# ======================================================================

@app.route('/kakao-login', methods=['POST'])
def kakao_login():
    data = request.get_json()
    access_token = data.get('token')

    if not access_token:
        return jsonify({'error': '카카오 액세스 토큰이 필요합니다.'}), 400

    KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        print("--- 카카오 서버에 사용자 정보 요청 ---")
        response = requests.get(KAKAO_USERINFO_URL, headers=headers)
        response.raise_for_status()
        kakao_user_info = response.json()
        print(f"✅ 카카오 사용자 정보 수신 성공: {kakao_user_info}")

        kakao_user_id = str(kakao_user_info.get('id'))
        profile = kakao_user_info.get('properties', {})
        nickname = profile.get('nickname')
        
        if not kakao_user_id:
            return jsonify({'error': '카카오로부터 사용자 ID를 받을 수 없습니다.'}), 400

        uid = f'kakao:{kakao_user_id}'

        print(f"--- Firebase 처리 시작 (UID: {uid}) ---")
        try:
            auth.update_user(uid, display_name=nickname)
            print(f"✅ 기존 Firebase 사용자 정보 업데이트 완료.")
        except auth.UserNotFoundError:
            auth.create_user(uid=uid, display_name=nickname)
            print(f"✅ 신규 Firebase 사용자 생성 완료.")
            
            # ★★★[기능 추가] 신규 사용자일 경우, Firestore DB에 회원 정보 저장 ★★★
            user_data = {
                'nickname': nickname,
                'createdAt': firestore.SERVER_TIMESTAMP
            }
            db.collection('users').document(uid).set(user_data)
            print(f"✅ Firestore DB에 신규 회원 정보 저장 완료 (UID: {uid})")
        
        custom_token = auth.create_custom_token(uid)
        print("✅ Firebase 커스텀 토큰 생성 성공.")

        return jsonify({'firebase_token': custom_token.decode('utf-8')})

    except requests.exceptions.HTTPError as e:
        print(f"🚨 카카오 토큰 인증 실패: {e.response.text}")
        return jsonify({'error': '유효하지 않은 카카오 토큰입니다.', 'details': e.response.json()}), 401
    except Exception as e:
        print(f"🚨 로그인 처리 중 심각한 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500

@app.route('/process-analysis', methods=['POST'])

def process_analysis():
    data = request.get_json()
    summary_text = data.get('summary_text')
    clauses_text = data.get('clauses_text')
    uid = data.get('uid') # ★★★[기능 추가] 프론트로부터 UID 수신

    # === [최종 분석] 블록 추출 ===
    import re

    if not summary_text:
        return jsonify({'error': '분석할 요약 내용이 없습니다.'}), 400
    if not uid:
        return jsonify({'error': '사용자 정보(UID)가 없습니다. 다시 로그인해주세요.'}), 401

    # 1. 백엔드에서 텍스트 파싱
    parsed_data = parse_summary_from_text(summary_text)
 
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    # ★★★ 요청하신 모든 변수의 개별 로그를 확인하는 부분 ★★★
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    print("\n--- [종합 분석] 파싱된 모든 변수 개별 확인 시작 ---")
    # 등기부등본 요약
    print(f"✅ UID: {uid}")
    print(f"✅ 소유주 이름: {parsed_data.get('owner_name')}, 타입: {type(parsed_data.get('owner_name'))}")
    print(f"✅ 등기부등본 주소: {parsed_data.get('register_addr')}, 타입: {type(parsed_data.get('register_addr'))}")
    print(f"✅ 근저당권 설정 여부: {parsed_data.get('has_mortgage')}, 타입: {type(parsed_data.get('has_mortgage'))}")
    print(f"✅ 채권최고액: {parsed_data.get('mortgage_amount')}, 타입: {type(parsed_data.get('mortgage_amount'))}")
    print(f"✅ 근저당권 말소 여부: {parsed_data.get('is_mortgage_cleared')}, 타입: {type(parsed_data.get('is_mortgage_cleared'))}")
    print(f"✅ 기타 등기사항: {parsed_data.get('other_register_info')}, 타입: {type(parsed_data.get('other_register_info'))}")
    
    print("---")
    
    # 계약 기본 정보
    print(f"✅ 계약일: {parsed_data.get('contract_date')}, 타입: {type(parsed_data.get('contract_date'))}")
    print(f"✅ 임대차 기간: {parsed_data.get('lease_period')}, 타입: {type(parsed_data.get('lease_period'))}")
    print(f"✅ 명도일: {parsed_data.get('handover_date')}, 타입: {type(parsed_data.get('handover_date'))}")
    print(f"✅ 계약주소: {parsed_data.get('contract_addr')}, 타입: {type(parsed_data.get('contract_addr'))}")

    print("---")

    # 금전 조건
    print(f"✅ 보증금: {parsed_data.get('deposit')}, 타입: {type(parsed_data.get('deposit'))}")
    print(f"✅ 월세: {parsed_data.get('monthly_rent')}, 타입: {type(parsed_data.get('monthly_rent'))}")
    print(f"✅ 관리비: {parsed_data.get('maintenance_fee')}, 타입: {type(parsed_data.get('maintenance_fee'))}")
    print(f"✅ 관리비 포함항목: {parsed_data.get('included_fees')}, 타입: {type(parsed_data.get('included_fees'))}")

    print("---")

    # 인적 정보
    print(f"✅ 임대인 이름: {parsed_data.get('lessor_name')}, 타입: {type(parsed_data.get('lessor_name'))}")
    print(f"✅ 임차인 이름: {parsed_data.get('lessee_name')}, 타입: {type(parsed_data.get('lessee_name'))}")
    print(f"✅ 임대인 계좌정보: {parsed_data.get('lessor_account')}, 타입: {type(parsed_data.get('lessor_account'))}")

    print("--- [종합 분석] 변수 개별 확인 종료 ---\n")

    # =========================
    # 특약사항 텍스트 최종 결정 및 로그 추가
    # =========================
    print("🧾 분석할 특약사항 최종 내용:\n", clauses_text)

    # ★★★[추가]위험 판단 로직 실행 (rule.rules 모듈 내 함수 기반으로 각 리스크 항목 평가) 
    
 
 # ======================================================================
 # ★★★[추가]위험 판단 로직 실행 (rule.rules 모듈 내 함수 기반으로 각 리스크 항목 평가) 
 # ======================================================================
    logic_results = {}

    market_price = None
    market_basis = None
    

    try:
        # === 입력 데이터 파싱 ===
        owner_name = parsed_data.get("owner_name")
        lessor_name = parsed_data.get("lessor_name")
        deposit = parsed_data.get("deposit")
        register_addr = parsed_data.get("register_addr")
        contract_addr = parsed_data.get("contract_addr")

        building_type = "아파트"  # 임시 지정. 실제론 계약서 기반으로 판단해야 정확.

        has_mortgage = parsed_data.get("has_mortgage")
        is_mortgage_cleared = parsed_data.get("is_mortgage_cleared")
        mortgage_amount = parsed_data.get("mortgage_amount")

        # === 위험 요소 판단 ===
        # --- 임대인-소유주 일치 메시지 생성 부분 확인용 ---
        if owner_name and lessor_name:
            import re
            def extract_name_only(text):
                # 괄호 안에 주민번호 형식 제거
                return re.sub(r'\s*\(.*?\)', '', text).strip()
            owner_name_only = extract_name_only(owner_name)
            lessor_name_only = extract_name_only(lessor_name)
            print("[검증] 임대인-소유주 일치 비교 대상 이름만:")
            print("  owner_name:", owner_name_only)
            print("  lessor_name:", lessor_name_only)
            logic_results['임대인-소유주 일치'] = check_owner_match(owner_name_only, lessor_name_only)
        # --- END 임대인-소유주 일치 메시지 생성 부분 ---

        if has_mortgage is not None and is_mortgage_cleared is not None:
            logic_results['근저당 위험'] = check_mortgage_risk(has_mortgage, is_mortgage_cleared)

        if register_addr and contract_addr:
            logic_results['주소 일치 여부'] = compare_address(register_addr, contract_addr, confm_key)

        # === 시세 예측 (실패해도 나머지 계속 진행) ===
        try:
            print("💬 시세 예측 시작:", contract_addr, building_type)
            _, market_price, market_basis= estimate_median_trade(contract_addr, building_type, 30.0)
            print("✅ 시세 예측 완료:", market_price, market_basis)

            if deposit and market_price:
                logic_results['시세 대비 보증금 위험'] = check_deposit_over_market(deposit, market_price)

            if deposit and mortgage_amount:
                logic_results['보증금 대비 채권최고액 위험'] = check_mortgage_vs_deposit(deposit, market_price, mortgage_amount)

        except Exception as e:
            print("❌ 거래 시세 예측 실패:", e)
            market_price = None
            market_basis = "시세 예측 실패"

        # # === 결과 포맷 정리 ===
        details = []
        for key, result in logic_results.items():
            if result and isinstance(result, dict) and result.get("grade"):
                details.append({
                    "type": key,
                    "grade":result["grade"],
                    "message": result["message"]
                })

    except Exception as e:
        print(f"오류오류 오류: {e}")
        return jsonify({
        "market_price": None,
        "market_basis": None,
        "details": [],
        "error": f"위험 판단 로직 오류: {str(e)}"
    }), 500




    # 2. clauses_text 결정 로직 및 로그 출력
    import re as _re
    if clauses_text and not _re.search(r"^특약사항\s*(없음|없습니다|없다)$", clauses_text.strip()):
        print("🧾 프론트에서 받은 clauses_text 사용")
    elif parsed_data.get("clauses_cleaned") and not _re.search(r"^특약사항\s*(없음|없습니다|없다)$", parsed_data["clauses_cleaned"].strip()):
        clauses_text = parsed_data["clauses_cleaned"]
        print("🧾 요약에서 추출한 clauses_cleaned 사용")
    else:
        clauses_text = "특약사항 없음"
        print("🧾 사용할 특약사항 없음")

    # 3. 특약사항 분석 (Gemini API 호출)
    clauses_analysis_result = "분석할 특약사항 없음"
    if clauses_text and "특약사항 없음" not in clauses_text:
        if not model: return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
        try:
            # ★★★[핵심 수정] 특약사항 위험도 분석을 위한 전용 프롬프트: 카드 스타일 HTML 강제 프롬프트로 변경 ★★★
            prompt = f"""
당신은 대한민국 부동산 계약의 법률 전문가입니다. 아래의 '특약사항' 조항들을 임차인의 입장에서 분석하세요.

            [특약사항 내용]
            {clauses_text}
            [/특약사항 내용]

            [분석 지침]
            1. 각 조항을 아래와 같은 카드 형태 HTML로 분석하세요.

            예시:
            <div class="risk-card">
              <div class="risk-title"><b><span class="risk-number">1.</span> 조항 내용</b></div>
              <div class="risk-badge risk-high">🚨 위험</div>
              <div class="risk-desc">해당 조항에 대한 위험 설명 및 조치 제안</div>
            </div>

            2. 반드시 위와 같은 HTML 카드 형태만 출력하세요. 표나 일반 텍스트, 인삿말, 서론 등은 포함하지 마세요.
            3. 위험도는 다음 중 하나만 사용하세요:
               - <div class="risk-badge risk-high">🚨 위험</div>
               - <div class="risk-badge risk-medium">⚠️ 주의</div>
               - <div class="risk-badge risk-low">✔️ 낮음</div>
            4. <div class="risk-card">로 시작해서, 내부에 title, badge, desc를 포함하는 구조로만 출력하세요.

            📌 중요: 절대 표 형태나 리스트 형태로 출력하지 마세요. 반드시
"""
            response = model.generate_content(prompt)
            clauses_analysis_result = response.text
            # ★★★[추가] Gemini 응답이 ```html ~ ``` 마크다운 코드블럭으로 감싸져 있을 경우 제거
            import re
            clauses_analysis_result = re.sub(r"```html\s*([\s\S]*?)\s*```", r"\1", clauses_analysis_result).strip()
        except Exception as e:
            print(f"특약사항 분석 중 오류 발생: {e}")
            clauses_analysis_result = "특약사항 분석 중 오류가 발생했습니다."

    # 🔢 [수정] 등급별 점수 설정 및 평균 계산
    print("\n--- [최종 등급 산출] 시작 ---")
    # 1. grade_list를 모든 핵심 검증 및 특약 분석에서 추출된 등급 문자열 리스트로 구성
    grade_list = []
    logic_items_to_score = [
        '임대인-소유주 일치',
        '주소 일치 여부',
        '시세 대비 보증금 위험',
        '보증금 대비 채권최고액 위험'
    ]
    for key in logic_items_to_score:
        result = logic_results.get(key)
        if result and 'grade' in result:
            grade_list.append(result['grade'])
    # 특약사항 분석 등급 추출
    clauses_grade = None
    if '위험도: 높음' in clauses_analysis_result:
        clauses_grade = '위험'
    elif '위험도: 중간' in clauses_analysis_result:
        clauses_grade = '주의'
    elif '위험도: 낮음' in clauses_analysis_result:
        clauses_grade = '안전'
    elif "특약사항 없음" in clauses_analysis_result or "특이사항이 발견되지 않았습니다" in clauses_analysis_result:
        clauses_grade = '안전'
    # 특약사항 분석에서 여러 개의 등급이 존재할 수 있는 경우, BeautifulSoup로 모두 추출
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(clauses_analysis_result, "html.parser")
        risk_cards = soup.find_all("div", class_="risk-card")
        for card in risk_cards:
            badge = card.find("div", class_="risk-badge")
            if badge:
                if "risk-high" in badge.get("class", []):
                    grade_list.append("위험")
                elif "risk-medium" in badge.get("class", []):
                    grade_list.append("주의")
                elif "risk-low" in badge.get("class", []):
                    grade_list.append("안전")
    except Exception as e:
        # fallback: 단일 등급만 추가
        if clauses_grade:
            grade_list.append(clauses_grade)

    # === 등급별 분류 ===
    high_grades = [g for g in grade_list if g == '위험']
    medium_grades = [g for g in grade_list if g == '주의']
    low_grades = [g for g in grade_list if g == '안전']
    all_grades = high_grades + medium_grades + low_grades

    # 🔢 등급별 점수화
    grade_points = []
    for g in grade_list:  # grade_list는 고정 검증 및 특약 분석에서 추출된 등급 문자열 리스트
        if g == '안전':
            grade_points.append(1)
        elif g == '주의':
            # 주의는 등장 횟수마다 1점 추가 가중치
            count = grade_points.count(3)
            grade_points.append(3 + count)
        elif g == '위험':
            grade_points.append(5)

    if grade_points:
        avg_score = sum(grade_points) / len(grade_points)
    else:
        avg_score = 0

    # 🏆 [수정] 평균 점수 기반 최종 등급 결정
    if avg_score <= 2.0:
        final_grade = '안전'
    elif avg_score <= 4.0:
        final_grade = '주의'
    else:
        final_grade = '위험'
    print("---")
    print(f"🔢 계산된 전체 등급 리스트: {grade_list}")
    print(f"🔢 계산된 전체 점수 리스트: {grade_points}")
    print(f"📊 최종 평균 점수: {avg_score:.2f}")
    print(f"🏆 최종 산출 등급: {final_grade}")
    print("--- [최종 등급 산출] 종료 ---\n")

    # ★★★[추가] 등급 판단 사유 생성 로직 ★★★
    if final_grade == '위험':
        judgment_reason = (
            "등급 판단 사유: 다수의 위험 등급 항목이 발견되었습니다. "
            "보증금 미반환 가능성이 높으며, 반드시 법률 전문가의 검토 후 계약 여부를 결정해야 합니다."
        )
    elif final_grade == '주의':
        judgment_reason = (
            "등급 판단 사유: 일부 항목에서 주의가 필요한 내용이 확인되었습니다. "
            "계약 전 세부 조항을 임대인과 충분히 협의하고 문제를 명확히 해야 합니다."
        )
    elif final_grade == '안전':
        judgment_reason = (
            "등급 판단 사유: 특이사항 없이 비교적 안전한 계약으로 판단됩니다. "
            "단, 계약 내용은 끝까지 꼼꼼히 검토하시기 바랍니다."
        )
    else:
        judgment_reason = "등급 판단 사유: 분석된 항목이 부족하여 정확한 등급을 산출할 수 없습니다."

    print(f"[디버깅] judgment_reason: {judgment_reason}")

    # ======================================================================
    # [추가] 평균 점수 산출을 위한 all_grades 기반 weighted score 계산
    # ======================================================================
    # --- all_grades는 모든 위험 평가의 등급 문자열 리스트로 구성 (grade_list와 유사, 혹은 동일 사용)
    all_grades = grade_list.copy()
    # Calculate weighted score for final grade
    grade_scores = []
    attention_score = 3
    for grade in all_grades:
        if grade == '안전':
            grade_scores.append(1)
        elif grade == '주의':
            grade_scores.append(attention_score)
            attention_score += 1
        elif grade == '위험':
            grade_scores.append(5)
    average_score = round(sum(grade_scores) / len(grade_scores), 2) if grade_scores else 0

    # 💡 카드형 UI 변환 및 요약 박스 추가
    def convert_clause_analysis_to_cards(raw_text, high=0, medium=0, low=0):
        summary_html = f"""
<div class="summary-box" style="background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 10px; padding: 20px; margin-bottom: 20px;">
  <p style="margin: 0; font-weight: bold;">분석 대상 수: {high + medium + low}개</p>
  <ul style="list-style: none; padding-left: 0; margin-top: 10px;">
    <li>- 위험 등급 높음: {high}개</li>
    <li>- 주의 등급: {medium}개</li>
    <li>- 안전 등급: {low}개</li>
  </ul>
</div>
"""
        card_html = ""
        blocks = raw_text.strip().split("<div class=\"risk-card\">")
        for block in blocks[1:]:
            block_content = block.split("</div>", 1)[0]
            card_html += f"<div class=\"risk-card\">{block_content}</div>\n"
        return summary_html + card_html

    # --- 분석 결과 요약 summary HTML 제거 및 카드형 UI 변환 ---
    high_count = sum(1 for d in details if d['grade'] == '위험')
    medium_count = sum(1 for d in details if d['grade'] == '주의')
    low_count = sum(1 for d in details if d['grade'] == '안전')

    clauses_analysis_html = convert_clause_analysis_to_cards(clauses_analysis_result, high=high_count, medium=medium_count, low=low_count)
    print("✅ 카드형 UI 변환 완료")
    # --- 특약사항 위험 카드 개수 카운트 (BeautifulSoup 기반으로 변경) ---
    print("🔍 등급 카운팅 시작 (BeautifulSoup 기반)")
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(clauses_analysis_result, "html.parser")
        risk_cards = soup.find_all("div", class_="risk-card")
        clauses_count = len(risk_cards)
        risk_high_count = 0
        risk_medium_count = 0
        risk_low_count = 0
        for card in risk_cards:
            badge = card.find("div", class_="risk-badge")
            if badge:
                badge_class = badge.get("class", [])
                if "risk-high" in badge_class:
                    risk_high_count += 1
                elif "risk-medium" in badge_class:
                    risk_medium_count += 1
                elif "risk-low" in badge_class:
                    risk_low_count += 1
        print(f"✅ 위험 카드 수: {risk_high_count}")
        print(f"✅ 주의 카드 수: {risk_medium_count}")
        print(f"✅ 안전 카드 수: {risk_low_count}")
    except Exception as e:
        print(f"🚨 BeautifulSoup 카드 카운팅 오류: {e}")
        clauses_count = 0
        risk_high_count = 0
        risk_medium_count = 0
        risk_low_count = 0

    final_result = {
        "verifications": {
            "logic_results": logic_results,
            "clauses_analysis": clauses_analysis_result,
            "clauses_html": clauses_analysis_html,  # 카드형 HTML
            # --- 아래 줄을 추가: 원본 Gemini 생성 결과(HTML)를 그대로 반환 ---
            "clauses_html": clauses_analysis_result,
            "final_grade": final_grade,
            "final_clauses_grade": clauses_grade,
            "average_score": average_score,
            "grade_scores": grade_scores,
            # === 특약 위험 카드 카운트 ===
            "clauses_count": clauses_count,
            "risk_high_count": risk_high_count,
            "risk_medium_count": risk_medium_count,
            "risk_low_count": risk_low_count,
            
        },
        "evaluation": {
            "scores": grade_scores,
            "average_score": round(average_score, 2),
            "final_grade": final_grade,
            "judgment_reason": judgment_reason  # ★★★[추가]
        }
    }

    # ★★★[기능 추가] 분석 결과를 Firestore에 저장 ★★★
    try:
        analysis_data_to_save = {
            'summaryText': summary_text,      # 사용자가 확인/수정한 요약 원본 텍스트
            'clausesText': clauses_text,      # ★★★[수정] 이 부분의 주석을 해제하여 특약사항 텍스트도 저장합니다.
            'analysisReport': clauses_analysis_html,   # AI가 생성한 최종 카드형 HTML 보고서 저장
            'createdAt': firestore.SERVER_TIMESTAMP, # 분석 시간
            'parsedData': parsed_data
        }
        # users/{uid}/analyses 컬렉션에 새로운 문서 추가
        db.collection('users').document(uid).collection('analyses').add(analysis_data_to_save)
        print(f"✅ Firestore에 분석 결과 저장 성공 (UID: {uid})")
    except Exception as e:
        print(f"🚨 Firestore 저장 실패: {e}")
        # 저장에 실패하더라도 사용자에게는 분석 결과를 보여줘야 하므로, 에러를 반환하지 않고 계속 진행합니다.

    # 6. 최종 결과를 프론트엔드에 반환
    # analysis_result dict에 final_risk_level도 추가 (호환성)
    analysis_result = final_result
    if "verifications" in analysis_result:
        analysis_result["verifications"]["final_risk_level"] = final_grade
    return jsonify(final_result)



# ======================================================================
# 3. 앱 실행
# ======================================================================
if __name__ == '__main__':
    # host='0.0.0.0'는 외부에서 접속 가능하게 함
    # debug=True는 개발 중에만 사용하고, 실제 배포 시에는 False로 변경하거나 제거합니다.
    app.run(host='0.0.0.0', port=5000, debug=True)
    

