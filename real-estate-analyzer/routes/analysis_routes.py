import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from firebase_admin import firestore

# config.py에서 초기화된 전역 변수들을 가져옵니다.
from config import app, reader, model, db
# utils 폴더에서 필요한 함수들을 가져옵니다.
from utils.image_processor import enhance_image_for_ocr
from utils.text_parser import parse_summary_from_text

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/ocr', methods=['POST'])
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
        """
        response = model.generate_content(prompt)
        full_corrected_text = response.text

        summary_part = ""
        clauses_part = "특약사항 없음"
        
        split_keyword = "특약사항"
        if split_keyword in full_corrected_text:
            parts = full_corrected_text.split(split_keyword, 1)
            summary_part = parts[0].strip()
            clauses_part = (split_keyword + parts[1]).strip()
        else:
            summary_part = full_corrected_text.strip()
        
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

@analysis_bp.route('/process-analysis', methods=['POST'])
def process_analysis():
    data = request.get_json()
    summary_text = data.get('summary_text')
    clauses_text = data.get('clauses_text')
    uid = data.get('uid')

    if not summary_text:
        return jsonify({'error': '분석할 요약 내용이 없습니다.'}), 400
    if not uid:
        return jsonify({'error': '사용자 정보(UID)가 없습니다. 다시 로그인해주세요.'}), 401

    parsed_data = parse_summary_from_text(summary_text)
    
    print("\n--- [종합 분석] 파싱된 모든 변수 개별 확인 시작 ---")
    print(f"✅ UID: {uid}")
    print(f"✅ 소유주 이름: {parsed_data.get('owner_name')}")
    print("--- [종합 분석] 변수 개별 확인 종료 ---\n")
    
    owner_name = parsed_data.get('owner_name')
    lessor_name = parsed_data.get('lessor_name')
    identity_verification = "확인 불가 (정보 부족)"
    if owner_name and lessor_name:
        identity_verification = "일치 ✅" if owner_name == lessor_name else f"불일치 ⚠️ (소유주: {owner_name}, 임대인: {lessor_name})"

    clauses_analysis_result = "분석할 특약사항 없음"
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

    price_verification = "시세 정보 확인 불가"
    contract_addr = parsed_data.get('contract_addr')
    deposit = parsed_data.get('deposit')
    if contract_addr and deposit:
        try:
            market_price = deposit + 5000000
            if deposit > market_price * 1.1:
                price_verification = f"주의 🟡: 보증금이 시세({market_price:,}원)보다 10% 이상 높습니다."
            elif deposit < market_price * 0.9:
                price_verification = f"양호 🟢: 보증금이 시세({market_price:,}원)보다 저렴합니다."
            else:
                price_verification = f"양호 🟢: 보증금이 시세({market_price:,}원) 수준입니다."
        except Exception as e:
            print(f"시세 조회 중 오류 발생: {e}")
            price_verification = "시세 정보를 가져오는 데 실패했습니다."

    final_result = {
        "verifications": {
            "identity": identity_verification,
            "clauses": clauses_analysis_result,
            "price": price_verification
        }
    }
    
    try:
        analysis_data_to_save = {
            'userInput': parsed_data,
            'summaryText': summary_text,
            'clausesText': clauses_text,
            'analysisReport': final_result,
            'createdAt': firestore.SERVER_TIMESTAMP
        }
        db.collection('users').document(uid).collection('analyses').add(analysis_data_to_save)
        print(f"✅ Firestore에 분석 결과 저장 성공 (UID: {uid})")
    except Exception as e:
        print(f"🚨 Firestore 저장 실패: {e}")
    
    return jsonify(final_result)