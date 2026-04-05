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
    
    try {
        const canvas = await html2canvas(document.querySelector('.glass-container'), {
            useCORS: true, // 외부 이미지(위키백과) 로딩 허용
            backgroundColor: '#0b0f19',
            scale: 2 // 고화질
        });
        
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
