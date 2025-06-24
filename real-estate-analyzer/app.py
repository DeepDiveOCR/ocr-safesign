from flask import render_template
from config import app
from routes.auth_routes import auth_bp
from routes.analysis_routes import analysis_bp

# --- Blueprint 등록 ---
# 각 기능 파일에 정의된 API 라우트들을 실제 앱에 연결합니다.
app.register_blueprint(auth_bp)
app.register_blueprint(analysis_bp)

# --- 메인 페이지 라우트 ---
@app.route('/')
def index():
    """메인 HTML 페이지를 렌더링합니다."""
    return render_template('index.html')

# --- 앱 실행 ---
if __name__ == '__main__':
    # 디버그 모드로 앱을 실행합니다.
    app.run(host='0.0.0.0', port=5000, debug=True)