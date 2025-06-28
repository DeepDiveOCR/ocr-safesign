import requests
import pandas as pd
import numpy as np
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from sklearn.neighbors import BallTree

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

# 건물 유형별 api url
def get_api_url(building_type, log_type):
    mapping = {
        "아파트": ("AptTrade", "AptRent"),
        "다세대": ("RHTrade", "RHRent"),
        "연립": ("RHTrade", "RHRent"),
        "오피스텔": ("OffiTrade", "OffiRent")
    }
    
    api_types = mapping.get(building_type)
    trade_type, rent_type = api_types
    if log_type == "trade":
        return f"https://apis.data.go.kr/1613000/RTMSDataSvc{trade_type}/getRTMSDataSvc{trade_type}"
    elif log_type == "rent":
        return f"https://apis.data.go.kr/1613000/RTMSDataSvc{rent_type}/getRTMSDataSvc{rent_type}"
    return None, None


# ✅ 실거래가 API 호출
def get_deals(lawd_cd, target_dong, target_jibun, building_type, yyyymm, log_type):
    url = get_api_url(building_type, log_type)

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
                break  # 더 이상 데이터 없음

            for item in items:
                dong = item.findtext("umdNm", "").strip()
                api_jibun = item.findtext("jibun", "").strip()

                if dong != target_dong or api_jibun != target_jibun:
                    continue

                year = item.findtext("dealYear")
                month = item.findtext("dealMonth")
                day = item.findtext("dealDay")
                date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                area_raw = item.findtext("excluUseAr")
                area = float(area_raw)

                if log_type == "trade":
                    deal_amount_raw = item.findtext("dealAmount")
                    deal_amount = int(deal_amount_raw.replace(",", "")) * 10000
                    
                    all_data.append({
                        "거래금액": deal_amount,
                        "전용면적": area,
                        "계약일": date
                        })
                
                elif log_type == "rent":
                    deposit_raw = item.findtext("deposit", "").replace(",", "").strip()
                    deposit = int(deposit_raw) * 10000

                    monthly_rent_raw = item.findtext("monthlyRent", "").replace(",", "").strip()
                    monthly_rent = int(monthly_rent_raw) * 10000 if monthly_rent_raw else 0

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

# ✅ 통합 시세 추정 함수
def estimate_price(lawd_cd, target_dong, target_jibun, target_area, building_type, log_type):
    all_df = pd.DataFrame()
    today = datetime.today()

    for year_offset in range(1, 6):
        month_list = [
            (today - timedelta(days=30 * i)).strftime("%Y%m")
            for i in range(year_offset * 12)
        ]
        
        # 해당 연도의 12개월 데이터 요청
        for yyyymm in month_list:
            new_df = get_deals(lawd_cd, target_dong, target_jibun, building_type, yyyymm, log_type)
            
            if not new_df.empty:
                all_df = pd.concat([all_df, new_df], ignore_index=True).drop_duplicates()

        if len(all_df) >= 5:
            all_df["계약일"] = pd.to_datetime(all_df["계약일"])

            if (log_type == "trade"):
                all_df["㎡당가격"] = all_df["거래금액"] / all_df["전용면적"]
            elif(log_type == "rent"):
                all_df["㎡당가격"] = all_df["보증금"] / all_df["전용면적"]


            filtered_df = all_df[
                (all_df["전용면적"] >= target_area - 3) & 
                (all_df["전용면적"] <= target_area + 3)
            ]

            target_df = filtered_df if len(filtered_df) >= 3 else all_df

            median_price = round(target_df["㎡당가격"].median())

            msg = f"{year_offset+1}년 기준 ({'유사 평형' if len(filtered_df) >= 3 else '전체'})"

            return all_df, median_price, f"{year_offset+1}년 기준 ({msg})"

    # 5년치 누적에도 5건 미만
    if not all_df.empty:
        all_df["계약일"] = pd.to_datetime(all_df["계약일"])
        latest = all_df.sort_values("계약일", ascending=False).iloc[0]

        if (log_type == "trade"):
            unit_price = round(latest["거래금액"] / latest["전용면적"])
        elif(log_type == "rent"):
            unit_price = round(latest["보증금"] / latest["전용면적"])
        
        print("⚠️ 거래 건수 부족 — 최근 거래 1건 기준으로 반환합니다.")
        return all_df, unit_price, f"최근 거래 1건 ({latest['계약일'].date()})"

    print("❌ 거래 데이터가 존재하지 않습니다.")
    return None, None, "데이터 부족"

def detect_outlier_transactions(all_df, median_price, target_area, area_tolerance=3, threshold_ratio=0.3):
    all_df["계약일"] = pd.to_datetime(all_df["계약일"])

    # 유사 평형 데이터 필터
    similar_df = all_df[
        (all_df["전용면적"] >= target_area - area_tolerance) &
        (all_df["전용면적"] <= target_area + area_tolerance)
    ].copy()

    if similar_df.empty:
        info = "⚠️ 유사 평형 데이터가 없습니다. 전체 데이터로 탐지 불가."
        return pd.DataFrame(), info

    # 중앙값 대비 차이 비율 계산
    similar_df["중앙값_차이비율"] = abs(similar_df["㎡당가격"] - median_price) / median_price
    similar_df["중앙값_차이비율(%)"] = (similar_df["중앙값_차이비율"] * 100).map(lambda x: f"{x:.2f}%")

    # 이상 거래 탐지
    outliers = similar_df[similar_df["중앙값_차이비율"] > threshold_ratio].copy()

    if not outliers.empty:
        info = f"⚠️ 유사 평형({target_area}±{area_tolerance}㎡) 거래 중 중앙값 대비 {int(threshold_ratio*100)}% 이상 차이 나는 거래 {len(outliers)}건 발견!"
    else:
        info = "✅ 유사 평형 거래는 중앙값과 큰 차이가 없습니다."

    return outliers, info

# 실행 부분
def estimate_median_trade(address, building_type, exclusive_area):
    region, dong, jibun = parse_address(address)
    lawd_cd = get_region_prefix(region)
    all_df, median, info = estimate_price(lawd_cd, dong, jibun, exclusive_area, building_type, "trade")
    return all_df, median, info

def estimate_median_rent(address, building_type, exclusive_area):
    region, dong, jibun = parse_address(address)
    lawd_cd = get_region_prefix(region)
    all_df, median, info1 = estimate_price(lawd_cd, dong, jibun, exclusive_area, building_type, "rent")
    outliers, info2 = detect_outlier_transactions(all_df, median, exclusive_area, area_tolerance=3, threshold_ratio=0.3)
    return all_df, median, info1, outliers, info2