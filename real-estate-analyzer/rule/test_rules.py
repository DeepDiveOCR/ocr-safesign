from rule.rules import (
    check_owner_match,
    check_mortgage_risk,
    check_deposit_over_market,
    check_mortgage_vs_deposit
)

def test_all():
    # 1. 소유자-임대인 일치 테스트
    print("✅ [소유자-임대인 일치 테스트]")
    print(check_owner_match("홍길동", "홍길동"))
    print(check_owner_match("홍길동", "김철수"))
    print()

    # 2. 근저당 설정 테스트
    print("✅ [근저당 설정 테스트]")
    print(check_mortgage_risk(True, False))   # 위험
    print(check_mortgage_risk(True, True))    # 안전
    print(check_mortgage_risk(False, False))  # 안전
    print()

    # 3. 전세보증금 vs 시세 테스트
    print("✅ [보증금 시세 대비 테스트]")
    print(check_deposit_over_market(90000000, 100000000))  # 위험
    print(check_deposit_over_market(80000000, 100000000))  # 주의
    print(check_deposit_over_market(60000000, 100000000))  # 안전
    print()

    # 4. 보증금 vs 담보금액 테스트
    print("✅ [깡통전세 위험 테스트]")
    print(check_mortgage_vs_deposit(85000000, 100000000, 20000000))  # 안전
    print(check_mortgage_vs_deposit(90000000, 100000000, 15000000))  # 위험
    print()

if __name__ == "__main__":
    test_all()
