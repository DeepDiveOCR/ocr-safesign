document.addEventListener('DOMContentLoaded', () => {
// !!! 본인의 실제 키로 반드시 교체해주세요 !!!
const firebaseConfig = {
    apiKey: "AIzaSyDshiVgNA04Cuhy4U0Mb16gxsHwUp_BKcM",
    authDomain: "safesign-5dd44.firebaseapp.com",
    projectId: "safesign-5dd44",
    storageBucket: "safesign-5dd44.firebasestorage.app",
    messagingSenderId: "221489615514",
    appId: "1:221489615514:web:981d7b423426dce93b8523",
    // measurementId: "G-NB9JVG2MNC"
};
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();

Kakao.init('f62a9ee355ae5511b4ca7ec18e582fe3');

const loginBtn = document.getElementById('login-btn');
const kakaoLoginBtn = document.getElementById('kakao-login-btn');
const logoutBtn = document.getElementById('logout-btn');
const userProfile = document.getElementById('user-profile');
const userDisplayName = document.getElementById('user-display-name');
const loginOverlay = document.getElementById('login-overlay');
const mainContent = document.getElementById('main-content');
let currentUser = null;
const showHistoryBtn = document.getElementById('show-history-btn');
const historyModal = document.getElementById('history-modal');
const closeHistoryModalBtn = document.getElementById('close-history-modal-btn');
const historyListContainer = document.getElementById('history-list-container');
const historyPlaceholder = document.getElementById('history-placeholder');
const registerUpload = document.getElementById('register-upload'), contractUpload = document.getElementById('contract-upload'), registerPlaceholder = document.getElementById('register-placeholder'), contractPlaceholder = document.getElementById('contract-placeholder'), registerPreview = document.getElementById('register-preview'), contractPreview = document.getElementById('contract-preview'), registerDeleteBtn = document.getElementById('register-delete-btn'), contractDeleteBtn = document.getElementById('contract-delete-btn'), ocrResults = document.getElementById('ocr-results'), actionBtn = document.getElementById('action-btn'), actionBtnText = document.getElementById('action-btn-text'), actionSpinner = document.getElementById('action-spinner'), analysisView = document.getElementById('analysis-view'), analysisPlaceholder = document.getElementById('analysis-placeholder'), placeholderText = document.getElementById('placeholder-text'), analysisResultView = document.getElementById('analysis-result-view'), sideImageViewer = document.getElementById('side-image-viewer'), sideViewerImage = document.getElementById('side-viewer-image'), sideViewerCloseBtn = document.getElementById('side-viewer-close-btn');
let appState = 'initial', registerFile = null, contractFile = null;
let originalClausesText = "";
let historyDataMap = new Map();

auth.onAuthStateChanged(user => {
    if (user) {
        currentUser = {
            uid: user.uid,
            displayName: user.displayName || '사용자',
            email: user.email
        };
        updateAuthUI(true);
        fetchAndDisplayHistory(user.uid);
    } else {
        currentUser = null;
        updateAuthUI(false);
        showHistoryBtn.classList.add('hidden');
        historyModal.classList.add('hidden');
    }
});

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

function signInWithKakao() {
    Kakao.Auth.login({
        scope: 'profile_nickname',
        success: function (authObj) {
            fetch('/kakao-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: authObj.access_token })
            })
            .then(response => {
                if (!response.ok) { throw new Error('Firebase 토큰 발급 실패'); }
                return response.json();
            })
            .then(data => {
                if (data.firebase_token) {
                    auth.signInWithCustomToken(data.firebase_token)
                        .catch(error => console.error('Firebase 로그인 실패:', error));
                } else { throw new Error('firebase_token 없음'); }
            })
            .catch(error => console.error('로그인 처리 오류:', error));
        },
        fail: err => console.error('카카오 로그인 실패:', err),
    });
}

function signOutUser() {
    if (auth.currentUser) { auth.signOut(); }
}

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

async function fetchAndDisplayHistory(uid) {
    historyDataMap.clear();
    historyListContainer.innerHTML = '';
    historyPlaceholder.classList.add('hidden');
    try {
        const querySnapshot = await db.collection('users').doc(uid).collection('analyses').orderBy('createdAt', 'desc').get();
        if (querySnapshot.empty) {
            historyPlaceholder.classList.remove('hidden');
        } else {
            querySnapshot.forEach(doc => {
                const data = doc.data();
                const docId = doc.id;
                historyDataMap.set(docId, data);
                const item = document.createElement('div');
                item.className = 'history-item p-3 mb-2 border rounded-lg cursor-pointer hover:bg-gray-100 transition';
                item.dataset.id = docId;
                let address = (data.parsedData && data.parsedData.contract_addr) ? data.parsedData.contract_addr.trim() : '주소 정보 없음';
                const date = data.createdAt ? data.createdAt.toDate().toLocaleDateString('ko-KR') : '날짜 정보 없음';
                item.innerHTML = `<p class="font-semibold text-gray-800 truncate">${address}</p><p class="text-sm text-gray-500">${date}</p>`;
                historyListContainer.appendChild(item);
            });
        }
        showHistoryBtn.classList.remove('hidden');
    } catch (error) {
        console.error("분석 기록 로딩 실패:", error);
        historyPlaceholder.textContent = '기록 로딩 중 오류 발생.';
        historyPlaceholder.classList.remove('hidden');
        showHistoryBtn.classList.remove('hidden');
    }
}

historyListContainer.addEventListener('click', (e) => {
    const historyItem = e.target.closest('.history-item');
    if (historyItem) {
        const docId = historyItem.dataset.id;
        const data = historyDataMap.get(docId);
        if (data) {
            resetAnalysisState();
            ocrResults.value = data.summaryText || '';
            originalClausesText = data.clausesText || '특약사항 없음';
            placeholderText.innerHTML = "선택한 기록이 복원되었습니다.<br>'종합 분석 실행'을 눌러 재분석하세요.";
            appState = 'ocr_done';
            updateUI();
            historyModal.classList.add('hidden');
        }
    }
});

showHistoryBtn.addEventListener('click', () => historyModal.classList.remove('hidden'));
closeHistoryModalBtn.addEventListener('click', () => historyModal.classList.add('hidden'));
historyModal.addEventListener('click', (e) => { if (e.target.id === 'history-modal') historyModal.classList.add('hidden'); });
loginBtn.addEventListener('click', () => loginOverlay.classList.remove('hidden'));
kakaoLoginBtn.addEventListener('click', signInWithKakao);
logoutBtn.addEventListener('click', signOutUser);

const updateUI = () => {
    actionBtn.disabled = true;
    switch (appState) {
        case 'files_uploaded':
            actionBtn.disabled = false;
            actionBtnText.textContent = 'AI로 텍스트 추출 및 보정';
            break;
        case 'ocr_done':
            actionBtn.disabled = false;
            actionBtnText.textContent = '종합 분석 실행';
            break;
        case 'analysis_done':
            actionBtnText.textContent = '분석 완료';
            break;
        default:
            actionBtnText.textContent = '서류를 모두 업로드하세요';
    }
};

const displayPreview = (file, previewEl, placeholderEl, deleteBtn) => {
    if (!file) {
        previewEl.classList.add('hidden');
        previewEl.classList.remove('preview-img-clickable');
        previewEl.src = '';
        deleteBtn.classList.add('hidden');
        placeholderEl.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-gray-400 mb-3"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg><p class="text-sm">파일을 드래그하거나 클릭</p>';
        placeholderEl.classList.remove('hidden');
        return;
    }
    deleteBtn.classList.remove('hidden');
    placeholderEl.classList.add('hidden');
    previewEl.classList.remove('hidden');
    if (file.type.startsWith('image/')) {
        const reader = new FileReader;
        reader.onload = e => { previewEl.src = e.target.result; previewEl.classList.add('preview-img-clickable') };
        reader.readAsDataURL(file);
    } else {
        previewEl.src = '';
        previewEl.classList.add('hidden');
        previewEl.classList.remove('preview-img-clickable');
        placeholderEl.innerHTML = `<div class="flex flex-col items-center text-gray-700"><svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-gray-400 mb-3"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg><p class="text-sm font-medium truncate w-full px-4">${file.name}</p></div>`;
        placeholderEl.classList.remove('hidden');
    }
};

const checkFilesAndUpdateState = () => {
    if (registerFile && contractFile) {
        appState = 'files_uploaded';
    } else {
        appState = 'initial';
        ocrResults.value = '';
        originalClausesText = '';
    }
    updateUI();
};

const showSideImageViewer = imageUrl => {
    if (imageUrl) {
        analysisView.classList.add('hidden');
        sideImageViewer.classList.remove('hidden');
        sideViewerImage.src = imageUrl;
    }
};
const hideSideImageViewer = () => {
    sideImageViewer.classList.add('hidden');
    analysisView.classList.remove('hidden');
    sideViewerImage.src = "";
};

const setupUploadListener = (dropZone, input, placeholder, preview, deleteBtn, isRegister) => {
    const handleFile = file => {
        if (isRegister) { registerFile = file; } else { contractFile = file; }
        displayPreview(file, preview, placeholder, deleteBtn);
        checkFilesAndUpdateState();
    };
    dropZone.addEventListener('click', () => {
        const fileExists = isRegister ? registerFile : contractFile;
        if (!fileExists) input.click();
    });
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', e => { e.preventDefault(); dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', e => { if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]); });
    deleteBtn.addEventListener('click', e => {
        e.stopPropagation();
        input.value = '';
        if (isRegister) { registerFile = null; } else { contractFile = null; }
        displayPreview(null, preview, placeholder, deleteBtn);
        checkFilesAndUpdateState();
        hideSideImageViewer();
    });
};
setupUploadListener(document.getElementById('drop-zone-register'), registerUpload, registerPlaceholder, registerPreview, registerDeleteBtn, true);
setupUploadListener(document.getElementById('drop-zone-contract'), contractUpload, contractPlaceholder, contractPreview, contractDeleteBtn, false);
document.getElementById('edit-btn').addEventListener('click', () => { ocrResults.focus(); ocrResults.select(); });

actionBtn.addEventListener('click', () => {
    if (actionBtn.disabled || !currentUser) {
        if (!currentUser) alert('로그인이 필요합니다.');
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
    } else if (appState === 'ocr_done') {
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
                fetchAndDisplayHistory(currentUser.uid);
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

// ★★★[수정된 최종 함수]★★★
function displayAnalysisResults(result) {
    const verifications = result.verifications || {};
    const logicResults = verifications.logic_results || {};
    let clausesHtml = verifications.clauses_html || "분석할 특약사항이 없거나 결과를 생성하지 못했습니다.";
    const finalRiskGrade = verifications.final_grade || '주의';
    
    const clausesContainer = document.getElementById('clauses-analysis-container');
    const finalCommentContainer = document.getElementById('final-comment-container');
    const summaryBox = document.getElementById("clause-summary-box");

    // 1. 최종 코멘트와 특약사항 HTML 분리
    const commentMarker = "### 최종 코멘트";
    let finalCommentText = "";
    if (clausesHtml.includes(commentMarker)) {
        const parts = clausesHtml.split(commentMarker);
        clausesHtml = parts[0].trim();
        finalCommentText = parts[1].trim();
    }

    // 2. 최종 코멘트를 Fancy한 UI로 렌더링
    if (finalCommentText) {
        finalCommentContainer.innerHTML = `
            <div class="final-comment-card">
                <div class="flex items-start gap-4">
                    <div class="flex-shrink-0 text-blue-500 mt-1">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    </div>
                    <div>
                        <h4 class="font-bold text-gray-900 text-lg">종합 의견</h4>
                        <p class="text-sm text-gray-700 mt-2 leading-relaxed">${finalCommentText}</p>
                    </div>
                </div>
            </div>`;
    } else {
        finalCommentContainer.innerHTML = '';
    }

    // 3. 특약사항 카드 렌더링
    let riskCardHeader = '';
    if (finalRiskGrade === '위험') {
        riskCardHeader = `<div class="p-4 rounded-lg flex items-center gap-4 bg-red-50 border border-red-200"><span class="text-red-500"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg></span><div><p class="font-bold text-xl text-red-700">위험</p><p class="text-sm text-red-600">보증금 미반환 위험이 높은 고위험 계약입니다.</p></div></div>`;
    } else if (finalRiskGrade === '주의') {
        riskCardHeader = `<div class="p-4 rounded-lg flex items-center gap-4 bg-yellow-50 border border-yellow-200"><span class="text-yellow-500"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg></span><div><p class="font-bold text-xl text-yellow-700">주의</p><p class="text-sm text-yellow-600">계약 전 반드시 확인해야 할 사항이 있습니다.</p></div></div>`;
    } else {
        riskCardHeader = `<div class="p-4 rounded-lg flex items-center gap-4 bg-green-50 border border-green-200"><span class="text-green-500"><svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></span><div><p class="font-bold text-xl text-green-700">안전</p><p class="text-sm text-green-600">분석 결과 특이사항이 발견되지 않았습니다.</p></div></div>`;
    }
    clausesContainer.innerHTML = `<h3>특약사항 분석</h3>` + riskCardHeader + `<div class="mt-4">${clausesHtml}</div>`;

    // 4. 나머지 UI 업데이트 (updateCell, summaryBox 등)
    const updateCell = (elementId, resultData) => {
        const cell = document.getElementById(elementId);
        if (!cell) return;
        cell.className = 'verification-value';
        if (resultData && resultData.message) {
            cell.textContent = resultData.message;
            if (resultData.grade === '안전') cell.classList.add('verification-safe');
            else if (resultData.grade === '주의') cell.classList.add('verification-warn');
            else if (resultData.grade === '위험') cell.classList.add('verification-danger');
        } else {
            cell.textContent = '확인 불가';
        }
    };
    updateCell('verification-identity', logicResults['임대인-소유주 일치']);
    updateCell('address-match-result', logicResults['주소 일치 여부']);
    updateCell('verification-price', logicResults['시세 대비 보증금 위험']);
    updateCell('verification-risk-calc', logicResults['보증금 대비 채권최고액 위험']);

    const logicKeys = ['임대인-소유주 일치', '주소 일치 여부', '시세 대비 보증금 위험', '보증금 대비 채권최고액 위험'];
    let riskHigh = 0, riskMedium = 0, riskLow = 0;
    logicKeys.forEach(key => {
        const item = logicResults[key];
        if (!item || !item.grade) return;
        if (item.grade === '위험') riskHigh++;
        else if (item.grade === '주의') riskMedium++;
        else if (item.grade === '안전') riskLow++;
    });
    const clausesCount = parseInt(verifications.clauses_count || 0, 10);
    const clauseHigh = parseInt(verifications.risk_high_count || 0, 10);
    const clauseMedium = parseInt(verifications.risk_medium_count || 0, 10);
    const clauseLow = parseInt(verifications.risk_low_count || 0, 10);
    const totalCount = logicKeys.length + clausesCount;
    const totalHigh = riskHigh + clauseHigh;
    const totalMedium = riskMedium + clauseMedium;
    const totalLow = riskLow + clauseLow;
    if (summaryBox) {
        summaryBox.innerHTML = `
            <div class="rounded-lg bg-gray-50 text-sm text-gray-700 p-4 border border-gray-200 mt-4">
                <p class="font-bold mb-2">종합 위험도 요약</p>
                <div class="space-y-1">
                    <p><strong>- 총 분석 항목:</strong> ${totalCount}개</p>
                    <p class="text-red-600"><strong>- 위험 항목:</strong> ${totalHigh}개</p>
                    <p class="text-yellow-600"><strong>- 주의 항목:</strong> ${totalMedium}개</p>
                    <p class="text-green-600"><strong>- 안전 항목:</strong> ${totalLow}개</p>
                </div>
                <hr class="my-3">
                <p id="grade-reason" class="text-xs text-gray-600 leading-relaxed">${result.evaluation.judgment_reason || ""}</p>
            </div>`;
    }

    document.getElementById('analysis-placeholder').classList.add('hidden');
    document.getElementById('analysis-result-view').classList.remove('hidden');
}

registerPreview.addEventListener('click', () => showSideImageViewer(registerPreview.src));
contractPreview.addEventListener('click', () => showSideImageViewer(contractPreview.src));
sideViewerCloseBtn.addEventListener('click', hideSideImageViewer);

});