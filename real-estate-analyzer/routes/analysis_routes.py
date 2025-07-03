import os
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template # type: ignore
from werkzeug.utils import secure_filename # type: ignore
from bs4 import BeautifulSoup # type: ignore
from firebase_admin import auth, firestore # type: ignore


# 설정 및 유틸리티 함수 임포트
from config import app, reader, model, db, confm_key
from utils.image_processor import enhance_image_for_ocr
from utils.text_parser import parse_summary_from_text
from rule.rules import check_owner_match, check_mortgage_risk, check_deposit_over_market, check_mortgage_vs_deposit, compare_address
from estimator.median_price import estimate_median_trade

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/')
def index():
    return render_template('index.html')

@analysis_bp.route('/ocr', methods=['POST'])
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

        # 프롬프트
        prompt = f"""
        당신은 대한민국 부동산 임대차 계약서와 등기부등본을 분석해 **요약 정보**와 **계약내용 및 특약사항**을 구분하여 제공하는 AI 전문가입니다.
        아래 OCR 텍스트를 바탕으로, 지정된 형식에 맞춰 **요약 정보**와 **계약내용 및 특약사항**을 정확히 추출해주세요.
        등기부등본 주소는 도로명 또는 지번 주소만 포함하고 동은 제외합니다.
        예를 들어 서울특별시 서초구 서초대로 46길 60, 101동 201호(서초동, 서초아파트) 일 경우 서울특별시 서초구 서초대로 46길 60 로 표기합니다.
        주어진 형식에서 정보를 추가하거나 ()로 묶어서 추정하지 마세요.
        만약 주소가 서울특별시 서초구 서초대로 46길 60 와 같이 온전한 형식이 아닌, 진해구 이동 649-12 와 같은 축약형일 경우 정규화 시켜주세요
        
        요약 형식:

        --- 등기부등본 요약 ---
        - 등기부등본 주소: xxx도 xxx시 xxx구 xx동 xx-xx (도로명 또는 지번 주소만 동과 호수는 제외)
        - 현재 소유자: OOO
        - 근저당권: [설정 있음 / 없음]
        - 채권최고액: XX,XXX,XXX원
        - 말소 여부: [말소됨 / 유지]

        --- 계약서 요약 ---
        계약 기본정보
        - 계약주소: xxx도 xxx시 xxx구 xx동 xx-xx (도로명 또는 지번 주소만 동과 호수는 제외)
        - 계약일: YYYY-MM-DD
        - 임대차 기간: YYYY-MM-DD ~ YYYY-MM-DD
        - 명도일: YYYY-MM-DD
        - 면적: XX ㎡ 인지 평 인지 표기기

        금전 조건
        - 보증금: X,XXX,XXX원 ([한글 보증금])
        - 월세: XX,XXX원 ([한글 월세])
        - 관리비: XX,XXX원 ([한글 관리비])
        - 관리비 포함항목: [인터넷, 전기, 수도 등]

        임차인/임대인 정보
        - 임대인: 성명
        - 임대인 계좌정보: 은행명 / 계좌번호
        - 임차인: 성명 

        계약내용 및 특약사항
        - 계약내용
        제 1조: [계약내용]
        제 2조: [계약내용]
        등등...
        --- OCR 텍스트 ---
        등기부등본 텍스트: {reg_text}
        계약서 텍스트: {con_text}
        ---
        """

        # [최종 분석]
        # - 아래 문단은 최종 분석을 포함하는 매우 중요한 항목입니다.
        # - 이 항목은 절대 생략하지 말고 반드시 작성해야 합니다.
        # - 누락되면 전체 응답이 무효 처리됩니다.
        # - 아래의 지시를 반드시 따르세요.
        # - 점수 기준에 따라 '위험', '주의', '안전' 중 하나로 최종 등급을 판단하세요.
        # - 등급 판단 사유를 자연스럽고 신뢰도 있게 설명하는 문장으로 서술해 주세요.
        # - 최종 분석 항목으로, 전체 계약서를 종합적으로 평가한 결과를 서술해 주세요.

        response = model.generate_content(prompt)
        # 🔍 Gemini 응답 전체 확인
        print("🔍 Gemini 응답 전체:\n", response.text)
        full_corrected_text = response.text

        # ★★★ [구조 변경] Gemini가 생성한 텍스트를 '요약'과 '특약사항'과 '최종 분석 '으로 분리
        split_keyword = "계약내용 및 특약사항"
        if split_keyword in full_corrected_text:
            parts = full_corrected_text.split(split_keyword, 1)
            summary_part = parts[0].strip()
            clauses_part = (split_keyword + parts[1]).strip()
        else:
            summary_part = full_corrected_text.strip()
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

@analysis_bp.route('/process-analysis', methods=['POST'])
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
    print(f"✅ 면적: {parsed_data.get('total_area')}, 타입: {type(parsed_data.get('total_area'))}")

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

    market_price = None
    
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
        total_area = parsed_data.get("total_area")

        # === 위험 요소 판단 ===
        # --- 임대인-소유주 일치 메시지 생성 부분 확인용 ---
        if owner_name and lessor_name:
            import re
            def extract_name_only(text):
                # Remove any parenthesized content
                cleaned = re.sub(r'\s*\(.*?\)', '', text).strip()
                # Keep only the part before the first comma
                return cleaned.split(',')[0].strip()
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
                final_deposit = deposit / total_area
                print(f"final_deposit: {final_deposit}")
                logic_results['시세 대비 보증금 위험'] = check_deposit_over_market(final_deposit, market_price)

            if deposit and mortgage_amount:
                logic_results['보증금 대비 채권최고액 위험'] = check_mortgage_vs_deposit(final_deposit, market_price, mortgage_amount)

        except Exception as e:
            print("❌ 거래 시세 예측 실패:", e)
            market_price = None
            market_basis = "시세 예측 실패"
            # 실패시 프론트엔드에 경고 출력 필
            # logic_results['시세 예측 실패'] = {
            #     "grade": "경고",
            #     "message": f"거래 시세 예측에 실패했습니다: {str(e)}"
            # }

        # # === 결과 포맷 정리 ===
        print(f"market_price: {market_price}")
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

    # 3. 특약사항 분석 및 최종 코멘트 생성
    clauses_analysis_result = "분석할 특약사항 없음"
    if clauses_text and "특약사항 없음" not in clauses_text:
        if not model: return jsonify({'error': 'Gemini API가 초기화되지 않았습니다.'}), 500
        try:
            prompt = f"""
            당신은 대한민국 부동산 계약의 법률 전문가입니다.
            아래 '특약사항 텍스트'를 임차인의 입장에서 분석하되, 위험 판단은 객관적인 사실과 조문 해석에 기반하여 균형 잡힌 어조로 작성해주세요. 과도하게 높은 위험 등급 표시는 자제하고, 실제로 분쟁 가능성이 있는 부분만 명확하게 지적해 주세요.

            1. 특약사항 위험 분석 (HTML 카드)
            - 제공된 텍스트의 각 조항을 분석하여, 결과를 아래 예시 같은 HTML 카드 형식으로만 출력합니다.
            - 카드 외 다른 텍스트(인사말, 서론, 요약)는 포함하지 마세요.
            - 위험도 클래스는 `risk-high`(위험), `risk-medium`(주의), `risk-low`(낮음) 세 가지를 사용합니다.
            [HTML 카드 예시]
            <div class="risk-card">
            <div class="risk-title"><b>1.</b> 조항 내용...</div>
            <div class="risk-badge risk-high">🚨 위험</div>
            <div class="risk-desc">위험 설명 및 조치 제안...</div>
            </div>

            2. 최종 코멘트 (마무리 멘트)
            - 분석 내용을 바탕으로 객관적이고 간결한 어투로 2~3문장 의견을 작성하세요.
            - 과도한 경고를 피하고, 실제로 조치가 필요한 부분만 강조해 주세요.
            - 반드시 `### 최종 코멘트` 제목으로 시작합니다.

            [분석할 특약사항 텍스트]
            {clauses_text}
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
    medium_count = 0
    for g in grade_list:  # grade_list는 고정 검증 및 특약 분석에서 추출된 등급 문자열 리스트
        if g == '안전':
            grade_points.append(1)
        elif g == '주의':
            medium_count += 1
            grade_points.append(2 + medium_count)
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
        # 프론트엔드에서 기록을 불러올 때 필요한 모든 정보를 포함하도록 구조 변경
        analysis_data_to_save = {
           'userInput': {
                # 파싱된 데이터에서 계약 주소를 가져와 저장합니다.
                'contract_addr': parsed_data.get('contract_addr', '주소 정보 없음') 
            },
            'summaryText': summary_text,      # 사용자가 확인/수정한 요약 원본 텍스트
            'clausesText': clauses_text,      # ★★★[수정] 이 부분의 주석을 해제하여 특약사항 텍스트도 저장합니다.
            'analysisReport': clauses_analysis_html,   # AI가 생성한 최종 카드형 HTML 보고서 저장
            'createdAt': firestore.SERVER_TIMESTAMP, # 분석 시간 # type: ignore
            'parsedData': parsed_data
        }
        # users/{uid}/analyses 컬렉션에 새로운 문서 추가
        db.collection('users').document(uid).collection('analyses').add(analysis_data_to_save)
        print(f"✅ Firestore에 분석 결과 저장 성공 (UID: {uid})")
        
        # 저장되는 데이터 구조를 디버깅용으로 확인
        print(f"💾 저장된 데이터: {analysis_data_to_save}") 

    except Exception as e:
        print(f"🚨 Firestore 저장 실패: {e}")
        # 저장에 실패하더라도 사용자에게는 분석 결과를 보여줘야 하므로, 에러를 반환하지 않고 계속 진행합니다.

    # 6. 최종 결과를 프론트엔드에 반환
    # analysis_result dict에 final_risk_level도 추가 (호환성)
    analysis_result = final_result
    if "verifications" in analysis_result:
        analysis_result["verifications"]["final_risk_level"] = final_grade
    return jsonify(final_result)
