# # rules.py
import re
import requests
import os
#핵심정보 검증 로직
# ----------------------------------------------------
# 1-1. 주소 타입 감지 함수
# ----------------------------------------------------
def detect_address_type(address):
    #도로명 주소의 일반적인 패턴 (예: 강남대로 123)
    if re.search(r"(로|길|대로)\s?\d+", address):
        return "도로명"
    return "지번"

# ----------------------------------------------------
# 1-2. 주소 변환 함수 (도로명 -> 지번) /현재 타켓은 지번 -> 다 지번 주소로 통일
# ----------------------------------------------------
def unify_address(address, confm_key, target="지번"):
    print(f"\n[unify_address] 입력주소: {address}\n")
    addr_type = detect_address_type(address)
    print(f"감지된 주소 타입 : {addr_type}\n")

   # 이미 원하는 형식이면 그대로 반환
    if target == addr_type:
        print("이미 원하는 주소 형식입니다. 변환 생략!\n")
        return address

    print(f"{addr_type} - {target} 변환 요청 중..\n")

    # 공공주소 변환 API 요청 
    url = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
    params = {
        "confmKey": confm_key,
        "currentPage": 1,
        "countPerPage": 1,
        "keyword": address, #변환할 주소
        "resultType": "json"
    }
    res = requests.get(url, params=params)
    try:
        res.raise_for_status()
        results = res.json()
        # print(f"api 응답: {results}\n")
        juso = results['results']['juso']
        if not juso:
            print("변환된 주소가 없음\n")
            return None

        # 변환된 주소 반환 
        if target == "지번":
            print(f"✅ 변환된 지번 주소: {juso[0]['jibunAddr']}\n")
            return juso[0]['jibunAddr']
        elif target == "도로명":
            print(f"✅ 변환된 도로명 주소: {juso[0]['roadAddr']}\n")
            return juso[0]['roadAddr']
    except:
        return None

# ----------------------------------------------------
#  1-3. 주소 문자열 정규화 (공백/괄호 제거)
# ----------------------------------------------------
def normalize_address(addr: str) -> str:
    """주소 비교를 위한 전처리 함수 (공백, 괄호 등 제거)"""
    return addr.strip().replace(" ", "").replace("(", "").replace(")", "")

# ----------------------------------------------------
# 1-4. 주소에서 동/호수 추출
# ----------------------------------------------------
def extract_dong_ho(address: str):
    """주소에서 동/호수(예: 105동 1501호)를 추출"""
    match = re.findall(r"\d{1,3}동|\d{1,4}호", address)
    return " ".join(match) if match else ""

# ----------------------------------------------------
# 1-5. 주소 비교 (계약서 vs 등기부)
# ----------------------------------------------------
def compare_address(contract_addr, register_addr, confm_key):
    contract_norm = unify_address(contract_addr, confm_key, target="지번")
    register_norm = unify_address(register_addr, confm_key, target="지번")

    if not contract_norm or not register_norm:
        return {
            "is_risk": False,
            "grade": None,
            "type": "주소 일치 여부",
            "message": "📛 주소 변환 또는 정제에 실패했습니다.",
        }
    
    # 문자열 정규화(공백/괄호 제거) 후 비교
    contract_clean = normalize_address(contract_norm)
    register_clean = normalize_address(register_norm)

    # 동/호수 추출
    contract_dongho = extract_dong_ho(contract_addr)
    register_dongho = extract_dong_ho(register_addr)

    print(f"[비교용 주소] 계약서 주소: {contract_clean} + {contract_dongho}")
    print(f"[비교용 주소] 등기부 주소: {register_clean} + {register_dongho}")


     # 지번 주소 + 동/호수 모두 비교
    if contract_clean == register_clean and contract_dongho == register_dongho:
        return {
            "is_risk": False,
            "grade": "안전",
            "type": "주소 일치 여부",
            "message": "✅ 지번주소 또는 동/호수까지 모두 일치합니다.",
        }
    else:
        return {
            "is_risk": True,
            "grade": "위험",
            "type": "주소 일치 여부",
            "message": f"📛 주소 또는 동/호수 불일치\n계약서: {contract_norm} {contract_dongho}\n 등기부: {register_norm} {register_dongho}",
        }

# ----------------------------------------------------
# 2. 임대인-소유자 일치 여부 확인
# ----------------------------------------------------
def check_owner_match(owner_name, lessor_name):
    if not owner_name or not lessor_name:
        return {
            "is_risk": False,
            "grade" : None,
            "type" : "소유자-임대인 일치 여부",
            "message" : "소유자 또는 임대인 정보가 부족합니다.",
        }
    if owner_name == lessor_name:
        return {
            "is_risk" : False,
            "grade" : "안전",
            "type" : "소유자-임대인 일치 여부",
            "message" : f"소유자({owner_name})와 임대인({lessor_name})이 일치합니다."
        }
    
    return {
        "is_risk" : True,
        "grade" : "위험",
        "type" : "소유자-임대인 일치 여부",
        "message" : f"⚠️소유자({owner_name})와 임대인({lessor_name})이 일치하지 않습니다."
    }

# ----------------------------------------------------
# 3. 근저당권 설정 여부 판단
# ----------------------------------------------------
def check_mortgage_risk(has_mortgage, is_mortgage_cleared):
    if has_mortgage and not is_mortgage_cleared:
        return {
            "is_risk": True,
            "grade": "위험",
            "type" : "근저당",
            "message" : "근저당권이 설정되어 있고 말소되지 않았습니다.",
        }
    return {
        "is_risk": False,
        "grade" : "안전",
        "type" : "근저당",
        "message" : None, #근저당권이 없거나 말소된 경우 
    }

# ----------------------------------------------------
# 4-1. 전세보증금 / 매매가 비율 계산 및 등급화
# ----------------------------------------------------
# 전세보증금이 매매가 대비 어느 수준인지 판단하여 위험도 메세지 반환
# True : 위험 메세지 경고
# False : 안전 메세지 
# False, None : 판단할 정보 부족 
def check_deposit_over_market(deposit, market_price):
    if deposit is None or market_price is None:
        return {
            "is_risk": False,
            "grade": None,
            "message": "보증금 또는 시세 정보가 부족합니다.",
            "deposit": deposit,
            "market_price":market_price,
            "ratio":None,
        }
    ratio = deposit / market_price #전세가율 계산 (0.8 -> 80%)
    ratio_percent = round(ratio * 100, 1) #소수점 한 자리까지 표시 

    if ratio >= 0.9:
        grade = "위험"
        msg = "📛전세보증금이 매매가의 90% 이상입니다. \n 깡통 전세 가능성이 있는 위험 매물입니다."
        is_risk = True
    elif ratio >= 0.8:
        grade = "주의"
        msg = "⚠️전세보증금이 매매가의 80% 이상입니다. \n 주의가 필요합니다."
        is_risk = True
    elif ratio < 0.7:
        grade = "안전"
        msg = "✅전세보증금이 매매가의 70% 이하입니다. \n 상대적으로 안정적인 매물입니다."
        is_risk = False
    else:
        grade = None
        msg = None
        is_risk = False

    return{
        "is_risk": is_risk,
        "grade" : grade,
        "message" : msg,
        "deposit" : deposit,
        "market_price" : market_price,
        "ratio" : ratio_percent
    }

# ----------------------------------------------------
# 4-2. 근저당권 있을 경우 : (매매가 - 담보금액)보다 보증금이 큰지 확인
# ----------------------------------------------------
def check_mortgage_vs_deposit(deposit, market_price, mortgage_amount):
  
    if deposit is None or market_price is None or mortgage_amount is None:
        return {
            "is_risk": False,
            "grade": None,
            "message": "보증금, 시세 또는 담보금액 정보가 부족합니다.",
            "deposit": deposit,
            "market_price": market_price,
            "mortgage_amount": mortgage_amount,
        }

    remaining_value = market_price - mortgage_amount

    if deposit > remaining_value:
        return {
            "is_risk": True,
            "grade": "위험",
            "message": (
                f"📛 보증금이 회수 가능한 금액({remaining_value:,}원)를 초과합니다.\n"
                f"경매 시 보증금 전액 회수가 어려울 수 있어 깡통전세 위험이 높습니다."
            ),
            "deposit": deposit,
            "market_price": market_price,
            "mortgage_amount": mortgage_amount,
        }
    else: #보증금이 회수 가능한 금액 이내인 경우
        return {
            "is_risk": True,
            "grade": "주의",
            "message": (
                f"보증금이 회수 가능한 금액({remaining_value:,}원) 이내입니다.\n"
                f"깡통전세 가능성은 낮지만, 경매 절차 및 기타 변수에 따라 달라질 수 있으므로 주의가 필요합니다."
            ),
            "deposit": deposit,
            "market_price": market_price,
            "mortgage_amount": mortgage_amount,
        }
    
# ----------------------------------------------------
# 5-1. 등급을 점수로 매핑 (위험:5 / 주의:3 / 안전:1)
# ----------------------------------------------------
def map_grade_to_score(grade):
    if grade == "위험":
        return 5
    elif grade == "주의":
        return 3
    elif grade == "안전":
        return 1
    return None

# ----------------------------------------------------
# 5-2. 종합 위험도 판단 함수
# ----------------------------------------------------
# def determine_overall_risk(logic_results: dict) -> dict:
#     scores = []
#     risk_count = 0
#     caution_count = 0  # 주의 카운터
#     owner_mismatch_risk = False

#     for key, result in logic_results.items():
#         grade = result.get("grade")
#         if grade == "위험":
#             scores.append(5)
#             risk_count += 1

#             #임대인-소유자 불일치가 위험인 경우, 전체도 무조건 위험 처리
#             if result.get("type") == "소유자-임대인 일치 여부":
#                 owner_mismatch_risk = True

#         elif grade == "주의":
#             caution_count += 1
#             scores.append(3 + (caution_count - 1))  # 주의 누적 시 가중치 적용
#         elif grade == "안전":
#             scores.append(1)

#     if not scores:
#         return {
#             "overall_grade": "판단불가",
#             "avg_score": 0.0,
#             "risk_count": risk_count,
#             "caution_count": caution_count,
#             "scores": scores,
#         }
    
#     #강제 위험 조건 : 임대인- 소유자 불일치
#     if owner_mismatch_risk:
#         return{
#             "overall_grade": "위험",
#             "avg_score": sum(scores) / len(scores),
#             "risk_count" : risk_count,
#             "caution_count": caution_count,
#             "scores": scores,
#         }

#     # 위험 요소 2개 이상이면 무조건 위험
#     if risk_count >= 2:
#         return {
#             "overall_grade": "위험",
#             "avg_score": sum(scores) / len(scores),
#             "risk_count": risk_count,
#             "caution_count": caution_count,
#             "scores": scores,
#         }

#     avg_score = sum(scores) / len(scores)

#     if 1.0 <= avg_score <= 2.0:
#         grade = "안전"
#     elif avg_score <= 4.0:
#         grade = "주의"
#     else:
#         grade = "위험"

#     return {
#         "overall_grade": grade,
#         "avg_score": avg_score,
#         "risk_count": risk_count,
#         "caution_count": caution_count,
#         "scores": scores,
#     }





