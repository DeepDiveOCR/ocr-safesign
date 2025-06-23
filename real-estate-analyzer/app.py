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

# ======================================================================
# 1. Flask 앱 설정 및 환경 변수 로드
# ======================================================================

load_dotenv() 

app = Flask(__name__)
# 세션 쿠키는 이제 사용하지 않으므로 secret_key가 필수적이지 않지만, 다른 확장을 위해 유지합니다.
app.secret_key = 'safesign_robust' 

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
    # ... (이미지 처리 코드는 기존과 동일) ...
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
        "deposit": r"보증금:\s*([\d,]+)원",
        "monthly_rent": r"월세:\s*([\d,]+)원",
        "maintenance_fee": r"관리비:\s*([\d,]+)원",
        "included_fees": r"관리비 포함항목:\s*\[(.*)\]",
        "lessor_name": r"임대인:\s*(?!계좌정보)(.*)",
        "lessee_name": r"임차인:\s*(.*)",
        "lessor_account": r"임대인 계좌정보:\s*(.*)"
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
    
    return summary

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
        if not enhanced_reg_path: raise Exception("등기부등본 이미지 처리 실패")
        reg_results = reader.readtext(enhanced_reg_path)
        reg_text = "\n".join([res[1] for res in reg_results])

        enhanced_con_path, _ = enhance_image_for_ocr(contract_path, f"enhanced_{contract_filename}")
        if not enhanced_con_path: raise Exception("계약서 이미지 처리 실패")
        con_results = reader.readtext(enhanced_con_path)
        con_text = "\n".join([res[1] for res in con_results])
        
        if not model: return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
            
        prompt = f"""
        당신은 대한민국 부동산 임대차 계약서와 등기부등본을 분석해 **요약 정보**와 **특약사항**을 구분하여 제공하는 AI 전문가입니다.
        아래 OCR 텍스트를 바탕으로, 지정된 형식에 맞춰 **요약 정보**와 **특약사항**을 정확히 추출해주세요.
        
        요약 형식:
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
        - (모든 특약 조항을 그대로 나열, 없으면 '특약사항 없음'으로 표기)

        --- OCR 텍스트 ---
        등기부등본 텍스트: {reg_text}
        계약서 텍스트: {con_text}
        ---
        """
        response = model.generate_content(prompt)
        full_corrected_text = response.text

        # ★★★ [구조 변경] Gemini가 생성한 텍스트를 '요약'과 '특약사항'으로 분리
        summary_part = ""
        clauses_part = "특약사항 없음" # 기본값
        
        split_keyword = "특약사항"
        if split_keyword in full_corrected_text:
            parts = full_corrected_text.split(split_keyword, 1)
            summary_part = parts[0].strip()
            clauses_part = (split_keyword + parts[1]).strip()
        else:
            summary_part = full_corrected_text.strip()
        
        # 분리된 텍스트를 각각 JSON으로 반환
        return jsonify({
            'summary_text': summary_part,
            'clauses_text': clauses_part
        })

    except Exception as e:
        print(f"OCR 처리 중 심각한 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500
    
    finally:
        if os.path.exists(register_path): os.remove(register_path)
        if os.path.exists(contract_path): os.remove(contract_path)
        if 'enhanced_reg_path' in locals() and os.path.exists(enhanced_reg_path): os.remove(enhanced_reg_path)
        if 'enhanced_con_path' in locals() and os.path.exists(enhanced_con_path): os.remove(enhanced_con_path)

# ======================================================================
# ★★★ [구조 변경] 모든 분석을 처리하는 새로운 단일 종합 엔드포인트 ★★★
# ======================================================================
@app.route('/process-analysis', methods=['POST'])
def process_analysis():
    data = request.get_json()
    summary_text = data.get('summary_text')
    clauses_text = data.get('clauses_text')

    if not summary_text:
        return jsonify({'error': '분석할 요약 내용이 없습니다.'}), 400

    # 1. 백엔드에서 텍스트 파싱
    parsed_data = parse_summary_from_text(summary_text)
    
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    # ★★★ 요청하신 모든 변수의 개별 로그를 확인하는 부분 ★★★
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    print("\n--- [종합 분석] 파싱된 모든 변수 개별 확인 시작 ---")
    
    # 등기부등본 요약
    print(f"✅ 소유주 이름: {parsed_data.get('owner_name')}, 타입: {type(parsed_data.get('owner_name'))}")
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
    
    # 2. 임대인-소유주 동일인 검증
    owner_name = parsed_data.get('owner_name')
    lessor_name = parsed_data.get('lessor_name')
    identity_verification = "확인 불가 (정보 부족)"
    if owner_name and lessor_name:
        identity_verification = "일치 ✅" if owner_name == lessor_name else f"불일치 ⚠️ (소유주: {owner_name}, 임대인: {lessor_name})"

    # 3. 특약사항 분석 (Gemini API 호출)
    clauses_analysis_result = "분석할 특약사항 없음"
    # ... (기존과 동일한 로직) ...
    if clauses_text and "특약사항 없음" not in clauses_text:
        if not model: return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
        try:
            prompt = f"""
            당신은 대한민국 부동산 법률 전문가입니다. 아래 특약사항을 '임차인'의 입장에서 분석하고, 잠재적 위험요소를 찾아 리포트를 작성해주세요.

            [특약사항 내용]
            {clauses_text}
            [/특약사항 내용]

            [분석 및 출력 가이드라인]
            1. **위험 조항 식별**: 임차인에게 불리한 조항을 모두 찾아내세요.
            2. **위험도 평가**: 각 위험 조항에 대해 '위험도: 높음', '위험도: 중간', '위험도: 낮음' 형식으로 명확하게 평가해주세요.
            3. **최종 요약 (가장 중요)**: "### 최종 요약" 제목으로, 가장 치명적인 위험 2~3개를 언급하며 최종 결론을 2문장 이내로 간결하게 요약해주세요.

            위 가이드라인에 따라 특약사항 분석 리포트를 작성해주세요.
            """
            response = model.generate_content(prompt)
            clauses_analysis_result = response.text
        except Exception as e:
            print(f"특약사항 분석 중 오류 발생: {e}")
            clauses_analysis_result = "특약사항 분석 중 오류가 발생했습니다."

    # 4. 시세 검증 (외부 API 호출) - 현재는 Mock(모의) 데이터로 구현
    price_verification = "시세 정보 확인 불가"
    contract_addr = parsed_data.get('contract_addr')
    deposit = parsed_data.get('deposit')
    if contract_addr and deposit:
        try:
            # 임시로 적어둔거에요 수정할때 주의부탁드립니다.
            # REAL_ESTATE_API_KEY = os.environ.get('REAL_ESTATE_API_KEY')
            # API_ENDPOINT = "https://실제.부동산.API/주소"
            # headers = {'Authorization': f'Bearer {REAL_ESTATE_API_KEY}'}
            # params = {'address': contract_addr}
            # response = requests.get(API_ENDPOINT, headers=headers, params=params)
            # response.raise_for_status()
            # market_price = response.json().get('average_deposit')
            
            # --- Mock(모의) 데이터 시작 ---
            market_price = deposit + 5000000 # 시세가 보증금보다 500만원 높다고 가정
            # --- Mock 데이터 끝 ---

            if deposit > market_price * 1.1:
                price_verification = f"주의 🟡: 보증금이 시세({market_price:,}원)보다 10% 이상 높습니다."
            elif deposit < market_price * 0.9:
                price_verification = f"양호 🟢: 보증금이 시세({market_price:,}원)보다 저렴합니다."
            else:
                price_verification = f"양호 🟢: 보증금이 시세({market_price:,}원) 수준입니다."
        except Exception as e:
            print(f"시세 조회 중 오류 발생: {e}")
            price_verification = "시세 정보를 가져오는 데 실패했습니다."

    # 5. 모든 결과를 종합하여 한번에 반환
    final_result = {
        "verifications": {
            "identity": identity_verification,
            "clauses": clauses_analysis_result,
            "price": price_verification
        }
    }
    
    return jsonify(final_result)


# ======================================================================
# 3. 앱 실행
# ======================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)