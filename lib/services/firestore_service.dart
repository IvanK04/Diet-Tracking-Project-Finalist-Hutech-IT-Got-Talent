import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

/// Service để quản lý user và gửi dữ liệu cho chatbox (Gemini qua FastAPI)
class FirestoreService {
  // Collections
  static const String _usersCollection = 'users';
  static const String _testCollection = 'test';

  final FirebaseFirestore _firestore;

  FirestoreService({FirebaseFirestore? firestore})
    : _firestore = firestore ?? FirebaseFirestore.instance;

  FirebaseFirestore get firestore => _firestore;

  /// 🔌 Kiểm tra kết nối Firestore
  Future<bool> testConnection() async {
    try {
      await _firestore.collection(_testCollection).limit(1).get();
      return true;
    } catch (e) {
      return false;
    }
  }

  /// 📥 Lấy tất cả users
  Stream<QuerySnapshot> getUsers() {
    return _firestore.collection(_usersCollection).snapshots();
  }

  /// 📥 Lấy user theo ID
  Future<DocumentSnapshot> getUserById(String userId) {
    return _firestore.collection(_usersCollection).doc(userId).get();
  }

  /// ❌ Xóa user
  Future<void> deleteUser(String userId) {
    return _firestore.collection(_usersCollection).doc(userId).delete();
  }

  /// 🔍 Kiểm tra user có tồn tại
  Future<bool> userExists(String userId) async {
    final doc = await _firestore.collection(_usersCollection).doc(userId).get();
    return doc.exists;
  }

  /// 👤 Lấy thông tin user đang đăng nhập
  Future<Map<String, dynamic>?> getCurrentUserData() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) return null;

    final doc = await _firestore
        .collection(_usersCollection)
        .doc(user.uid)
        .get();
    return doc.data();
  }

  /// 💬 Gửi prompt + thông tin user tới API (FastAPI -> Gemini)
  Future<String> sendMessageToChatbox(String prompt) async {
    final userData = await getCurrentUserData();
    if (userData == null) {
      throw Exception(
        "Chưa đăng nhập hoặc không tìm thấy user trong Firestore",
      );
    }

    // API backend (FastAPI endpoint)
    final url = Uri.parse(
      "http://localhost:8000/chat",
    ); // đổi thành server thật

    final body = jsonEncode({
      "prompt": prompt,
      "age": userData["age"],
      "height": userData["height"],
      "weight": userData["weight"],
      "disease": userData["disease"],
      "goal": userData["goal"],
    });

    final response = await http.post(
      url,
      headers: {"Content-Type": "application/json"},
      body: body,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data["reply"]; // backend phải trả {"reply": "..."}
    } else {
      throw Exception("Lỗi chatbox: ${response.statusCode} - ${response.body}");
    }
  }
}
