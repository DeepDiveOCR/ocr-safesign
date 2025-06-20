import os
import cv2
import numpy as np
import easyocr
import google.generativeai as genai
# session 사용을 위해 import 추가
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# ======================================================================
# 1. Flask 앱 설정 및 환경 변수 로드
# ======================================================================

load_dotenv() 

app = Flask(__name__)
# 세션을 사용하기 위한 비밀 키 설정
app.secret_key = 'safesign'

if not os.path.exists('uploads'):
    os.makedirs('uploads')
    
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

print("EasyOCR 리더를 초기화합니다...")
reader = easyocr.Reader(['ko','en'])
print("✅ EasyOCR 리더 초기화 완료.")

try:
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') 
    if not GOOGLE_API_KEY:
        raise ValueError("환경 변수에서 GOOGLE_API_KEY를 찾을 수 없습니다. .env 파일을 확인해주세요.")
    
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini API 설정 완료.")
except Exception as e:
    print(f"🚨 Gemini API 설정 오류: {e}")
    model = None

def enhance_image_for_ocr(image_path, output_path="enhanced_image.png"):
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
        rotated = img.copy()
    gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    final_img = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    cv2.imwrite(output_path, final_img)
    print(f"✅ 전처리 완료, 결과 저장: '{output_path}'")
    return output_path, rotated

# ======================================================================
# 2. Flask 라우트(경로) 정의
# ======================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ocr', methods=['POST'])
def ocr_process():
    if 'registerFile' not in request.files or 'contractFile' not in request.files:
        return jsonify({'error': '두 개의 파일(등기부등본, 계약서)이 모두 필요합니다.'}), 400

    register_file = request.files['registerFile']
    contract_file = request.files['contractFile']
    
    register_filename = secure_filename(register_file.filename)
    contract_filename = secure_filename(contract_file.filename)
    register_path = os.path.join(app.config['UPLOAD_FOLDER'], register_filename)
    contract_path = os.path.join(app.config['UPLOAD_FOLDER'], contract_filename)
    register_file.save(register_path)
    contract_file.save(contract_path)

    try:
        enhanced_reg_path, _ = enhance_image_for_ocr(register_path, f"enhanced_{register_filename}")
        if not enhanced_reg_path:
            raise Exception("등기부등본 이미지 처리 실패")
        reg_results = reader.readtext(enhanced_reg_path)
        reg_text = "\n".join([res[1] for res in reg_results])

        enhanced_con_path, _ = enhance_image_for_ocr(contract_path, f"enhanced_{contract_filename}")
        if not enhanced_con_path:
            raise Exception("계약서 이미지 처리 실패")
        con_results = reader.readtext(enhanced_con_path)
        con_text = "\n".join([res[1] for res in con_results])
        
        if not model:
            return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
            
        full_ocr_text = f"[등기부등본 OCR 결과]\n{reg_text}\n\n[계약서 OCR 결과]\n{con_text}"
        
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
        9. 계약서의 특약사항은 반드시 전문을 포함합니다. 특약이 없는 경우 "특약사항 없음"으로 표기합니다.
        10. 만약 n번 근저당 말소됨 등 과 같은 말이 있으면 해당 필드는 말소된것입니다. 결과에서 지워주세요

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
        - 비상 연락처: 성명 / 전화번호

        특약사항
        - 제 1조 : (특약 내용)
        - 제 2조 : (특약 내용)
        - 제 3조 : (특약 내용)
        - 제 n조 : (특약 내용)
        - (특약이 없는 경우 "특약사항 없음"으로 표기)

        --- OCR 텍스트 ---
        등기부등본 텍스트: {reg_text}
        계약서 텍스트: {con_text}
        ---

        위 문서를 바탕으로 위 형식에 맞춰 요약 정보를 작성해주세요.
        """
        response = model.generate_content(prompt)
        full_corrected_text = response.text

        summary_to_display = full_corrected_text
        special_clauses_text = "" # 기본값은 빈 문자열
        
        # '특약사항' 키워드를 찾습니다.
        split_keyword = "특약사항"
        split_index = full_corrected_text.find(split_keyword)

        if split_index != -1:
            # 키워드를 찾았다면, 해당 위치를 기준으로 텍스트를 나눕니다.
            summary_to_display = full_corrected_text[:split_index].strip()
            special_clauses_text = full_corrected_text[split_index:].strip()
        
        # 분리된 특약사항 내용을 세션에 저장합니다.
        session['special_clauses'] = special_clauses_text
        # 확인용 로그: 실제 운영 시에는 제거해도 됩니다.
        print("--- 특약사항 정보 (세션에 저장됨) ---")
        print(session.get('special_clauses'))
        print("------------------------------------")
        
        # ★★★★★ 변경점 3: 화면에 표시할 요약 정보만 JSON으로 반환 ★★★★★
        return jsonify({'corrected_text': summary_to_display})

    except Exception as e:
        print(f"OCR 처리 중 심각한 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500
    
    finally:
        if os.path.exists(register_path): os.remove(register_path)
        if os.path.exists(contract_path): os.remove(contract_path)
        if 'enhanced_reg_path' in locals() and os.path.exists(enhanced_reg_path): os.remove(enhanced_reg_path)
        if 'enhanced_con_path' in locals() and os.path.exists(enhanced_con_path): os.remove(enhanced_con_path)

# ======================================================================
# 2-1. 특약사항 분석을 담당하는 API 라우트
# ======================================================================
@app.route('/clauses', methods=['POST'])
def clauses_analysis():
    special_clauses = session.get('special_clauses')

    if not special_clauses or special_clauses.strip() == "특약사항 없음":
        return jsonify({
            'analysis_result': '분석할 특약사항이 없거나, 계약서에 특약사항이 기재되어 있지 않습니다.',
            'overall_risk': '안전' # 특약이 없으면 '안전'으로 간주
        })

    if not model:
        return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500

    try:
        # ★★★★★ 프롬프트 수정 ★★★★★
        # '종합 의견' 부분을 '최종 요약'으로 바꾸고, 간결하게 작성하도록 명확히 지시합니다.
        prompt = f"""
        당신은 대한민국 부동산 법률 전문가입니다. 당신의 임무는 전월세 계약서의 특약사항을 '임차인'의 입장에서 분석하고, 잠재적인 위험 요소와 그 결론을 간결하게 제시하는 것입니다.

        아래는 계약서의 특약사항 전문입니다. 각 조항을 면밀히 검토해 주세요.

        [특약사항 내용]
        {special_clauses}
        [/특약사항 내용]

        [분석 및 출력 가이드라인]
        1.  **위험 조항 식별**: 임차인에게 불리한 조항을 모두 찾아내세요.
        2.  **위험도 평가**: 각 위험 조항에 대해 '위험도: 높음', '위험도: 중간', '위험도: 낮음' 형식으로 명확하게 평가해주세요.
        3.  **위험 이유 설명**: 왜 해당 조항이 위험한지 구체적이고 이해하기 쉽게 설명해주세요.
        4.  **대응 방안 제시**: 각 위험에 대한 구체적인 대응 방안을 제시해주세요.
        5.  **표 형식 결과**: 위 1~4번 분석 내용을 Markdown 형식의 표(table)로 명확하게 작성해주세요.
        6.  **최종 요약 (가장 중요)**: 표 아래에 "### 최종 요약"이라는 제목으로, **가장 치명적인 위험 조항 2~3개를 구체적으로 언급하며 최종 결론을 2문장 이내로 간결하게 요약해주세요.** 절대 길게 서술하지 마세요.
            (예시: "### 최종 요약\n제6조 계약금 귀속 및 제8조 일방적 계약 해지 조항은 임차인에게 매우 불리하므로, 계약 전 반드시 수정 또는 삭제가 필요합니다.")

        위 가이드라인에 따라 특약사항 분석 리포트를 작성해주세요.
        """
        response = model.generate_content(prompt)
        analysis_result_text = response.text
        
        # 종합 위험도 자동 판별 로직 (기존과 동일)
        overall_risk = '안전' 
        if '위험도: 높음' in analysis_result_text:
            overall_risk = '위험'
        elif '위험도: 중간' in analysis_result_text:
            overall_risk = '주의'
        
        # 분석 결과와 종합 위험도를 함께 JSON으로 반환
        return jsonify({
            'analysis_result': analysis_result_text,
            'overall_risk': overall_risk
        })

    except Exception as e:
        print(f"특약사항 분석 중 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500

# ======================================================================
# 3. 앱 실행
# ======================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)