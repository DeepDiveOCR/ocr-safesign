# # rules.py
# 1.임대인과 소유자 일치하는지 확인
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

# 2. 근저당권 설정 및 말소 여부 확인

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
        "grade" : None,
        "type" : "근저당",
        "message" : None,
    }

# 3. 전세보증금이 매매가 대비 어느 수준인지 판단하여 위험도 메세지 반환
# True >> 위험 메세지 경고
# False >> 안전 메세지 
# False, None >> 애매하거나 판단할 정보 부족 
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

# 근저당권이 잡혀 있고, 담보금액(채권최고액)이 존재할 때
# (보증금 > 매매가 - 담보금액) 이면, 깡통전세 위험 

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
    else:
        return {
            "is_risk": False,
            "grade": None,
            "message": None,
            "deposit": deposit,
            "market_price": market_price,
            "mortgage_amount": mortgage_amount,
        }


# # 6. 종합 판단 함수
# def evaluate_risk(
#     owner_name, lessor_name, deposit, market_price,
#     has_mortgage, is_mortgage_cleared, mortgage_amount,
#     contract_address, registry_address
# ):
#     checks = [
#         check_owner_match(owner_name, lessor_name),
#         check_mortgage_risk(has_mortgage, is_mortgage_cleared),
#         check_deposiot_over_market(deposit, market_price),
#         check_mortgage_vs_deposit(deposit, market_price, mortgage_amount),
#         check_contract_address_match(contract_address, registry_address),
#     ]

#     # 등급별 카운트
#     grades = [c["grade"] for c in checks if c["grade"]]
#     risk_count = grades.count("위험")
#     caution_count = grades.count("주의")

#     if risk_count >= 2:
#         overall_grade = "위험"
#     elif risk_count == 1 or caution_count >= 2:
#         overall_grade = "주의"
#     else:
#         overall_grade = "안전"

#     return {
#         "overall_grade": overall_grade,
#         "risk_count": risk_count,
#         "caution_count": caution_count,
#         "details": checks,
#         "messages": [c["message"] for c in checks if c["message"]],
#     }



