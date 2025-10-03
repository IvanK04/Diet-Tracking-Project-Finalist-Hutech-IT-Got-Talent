import google.generativeai as genai
import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI
from pydantic import BaseModel

#---api_key---#
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#---api_key---#

#---model_database_config---#
pc = Pinecone(api_key=PINECONE_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
model_gemini = genai.GenerativeModel('gemini-2.5-flash-lite')
model_llm = SentenceTransformer('all-MiniLM-L12-v2')
#---model_database_config---#

#--FastAPI--#
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#--FastAPI--#

#--pinecone--#
index_name = "nutrition-db"
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=384,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
index = pc.Index(index_name)

def get_embedding(text: str):
    return model_llm.encode(text, convert_to_numpy=True).tolist()

def extract_filter(user_query):
    filter = {}
    if "ít calo" in user_query.lower() or "giảm cân" in user_query.lower():
        filter["tags"] = {"$in": ["giảm cân"]}
        filter["calories"] = {"$lte": 350}
    if "tăng cân" in user_query.lower():
        filter["tags"] = {"$in": ["tăng cân"]}
        filter["calories"] = {"$gte": 300}
    if "nhiều protein" in user_query.lower():
        filter["tags"] = {"$in": ["nhiều protein"]}
        filter["protein"] = {"$gte": 25}
    return filter
#--pinecone--#

#--schema--#
class ChatRequest(BaseModel):
    prompt: str
    user: dict   # <-- nhận object user từ Firestore (Dart gửi sang)
#--schema--#

def build_system_prompt():
    return """
Bạn là chuyên gia dinh dưỡng Việt Nam với giọng điệu như 1 đầu bếp chuyên nghiệp và cách nói chuyện đi thẳng vào vấn đề nhưng nhẹ nhàng.

Luật bắt buộc:
- Tuyệt đối không nhắc lại thông tin **tuổi, chiều cao, cân nặng, bệnh lí, dị ứng** trong bất kỳ trường hợp nào.
- Chỉ trả lời câu hỏi liên quan đến dinh dưỡng. Nếu người dùng hỏi ngoài chủ đề thì từ chối.
- Nếu người dùng đề xuất món ăn liên quan đến bệnh lí hoặc dị ứng của họ thì phải ngăn lại và giải thích lý do.
- Món ăn phải thực tế (tìm được ở tiệm hoặc tự làm) và phù hợp với bối cảnh Sài Gòn.
- Nếu người dùng yêu cầu công thức thì đưa công thức chi tiết.
- Giải thích ngắn lý do lựa chọn từng món ăn kèm theo thông tin dinh dưỡng của món ăn đó như calo, protein, carb và fat.
"""

def build_user_prompt(user_data, user_prompt):
    return f"""
Dựa trên thông tin sau:
- Tuổi: {user_data.get("age", "unknown")}
- Chiều cao: {user_data.get("height", "unknown")} cm
- Cân nặng: {user_data.get("weight", "unknown")} kg
- Bệnh lý: {user_data.get("disease", "none")}
- Dị ứng: {user_data.get("allergy", "none")}
- Mục tiêu: {user_data.get("goal", "none")}

Người dùng hỏi: {user_prompt}
"""

@app.post("/chat")
async def chatbox(request: ChatRequest):
    user_data = request.user
    query_text = request.prompt

    # 🔍 Search Pinecone
    filters = extract_filter(query_text)
    query_embedding = get_embedding(query_text)
    results = index.query(
        vector=query_embedding,
        top_k=3,
        include_metadata=True,
        filter=filters
    )

    # Chuẩn bị ngữ cảnh
    retrieved_docs = []
    for match in results.matches:
        meta = match["metadata"]
        retrieved_docs.append(
            f"{meta['title']} - Nguyên liệu: {', '.join(meta['ingredients'])}\n"
            f"Cách nấu: {meta['how-to-cook']}\n"
            f"Tags: {', '.join(meta['tags'])}\n"
            f"Calories: {meta['calories']} - Protein: {meta['protein']}"
        )

    context_text = "\n".join(retrieved_docs)

    # Prompt cho Gemini
    full_prompt = (
        build_system_prompt()
        + "\n\nNgữ cảnh từ CSDL món ăn\n"
        + context_text
        + "\n\n"
        + build_user_prompt(user_data, query_text)
    )

    chat = model_gemini.start_chat(history=[])
    response = chat.send_message(full_prompt)

    return {"reply": response.text}