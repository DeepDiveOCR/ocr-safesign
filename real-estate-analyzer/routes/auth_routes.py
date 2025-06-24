from flask import Blueprint, request, jsonify
import requests
from firebase_admin import auth, firestore

# config.py에서 초기화된 db 클라이언트를 가져옵니다.
from config import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/kakao-login', methods=['POST'])
def kakao_login():
    data = request.get_json()
    access_token = data.get('token')

    if not access_token:
        return jsonify({'error': '카카오 액세스 토큰이 필요합니다.'}), 400

    KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        print("--- 카카오 서버에 사용자 정보 요청 ---")
        response = requests.get(KAKAO_USERINFO_URL, headers=headers)
        response.raise_for_status()
        kakao_user_info = response.json()
        print(f"✅ 카카오 사용자 정보 수신 성공: {kakao_user_info}")

        kakao_user_id = str(kakao_user_info.get('id'))
        profile = kakao_user_info.get('properties', {})
        nickname = profile.get('nickname')
        
        if not kakao_user_id:
            return jsonify({'error': '카카오로부터 사용자 ID를 받을 수 없습니다.'}), 400

        uid = f'kakao:{kakao_user_id}'

        print(f"--- Firebase 처리 시작 (UID: {uid}) ---")
        try:
            auth.update_user(uid, display_name=nickname)
            print(f"✅ 기존 Firebase 사용자 정보 업데이트 완료.")
        except auth.UserNotFoundError:
            auth.create_user(uid=uid, display_name=nickname)
            print(f"✅ 신규 Firebase 사용자 생성 완료.")
            
            user_data = {
                'nickname': nickname,
                'createdAt': firestore.SERVER_TIMESTAMP
            }
            db.collection('users').document(uid).set(user_data)
            print(f"✅ Firestore DB에 신규 회원 정보 저장 완료 (UID: {uid})")
        
        custom_token = auth.create_custom_token(uid)
        print("✅ Firebase 커스텀 토큰 생성 성공.")

        return jsonify({'firebase_token': custom_token.decode('utf-8')})

    except requests.exceptions.HTTPError as e:
        print(f"🚨 카카오 토큰 인증 실패: {e.response.text}")
        return jsonify({'error': '유효하지 않은 카카오 토큰입니다.', 'details': e.response.json()}), 401
    except Exception as e:
        print(f"🚨 로그인 처리 중 심각한 오류 발생: {e}")
        return jsonify({'error': f'서버 내부 오류 발생: {e}'}), 500