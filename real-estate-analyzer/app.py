import os
import cv2
import numpy as np
import easyocr
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv # .env 파일을 위한 라이브러리 임포트

# ======================================================================
# 1. Flask 앱 설정 및 환경 변수 로드
# ======================================================================

# .env 파일에서 환경 변수를 로드합니다.
# 이 함수는 app.py와 같은 위치에 있는 .env 파일을 찾아서 그 안의 값들을 환경 변수로 설정합니다.
load_dotenv() 

app = Flask(__name__)
# 'uploads' 폴더가 없으면 생성합니다.
if not os.path.exists('uploads'):
    os.makedirs('uploads')
    
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB 파일 사이즈 제한

# EasyOCR 리더 전역 변수로 초기화 (매번 로드하지 않도록)
print("EasyOCR 리더를 초기화합니다...")
reader = easyocr.Reader(['ko','en'])
print("✅ EasyOCR 리더 초기화 완료.")

# Gemini 모델 설정
try:
    # os.environ.get()을 사용하여 .env 파일에서 로드된 API 키를 가져옵니다.
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') 
    if not GOOGLE_API_KEY:
        # .env 파일에 키가 없는 경우 에러를 발생시켜 서버가 실행되지 않도록 합니다.
        raise ValueError("환경 변수에서 GOOGLE_API_KEY를 찾을 수 없습니다. .env 파일을 확인해주세요.")
    
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # 최신 모델명 사용
    print("✅ Gemini API 설정 완료.")
except Exception as e:
    print(f"🚨 Gemini API 설정 오류: {e}")
    model = None

# Colab 코드에 있던 이미지 처리 함수들
def enhance_image_for_ocr(image_path, output_path="enhanced_image.png"):
    # (Colab 코드의 enhance_image_for_ocr 함수 내용 전체를 여기에 붙여넣기)
    print(f"--- '{os.path.basename(image_path)}' 이미지 전처리 시작 ---")
    img = cv2.imread(image_path)
    if img is None: return None, None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    try:
        gray_inv = cv2.bitwise_not(gray)
        _, thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45: angle = -(90 + angle)
        else: angle = -angle
        if abs(angle) > 45: 
            print(f"⚠️ 비정상적인 각도({angle:.2f}°)가 감지되어 회전을 건너뜁니다.")
            rotated = img.copy()
        else:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            print(f"✅ 기울기 보정 완료 (감지된 각도: {angle:.2f}°)")
    except Exception as e:
        print(f"⚠️ 기울기 보정 중 오류 발생 (원본 사용): {e}")
        rotated = img.copy() # 오류 발생 시 원본 이미지 사용
    gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    final_img = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    cv2.imwrite(output_path, final_img)
    print(f"✅ 전처리 완료, 결과 저장: '{output_path}'")
    return output_path, rotated

# ======================================================================
# 2. Flask 라우트(경로) 정의
# ======================================================================

# 메인 페이지를 보여주는 라우트
@app.route('/')
def index():
    return render_template('index.html')

# OCR 처리를 담당하는 API 라우트
@app.route('/ocr', methods=['POST'])
def ocr_process():
    if 'registerFile' not in request.files or 'contractFile' not in request.files:
        return jsonify({'error': '두 개의 파일(등기부등본, 계약서)이 모두 필요합니다.'}), 400

    register_file = request.files['registerFile']
    contract_file = request.files['contractFile']
    
    # 파일 임시 저장
    register_filename = secure_filename(register_file.filename)
    contract_filename = secure_filename(contract_file.filename)
    register_path = os.path.join(app.config['UPLOAD_FOLDER'], register_filename)
    contract_path = os.path.join(app.config['UPLOAD_FOLDER'], contract_filename)
    register_file.save(register_path)
    contract_file.save(contract_path)

    try:
        # --- 등기부등본 처리 ---
        enhanced_reg_path, _ = enhance_image_for_ocr(register_path, f"enhanced_{register_filename}")
        if not enhanced_reg_path:
            raise Exception("등기부등본 이미지 처리 실패")
        reg_results = reader.readtext(enhanced_reg_path)
        reg_text = "\n".join([res[1] for res in reg_results])

        # --- 계약서 처리 ---
        enhanced_con_path, _ = enhance_image_for_ocr(contract_path, f"enhanced_{contract_filename}")
        if not enhanced_con_path:
            raise Exception("계약서 이미지 처리 실패")
        con_results = reader.readtext(enhanced_con_path)
        con_text = "\n".join([res[1] for res in con_results])
        
        # --- Gemini로 텍스트 보정 ---
        if not model:
            return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
            
        full_ocr_text = f"[등기부등본 OCR 결과]\n{reg_text}\n\n[계약서 OCR 결과]\n{con_text}"
        
        # 프롬프트
        prompt = f"""
        당신은 대한민국 부동산 임대차 계약서와 등기부등본을 분석해 **요약 정보**를 제공하는 AI 전문가입니다.

        아래는 OCR로 추출된 계약서와 등기부등본 텍스트입니다. 이 텍스트에는 오타, 숫자 오류, 누락 등이 있을 수 있습니다.  
        당신의 임무는 다음과 같습니다:

        1. 문서를 정리하여 계약서와 등기부등본을 각각 요약합니다.  
        2. **형식을 고정된 구조로** 작성합니다 (예시는 아래에 명시).  
        3. 숫자 오류는 자연스럽게 보정하고, 개인정보는 마스킹 하지 않습니다.
        4. 현시점의 근저당 여부를 계산해서 만약 모든 근저당 항목이 말소된 경우 "설정 없음"으로 표기합니다.
        5. 형식 외에는 추가적인 내용은 포함하지 않습니다.
        6. 임대인과 임차인의 정보는 매우 중요하므로 정확하게 요약합니다.
        7. 등기부등본의 요약과 계약서 요약은 따로 처리합니다.
        8. 등기부등본의 소유주와 계약서 상의 임대인은 다를 수 있습니다. 이 경우 등기부등본 요약에는 등기부등본 소유주, 계약서에는 계약서의 임대인 정보를 우선시합니다. 
        요약 형식은 다음과 같이 출력하세요:

        --- 등기부등본 요약 ---
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

        --- OCR 텍스트 ---
        등기부등본 텍스트: {reg_text}
        계약서 텍스트: {con_text}
        ---

        위 문서를 바탕으로 위 형식에 맞춰 요약 정보를 작성해주세요.
        """
        response = model.generate_content(prompt)
        corrected_text = response.text
        
        # 성공 시 보정된 텍스트를 JSON으로 반환
        return jsonify({'corrected_text': corrected_text})

    except Exception as e:
        print(f"OCR 처리 중 심각한 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500
    
    finally:
        # try/except 블록이 끝나면 항상 임시 파일들을 삭제합니다.
        if os.path.exists(register_path): os.remove(register_path)
        if os.path.exists(contract_path): os.remove(contract_path)
        # 전처리된 파일들도 삭제
        if 'enhanced_reg_path' in locals() and os.path.exists(enhanced_reg_path): os.remove(enhanced_reg_path)
        if 'enhanced_con_path' in locals() and os.path.exists(enhanced_con_path): os.remove(enhanced_con_path)


# ======================================================================
# 3. 앱 실행
# ======================================================================
if __name__ == '__main__':
    # host='0.0.0.0'는 외부에서 접속 가능하게 함
    # debug=True는 개발 중에만 사용하고, 실제 배포 시에는 False로 변경하거나 제거합니다.
    app.run(host='0.0.0.0', port=5000, debug=True)

