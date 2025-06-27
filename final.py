import requests
import pandas as pd
import numpy as np
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from sklearn.neighbors import BallTree

def parse_address(address):
    """
    구, 동, 지번을 기준으로 분리하는 범용 주소 파서
    예: '서울특별시 강남구 논현동 203-1' → ('서울특별시 강남구', '논현동', '203-1')
    """
    tokens = address.strip().split()

    # 구 or 군 찾기
    gu_index = next((i for i, t in enumerate(tokens) if t.endswith("구") or t.endswith("군")), None)

    region_name = " ".join(tokens[:gu_index + 1])      # 예: 서울특별시 강남구
    umdNm = tokens[gu_index + 1]                        # 예: 논현동
    jibun = tokens[gu_index + 2]                        # 예: 203-1

    return region_name, umdNm, jibun

# ✅ 지역명 → 법정동코드(앞 5자리) 변환 함수
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
                        return entry['region_cd'][:5]  # 앞 5자리 (법정동코드 상위)
        print("❌ 해당 지역명을 찾을 수 없습니다.")
        return None
    else:
        print(f"❌ API 요청 실패: 상태 코드 {response.status_code}")
        return None

# 건물 유형별 api url
def get_trade_api_url(building_type):
    mapping = {
        "아파트": "AptTrade",
        "다세대": "RHTrade",
        "연립": "RHTrade",
        "오피스텔": "OffiTrade"
    }
    api_type = mapping.get(building_type)
    if api_type:
        return f"https://apis.data.go.kr/1613000/RTMSDataSvc{api_type}/getRTMSDataSvc{api_type}"
    return None

# ✅ 실거래가 API 호출
def get_trade_deals(lawd_cd, target_dong, target_jibun, building_type, yyyymm):
    url = get_trade_api_url(building_type)
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

                deal_amount_raw = item.findtext("dealAmount")
                area_raw = item.findtext("excluUseAr")
                year = item.findtext("dealYear")
                month = item.findtext("dealMonth")
                day = item.findtext("dealDay")

                if not (deal_amount_raw and area_raw and year and month and day):
                    continue

                deal_amount = int(deal_amount_raw.replace(",", "")) * 10000
                area = float(area_raw)
                date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                all_data.append({
                    "거래금액": deal_amount,
                    "전용면적": area,
                    "계약일": date
                })

            page += 1

        except Exception as e:
            print(f"❌ API 오류 (page {page}): {e}")
            break

    return pd.DataFrame(all_data)

def weighted_median(values, weights):
    sorted_idx = np.argsort(values)
    sorted_values = np.array(values)[sorted_idx]
    sorted_weights = np.array(weights)[sorted_idx]
    cumulative_weight = np.cumsum(sorted_weights)
    cutoff = 0.5 * sum(sorted_weights)
    return sorted_values[cumulative_weight >= cutoff][0]

# ✅ 통합 시세 추정 함수
def estimate_real_estate_price(lawd_cd, target_dong, target_jibun, target_area, building_type):
    all_df = pd.DataFrame()
    today = datetime.today()

    for year_offset in range(0, 5):
        # 이 루프에서 가져올 1년치 기간의 yyyymm 리스트
        month_list = [
            (today - timedelta(days=30 * (year_offset * 12 + i))).strftime("%Y%m") 
            for i in range(12)
        ]
        
        # 해당 연도의 12개월 데이터 요청
        for yyyymm in month_list:
            new_df = get_trade_deals(lawd_cd, target_dong, target_jibun, building_type, yyyymm=yyyymm)
            
            if not new_df.empty:
                all_df = pd.concat([all_df, new_df], ignore_index=True).drop_duplicates()

        if len(all_df) >= 5:
            filtered_df = all_df[
                (all_df["전용면적"] >= target_area - 3) & 
                (all_df["전용면적"] <= target_area + 3)
            ]
            target_df = (filtered_df if len(filtered_df) >= 3 else all_df).copy()

            target_df["㎡당가격"] = target_df["거래금액"] / target_df["전용면적"]
            target_df["계약일"] = pd.to_datetime(target_df["계약일"])
            target_df["개월수"] = (
                (today.year - target_df["계약일"].dt.year) * 12 +
                (today.month - target_df["계약일"].dt.month)
            )
            target_df["가중치"] = np.exp(-0.02 * target_df["개월수"])

            median_price = round(target_df["㎡당가격"].median())
            weighted_mean = round(np.average(target_df["㎡당가격"], weights=target_df["가중치"]))

            msg = "유사 평형" if len(filtered_df) >= 3 else "전체"

            return median_price, weighted_mean, f"{year_offset+1}년 기준 ({msg})"

    # 5년치 누적에도 5건 미만
    if not all_df.empty:
        all_df["계약일"] = pd.to_datetime(all_df["계약일"])
        latest = all_df.sort_values("계약일", ascending=False).iloc[0]
        unit_price = round(latest["거래금액"] / latest["전용면적"])
        print("⚠️ 거래 건수 부족 — 최근 거래 1건 기준으로 반환합니다.")
        return unit_price, unit_price, f"최근 거래 1건 ({latest['계약일'].date()})"

    print("❌ 거래 데이터가 존재하지 않습니다.")
    return None, None, "데이터 부족"

address = "서울특별시 관악구 봉천동 148-149"
building_type = "다세대"
exclusive_area = 64

region, dong, jibun = parse_address(address)

# 법정동 코드 조회
lawd_cd = get_region_prefix(region)

# 메인 실행
median_price, mean_price, per = estimate_real_estate_price(lawd_cd, dong, jibun, exclusive_area, building_type)
print(per)
print(f"최종 추정 시세 중앙값: {median_price:,} 원/㎡")
print(f"최종 추정 시세 가중 평균값: {mean_price:,} 원/㎡")