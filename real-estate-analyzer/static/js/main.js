document.addEventListener('DOMContentLoaded', () => {
    // ★★★[추가] Firebase & Auth UI Elements ★★★
    const firebaseConfig = {
        apiKey: "AIzaSyDUHNNboNybvxgJyy9dPf797UlPaLzLFqk",
        authDomain: "safesign-c8e3d.firebaseapp.com",
        projectId: "safesign-c8e3d",
        storageBucket: "safesign-c8e3d.appspot.com",
        messagingSenderId: "348853030550",
        appId: "1:348853030550:web:fa8f8f9f0311639f5afcb7"
    };
    firebase.initializeApp(firebaseConfig);
    const auth = firebase.auth();
    const db = firebase.firestore();
    
    // Kakao JavaScript 키 적용
    Kakao.init('f62a9ee355ae5511b4ca7ec18e582fe3');

    const loginBtn = document.getElementById('login-btn');
    const kakaoLoginBtn = document.getElementById('kakao-login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const userProfile = document.getElementById('user-profile');
    const userDisplayName = document.getElementById('user-display-name');
    const loginOverlay = document.getElementById('login-overlay');
    const mainContent = document.getElementById('main-content');
    
    let currentUser = null; // 현재 로그인한 사용자 정보

    // Element References (기존 코드)
    const registerUpload = document.getElementById('register-upload'), contractUpload = document.getElementById('contract-upload'), registerPlaceholder = document.getElementById('register-placeholder'), contractPlaceholder = document.getElementById('contract-placeholder'), registerPreview = document.getElementById('register-preview'), contractPreview = document.getElementById('contract-preview'), registerDeleteBtn = document.getElementById('register-delete-btn'), contractDeleteBtn = document.getElementById('contract-delete-btn'), ocrResults = document.getElementById('ocr-results'), actionBtn = document.getElementById('action-btn'), actionBtnText = document.getElementById('action-btn-text'), actionSpinner = document.getElementById('action-spinner'), analysisView = document.getElementById('analysis-view'), analysisPlaceholder = document.getElementById('analysis-placeholder'), placeholderText = document.getElementById('placeholder-text'), analysisResultView = document.getElementById('analysis-result-view'), sideImageViewer = document.getElementById('side-image-viewer'), sideViewerImage = document.getElementById('side-viewer-image'), sideViewerCloseBtn = document.getElementById('side-viewer-close-btn');
    
    // State Management (기존 코드)
    let appState = 'initial', registerFile = null, contractFile = null;

    // ★★★[구조 변경] 특약사항 원본 텍스트를 저장할 변수 (기존 코드)
    let originalClausesText = "";

    // ★★★[추가] Firebase 인증 상태 리스너 ★★★
    auth.onAuthStateChanged(user => {
        if (user) {
            currentUser = {
                uid: user.uid,
                displayName: user.displayName || '사용자',
                email: user.email
            };
            updateAuthUI(true);
        } else {
            currentUser = null;
            updateAuthUI(false);
        }
    });

    // ★★★[추가] 인증 상태에 따른 UI 업데이트 함수 ★★★
    function updateAuthUI(isLoggedIn) {
        if (isLoggedIn) {
            loginBtn.classList.add('hidden');
            userProfile.classList.remove('hidden');
            userProfile.classList.add('flex');
            userDisplayName.textContent = `${currentUser.displayName}님`;
            loginOverlay.classList.add('hidden');
            mainContent.classList.remove('blurred');
        } else {
            loginBtn.classList.remove('hidden');
            userProfile.classList.add('hidden');
            userProfile.classList.remove('flex');
            loginOverlay.classList.remove('hidden');
            mainContent.classList.add('blurred');
            resetAnalysisState();
        }
    }
    
    // ★★★[기능 구현] 실제 카카오 로그인 로직으로 교체 ★★★
    function signInWithKakao() {
        Kakao.Auth.login({
            scope: 'profile_nickname',
            success: function(authObj) {
                console.log('카카오 로그인 성공:', authObj);
                const kakaoAccessToken = authObj.access_token;
                
                fetch('/kakao-login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: kakaoAccessToken })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('백엔드 서버에서 Firebase 토큰을 받아오지 못했습니다.');
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.firebase_token) {
                        auth.signInWithCustomToken(data.firebase_token)
                        .catch(function(error) {
                            console.error('Firebase 커스텀 토큰 로그인 실패:', error);
                            alert('로그인에 실패했습니다. 잠시 후 다시 시도해주세요.');
                        });
                    } else {
                        throw new Error('백엔드 응답에 firebase_token이 없습니다.');
                    }
                })
                .catch(error => {
                    console.error('백엔드 통신 오류:', error);
                    alert('로그인 처리 중 오류가 발생했습니다.');
                });
            },
            fail: function(err) {
                console.error('카카오 로그인 실패:', err);
                alert('카카오 로그인에 실패했습니다. 팝업 차단 여부를 확인해주세요.');
            },
        });
    }

    // ★★★[추가] 로그아웃 함수 ★★★
    function signOutUser() {
        if (auth.currentUser) {
            auth.signOut().catch(error => console.error("Firebase Logout Error:", error));
        }
    }

    // ★★★[추가] 분석 상태 초기화 함수 ★★★
    function resetAnalysisState() {
        appState = 'initial';
        registerFile = null;
        contractFile = null;
        displayPreview(null, registerPreview, registerPlaceholder, registerDeleteBtn);
        displayPreview(null, contractPreview, contractPlaceholder, contractDeleteBtn);
        ocrResults.value = "";
        originalClausesText = "";
        analysisResultView.classList.add('hidden');
        analysisPlaceholder.classList.remove('hidden');
        updateUI();
    }
    
    // ★★★[추가] 버튼 이벤트 리스너 연결 ★★★
    loginBtn.addEventListener('click', () => loginOverlay.classList.remove('hidden'));
    kakaoLoginBtn.addEventListener('click', signInWithKakao);
    logoutBtn.addEventListener('click', signOutUser);

    // UI Update Function (기존 코드)
    const updateUI = () => {
        switch(appState){
            case 'initial':
                actionBtn.disabled = true;
                actionBtnText.textContent = '서류를 모두 업로드하세요';
                analysisResultView.classList.add('hidden');
                analysisPlaceholder.classList.remove('hidden');
                placeholderText.innerHTML = "왼쪽에서 서류를 업로드하고<br>텍스트 추출을 진행해주세요.";
                break;
            case 'files_uploaded':
                actionBtn.disabled = false;
                actionBtnText.textContent = 'AI로 텍스트 추출 및 보정';
                break;
            case 'ocr_done':
                actionBtn.disabled = false;
                actionBtnText.textContent = '종합 분석 실행';
                placeholderText.innerHTML = "AI 보정 결과를 확인 및 수정 후<br>종합 분석을 실행해주세요.";
                ocrResults.classList.add('highlight-animation');
                setTimeout(() => { ocrResults.classList.remove('highlight-animation') }, 1500);
                break;
            case 'analysis_done':
                actionBtn.disabled = true;
                actionBtnText.textContent = '분석 완료';
                break;
        }
    };
    
    // Preview Display Function (기존 코드)
    const displayPreview = (file, previewEl, placeholderEl, deleteBtn) => {
        if(!file){previewEl.classList.add('hidden');previewEl.classList.remove('preview-img-clickable');previewEl.src='';deleteBtn.classList.add('hidden');placeholderEl.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-gray-400 mb-3"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg><p class="text-sm">파일을 드래그하거나 클릭</p>';placeholderEl.classList.remove('hidden');return}
        deleteBtn.classList.remove('hidden');placeholderEl.classList.add('hidden');previewEl.classList.remove('hidden');
        if(file.type.startsWith('image/')){const reader=new FileReader;reader.onload=e=>{previewEl.src=e.target.result;previewEl.classList.add('preview-img-clickable')};reader.readAsDataURL(file)}else{previewEl.src='';previewEl.classList.add('hidden');previewEl.classList.remove('preview-img-clickable');placeholderEl.innerHTML=`<div class="flex flex-col items-center text-gray-700"><svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-gray-400 mb-3"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg><p class="text-sm font-medium truncate w-full px-4">${file.name}</p></div>`;placeholderEl.classList.remove('hidden')}
    };

    const checkFilesAndUpdateState = () => { registerFile && contractFile ? appState = 'files_uploaded' : (appState = 'initial', ocrResults.value = '', originalClausesText = ''), updateUI() };
    const showSideImageViewer = imageUrl => { if(imageUrl){analysisView.classList.add('hidden'); sideImageViewer.classList.remove('hidden'); sideViewerImage.src = imageUrl;} };
    const hideSideImageViewer = () => { sideImageViewer.classList.add('hidden'); analysisView.classList.remove('hidden'); sideViewerImage.src = ""; };
    
    // Upload Listener Setup (기존 코드)
    const setupUploadListener = (dropZone, input, placeholder, preview, deleteBtn, isRegister) => {
        const handleFile=file=>{isRegister?registerFile=file:contractFile=file;displayPreview(file,preview,placeholder,deleteBtn);checkFilesAndUpdateState()};
        dropZone.addEventListener('click',()=>{const fileExists=isRegister?registerFile:contractFile;if(!fileExists)input.click()});
        dropZone.addEventListener('dragover',e=>{e.preventDefault();dropZone.classList.add('dragover')});
        dropZone.addEventListener('dragleave',e=>{e.preventDefault();dropZone.classList.remove('dragover')});
        dropZone.addEventListener('drop',e=>{e.preventDefault();dropZone.classList.remove('dragover');if(e.dataTransfer.files&&e.dataTransfer.files[0])handleFile(e.dataTransfer.files[0])});
        input.addEventListener('change',e=>{if(e.target.files&&e.target.files[0])handleFile(e.target.files[0])});
        deleteBtn.addEventListener('click',e=>{e.stopPropagation();input.value='';isRegister?registerFile=null:contractFile=null;displayPreview(null,preview,placeholder,deleteBtn);checkFilesAndUpdateState();hideSideImageViewer()});
    };

    setupUploadListener(document.getElementById('drop-zone-register'), registerUpload, registerPlaceholder, registerPreview, registerDeleteBtn, true);
    setupUploadListener(document.getElementById('drop-zone-contract'), contractUpload, contractPlaceholder, contractPreview, contractDeleteBtn, false);
    document.getElementById('edit-btn').addEventListener('click', () => { ocrResults.focus(); ocrResults.select(); });

    // ★★★[구조 변경] Main Action Button 로직 재구성 (기존 코드)
    actionBtn.addEventListener('click', () => {
        if (actionBtn.disabled || !currentUser) {
            if(!currentUser) alert('로그인이 필요합니다.');
            return;
        }
        
        if (appState === 'files_uploaded') {
            hideSideImageViewer();
            actionBtn.disabled = true;
            actionSpinner.classList.remove('hidden');
            actionBtnText.textContent = 'AI로 텍스트 보정 중...';
            
            const formData = new FormData();
            formData.append('registerFile', registerFile);
            formData.append('contractFile', contractFile);
            formData.append('uid', currentUser.uid);
            
            fetch('/ocr', { method: 'POST', body: formData })
            .then(response => {
                if (!response.ok) { return response.json().then(err => { throw new Error(err.error || '서버 응답 오류') }); }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    alert('오류: ' + data.error);
                    ocrResults.value = `오류 발생: ${data.error}`;
                } else {
                    ocrResults.value = data.summary_text;
                    originalClausesText = data.clauses_text;
                    appState = 'ocr_done';
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                alert('텍스트 추출 중 오류가 발생했습니다. 서버 로그를 확인하거나 잠시 후 다시 시도해주세요.');
                appState = 'files_uploaded';
            })
            .finally(() => {
                actionSpinner.classList.add('hidden');
                updateUI();
            });
        } 
        else if (appState === 'ocr_done') {
            hideSideImageViewer();
            actionBtn.disabled = true;
            actionSpinner.classList.remove('hidden');
            actionBtnText.textContent = '종합 분석 중...';
            
            const finalSummaryText = ocrResults.value;

            fetch('/process-analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    summary_text: finalSummaryText,
                    clauses_text: originalClausesText,
                    uid: currentUser.uid
                })
            })
            .then(response => {
                if (!response.ok) { return response.json().then(err => { throw new Error(err.error || '서버 응답 오류') }); }
                return response.json();
            })
            .then(result => {
                if (result.error) {
                    alert('분석 오류: ' + result.error);
                } else {
                    displayAnalysisResults(result);
                    appState = 'analysis_done';
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                alert('분석 중 오류가 발생했습니다: ' + error.message);
            })
            .finally(() => {
                actionSpinner.classList.add('hidden');
                updateUI();
            });
        }
    });

    // ★★★[기능 추가] 종합 분석 결과를 화면에 표시하는 함수 (기존 코드)
    function displayAnalysisResults(result) {
        const identityCell = document.getElementById('verification-identity');
        const priceCell = document.getElementById('verification-price');

        identityCell.textContent = result.verifications.identity || '확인 불가';
        priceCell.textContent = result.verifications.price || '확인 불가';
        
        identityCell.className = 'verification-value';
        if (identityCell.textContent.includes('불일치')) {
            identityCell.classList.add('verification-danger');
        } else if (identityCell.textContent.includes('일치')) {
            identityCell.classList.add('verification-safe');
        }

        priceCell.className = 'verification-value';
        if (priceCell.textContent.includes('주의') || priceCell.textContent.includes('높습니다')) {
            priceCell.classList.add('verification-warn');
        } else if (priceCell.textContent.includes('양호')) {
            priceCell.classList.add('verification-safe');
        }
        
        const clausesContainer = document.getElementById('clauses-analysis-container');
        const analysisData = result.verifications.clauses;
        let overallRisk = '안전';

        if (analysisData.includes('위험도: 높음')) {
            overallRisk = '위험';
        } else if (analysisData.includes('위험도: 중간')) {
            overallRisk = '주의';
        }

        let riskCardHtml = '';
        if (overallRisk === '위험') {
            riskCardHtml = `<div class="p-4 rounded-lg flex items-center gap-4 bg-red-50 border border-red-200"><span class="text-red-500"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg></span><div><p class="font-bold text-xl text-red-700">위험</p><p class="text-sm text-red-600">보증금 미반환 위험이 높은 고위험 계약입니다.</p></div></div>`;
        } else if (overallRisk === '주의') {
            riskCardHtml = `<div class="p-4 rounded-lg flex items-center gap-4 bg-yellow-50 border border-yellow-200"><span class="text-yellow-500"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg></span><div><p class="font-bold text-xl text-yellow-700">주의</p><p class="text-sm text-yellow-600">계약 전 반드시 확인해야 할 사항이 있습니다.</p></div></div>`;
        } else {
            riskCardHtml = `<div class="p-4 rounded-lg flex items-center gap-4 bg-green-50 border border-green-200"><span class="text-green-500"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></span><div><p class="font-bold text-xl text-green-700">안전</p><p class="text-sm text-green-600">분석 결과 특이사항이 발견되지 않았습니다.</p></div></div>`;
        }

        const converter = new showdown.Converter({tables: true, openLinksInNewWindow: true});
        const clausesHtml = converter.makeHtml(analysisData);
        clausesContainer.innerHTML = `<h3>특약사항 분석</h3>` + riskCardHtml + `<div class="mt-4">${clausesHtml}</div>`;
        
        const riskKeywords = { '높음': 'risk-high', '중간': 'risk-medium', '낮음': 'risk-low' };
        clausesContainer.querySelectorAll('td, p').forEach(el => {
            for (const keyword in riskKeywords) {
                if (el.textContent.includes(keyword)) {
                    const regex = new RegExp(`(위험도: |\\|)\\s*${keyword}`, 'g');
                    el.innerHTML = el.innerHTML.replace(regex, `<span class="risk-badge ${riskKeywords[keyword]}">${keyword}</span>`);
                }
            }
        });

        analysisPlaceholder.classList.add('hidden');
        analysisResultView.classList.remove('hidden');
    }

    registerPreview.addEventListener('click', () => showSideImageViewer(registerPreview.src));
    contractPreview.addEventListener('click', () => showSideImageViewer(contractPreview.src));
    sideViewerCloseBtn.addEventListener('click', hideSideImageViewer);

});
