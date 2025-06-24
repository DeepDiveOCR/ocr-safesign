import re

def parse_summary_from_text(text):
    """입력된 요약 텍스트 전체를 파싱하여 딕셔너리로 반환합니다."""
    summary = {}
    
    def extract_value(pattern, txt):
        match = re.search(pattern, txt, re.MULTILINE)
        return match.group(1).strip() if match else None

    patterns = {
        "owner_name": r"현재 소유자:\s*(.*)", "has_mortgage": r"근저당권:\s*(.*)",
        "mortgage_amount": r"채권최고액:\s*([\d,]+)원", "is_mortgage_cleared": r"말소 여부:\s*(.*)",
        "other_register_info": r"기타 등기사항:\s*(.*)", "contract_date": r"계약일:\s*(\d{4}-\d{2}-\d{2})",
        "lease_period": r"임대차 기간:\s*(.*)", "handover_date": r"명도일:\s*(\d{4}-\d{2}-\d{2})",
        "contract_addr": r"계약주소:\s*(.*)", "register_addr": r"등기부등본 주소:\s*(.*)",
        "deposit": r"보증금:\s*([\d,]+)원", "monthly_rent": r"월세:\s*([\d,]+)원",
        "maintenance_fee": r"관리비:\s*([\d,]+)원", "included_fees": r"관리비 포함항목:\s*\[(.*)\]",
        "lessor_name": r"임대인:\s*(?!계좌정보)(.*)", "lessee_name": r"임차인:\s*(.*)",
        "lessor_account": r"임대인 계좌정보:\s*(.*)"
    }

    for key, pattern in patterns.items():
        summary[key] = extract_value(pattern, text)

    # 데이터 후처리 (문자열 -> 숫자/bool/리스트 등)
    if summary.get("has_mortgage"): summary["has_mortgage"] = "있음" in summary["has_mortgage"]
    if summary.get("is_mortgage_cleared"): summary["is_mortgage_cleared"] = "말소됨" in summary["is_mortgage_cleared"]
    for key in ["mortgage_amount", "deposit", "monthly_rent", "maintenance_fee"]:
        if summary.get(key):
            try: summary[key] = int(summary[key].replace(',', ''))
            except (ValueError, TypeError): summary[key] = 0
    if summary.get("lease_period"):
        parts = summary["lease_period"].split('~')
        if len(parts) == 2: summary["lease_period"] = (parts[0].strip(), parts[1].strip())
    if summary.get("included_fees"): summary["included_fees"] = [fee.strip() for fee in summary["included_fees"].split(',')]
    
    return summary
