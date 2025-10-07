import firebase_admin
from firebase_admin import credentials, firestore

# Khởi tạo Firebase Admin với file service account
cred = credentials.Certificate("diet-tracking\chat_box\diet-tracking-f365a-firebase-adminsdk-fbsvc-837f36103f.json")  # Đổi đường dẫn file JSON của bạn
firebase_admin.initialize_app(cred)

db = firestore.client()

def get_user_info(uid):
    doc_ref = db.collection("users").document(uid)
    doc = doc_ref.get()
    if doc.exists:
        print(f"Thông tin người dùng {uid}:")
        print(doc.to_dict())
    else:
        print(f"Không tìm thấy người dùng với uid: {uid}")

if __name__ == "__main__":
    uid = input("Nhập uid người dùng: ")
    get_user_info(uid)