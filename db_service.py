import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================================================================
# SME Financial Management System - Database Service (Firebase Ready Architecture)
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "finance.db")
FIREBASE_KEY_PATH = os.path.join(BASE_DIR, "firebase_credentials.json")

# ตรวจสอบว่าเปิดใช้งาน Firebase หรือไม่ (เปิดใช้งานเมื่อมีไฟล์ firebase_credentials.json)
USE_FIREBASE = os.path.exists(FIREBASE_KEY_PATH)
_firestore_db = None

if USE_FIREBASE:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        _firestore_db = firestore.client()
        print(" Connected to Google Firebase Firestore successfully.")
    except Exception as e:
        print(f"⚠️ Firebase initialization skipped or failed: {e}. Falling back to SQLite.")
        USE_FIREBASE = False


# ==============================================================================
# SQLite Driver Implementation (Local & PythonAnywhere Default)
# ==============================================================================

def get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """สร้างตารางและดัชนีความปลอดภัยในฐานข้อมูล"""
    if USE_FIREBASE:
        print("Firebase Firestore is active: Collections 'users' and 'transactions' are schema-less.")
        return

    conn = get_sqlite_conn()
    cursor = conn.cursor()

    # ตารางจัดเก็บบัญชีผู้ใช้ (Users)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            business_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # ตารางธุรกรรม มี user_id ชัดเจนเพื่อความปลอดภัยในการแบ่งแยกสิทธิ์ (Data Scoping)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trans_date TEXT NOT NULL,
            trans_time TEXT NOT NULL DEFAULT '12:00',
            payment_method TEXT NOT NULL DEFAULT 'โอนเงิน',
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # ตรวจสอบคอลัมน์ใหม่ (trans_time, payment_method) สำหรับฐานข้อมูลเดิม
    cursor.execute("PRAGMA table_info(transactions)")
    col_names = [col["name"] for col in cursor.fetchall()]
    if "trans_time" not in col_names:
        cursor.execute("ALTER TABLE transactions ADD COLUMN trans_time TEXT NOT NULL DEFAULT '12:00'")
    if "payment_method" not in col_names:
        cursor.execute("ALTER TABLE transactions ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'โอนเงิน'")

    # ตารางคำขอความช่วยเหลือ / แจ้งปัญหาถึงเจ้าของระบบ (Support Tickets)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            business_name TEXT NOT NULL,
            topic TEXT NOT NULL,
            message TEXT NOT NULL,
            contact_info TEXT,
            status TEXT DEFAULT 'รอดำเนินการ',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # ดัชนีความเร็วและความปลอดภัยในการค้นหาตาม user_id (Anti-leak index)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_user ON transactions(user_id, trans_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user ON support_tickets(user_id)")

    # ตรวจสอบบัญชี Demo เริ่มต้น
    cursor.execute("SELECT COUNT(*) AS count FROM users")
    if cursor.fetchone()["count"] == 0:
        demo_pwd_hash = generate_password_hash("demo1234")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO users (username, password_hash, business_name, created_at)
            VALUES (?, ?, ?, ?)
        """, ("demo", demo_pwd_hash, "ร้านค้าตัวอย่าง (SME Demo)", now_str))

    conn.commit()
    conn.close()


# ==============================================================================
# User Management & Authentication (สมัครสมาชิก & เข้าสู่ระบบ)
# เส้นทางข้อมูล:
# Firebase  -> /users/{userId}
# SQLite    -> users WHERE id = ?
# ==============================================================================

def create_user(username, password, business_name):
    """
    สร้างบัญชีผู้ใช้ใหม่
    - เข้ารหัสรหัสผ่านด้วย Password Hash เพื่อความปลอดภัย
    - ตรวจสอบชื่อผู้ใช้ซ้ำ
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    password_hash = generate_password_hash(password)

    if USE_FIREBASE:
        # ตรวจสอบชื่อผู้ใช้ซ้ำใน Firebase
        users_ref = _firestore_db.collection("users")
        query = users_ref.where("username", "==", username).limit(1).stream()
        if any(query):
            return None, "ชื่อผู้ใช้งานนี้มีอยู่ในระบบแล้ว กรุณาใช้ชื่ออื่น"

        # เพิ่มเอกสารใหม่ลง Path: /users/{userId}
        new_doc_ref = users_ref.document()
        user_data = {
            "username": username,
            "password_hash": password_hash,
            "business_name": business_name,
            "created_at": now_str
        }
        new_doc_ref.set(user_data)
        user_data["id"] = new_doc_ref.id
        return user_data, None
    else:
        conn = get_sqlite_conn()
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.close()
            return None, "ชื่อผู้ใช้งานนี้มีอยู่ในระบบแล้ว กรุณาใช้ชื่ออื่น"

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password_hash, business_name, created_at)
            VALUES (?, ?, ?, ?)
        """, (username, password_hash, business_name, now_str))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {"id": user_id, "username": username, "business_name": business_name}, None


def authenticate_user(username, password):
    """ตรวจสอบชื่อผู้ใช้และรหัสผ่าน"""
    if USE_FIREBASE:
        users_ref = _firestore_db.collection("users")
        docs = list(users_ref.where("username", "==", username).limit(1).stream())
        if not docs:
            return None
        user_data = docs[0].to_dict()
        user_data["id"] = docs[0].id
        if check_password_hash(user_data["password_hash"], password):
            return user_data
        return None
    else:
        conn = get_sqlite_conn()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            return dict(user)
        return None


# ==============================================================================
# Transaction Management (บันทึก แก้ไข ลบ รายรับ-รายจ่าย)
# เส้นทางข้อมูลที่ปลอดภัยกันการแฮ็กข้ามร้าน (Anti-Hack Scoped Path):
# Firebase  -> /users/{userId}/transactions/{transId}
# SQLite    -> transactions WHERE user_id = ? AND id = ?
# ==============================================================================

def add_transaction(user_id, trans_date, trans_type, category, amount, note="", trans_time=None, payment_method="โอนเงิน"):
    """บันทึกรายการรายรับ-รายจ่ายใหม่ พร้อมเวลาและช่องทางชำระเงิน"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not trans_time:
        trans_time = datetime.now().strftime("%H:%M")
    if not payment_method:
        payment_method = "โอนเงิน"

    if USE_FIREBASE:
        # บันทึกลง Path: /users/{userId}/transactions/{transId}
        trans_ref = _firestore_db.collection("users").document(str(user_id)).collection("transactions").document()
        trans_data = {
            "trans_date": trans_date,
            "trans_time": trans_time,
            "payment_method": payment_method,
            "type": trans_type,
            "category": category,
            "amount": float(amount),
            "note": note,
            "created_at": now_str
        }
        trans_ref.set(trans_data)
        trans_data["id"] = trans_ref.id
        return trans_data
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (user_id, trans_date, trans_time, payment_method, type, category, amount, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, trans_date, trans_time, payment_method, trans_type, category, float(amount), note, now_str))
        trans_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": trans_id, "amount": amount}


def get_all_user_transactions_with_balance(user_id):
    """
    ดึงรายการธุรกรรมทั้งหมดและคำนวณยอดเงินคงเหลือสะสม (Running Balance / สเตทเมนต์)
    ตามลำดับเวลาที่เกิดขึ้นจริง
    """
    if USE_FIREBASE:
        trans_ref = _firestore_db.collection("users").document(str(user_id)).collection("transactions")
        query = trans_ref.order_by("trans_date", direction=firestore.Query.ASCENDING).order_by("trans_time", direction=firestore.Query.ASCENDING)
        items = []
        for doc in query.stream():
            d = doc.to_dict()
            d["id"] = doc.id
            items.append(d)
    else:
        conn = get_sqlite_conn()
        query = "SELECT * FROM transactions WHERE user_id = ? ORDER BY trans_date ASC, trans_time ASC, id ASC"
        items = [dict(r) for r in conn.execute(query, (user_id,)).fetchall()]
        conn.close()

    # คำนวณ Running Balance ตามลำดับเวลา
    current_balance = 0.0
    for item in items:
        amt = float(item["amount"])
        if item["type"] == "income":
            current_balance += amt
        else:
            current_balance -= amt
        item["running_balance"] = current_balance
        if not item.get("trans_time"):
            item["trans_time"] = "12:00"
        if not item.get("payment_method"):
            item["payment_method"] = "โอนเงิน"

    return items


def get_transactions(user_id, current_type="all", start_date="", end_date="", payment_method="all"):
    """ดึงรายการธุรกรรมพร้อมยอดคงเหลือสะสม เรียงจากล่าสุดไปอดีต"""
    all_items = get_all_user_transactions_with_balance(user_id)

    filtered = []
    for item in all_items:
        if current_type in ["income", "expense"] and item["type"] != current_type:
            continue
        if payment_method != "all" and item.get("payment_method") != payment_method:
            continue
        if start_date and item["trans_date"] < start_date:
            continue
        if end_date and item["trans_date"] > end_date:
            continue
        filtered.append(item)

    # เรียงลำดับจากล่าสุดไปหาอดีตสำหรับหน้าประวัติรายการ
    filtered.sort(key=lambda x: (x["trans_date"], x.get("trans_time", "00:00"), x["id"]), reverse=True)
    return filtered


def get_statement(user_id, start_date="", end_date="", payment_method="all"):
    """
    ดึงข้อมูลสเตทเมนต์บัญชีการเงิน (Financial Statement) อย่างเป็นทางการ
    พร้อมยอดเงินยกมา (Opening Balance), ยอดเข้า, ยอดออก และยอดคงเหลือสุทธิ
    """
    all_items = get_all_user_transactions_with_balance(user_id)

    opening_balance = 0.0
    period_inflow = 0.0
    period_outflow = 0.0
    statement_rows = []

    for item in all_items:
        tdate = item["trans_date"]
        amt = float(item["amount"])

        # คำนวณยอดเงินยกมาก่อนช่วงเวลาเริ่มต้น
        if start_date and tdate < start_date:
            if item["type"] == "income":
                opening_balance += amt
            else:
                opening_balance -= amt
            continue

        # คัดกรองช่วงเวลาสิ้นสุด
        if end_date and tdate > end_date:
            continue

        if payment_method != "all" and item.get("payment_method") != payment_method:
            continue

        if item["type"] == "income":
            period_inflow += amt
        else:
            period_outflow += amt

        statement_rows.append(item)

    # จัดลำดับสเตทเมนต์แบบบันทึกสมุดบัญชี (เรียงจากล่าสุด หรือ เก่าไปใหม่)
    statement_rows.sort(key=lambda x: (x["trans_date"], x.get("trans_time", "00:00"), x["id"]), reverse=True)
    closing_balance = opening_balance + period_inflow - period_outflow

    return {
        "opening_balance": opening_balance,
        "period_inflow": period_inflow,
        "period_outflow": period_outflow,
        "closing_balance": closing_balance,
        "transactions": statement_rows,
        "total_count": len(statement_rows)
    }


def get_transaction(user_id, trans_id):
    """ดึงรายการเดียว โดยตรวจสอบสิทธิ์ user_id ร่วมด้วยเสมอ (Anti-Hack check)"""
    if USE_FIREBASE:
        doc = _firestore_db.collection("users").document(str(user_id)).collection("transactions").document(str(trans_id)).get()
        if doc.exists:
            d = doc.to_dict()
            d["id"] = doc.id
            return d
        return None
    else:
        conn = get_sqlite_conn()
        row = conn.execute("SELECT * FROM transactions WHERE id = ? AND user_id = ?", (trans_id, user_id)).fetchone()
        conn.close()
        return dict(row) if row else None


def update_transaction(user_id, trans_id, trans_date, trans_type, category, amount, note="", trans_time="12:00", payment_method="โอนเงิน"):
    """แก้ไขรายการโดยตรวจสอบ user_id ป้องกันผู้ไม่หวังดีส่ง ID อื่นมาแก้"""
    if not trans_time:
        trans_time = "12:00"
    if not payment_method:
        payment_method = "โอนเงิน"

    if USE_FIREBASE:
        doc_ref = _firestore_db.collection("users").document(str(user_id)).collection("transactions").document(str(trans_id))
        doc_ref.update({
            "trans_date": trans_date,
            "trans_time": trans_time,
            "payment_method": payment_method,
            "type": trans_type,
            "category": category,
            "amount": float(amount),
            "note": note,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return True
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions 
            SET trans_date = ?, trans_time = ?, payment_method = ?, type = ?, category = ?, amount = ?, note = ?
            WHERE id = ? AND user_id = ?
        """, (trans_date, trans_time, payment_method, trans_type, category, float(amount), note, trans_id, user_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0


def delete_transaction(user_id, trans_id):
    """ลบรายการเฉพาะที่เป็นของ User นั้นๆ"""
    if USE_FIREBASE:
        _firestore_db.collection("users").document(str(user_id)).collection("transactions").document(str(trans_id)).delete()
        return True
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (trans_id, user_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0


# ==============================================================================
# Dashboard & Analytics Summary
# ==============================================================================

def get_dashboard_data(user_id):
    """ประมวลผลข้อมูลแดชบอร์ด รายรับรวม รายจ่ายรวม กำไร และสัดส่วนหมวดหมู่"""
    items = get_transactions(user_id)

    total_income = sum(item["amount"] for item in items if item["type"] == "income")
    total_expense = sum(item["amount"] for item in items if item["type"] == "expense")
    net_balance = total_income - total_expense

    # รวมสัดส่วนรายจ่ายแยกตามหมวดหมู่
    cat_totals = {}
    for item in items:
        if item["type"] == "expense":
            cat = item["category"]
            cat_totals[cat] = cat_totals.get(cat, 0.0) + float(item["amount"])

    # เรียงลำดับจากมากไปน้อย
    sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
    expense_cat_labels = [c[0] for c in sorted_cats]
    expense_cat_values = [round(c[1], 2) for c in sorted_cats]

    recent_transactions = items[:5]

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_balance": net_balance,
        "expense_cat_labels": expense_cat_labels,
        "expense_cat_values": expense_cat_values,
        "recent_transactions": recent_transactions
    }


def get_report_data(user_id, period_type, selected_month, selected_date, selected_year):
    """ประมวลผลรายงานสรุปตามช่วงเวลา"""
    all_items = get_transactions(user_id)

    filtered_items = []
    for item in all_items:
        tdate = item["trans_date"]
        if period_type == "monthly" and selected_month:
            if tdate.startswith(selected_month):
                filtered_items.append(item)
        elif period_type == "daily" and selected_date:
            if tdate == selected_date:
                filtered_items.append(item)
        elif period_type == "yearly" and selected_year:
            if tdate.startswith(selected_year):
                filtered_items.append(item)
        elif period_type == "all":
            filtered_items.append(item)

    period_income = sum(item["amount"] for item in filtered_items if item["type"] == "income")
    period_expense = sum(item["amount"] for item in filtered_items if item["type"] == "expense")
    period_profit = period_income - period_expense

    # สรุปรายรับแยกตามหมวดหมู่
    inc_cats = {}
    for item in filtered_items:
        if item["type"] == "income":
            c = item["category"]
            inc_cats[c] = inc_cats.get(c, 0.0) + float(item["amount"])
    income_by_category = sorted(inc_cats.items(), key=lambda x: x[1], reverse=True)

    # สรุปรายจ่ายแยกตามหมวดหมู่
    exp_cats = {}
    for item in filtered_items:
        if item["type"] == "expense":
            c = item["category"]
            exp_cats[c] = exp_cats.get(c, 0.0) + float(item["amount"])
    expense_by_category = sorted(exp_cats.items(), key=lambda x: x[1], reverse=True)

    # สรุปแยกตามไทม์ไลน์
    timeline_dict = {}
    group_len = 10 if period_type == "monthly" else 7  # YYYY-MM-DD vs YYYY-MM
    for item in filtered_items:
        key = item["trans_date"][:group_len]
        if key not in timeline_dict:
            timeline_dict[key] = {"income": 0.0, "expense": 0.0}
        if item["type"] == "income":
            timeline_dict[key]["income"] += float(item["amount"])
        else:
            timeline_dict[key]["expense"] += float(item["amount"])

    timeline_rows = []
    for k in sorted(timeline_dict.keys(), reverse=True):
        inc = timeline_dict[k]["income"]
        exp = timeline_dict[k]["expense"]
        timeline_rows.append({
            "period_label": k,
            "income": inc,
            "expense": exp,
            "net": inc - exp
        })

    return {
        "period_income": period_income,
        "period_expense": period_expense,
        "period_profit": period_profit,
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category,
        "timeline_rows": timeline_rows
    }


# ==============================================================================
# Support & Help Request Management (ระบบช่วยเหลือและแจ้งปัญหาถึงเจ้าของระบบ)
# เส้นทางข้อมูล:
# Firebase  -> /users/{userId}/support_tickets/{ticketId}
# SQLite    -> support_tickets WHERE user_id = ?
# ==============================================================================

def create_support_ticket(user_id, business_name, topic, message, contact_info=""):
    """บันทึกคำขอความช่วยเหลือหรือแจ้งปัญหาถึงเจ้าของระบบ"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if USE_FIREBASE:
        ticket_ref = _firestore_db.collection("users").document(str(user_id)).collection("support_tickets").document()
        ticket_data = {
            "business_name": business_name,
            "topic": topic,
            "message": message,
            "contact_info": contact_info,
            "status": "รอดำเนินการ",
            "created_at": now_str
        }
        ticket_ref.set(ticket_data)
        ticket_data["id"] = ticket_ref.id
        return ticket_data
    else:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_tickets (user_id, business_name, topic, message, contact_info, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'รอดำเนินการ', ?)
        """, (user_id, business_name, topic, message, contact_info, now_str))
        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": ticket_id, "topic": topic}


def get_user_tickets(user_id):
    """ดึงประวัติการแจ้งปัญหาของ User นี้"""
    if USE_FIREBASE:
        ticket_ref = _firestore_db.collection("users").document(str(user_id)).collection("support_tickets")
        query = ticket_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
        items = []
        for doc in query.stream():
            d = doc.to_dict()
            d["id"] = doc.id
            items.append(d)
        return items
    else:
        conn = get_sqlite_conn()
        query = "SELECT * FROM support_tickets WHERE user_id = ? ORDER BY id DESC"
        rows = [dict(r) for r in conn.execute(query, (user_id,)).fetchall()]
        conn.close()
        return rows

