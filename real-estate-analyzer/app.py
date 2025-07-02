# 1. config에서 초기화된 Flask 앱 객체(app)를 가져옵니다.
from config import app

# 2. 분리된 라우트(블루프린트)들을 가져옵니다.
from routes.auth_routes import auth_bp
from routes.analysis_routes import analysis_bp

# 3. 앱에 블루프린트를 등록합니다.
# url_prefix를 사용하면 특정 경로 하위에 라우트를 그룹화할 수 있습니다. (예: /api/ocr)
app.register_blueprint(auth_bp) 
app.register_blueprint(analysis_bp)

# 4. 서버를 실행합니다.
if __name__ == '__main__':
    # host='0.0.0.0'는 외부에서 접속 가능하게 함
    # 실제 배포 시에는 debug=False로 설정해야 합니다.
    app.run(host='0.0.0.0', port=5000, debug=False)