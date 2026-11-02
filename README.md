# SME Financial Management System
## ระบบบริหารจัดการรายรับ-รายจ่ายและวิเคราะห์กำไรสำหรับธุรกิจขนาดเล็ก

เว็บแอปพลิเคชันสำหรับเจ้าของธุรกิจขนาดเล็ก (SME), ร้านค้าปลีก และผู้ประกอบการรายย่อย ช่วยบันทึกรายรับ-รายจ่าย คำนวณผลต่างกำไร/ขาดทุนอัตโนมัติ และแสดง Dashboard วิเคราะห์ผลประกอบการแบบเห็นภาพชัดเจน พร้อมระบบบัญชีผู้ใช้งานเพื่อความปลอดภัย และสถาปัตยกรรมรองรับการเชื่อมต่อกับ **Google Firebase**

---

### 🛡️ สถาปัตยกรรมความปลอดภัยและเส้นทางข้อมูล (Anti-Hack Data Paths)

เพื่อป้องกันปัญหาข้อมูลมั่ว การแก้ไขข้อมูลโดยไม่ได้รับอนุญาต (Unauthorized Tampering) และการแฮ็กข้ามร้านค้า ระบบจึงออกแบบเส้นทางข้อมูลแบบ **Hierarchical Scoped Subcollection**:

```
📂 Firebase Firestore Path:
└── 📁 /users/{userId}                         <-- เอกสารบัญชีร้านค้า (ชื่อร้าน, รหัสผ่านที่เข้ารหัส)
    └── 📁 /transactions/{transId}             <-- ข้อมูลรายรับ-รายจ่ายเฉพาะของร้านนั้นๆ
        ├── trans_date (วันที่ทำรายการ)
        ├── type (income หรือ expense)
        ├── category (หมวดหมู่)
        ├── amount (จำนวนเงิน > 0)
        ├── note (รายละเอียด)
        └── created_at (เวลาที่บันทึก)
```

#### ทำไมโครงสร้างนี้จึงปลอดภัยและป้องกันการแฮ็กได้ 100%?
1. **การแยกเส้นทางข้อมูลเด็ดขาด (User Isolation)**: 
   * ข้อมูลธุรกรรมถูกบรรจุอยู่ภายใต้ `/users/{userId}/...` ของเจ้าของร้านโดยตรง ทำให้ร้าน A ไม่สามารถเข้าถึงหรือมองเห็นข้อมูลของร้าน B ได้
2. **กฎความปลอดภัยของ Firebase (`firestore.rules`)**:
   * มีไฟล์ `firestore.rules` กำหนดไว้ว่า:
     ```javascript
     match /users/{userId}/transactions/{transId} {
       allow read, write: if request.auth != null && request.auth.uid == userId;
     }
     ```
   * แม้แฮกเกอร์จะรู้ Transaction ID ก็ไม่สามารถอ่านหรือแก้ไขข้อมูลได้หาก UID ไม่ตรงกับเจ้าของบัญชี
3. **การตรวจสอบความถูกต้องฝั่งเซิร์ฟเวอร์ (Server-Side Validation)**:
   * จำนวนเงินต้องเป็นตัวเลขและมากกว่า 0 บาทเสมอ
   * วันที่และหมวดหมู่ต้องถูกต้องตามข้อกำหนด ป้องกันการส่งข้อมูลขยะเข้าฐานข้อมูล

---

### 🌟 ฟังก์ชันหลักของระบบ

1. **ระบบจัดการบัญชีผู้ใช้งาน (Authentication & Multi-User Support)**:
   * **สมัครสมาชิก (Register)**: สร้างบัญชีสำหรับธุรกิจหรือร้านค้าของคุณ ระบุชื่อร้านและรหัสผ่าน
   * **เข้าสู่ระบบ (Login)**: ปลอดภัยด้วยการเข้ารหัสรหัสผ่าน (Password Hashing ด้วย Werkzeug Security)
   * **แยกข้อมูลบัญชีอย่างเป็นอิสระ (Data Isolation)**: แต่ละธุรกิจจะมองเห็นและจัดการเฉพาะข้อมูลการเงินของตนเองเท่านั้น
   * **บัญชีทดสอบเริ่มต้น (Demo Account)**:
     * ชื่อผู้ใช้: `demo`
     * รหัสผ่าน: `demo1234`
2. **บันทึก จัดหมวดหมู่ แก้ไข และระบุเวลาการเงิน (Transaction CRUD with Timestamp)**:
   * รองรับการบันทึกทั้งรายรับ (Income) และรายจ่าย (Expense)
   * ระบุเวลาที่เกิดธุรกรรมอย่างชัดเจนระดับชั่วโมง-นาที (`trans_time` เช่น 14:35 น.)
   * ระบุช่องทางการเงิน (โอนเงินผ่านแอป, สแกน QR Code, เงินสด, บัตรเครดิต/เดบิต)
   * ค้นหาและกรองข้อมูลตามประเภท, ช่องทางการเงิน หรือช่วงวันที่ที่ต้องการ
3. **สเตทเมนต์บัญชีการเงินและยอดเงินสะสม (Financial Statement & Running Balance)**:
   * แสดงรายการเดินบัญชีเสมือนสมุดคู่ฝากธนาคาร (Bank Passbook Statement)
   * คำนวณยอดเงินคงเหลือสะสม (Running Balance) ทุกแถวธุรกรรมแบบเรียลไทม์
   * สรุปยอดเงินยกมา (Opening Balance), ยอดเข้าสะสม, ยอดออกสะสม และยอดคงเหลือสุทธิ
   * รองรับการพิมพ์ใบสเตทเมนต์ หรือบันทึกเป็น PDF (`window.print()`)
4. **คำนวณยอดเงินและกำไรอัตโนมัติ (Automated Calculation)**:
   * คำนวณยอดรายรับรวม, รายจ่ายรวม, และกำไร/ขาดทุนสุทธิของธุรกิจแบบเรียลไทม์
5. **แดชบอร์ดและกราฟวิเคราะห์ (Dashboard & Data Visualization)**:
   * แสดงการ์ดสรุปสถานะการเงิน (Floating KPI Cards)
   * กราฟแท่งเปรียบเทียบสัดส่วนรายรับ vs รายจ่าย
   * กราฟวงกลม (Doughnut) สัดส่วนรายจ่ายแยกตามหมวดหมู่
   * ประวัติรายการธุรกรรมล่าสุด (รองรับทั้ง Desktop และ Mobile Wallet Cards)
6. **รายงานสรุปผลประกอบการ (Periodic Reports)**:
   * สรุปผลประกอบการแบบเลือกดู รายวัน, รายเดือน, รายปี หรือทั้งหมด
   * ตารางวิเคราะห์สัดส่วนรายจ่ายและรายรับแยกตามหมวดหมู่ (%)
7. **ศูนย์ช่วยเหลือและแจ้งปัญหาถึงเจ้าของระบบ (Help & Support System)**:
   * มีคำแนะนำการบริหารการเงิน SME และเทคนิคการอ่านตัวเลขผลกำไรสุทธิ
   * แบบฟอร์มส่งข้อความแจ้งปัญหา หรือขอความช่วยเหลือจากเจ้าของระบบ/ผู้ดูแลได้โดยตรง
   * มีตารางติดตามสถานะคำขอความช่วยเหลือ (Support Tickets) ของร้านค้า
   * แสดงช่องทางติดต่อด่วน เช่น Line Support และอีเมลฝ่ายดูแลระบบ

---

### 🛠️ เครื่องมือและเทคโนโลยีที่ใช้
* **ภาษาและเวอร์ชัน**: Python 3.13
* **Backend Framework**: Flask
* **สถาปัตยกรรมฐานข้อมูล (Dual Database Architecture)**:
  * **SQLite (ค่าเริ่มต้น)**: ใช้งานได้ทันทีทั้งบนเครื่องและบน PythonAnywhere โดยไม่ต้องตั้งค่าหรือเสียค่าบริการใดๆ
  * **Google Firebase Firestore (พร้อมเชื่อมต่อ)**: รองรับการเสียบกุญแจ `firebase_credentials.json` เพื่อบันทึกข้อมูลลง Cloud Firebase ได้ทันที
* **ระบบความปลอดภัย**: Werkzeug Security (Password Hashing & Session Isolation)
* **Frontend**: HTML5, CSS3, Google Fonts (Prompt & Plus Jakarta Sans)
* **Visualization**: Chart.js ผ่าน CDN

---

### 📂 โครงสร้างโฟลเดอร์ของโปรเจกต์
```
sme-financial-management-system-ระบบบร-หารจ-ดการรายร-บ-รายจ-/
│
├── flask_app.py                      # ไฟล์แอปพลิเคชัน Flask หลัก
├── db_service.py                     # Service เชื่อมต่อฐานข้อมูล (SQLite & Firebase Engine)
├── requirements.txt                  # รายการ Library ที่โปรเจกต์ใช้งานจริง
├── README.md                         # คู่มือการติดตั้งและการใช้งาน
├── firestore.rules                   # กฎความปลอดภัยของ Firebase กันการแฮ็ก
├── firebase_credentials.json.example # ตัวอย่างไฟล์กุญแจ Firebase Service Account
├── finance.db                        # ฐานข้อมูล SQLite (สร้างอัตโนมัติเมื่อเริ่มระบบ)
│
├── static/
│   └── css/
│       └── style.css                 # ไฟล์ CSS ดีไซน์ Fintech & Responsive
│
└── templates/
    ├── base.html                     # โครงร่างหน้าเว็บหลัก (Navigation, Mobile Tab Bar & Footer)
    ├── login.html                    # หน้าเข้าสู่ระบบ
    ├── register.html                 # หน้าสมัครสมาชิกสร้างบัญชีธุรกิจ
    ├── index.html                    # หน้าแดชบอร์ดสรุปภาพรวมและกราฟ
    ├── statement.html                # สเตทเมนต์บัญชีการเงินและยอดเงินสะสม (พร้อมพิมพ์ PDF)
    ├── transactions.html             # หน้าบันทึก ค้นหา และแสดงรายการธุรกรรม
    ├── edit_transaction.html        # หน้าฟอร์มสำหรับแก้ไขรายการ
    ├── reports.html                  # หน้ารายงานสรุปผลประกอบการ
    └── support.html                  # ศูนย์ช่วยเหลือ แนะนำการใช้งาน และแจ้งปัญหาถึงเจ้าของระบบ
```

---

### 🚀 วิธีเปิดใช้งาน Google Firebase (เมื่อต้องการนำขึ้น Cloud)

1. เข้าไปที่ [Firebase Console](https://console.firebase.google.com/) แล้วสร้างโปรเจกต์
2. ไปที่ **Project Settings** > **Service accounts**
3. กดปุ่ม **Generate new private key** จะได้ไฟล์ `.json` ดาวน์โหลดลงมา
4. นำไฟล์นั้นมาวางในโฟลเดอร์โครงงาน และเปลี่ยนชื่อเป็น **`firebase_credentials.json`**
5. ติดตั้งแพ็กเกจ Firebase:
   ```bash
   pip install firebase-admin
   ```
6. ไปที่เมนู **Firestore Database** > **Rules** บน Firebase แล้วคัดลอกกฎในไฟล์ `firestore.rules` ไปวาง
7. เริ่มรันแอปพลิเคชัน ระบบจะตรวจพบไฟล์และเปลี่ยนไปบันทึกข้อมูลบน Firebase Firestore อัตโนมัติทันที!

---

### 💻 วิธีการรันบนเครื่องคอมพิวเตอร์ (Local Machine)

1. **สร้างสภาพแวดล้อมจำลอง (Virtual Environment)**:
   ```bash
   python -m venv .venv
   ```

2. **เปิดใช้งาน Virtual Environment**:
   * บน Windows (PowerShell):
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   * บน macOS / Linux:
     ```bash
     source .venv/bin/activate
     ```

3. **ติดตั้งแพ็กเกจ**:
   ```bash
   pip install -r requirements.txt
   ```

4. **เริ่มการทำงานของแอปพลิเคชัน**:
   ```bash
   python flask_app.py
   ```

5. เปิดเว็บเบราว์เซอร์ไปที่: `http://127.0.0.1:5000`

---

### ☁️ วิธีการติดตั้งและเผยแพร่บน PythonAnywhere

1. **อัปโหลดไฟล์**:
   * นำไฟล์ `.zip` โครงงานอัปโหลดขึ้นไปยังแท็บ **Files** บน PythonAnywhere
   * แตกไฟล์ ZIP ด้วยคำสั่งใน Bash Console:
     ```bash
     unzip sme-financial-management-system-ระบบบร-หารจ-ดการรายร-บ-รายจ-.zip
     ```
2. **สร้าง Virtual Environment ด้วย Python 3.13 บน PythonAnywhere**:
   * ใน Bash Console รันคำสั่ง:
     ```bash
     mkvirtualenv --python=/usr/bin/python3.13 sme-env
     pip install -r requirements.txt
     ```
3. **ตั้งค่าในหน้า Web Tab**:
   * ไปที่แท็บ **Web** บนเมนูของ PythonAnywhere
   * สร้าง Web App แบบ **Manual configuration** เลือก **Python 3.13**
   * ในส่วน **Virtualenv**: ใส่ path ไปยัง virtualenv เช่น `/home/yourusername/.virtualenvs/sme-env`
   * ในส่วน **Code**:
     * **Source code**: `/home/yourusername/sme-financial-management-system-ระบบบร-หารจ-ดการรายร-บ-รายจ-`
     * **Working directory**: `/home/yourusername/sme-financial-management-system-ระบบบร-หารจ-ดการรายร-บ-รายจ-`
4. **แก้ไขไฟล์ WSGI configuration file**:
   * คลิกที่ลิงก์ไฟล์ WSGI configuration (เช่น `/var/www/yourusername_pythonanywhere_com_wsgi.py`)
   * ปรับแก้เนื้อหาให้เป็นดังนี้:
     ```python
     import sys
     import os

     # กำหนด path ไปยังโฟลเดอร์โปรเจกต์
     project_home = '/home/yourusername/sme-financial-management-system-ระบบบร-หารจ-ดการรายร-บ-รายจ-'
     if project_home not in sys.path:
         sys.path.insert(0, project_home)

     from flask_app import app as application
     ```
5. **Reload Web App**:
   * กดปุ่มสีเขียว **Reload <username>.pythonanywhere.com**
   * เข้าใช้งานเว็บแอปพลิเคชันผ่าน URL ของ PythonAnywhere ได้ทันที!
