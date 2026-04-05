import os
import cv2
import httpx
import asyncio
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from deepface import DeepFace

app = FastAPI(title="Lightweight Face-Similarity API")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_home():
    return FileResponse("static/index.html")

# 유명인 이름 리스트 (여기에 이름을 추가하면 서버 시작 시 자동으로 위키백과 사진을 긁어옵니다!)
CELEB_NAMES = [
    # 🎭 대한민국 배우/엔터테이너
    "이정재", "공유 (배우)", "송강호", "황정민", "마동석", "유재석", "강호동", "신동엽", 
    "이병헌", "하정우", "조승우", "최민식", "박서준", "송중기", "김수현 (1988년)", "현빈", "원빈",
    "정우성", "전지현", "송혜교", "김태희", "손예진", "한소희", "김고은", "박보영", "아이유", "수지 (1994년)",
    "김혜수", "공효진", "박은빈", "이영애", "박보검", "이민호", "이제훈", "조인성", "류승룡",
    "유아인", "박해일", "차은우", "유해진", "류준열", "유연석", "조정석", "강동원",
    
    # 🎤 대한민국 아이돌 및 가수
    "RM (가수)", "진 (가수)", "슈가 (방탄소년단)", "제이홉", "지민 (방탄소년단)", "뷔 (가수)", "정국",
    "지수 (1995년)", "제니 (배우)", "로제 (가수)", "리사 (가수)",
    "태연", "윤아 (1990년)", "임영웅", "장범준", "박효신", "나얼", "싸이", "지드래곤",
    "카리나 (가수)", "윈터 (가수)", "장원영", "안유진", "카이 (가수)", "백현", "이효리",

    # ⚽ 대한민국 스포츠 스타 및 감독
    "손흥민", "김연아", "박지성", "류현진", "추신수", "이강인", "김민재", "서장훈", "안정환", 
    "이승엽", "박찬호", "홍명보", "거스 히딩크",

    # 🎬 글로벌 할리우드 배우 및 유명인
    "톰 크루즈", "브래드 피트", "레오나르도 디카프리오", "로버트 다우니 주니어", "크리스 에반스",
    "스칼렛 요한슨", "마고 로비", "앤 해서웨이", "엠마 왓슨", "톰 홀랜드", "키아누 리브스",
    "드웨인 존슨", "라이언 고슬링", "휴 잭맨", "나탈리 포트만",

    # 💼 비즈니스/IT 거물 및 위인
    "일론 머스크", "빌 게이츠", "마크 저커버그", "스티브 잡스", "워런 버핏", "봉준호", 
    "아인슈타인", "마리 퀴리", "아이작 뉴턴", "에이브러햄 링컨", "윈스턴 처칠", "세종대왕", "이순신"
]

# Senior's Tip 1: "SFace"는 모델 크기가 약 40MB에 불과해 메모리와 초기 구동 속도를 크게 아낄 수 있는 경량화 모델입니다.
MODEL_NAME = "SFace"

# 글로벌 메모리 저장소
celeb_names = []
celeb_urls = {}
celeb_matrix = None  # (N, D) 형태의 numpy array로 벡터화 연산을 위해 사용

async def fetch_wiki_image_url(client: httpx.AsyncClient, name: str) -> str:
    # 위키백과 API를 호출하여 해당 인물의 프로필 썸네일(500px) 주소를 자동으로 찾아냅니다.
    url = f"https://ko.wikipedia.org/w/api.php?action=query&titles={name}&prop=pageimages&format=json&pithumbsize=500"
    try:
        resp = await client.get(url)
        pages = resp.json().get("query", {}).get("pages", {})
        for page_id, info in pages.items():
            if "thumbnail" in info:
                return info["thumbnail"]["source"]
    except Exception:
        pass
    return None

async def download_image_as_numpy(client: httpx.AsyncClient, url: str) -> np.ndarray:
    # 위키백과 같은 사이트는 봇 접근을 막아서 에러(403)가 나기 때문에, 일반 브라우저인 척 속이는 헤더가 필요합니다.
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = await client.get(url, headers=headers)
    response.raise_for_status()
    image_bytes = response.content
    np_arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
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
    print("🚀 시작: 유명인 위키백과 이미지 자동 탐색 및 임베딩 벡터화...")
    
    embeddings_list = []
    
    # 봇 차단 방지용 헤더
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LightweightFaceAPI/1.0"}
    async with httpx.AsyncClient(headers=headers) as client:
        for name in CELEB_NAMES:
            try:
                # 1. 이름으로 위키백과 이미지 주소 자동 검색
                img_url = await fetch_wiki_image_url(client, name)
                if not img_url:
                    print(f"⚠️ {name}의 위키백과 프로필 사진을 찾을 수 없습니다. (이름이 정확한지 확인하세요)")
                    continue

                # 2. 이미지 다운로드 및 OpenCV 변환
                img_array = await download_image_as_numpy(client, img_url)
                
                # 3. 비동기 스레드 풀에서 AI 얼굴 인식 및 추출
                loop = asyncio.get_running_loop()
                emb = await loop.run_in_executor(None, get_embedding, img_array)
                
                if emb is not None:
                    clean_name = name.split(" (")[0]  # "공유 (배우)" -> "공유" 로 깔끔하게 정리
                    celeb_names.append(clean_name)
                    celeb_urls[clean_name] = img_url  # 프론트 화면 표출용으로 저장
                    embeddings_list.append(emb)
                    print(f"✅ {clean_name} 프로필 이미지 & 벡터 로드 완료! (from 위키백과)")
                else:
                    print(f"❌ {name}의 얼굴을 인식할 수 없습니다. (전신 사진이거나 얼굴이 작음)")
                
                # [중요] 위키미디어(Wikipedia) 이미지 서버에서 짧은 시간에 너무 많이 다운받으면
                # 해킹 공격으로 간주하고 429(Too Many Requests) 차단을 먹이기 때문에 0.5초간 휴식합니다.
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ {name} 처리 중 에러: {e}")

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
    
    # 0~1 사이의 내적값을 퍼센트로 보기 좋게 변환
    similarity_percent = round(float(best_score) * 100, 2)

    return JSONResponse({
        "lookalike": best_match,
        "image_url": celeb_urls.get(best_match, ""),
        "similarity_percent": similarity_percent
    })
