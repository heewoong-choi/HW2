const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const previewArea = document.getElementById('preview-area');
const resultArea = document.getElementById('result-area');
const userImage = document.getElementById('user-image');
const celebImage = document.getElementById('celeb-image');
const celebSkeleton = document.getElementById('celeb-skeleton');
const celebLabel = document.getElementById('celeb-label');
const matchName = document.getElementById('match-name');
const matchScore = document.getElementById('match-score');
const similarityBar = document.getElementById('similarity-bar');
const errorMsg = document.getElementById('error-message');
const resetBtn = document.getElementById('reset-btn');
const igShareBtn = document.getElementById('ig-share-btn');

// Drag and Drop Events
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
});

dropZone.addEventListener('drop', handleDrop, false);
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleChange);
resetBtn.addEventListener('click', resetApp);
igShareBtn.addEventListener('click', shareToInstagram);

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
        handleFile(files[0]);
    }
}

function handleChange(e) {
    if (this.files && this.files.length > 0) {
        handleFile(this.files[0]);
    }
}

function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        showError('이미지 파일만 업로드 가능합니다.');
        return;
    }

    // UI Updates - Show Loading
    errorMsg.classList.add('hidden');
    dropZone.classList.add('hidden');
    previewArea.classList.remove('hidden');
    resultArea.classList.add('hidden');
    
    celebImage.classList.add('hidden');
    celebSkeleton.classList.remove('hidden');
    celebLabel.innerText = '비교 중...';
    similarityBar.style.width = '0%';

    // Preview User Image
    const reader = new FileReader();
    reader.onload = (e) => {
        userImage.src = e.target.result;
    };
    reader.readAsDataURL(file);

    // Upload to API
    uploadImage(file);
}

async function uploadImage(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/find_lookalike', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'API 통신 에러가 발생했습니다.');
        }

        // Display Results
        setTimeout(() => { // UI Smoothness 딜레이
            celebSkeleton.classList.add('hidden');
            celebImage.src = data.image_url;
            celebImage.classList.remove('hidden');
            celebLabel.innerText = data.lookalike;

            matchName.innerText = data.lookalike;
            matchScore.innerText = data.similarity_percent;
            
            resultArea.classList.remove('hidden');
            
            // Bar animation
            setTimeout(() => {
                similarityBar.style.width = `${data.similarity_percent}%`;
            }, 100);

        }, 500);

    } catch (err) {
        previewArea.classList.add('hidden');
        dropZone.classList.remove('hidden');
        showError(err.message);
    }
}

function resetApp() {
    fileInput.value = '';
    dropZone.classList.remove('hidden');
    previewArea.classList.add('hidden');
    resultArea.classList.add('hidden');
    errorMsg.classList.add('hidden');
}

function showError(msg) {
    errorMsg.innerText = `⚠️ ${msg}`;
    errorMsg.classList.remove('hidden');
}

async function shareToInstagram() {
    // 캡처 화면에서 버튼 숨기기
    const buttonGroup = document.querySelector('.button-group');
    buttonGroup.classList.add('hidden');
    
    // [중요] html2canvas가 CSS 최신 그라데이션과 CSS 변수를 잘 못 읽는 고질적 버그 대응
    const titleObj = document.querySelector('.gradient-text');
    if (titleObj) {
        titleObj.style.background = 'transparent';
        titleObj.style.webkitTextFillColor = '#00f2fe'; // 스크린샷 뜰 때만 단색 처리
    }
    const container = document.querySelector('.glass-container');
    const originalBg = container.style.background;
    container.style.background = '#0b0f19'; // 반투명 유리(glass) 속성 버리고 아예 불투명 배경 적용
    
    // 🔥 텍스트 강제 색상 주입: 캐시 안 먹어도 자바스크립트로 강제 치환
    const textEls = container.querySelectorAll('.result-area h2, .result-area p, .progress-text, footer');
    textEls.forEach(el => {
        el.dataset.oldColor = el.style.color || '';
        el.style.color = '#ffffff';
        el.style.textShadow = 'none'; // 그림자 렌더링 버그 제거
    });

    const highlight = container.querySelector('.highlight');
    if (highlight) {
        highlight.dataset.oldColor = highlight.style.color || '';
        highlight.style.color = '#00f2fe';
    }
    
    // 🔥 CSS Animation 투명도 캡처 버그 원천 차단
    const resultArea = document.getElementById('result-area');
    const originalAnimation = resultArea.style.animation;
    resultArea.style.animation = 'none';
    resultArea.style.opacity = '1';
    resultArea.style.transform = 'none';
    
    try {
        const canvas = await html2canvas(container, {
            useCORS: true, // 외부 이미지(위키백과) 로딩 허용
            backgroundColor: '#0b0f19',
            scale: 2 // 고화질
        });
        
        // 원상 복구
        if (titleObj) {
            titleObj.style.background = '';
            titleObj.style.webkitTextFillColor = '';
        }
        container.style.background = originalBg;
        
        textEls.forEach(el => {
            el.style.color = el.dataset.oldColor;
        });
        if (highlight) {
            highlight.style.color = highlight.dataset.oldColor;
        }
        
        resultArea.style.animation = originalAnimation;

        buttonGroup.classList.remove('hidden');
        
        canvas.toBlob(async (blob) => {
            const file = new File([blob], 'my_lookalike.png', { type: 'image/png' });
            
            // 모바일 Web Share API (인스타그램 인텐트로 바로 연결 가능)
            if (navigator.share && navigator.canShare({ files: [file] })) {
                try {
                    await navigator.share({
                        files: [file],
                        title: 'AI 닮은꼴 테스트',
                        text: `내 닮은꼴은 ${matchName.innerText}! (${matchScore.innerText}% 일치) 흥미진진한 AI 테스트를 해보세요 😆`
                    });
                } catch (e) {
                    console.log('Share canceled or failed', e);
                }
            } else {
                // PC 등 Web Share 미지원 환경에서는 사진 자동 다운로드
                const link = document.createElement('a');
                link.download = `lookalike_${matchName.innerText}.png`;
                link.href = URL.createObjectURL(blob);
                link.click();
                alert('📸 결과 이미지가 다운로드 되었습니다!\n인스타그램 스토리에 직접 올려서 친구들에게 자랑해보세요!');
            }
        });
    } catch(err) {
        buttonGroup.classList.remove('hidden');
        showError('이미지 캡처 중 오류가 발생했습니다.');
    }
}
