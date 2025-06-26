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
def get_trade_deals(lawd_cd, target_dong, target_jibun, months, building_type):
    url = get_trade_api_url(building_type)
    today = datetime.today()
    month_list = [(today - timedelta(days=30 * i)).strftime("%Y%m") for i in range(months)]
    all_data = []

    for yyyymm in month_list:
        params = {
            "serviceKey": "7vMdnzTpnFnBO5wPN3LkHyPgPNFu3A/w/+RH8EJw3ihZfuhA5UiMx4x/PYl1qjlCx1VAzTL+i2GJXf1c/oHfyg==",
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": yyyymm,
            "numOfRows": "1000",
            "pageNo": "1"
        }
        try:
            response = requests.get(url, params=params)
            root = ET.fromstring(response.content)

            for item in root.iter("item"):
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
        except Exception as e:
            print(f"❌ API 오류: {e}")
            continue

    return pd.DataFrame(all_data)

# ✅ 통합 시세 추정 함수
def estimate_real_estate_price(lawd_cd, target_dong, target_jibun, building_type, fallback_callback=None):
    def fetch_and_estimate(months, label):
        df = get_trade_deals(lawd_cd, target_dong, target_jibun, months, building_type)
        if len(df) >= 5:
            df["㎡당가격"] = df["거래금액"] / df["전용면적"]
            median = df["㎡당가격"].median()
            print(f"✅ {label} 데이터를 기반으로 시세를 계산하였습니다.")
            return round(median), label
        return None, None

    # 1️⃣ 최근 1년
    price, 기준 = fetch_and_estimate(12, "1년 기준")
    if price is not None:
        return price, 기준

    # 2️⃣ 최근 2년
    price, 기준 = fetch_and_estimate(24, "2년 기준")
    if price is not None:
        print("⚠️ 최근 거래가 부족하여 최근 2년간 데이터를 활용하였습니다.")
        return price, 기준

    # 3️⃣ 대체 전략 (인근 단지 등)
    if fallback_callback:
        price = fallback_callback()
        print("⚠️ 2년간 데이터도 부족하여 인근 단지 기반으로 시세를 추정합니다.")
        return round(price), "인근 단지"

    print("❌ 시세를 추정할 수 없습니다.")
    return None, "데이터 부족"


### fallback
def load_coords_by_building_type(building_type):
    file_mapping = {
        "오피스텔": "df_office.csv",
        "아파트" : "df_apartment.csv",
        "다세대": "df_villa.csv"
    }
    filepath = file_mapping.get(building_type)
    return pd.read_csv(filepath)

def get_coords(address):
    kakao_api_key = "6665946ef83bd1dc889184a24cf212a2"
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    params = {"query": address}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        result = response.json()
        if result['documents']:
            x = float(result['documents'][0]['x'])  # longitude
            y = float(result['documents'][0]['y'])  # latitude
            return y, x
        else:
            print("❌ 주소에 대한 좌표를 찾을 수 없습니다.")
            return None, None
    else:
        print(f"❌ API 오류: {response.status_code}")
        return None, None
    
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # 지구 반지름(km)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def weighted_median(values, weights):
    sorted_idx = np.argsort(values)
    sorted_values = np.array(values)[sorted_idx]
    sorted_weights = np.array(weights)[sorted_idx]
    cumulative_weight = np.cumsum(sorted_weights)
    cutoff = 0.5 * sum(sorted_weights)
    return sorted_values[cumulative_weight >= cutoff][0]

def fallback_strategy(address, lawd_cd, df_coords, building_type, months=24):
    # 1️⃣ 주소 → 위도, 경도
    lat, lon = get_coords(address)

    # 2️⃣ 거리 계산
    df_coords["거리_km"] = df_coords.apply(
        lambda row: haversine(lat, lon, row["위도"], row["경도"]),
        axis=1
    )

    # 3️⃣ 인접 단지 1km 이내 상위 10개 선택
    nearby_df = df_coords[df_coords["거리_km"] <= 1].sort_values(by="거리_km").head(10)
    deal_list = []

    for _, row in nearby_df.iterrows():
        full_address = row["전체주소"]
        _, dong, jibun = parse_address(full_address)

        deals = get_trade_deals(lawd_cd, dong, jibun, months, building_type)
        if not deals.empty:
            deals["거리_km"] = row["거리_km"]
            deal_list.append(deals)

    # 4️⃣ 시세 계산 (가중 중앙값)
    combined = pd.concat(deal_list, ignore_index=True)
    combined["㎡당가격"] = combined["거래금액"] / combined["전용면적"]

    today = pd.Timestamp.today()
    combined["계약일"] = pd.to_datetime(combined["계약일"])
    combined["개월수"] = (today.year - combined["계약일"].dt.year) * 12 + (today.month - combined["계약일"].dt.month)

    combined["거리_가중치"] = np.exp(-3.0 * combined["거리_km"])
    combined["시간_가중치"] = np.exp(-0.15 * combined["개월수"])
    combined["가중치"] = combined["거리_가중치"] * combined["시간_가중치"]

    return weighted_median(combined["㎡당가격"], combined["가중치"])

address = "서울특별시 관악구 남현동 602-28"
building_type = "아파트"

region, dong, jibun = parse_address(address)

# 법정동 코드 조회
lawd_cd = get_region_prefix(region)
df_coords = load_coords_by_building_type(building_type)
fallback_callback = lambda: fallback_strategy(address, lawd_cd, df_coords, building_type)

# 메인 실행
price, per = estimate_real_estate_price(lawd_cd, dong, jibun, building_type, fallback_callback=fallback_callback)
print(f"\n📊 최종 추정 시세: {price:,} 원/㎡ ({per})")