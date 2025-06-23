# ======================================================================
# 1. 필요 라이브러리 설치 (터미널에서 최초 1회만 실행)
# ======================================================================
# pip install streamlit easyocr google-generativeai opencv-python-headless scikit-image pandas Pillow

# ======================================================================
# 2. 라이브러리 임포트
# ======================================================================
import streamlit as st
import os
import cv2
import numpy as np
import re
from PIL import Image
import easyocr 
import google.generativeai as genai
import io
import tempfile

# ======================================================================
# 3. 페이지 기본 설정 및 모델 로딩
# ======================================================================
st.set_page_config(
    page_title="AI 부동산 계약 분석 시스템",
    page_icon="🤖",
    layout="wide"
)

# --- AI 모델 로딩 (캐시 사용으로 재실행 시 속도 향상) ---
@st.cache_resource
def load_models():
    """EasyOCR 리더와 Gemini 모델을 로드합니다."""
    try:
        # 🚨 실제 실행 시, 발급받은 API 키를 여기에 입력하세요.
        # GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] # Streamlit 배포 시 권장
        GOOGLE_API_KEY = "AIzaSyAO-sexprR8YP8q69FZdvcFQ1d5llloL68" 
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        st.success("✅ Gemini API 설정 완료")
    except Exception as e:
        st.error(f"🚨 Gemini API 키 설정에 실패했습니다: {e}")
        model = None

    try:
        reader = easyocr.Reader(['ko','en'])
        st.success("✅ EasyOCR 모델 로드 완료 (최초 실행 시 다소 시간이 걸릴 수 있습니다)")
    except Exception as e:
        st.error(f"🚨 EasyOCR 모델 로드에 실패했습니다: {e}")
        reader = None

    return reader, model

reader, model = load_models()

# ======================================================================
# 4. 이미지 전처리, OCR, AI 교정 함수 (사용자 제공 코드 기반)
# ======================================================================
def enhance_image_for_ocr(image_path, title="이미지"):
    """이미지 경로를 받아 전처리를 수행합니다."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"이미지를 로드할 수 없습니다: {image_path}")
        
        st.write(f"✅ **{title}**: 이미지 로딩 및 전처리 시작...")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        rotated = img
        try:
            gray_inv = cv2.bitwise_not(gray)
            _, thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            coords = np.column_stack(np.where(thresh > 0))
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45: angle = -(90 + angle)
            else: angle = -angle
            
            if abs(angle) > 45:
                 st.warning(f"⚠️ **{title}**: 비정상적인 각도({angle:.2f}°)가 감지되어 회전을 건너뜁니다.")
            else:
                (h, w) = img.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        except Exception as e:
            st.warning(f"⚠️ **{title}**: 기울기 보정 중 오류 발생 (원본 사용): {e}")

        gray_rotated = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray_rotated, None, 10, 7, 21)
        final_img = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        return final_img, rotated
    except Exception as e:
        st.error(f"이미지 전처리 중 오류 발생: {e}")
        return None, None

def perform_ocr_and_correction(register_img_bytes, contract_img_bytes):
    """두 개의 이미지 바이트를 받아 전처리, OCR, AI 교정을 수행합니다."""
    
    full_ocr_text = ""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as fp:
        fp.write(register_img_bytes)
        register_path = fp.name
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as fp:
        fp.write(contract_img_bytes)
        contract_path = fp.name

    with st.expander("등기부등본 처리 과정 보기", expanded=True):
        enhanced_register, _ = enhance_image_for_ocr(register_path, "등기부등본")
        if enhanced_register is not None:
            st.image(enhanced_register, caption="전처리된 등기부등본")
            register_results = reader.readtext(enhanced_register, detail=0, paragraph=True)
            full_ocr_text += "[등기부등본 OCR 결과]\n" + "\n".join(register_results) + "\n\n"
            st.success("등기부등본 텍스트 추출 완료!")

    with st.expander("계약서 처리 과정 보기", expanded=True):
        enhanced_contract, _ = enhance_image_for_ocr(contract_path, "계약서")
        if enhanced_contract is not None:
            st.image(enhanced_contract, caption="전처리된 계약서")
            contract_results = reader.readtext(enhanced_contract, detail=0, paragraph=True)
            full_ocr_text += "[계약서 OCR 결과]\n" + "\n".join(contract_results)
            st.success("계약서 텍스트 추출 완료!")
    
    os.remove(register_path)
    os.remove(contract_path)

    if not model or not full_ocr_text:
        return "AI 모델 또는 OCR 결과가 없어 교정을 진행할 수 없습니다."

    st.info("3. Gemini AI로 최종 내용 교정 및 복원 중...")
    prompt = f"""
    당신은 OCR로 스캔한 문서의 텍스트를 교정하고 원본 형식으로 복원하는 전문가입니다.
    아래는 대한민국 부동산 서류의 OCR 스캔 결과입니다.
    이 텍스트에는 오타, 잘못 인식된 숫자, 빠진 글자들이 포함되어 있을 수 있습니다.

    다음 지침에 따라 텍스트를 완벽한 원본 계약서 형식으로 복원하고 내용을 교정해주세요:

    1. '원롭 토룹', '올' -> '원룸 투룸', '을' 과 같은 명백한 오타를 수정하세요.
    2. '3op00000원' -> '30,000,000원', '190 o0원' -> '190,000원' 처럼 잘못 인식된 숫자를 올바르게 수정하고, 세 자리마다 쉼표(,)를 넣어주세요.
    3. '202 년' -> '202' 뒤에 적절한 숫자를 문맥에 맞게 채워주세요 (예: 2023년).
    4. '제I조', '1. 부동산의 표시' 등과 같은 문서의 구조와 레이아웃을 최대한 원본과 가깝게 복원해주세요.
    5. 계약서의 모든 조항과 내용을 논리적으로 완성된 문장으로 만드세요.

    [주의]
    - 이미지에 없는 정보를 추측하거나 만들지 마십시오.
    - 개인정보(이름, 주민등록번호 등)를 절대로 "**" 등으로 마스킹하지 마십시오. 원본에 보이는 그대로 추출해야 합니다.

    --- OCR 원본 텍스트 ---
    {full_ocr_text}
    ---

    위 텍스트를 교정한 최종 계약서 내용을 아래에 작성해주세요:
    """
    try:
        response = model.generate_content(prompt)
        st.success("AI 교정 완료!")
        return response.text
    except Exception as e:
        st.error(f"Gemini API 호출 중 오류 발생: {e}")
        return "오류: AI 교정에 실패했습니다."

def parse_text_to_data(text):
    """UI의 텍스트를 다시 데이터 구조로 파싱합니다."""
    data = { "등기부등본": {}, "계약서": {} }
    try:
        lines = text.split('\n')
        current_section = None
        clauses_started = False
        clauses_text = []

        for line in lines:
            if line.strip() == '[등본]':
                current_section = '등본'
                clauses_started = False
                continue
            elif line.strip() == '[계약서]':
                current_section = '계약서'
                clauses_started = False
                continue
            
            if "약정 및 특약사항:" in line:
                clauses_started = True
                continue

            if clauses_started:
                clauses_text.append(line)
                continue

            if line.startswith('- '):
                key_val = line.split(':', 1)
                key = key_val[0][2:].strip()
                val = key_val[1].strip() if len(key_val) > 1 else ""

                if current_section == '등본':
                    if key == '표제부': data['등기부등본']['표제부'] = val
                    if key == '갑구': data['등기부등본']['갑구'] = val.replace('소유자 ', '')
                    if key == '을구': data['등기부등본']['을구'] = val
                elif current_section == '계약서':
                    if key == '소재지': data['계약서']['소재지'] = val
                    if key == '임대인': data['계약서']['임대인'] = val
                    if key == '임차인': data['계약서']['임차인'] = val
                    if key == '보증금': data['계약서']['보증금'] = int("".join(filter(str.isdigit, val))) if val else 0
        
        data['계약서']['약정 및 특약사항'] = "\n".join(clauses_text)
    except Exception as e:
        st.error(f"수정된 텍스트를 분석하는 중 오류 발생: {e}")
    return data

def run_analysis(data):
    """추출된 데이터를 기반으로 위험 요소를 분석합니다."""
    messages = []
    special_clauses = []
    level = "safe"

    owner = data.get("등기부등본", {}).get("갑구", "")
    landlord = data.get("계약서", {}).get("임대인", "")
    deposit = data.get("계약서", {}).get("보증금", 0)
    
    reg_addr = data.get("등기부등본", {}).get("표제부", "")
    con_addr = data.get("계약서", {}).get("소재지", "")
    if reg_addr and con_addr and reg_addr.split(' ')[0] != con_addr.split(' ')[0]:
        level = "danger"
        messages.append(("🚨 주소 불일치", f"등본 주소({reg_addr})와 계약서 주소({con_addr})가 다릅니다. 서류를 다시 확인하세요."))

    if owner and landlord and owner != landlord:
        level = "danger"
        messages.append(("🚨 소유자 불일치", f"등기부상 소유자({owner})와 계약서상 임대인({landlord})이 다릅니다. 계약 권한 확인이 필수입니다."))
    
    debt_str = data.get("등기부등본", {}).get("을구", "")
    debt_match = re.findall(r'\d[\d,]*', debt_str) 
    debt = int(debt_match[0].replace(",", "")) if debt_match else 0

    if debt > 0 and deposit > 0:
        market_price = deposit / 0.7
        total_debt_ratio = (deposit + debt) / market_price
        if total_debt_ratio > 0.8:
            level = "danger"
            messages.append(("🚨 과도한 선순위 채권", f"총부채 비율이 {total_debt_ratio:.1%}로, '깡통전세' 위험이 매우 높습니다."))
        elif total_debt_ratio > 0.7:
            if level != "danger": level = "caution"
            messages.append(("⚠️ 높은 선순위 채권", f"총부채 비율이 {total_debt_ratio:.1%}로, 주의가 필요합니다."))

    clauses = data.get("계약서", {}).get("약정 및 특약사항", "")
    if "추가 대출" in clauses or "담보로" in clauses:
        level = "danger"
        special_clauses.append(("🚨 매우 위험한 추가 담보 조항", "계약 후 임대인이 추가 대출을 받을 수 있도록 허용하는 독소 조항입니다."))
    if "모든 수리" in clauses or "임차인이 부담" in clauses and "기본적인 수선" not in clauses:
        if level != "danger": level = "caution"
        special_clauses.append(("⚠️ 과도한 수리비 부담 조항", "민법상 주요 설비 수리 의무는 임대인에게 있으나, 모든 수리를 임차인에게 전가할 수 있습니다."))

    return {"level": level, "messages": messages, "special_clauses": special_clauses}


# ======================================================================
# 5. Streamlit UI 및 메인 로직
# ======================================================================

st.title("🤖 AI 부동산 계약 분석 시스템")
st.markdown("임대차 계약서와 등기부등본을 업로드하여 전세사기 위험도를 탐지하세요.")
st.markdown("---")

if 'app_stage' not in st.session_state:
    st.session_state.app_stage = 'initial'
    st.session_state.ocr_text = ""
    st.session_state.report = None

left_column, right_column = st.columns(2)

with left_column:
    st.subheader("1. 서류 업로드")
    
    register_file = st.file_uploader("등기부등본", type=['png', 'jpg', 'jpeg'], key="register")
    contract_file = st.file_uploader("전세계약서", type=['png', 'jpg', 'jpeg'], key="contract")

    if st.button("분석 실행", type="primary", use_container_width=True, disabled=(not register_file or not contract_file)):
        st.session_state.app_stage = 'processing'
        st.rerun()

if st.session_state.app_stage == 'processing':
    with st.spinner("이미지 전처리 및 AI 분석을 시작합니다..."):
        register_bytes = register_file.getvalue()
        contract_bytes = contract_file.getvalue()
        st.session_state.ocr_text = perform_ocr_and_correction(register_bytes, contract_bytes)
        st.session_state.app_stage = 'done'
        st.rerun()

if st.session_state.app_stage == 'done':
    with left_column:
        st.subheader("2. AI 보정 결과 (수정 가능)")
        # ✨ 오류 수정: 위젯이 스스로 상태를 관리하도록 하고, 초기값만 세션 상태에서 가져옵니다.
        st.text_area("분석된 텍스트", value=st.session_state.ocr_text, height=400, key="edited_text")

    with right_column:
        st.subheader("3. 위험 요소 분석 리포트")
        
        # 'edited_text' 가 변경될 수 있으므로, 항상 최신 값을 사용합니다.
        final_data_to_analyze = parse_text_to_data(st.session_state.edited_text)
        
        if st.button("최종 분석 리포트 보기", use_container_width=True):
             with st.spinner("수정된 내용을 바탕으로 최종 분석을 진행합니다..."):
                st.session_state.report = run_analysis(final_data_to_analyze)
        
        if st.session_state.report:
            report = st.session_state.report
            
            if report['level'] == 'danger':
                st.error(f"**종합 위험도: 위험** - 보증금 미반환 위험이 매우 높은 고위험 계약입니다.")
            elif report['level'] == 'caution':
                st.warning(f"**종합 위험도: 주의** - 계약 전 반드시 확인해야 할 사항이 있습니다.")
            else:
                st.success(f"**종합 위험도: 안전** - 현재까지 발견된 특이사항은 없습니다.")

            if report.get("messages"):
                st.markdown("**핵심 권리관계 분석**")
                for title, text in report["messages"]:
                    st.info(f"**{title}**: {text}")
                    
            if report.get("special_clauses"):
                st.markdown("**🚨 주요 특약사항 분석**")
                for title, text in report["special_clauses"]:
                    st.warning(f"**{title}**: {text}")
        else:
            st.info("왼쪽 텍스트를 확인/수정한 후 '최종 분석 리포트 보기' 버튼을 눌러주세요.")
