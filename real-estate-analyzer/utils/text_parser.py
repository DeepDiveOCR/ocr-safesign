import re

def parse_summary_from_text(text):
    """
    입력된 요약 텍스트 전체를 파싱하여 딕셔너리로 반환합니다. (최종 수정 버전)
    """
    summary = {}

    # 1. (핵심) "계약내용 및"을 기준으로 파싱할 텍스트를 미리 잘라냅니다.
    #    이후 모든 파싱은 잘라낸 텍스트 안에서만 이루어지므로 안전합니다.
    parsing_text = text
    markers = ["특약사항", "계약내용 및"]
    for marker in markers:
        cutoff_index = text.find(marker)
        if cutoff_index != -1:
            parsing_text = text[:cutoff_index]
            break

    def extract_value(pattern, txt):
        match = re.search(pattern, txt, re.MULTILINE)
        return match.group(1).strip() if match else None

    # 2. 유연한 정규식 패턴을 사용합니다.
    patterns = {
        "owner_name": r"현재 소유자:\s*(.*)",
        "has_mortgage": r"근저당권:\s*(.*)",
        "mortgage_amount": r"채권최고액:\s*(.*)",
        "is_mortgage_cleared": r"말소 여부:\s*(.*)",
        "other_register_info": r"기타 등기사항:\s*(.*)",
        "contract_date": r"계약일:\s*(\d{4}-\d{2}-\d{2})",
        "total_area": r"면적:\s*(.*)",
        "lease_period": r"임대차 기간:\s*(.*)",
        "handover_date": r"명도일:\s*(\d{4}-\d{2}-\d{2})",
        "contract_addr": r"계약주소:\s*(.*)",
        "register_addr": r"등기부등본 주소:\s*(.*)",
        "deposit": r"보증금:\s*(.*)",
        "monthly_rent": r"월세:\s*(.*)",
        "maintenance_fee": r"관리비:\s*(.*)",
        "included_fees": r"관리비 포함항목:\s*(.*)",
        "lessor_name": r"임대인:\s*(?!계좌정보)(.*)",
        "lessee_name": r"임차인:\s*(.*)",
        "lessor_account": r"임대인 계좌정보:\s*(.*)",
        "lessee_account": r"임차인 계좌정보:\s*(.*)",
        "building_type": r"건물유형:\s*(.*)"
    }

    # 잘라낸 'parsing_text'를 대상으로만 값을 추출합니다.
    for key, pattern in patterns.items():
        summary[key] = extract_value(pattern, parsing_text)

    # 면적 단위 변환 (항상 평 단위로 저장)
    if summary.get("total_area"):
        area_str = str(summary["total_area"])
        # 숫자와 단위 분리 (㎡, m2, 제곱미터, 평, py, pyeong 등 모두 인식)
        area_match = re.match(r"([\d\.]+)\s*(㎡|m2|제곱미터|평|py|pyeong)?", area_str, re.IGNORECASE)
        if area_match:
            area_value = float(area_match.group(1))
            area_unit = area_match.group(2)
            if area_unit and area_unit.strip() in ["㎡", "m2", "제곱미터"]:
                summary["total_area"] = round(area_value / 3.305785, 2)  # 1평 = 3.305785㎡
            else:
                # 평, py, pyeong, 단위 없음 등은 평으로 간주
                summary["total_area"] = round(area_value, 2)
        else:
            summary["total_area"] = 0

    # 3. 강화된 후처리 로직으로 데이터를 정확하게 정리합니다.
    if summary.get("has_mortgage"):
        summary["has_mortgage"] = "있음" in summary["has_mortgage"] and "없음" not in summary["has_mortgage"]
    if summary.get("is_mortgage_cleared"):
        summary["is_mortgage_cleared"] = "말소" in summary["is_mortgage_cleared"]

    # 금액 관련 필드 처리 (문자열에서 숫자만 정확히 추출)
    for key in ["mortgage_amount", "deposit", "monthly_rent", "maintenance_fee"]:
        value_str = summary.get(key)
        if value_str:
            numeric_match = re.search(r'([\d,]+)', value_str)
            if numeric_match:
                try:
                    summary[key] = int(numeric_match.group(1).replace(',', ''))
                except (ValueError, TypeError):
                    summary[key] = 0
            else: # 숫자 부분이 아예 없는 경우 (예: "정보 없음")
                summary[key] = 0
        else: # 키 자체가 없는 경우
             summary[key] = 0

    if summary.get("lease_period"):
        parts = summary["lease_period"].split('~')
        if len(parts) == 2:
            summary["lease_period"] = (parts[0].strip(), parts[1].strip())
            
    if summary.get("included_fees"):
        # "정보 없음" 등의 텍스트를 고려하여 처리
        if '정보' in summary["included_fees"] or not summary["included_fees"]:
            summary["included_fees"] = []
        else:
            summary["included_fees"] = [fee.strip() for fee in summary["included_fees"].split(',')]

    # 특약사항 부분은 원본 텍스트 전체에서 다시 찾아 저장합니다.
    clause_block_match = re.search(r"(특약사항|계약내용 및)[\s\S]*", text)
    if clause_block_match:
        summary["clauses"] = clause_block_match.group(0).strip()
    else:
        summary["clauses"] = "특약사항 없음"
        
    # 기존 코드와의 호환성을 위해 'clauses_raw', 'clauses_cleaned' 유지
    summary["clauses_raw"] = summary["clauses"]
    summary["clauses_cleaned"] = summary["clauses"]
        
    return summary