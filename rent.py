import requests
import pandas as pd
import numpy as np
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta

# 주소 파싱
def parse_address(address):
    tokens = address.strip().split()
    gu_index = next((i for i, t in enumerate(tokens) if t.endswith("구") or t.endswith("군")), None)
    region_name = " ".join(tokens[:gu_index + 1])
    umdNm = tokens[gu_index + 1]
    jibun = tokens[gu_index + 2]
    return region_name, umdNm, jibun

# 법정동 코드 조회
def get_region_prefix(region_name):
    url = "http://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
    params = {
        'ServiceKey': "7vMdnzTpnFnBO5wPN3LkHyPgPNFu3A/w/+RH8EJw3ihZfuhA5UiMx4x/PYl1qjlCx1VAzTL+i2GJXf1c/oHfyg==",
        'type': 'json',
        'pageNo': '1',
        'numOfRows': '1000',
        'flag': 'Y',
        'locatadd_nm': region_name
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        stanregin = data.get('StanReginCd', [])
        for item in stanregin:
            if 'row' in item:
                for entry in item['row']:
                    if entry.get('locatadd_nm') == region_name:
                        return entry['region_cd'][:5]
    print("❌ 법정동 코드 조회 실패")
    return None

# 건물 유형별 API URL
def get_trade_api_url(building_type):
    mapping = {
        "아파트": "AptRent",
        "오피스텔": "OffiRent",
        "다세대": "RHRent",
        "연립": "RHRent"
    }
    api_type = mapping.get(building_type)
    if api_type:
        return f"https://apis.data.go.kr/1613000/RTMSDataSvc{api_type}/getRTMSDataSvc{api_type}"
    else:
        print(f"❌ 건물 유형 '{building_type}' 은 지원되지 않습니다.")
        return None

# API 데이터 수집
def get_trade_deals(lawd_cd, target_dong, target_jibun, building_type, yyyymm):
    url = get_trade_api_url(building_type)
    if not url:
        return pd.DataFrame()

    all_data = []
    page = 1

    while True:
        params = {
            "serviceKey": "7vMdnzTpnFnBO5wPN3LkHyPgPNFu3A/w/+RH8EJw3ihZfuhA5UiMx4x/PYl1qjlCx1VAzTL+i2GJXf1c/oHfyg==",
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": yyyymm,
            "numOfRows": "1000",
            "pageNo": str(page)
        }
        try:
            response = requests.get(url, params=params)
            root = ET.fromstring(response.content)
            items = list(root.iter("item"))
            if not items:
                break
            for item in items:
                dong = item.findtext("umdNm", "").strip()
                jibun = item.findtext("jibun", "").strip()
                if dong != target_dong or jibun != target_jibun:
                    continue

                deposit_raw = item.findtext("deposit", "").replace(",", "").strip()
                monthly_rent_raw = item.findtext("monthlyRent", "").replace(",", "").strip()
                area_raw = item.findtext("excluUseAr", "").strip()
                year = item.findtext("dealYear", "")
                month = item.findtext("dealMonth", "")
                day = item.findtext("dealDay", "")

                if not (deposit_raw and area_raw and year and month and day):
                    continue

                deposit = int(deposit_raw) * 10000
                monthly_rent = int(monthly_rent_raw) * 10000 if monthly_rent_raw else 0
                area = float(area_raw)
                date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                # 전세 조건: 보증금 > 0 + 월세 = 0
                if deposit > 0 and monthly_rent == 0:
                    all_data.append({
                        "보증금": deposit,
                        "전용면적": area,
                        "계약일": date
                    })
            page += 1
        except Exception as e:
            print(f"❌ API 오류 (page {page}): {e}")
            break
    return pd.DataFrame(all_data)

# 시세 추정
def estimate_price(lawd_cd, target_dong, target_jibun, target_area, building_type):
    all_df = pd.DataFrame()
    today = datetime.today()

    for year_offset in range(1, 6):  # 1년 ~ 5년까지 점진적 확대
        month_list = [
            (today - timedelta(days=30 * i)).strftime("%Y%m")
            for i in range(year_offset * 12)
        ]

        for yyyymm in month_list:
            new_df = get_trade_deals(lawd_cd, target_dong, target_jibun, building_type, yyyymm=yyyymm)
            if not new_df.empty:
                all_df = pd.concat([all_df, new_df], ignore_index=True).drop_duplicates()

        if len(all_df) >= 5:
            break

    if all_df.empty:
        print("❌ 거래 데이터가 존재하지 않습니다.")
        return None, None, "데이터 부족"

    # 공통 처리
    all_df["계약일"] = pd.to_datetime(all_df["계약일"])
    all_df["㎡당가격"] = all_df["보증금"] / all_df["전용면적"]
    all_df["개월수"] = (today.year - all_df["계약일"].dt.year) * 12 + (today.month - all_df["계약일"].dt.month)
    all_df["가중치"] = np.exp(-0.02 * all_df["개월수"])

    # 유사 평형 필터
    filtered_df = all_df[
        (all_df["전용면적"] >= target_area - 3) &
        (all_df["전용면적"] <= target_area + 3)
    ]
    target_df = filtered_df if len(filtered_df) >= 3 else all_df

    # 중앙값 계산
    median_price = round(target_df["㎡당가격"].median())

    msg = f"{year_offset}년 데이터 ({'유사 평형' if len(filtered_df) >= 3 else '전체'})"
    return all_df, median_price, msg

# 실행 예시
address = "서울특별시 관악구 봉천동 1566-10"
building_type = "오피스텔"
target_area = 15

region, dong, jibun = parse_address(address)
lawd_cd = get_region_prefix(region)

if lawd_cd:
    all_df, median, info = estimate_price(lawd_cd, dong, jibun, target_area, building_type)
    if median:
        print(f"\n✅ {info}")
        print(f"중앙값 시세: {median:,} 원/㎡")
    else:
        print("⚠️ 시세 추정 불가")
else:
    print("⚠️ 법정동 코드 조회 실패")



# 최근 거래 기록 중 이상치 탐지
def detect_outlier_transactions(all_df, median_price, target_area, area_tolerance=3, threshold_ratio=0.3):
    all_df["계약일"] = pd.to_datetime(all_df["계약일"])

    # 유사 평형 데이터 필터
    similar_df = all_df[
        (all_df["전용면적"] >= target_area - area_tolerance) &
        (all_df["전용면적"] <= target_area + area_tolerance)
    ].copy()

    if similar_df.empty:
        print("⚠️ 유사 평형 데이터가 없습니다. 전체 데이터로 탐지 불가.")
        return pd.DataFrame()

    # 중앙값 대비 차이 비율 계산
    similar_df["중앙값_차이비율"] = abs(similar_df["㎡당가격"] - median_price) / median_price

    # 이상 거래 탐지
    outliers = similar_df[similar_df["중앙값_차이비율"] > threshold_ratio]
    if not outliers.empty:
        print(f"\n⚠️ 유사 평형({target_area}±{area_tolerance}㎡) 거래 중 중앙값 대비 {int(threshold_ratio*100)}% 이상 차이 나는 거래 {len(outliers)}건 발견!")
        for _, row in outliers.iterrows():
            print(f" - {row['계약일'].date()} | ㎡당 보증금: {round(row['㎡당가격']):,} 만원 | 차이비율: {row['중앙값_차이비율']:.2%}")
    else:
        print("\n✅ 유사 평형 거래는 중앙값과 큰 차이가 없습니다.")

    return outliers

outliers = detect_outlier_transactions(all_df, median, target_area, area_tolerance=3, threshold_ratio=0.3)

# 서울특별시 관악구 봉천동 1566-10, 오피스텔 검색시 이상치 탐지 가능