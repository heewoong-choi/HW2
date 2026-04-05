import os
import cv2
import httpx
import asyncio
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from deepface import DeepFace

app = FastAPI(title="Lightweight Face-Similarity API")

# 예시용 유명인 URL 데이터베이스 (서버 실행 시 1회 메모리로 다운로드 후 추출)
CELEBS = [
    {"name": "Einstein", "url": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Einstein_1921_by_F_Schmutzer_-_restoration.jpg"},
    {"name": "Marie Curie", "url": "https://upload.wikimedia.org/wikipedia/commons/c/c8/Marie_Curie_c._1920s.jpg"},
]

# Senior's Tip 1: "SFace"는 모델 크기가 약 40MB에 불과해 메모리와 초기 구동 속도를 크게 아낄 수 있는 경량화 모델입니다.
MODEL_NAME = "SFace"

# 글로벌 메모리 저장소
celeb_names = []
celeb_matrix = None  # (N, D) 형태의 numpy array로 벡터화 연산을 위해 사용

async def download_image_as_numpy(client: httpx.AsyncClient, url: str) -> np.ndarray:
    response = await client.get(url)
    response.raise_for_status()
    image_bytes = response.content
    np_arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

def get_embedding(img_array: np.ndarray) -> np.ndarray:
    # DeepFace.represent는 얼굴을 찾아서 Embedding (Vector) 리스트를 리턴함. (디스크 저장 안 함)
    results = DeepFace.represent(img_path=img_array, model_name=MODEL_NAME, enforce_detection=False)
    if results and len(results) > 0:
        return np.array(results[0]["embedding"])
    return None

@app.on_event("startup")
async def startup_event():
    global celeb_matrix
    print("🚀 시작: 유명인 이미지 URL 다운로드 및 임베딩 벡터화...")
    
    embeddings_list = []
    
    async with httpx.AsyncClient() as client:
        # 비동기 다운로드 및 벡터 추출
        for celeb in CELEBS:
            try:
                img_array = await download_image_as_numpy(client, celeb["url"])
                
                # Senior's Tip 2: 머신러닝 연산은 CPU를 블로킹할 수 있으므로, ThreadPool(run_in_executor)에 위임하여 비동기 처리 극대화
                loop = asyncio.get_running_loop()
                emb = await loop.run_in_executor(None, get_embedding, img_array)
                
                if emb is not None:
                    celeb_names.append(celeb["name"])
                    embeddings_list.append(emb)
                    print(f"✅ {celeb['name']} 벡터 로드 완료")
                else:
                    print(f"❌ {celeb['name']} 얼굴 인식 실패")
            except Exception as e:
                print(f"❌ {celeb['name']} 다운로드/처리 중 에러: {e}")

    # Senior's Tip 3: for루프 순회가 아닌, (N, D) 2D 행렬 형태로 정규화하여 
    # 내적(Dot Product) 연산을 통해 O(1) in numpy vectorization 으로 초고속 코사인 유사도 측정을 수행합니다.
    if embeddings_list:
        matrix = np.array(embeddings_list)
        # Cosine 유사도를 위해 미리 Norm으로 나눠 단위 벡터(Unit Vector)로 만듭니다.
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        celeb_matrix = matrix / norms
    
    print(f"🔥 서버 초기화 완료! 저장된 메모리 DB 갯수: {len(celeb_names)}")

@app.post("/find_lookalike")
async def find_lookalike(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="업로드된 파일이 이미지 형식이 아닙니다.")
    
    if celeb_matrix is None or len(celeb_names) == 0:
        raise HTTPException(status_code=500, detail="메모리에 비교할 유명인 데이터가 존재하지 않습니다.")

    # 1. 파일 메모리에서 직접 읽기 (No-Storage Strategy: Bytes 메모리 읽기 -> numpy BGR 변환)
    content = await file.read()
    np_arr = np.frombuffer(content, np.uint8)
    img_array = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_array is None:
        raise HTTPException(status_code=400, detail="이미지를 디코딩할 수 없습니다.")

    # 2. 업로드된 이미지에서 임베딩 추출
    loop = asyncio.get_running_loop()
    user_emb = await loop.run_in_executor(None, get_embedding, img_array)

    if user_emb is None:
        return {"match": False, "message": "업로드한 사진에서 얼굴을 인식하지 못했습니다."}

    # 3. 브로드캐스팅 행렬 연산으로 코사인 유사도 1ms 이내 전체 탐색
    user_norm = np.linalg.norm(user_emb)
    user_emb_normalized = user_emb / user_norm
    
    # 두 벡터군 모두 단위 벡터이므로, 내적(Dot Product) 연산 결과가 곧 코사인 유사도입니다.
    similarities = np.dot(celeb_matrix, user_emb_normalized)
    
    best_idx = np.argmax(similarities)
    best_score = similarities[best_idx]
    best_match = celeb_names[best_idx]

    return {
        "match": True,
        "name": best_match,
        "score": float(best_score),  # 1.0에 가까울 수록 닮음
        "detail": f"Vectorized Cosine Similarity 측정 완료 (Score: {best_score:.4f})"
    }
