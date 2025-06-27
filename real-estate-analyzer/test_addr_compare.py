from rule.rules import compare_address
from dotenv import load_dotenv
import os


print("현재 파일 위치:", os.getcwd())
# .env 파일에서 CONFIRM_KEY 불러오기
load_dotenv()
confm_key = os.getenv("CONFIRM_KEY")

print("CONFIRM_KEY:", confm_key)

# 테스트용 주소 입력
contract_addr = "경기 평택시 상서재로5길 15 101동 501호"
register_addr = "경기 평택시 상서재로5길 15 101동 501호"

# compare_address 함수 실행
result = compare_address(contract_addr, register_addr, confm_key)

# 결과 출력
print("📍주소 비교 결과📍:")
print(result)
for key, value in result.items():
    print(f"{key}: {value}")


