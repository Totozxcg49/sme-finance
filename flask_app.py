from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import db_service

# 1. การตั้งค่าแอปพลิเคชัน Flask
app = Flask(__name__)
app.secret_key = "sme_financial_management_system_secure_key_2026"

# เริ่มต้นระบบฐานข้อมูล (รองรับทั้ง SQLite และ Firebase Architecture)
db_service.init_db()


# 2. Decorator สำหรับตรวจสอบการเข้าสู่ระบบ (Login Required)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("กรุณาเข้าสู่ระบบก่อนเข้าใช้งาน", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# 3. Route: สมัครสมาชิก (Register)
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        # ตรวจสอบความถูกต้องของข้อมูล
        if not business_name or not username or not password:
            flash("กรุณากรอกข้อมูลให้ครบทุกช่อง", "danger")
            return render_template("register.html")

        if len(username) < 3:
            flash("ชื่อผู้ใช้งานต้องมีความยาวอย่างน้อย 3 ตัวอักษร", "danger")
            return render_template("register.html")

        if len(password) < 4:
            flash("รหัสผ่านต้องมีความยาวอย่างน้อย 4 ตัวอักษร", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน", "danger")
            return render_template("register.html")

        user_data, error = db_service.create_user(username, password, business_name)
        if error:
            flash(error, "danger")
            return render_template("register.html")

        # บันทึกสถานะเข้าสู่ระบบทันที
        session["user_id"] = user_data["id"]
        session["username"] = user_data["username"]
        session["business_name"] = user_data["business_name"]

        flash(f"ยินดีต้อนรับ {business_name}! สร้างบัญชีและเข้าสู่ระบบเรียบร้อยแล้ว", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


# 4. Route: เข้าสู่ระบบ (Login)
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("กรุณากรอกชื่อผู้ใช้งานและรหัสผ่าน", "danger")
            return render_template("login.html")

        user = db_service.authenticate_user(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["business_name"] = user["business_name"]

            flash(f"เข้าสู่ระบบสำเร็จ ยินดีต้อนรับคุณ {user['business_name']}", "success")
            return redirect(url_for("index"))
        else:
            flash("ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง", "danger")
            return render_template("login.html")

    return render_template("login.html")


# 5. Route: ออกจากระบบ (Logout)
@app.route("/logout")
def logout():
    session.clear()
    flash("ออกจากระบบเรียบร้อยแล้ว", "success")
    return redirect(url_for("login"))


# 6. Route: หน้าหลัก / แดชบอร์ด (Dashboard)
@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    data = db_service.get_dashboard_data(user_id)

    return render_template(
        "index.html",
        total_income=data["total_income"],
        total_expense=data["total_expense"],
        net_balance=data["net_balance"],
        expense_cat_labels=data["expense_cat_labels"],
        expense_cat_values=data["expense_cat_values"],
        recent_transactions=data["recent_transactions"],
    )


# 7. Route: หน้ารายการรายรับ-รายจ่าย (List & Filter Transactions)
@app.route("/transactions")
@login_required
def transactions():
    user_id = session["user_id"]
    current_type = request.args.get("type", "all")
    payment_method = request.args.get("payment_method", "all")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    items = db_service.get_transactions(
        user_id=user_id,
        current_type=current_type,
        start_date=start_date,
        end_date=end_date,
        payment_method=payment_method
    )

    today_str = date.today().strftime("%Y-%m-%d")
    current_time_str = date.today().strftime("%H:%M")

    return render_template(
        "transactions.html",
        transactions=items,
        today=today_str,
        current_type=current_type,
        payment_method=payment_method,
        start_date=start_date,
        end_date=end_date,
    )


# 8. Route: สเตทเมนต์บัญชีการเงิน (Financial Statement)
@app.route("/statement")
@login_required
def statement():
    user_id = session["user_id"]
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    payment_method = request.args.get("payment_method", "all")

    stmt_data = db_service.get_statement(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        payment_method=payment_method
    )

    today_str = date.today().strftime("%Y-%m-%d")

    return render_template(
        "statement.html",
        statement=stmt_data,
        start_date=start_date,
        end_date=end_date,
        payment_method=payment_method,
        today=today_str,
        business_name=session.get("business_name", "ธุรกิจ SME")
    )


# 9. Route: เพิ่มรายการใหม่ (Add Transaction)
@app.route("/transactions/add", methods=["POST"])
@login_required
def add_transaction():
    user_id = session["user_id"]
    trans_date = request.form.get("trans_date", "").strip()
    trans_time = request.form.get("trans_time", "").strip()
    payment_method = request.form.get("payment_method", "โอนเงิน").strip()
    trans_type = request.form.get("type", "").strip()
    category = request.form.get("category", "").strip()
    amount_str = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()

    # ตรวจสอบความถูกต้องของข้อมูล (Server-Side Validation)
    if not trans_date or trans_type not in ["income", "expense"] or not category:
        flash("กรุณากรอกข้อมูลวันที่ ประเภท และหมวดหมู่ให้ครบถ้วน", "danger")
        return redirect(url_for("transactions"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("จำนวนเงินต้องมากกว่า 0 บาท", "danger")
            return redirect(url_for("transactions"))
    except ValueError:
        flash("จำนวนเงินไม่ถูกต้อง กรุณากรอกเป็นตัวเลข", "danger")
        return redirect(url_for("transactions"))

    db_service.add_transaction(
        user_id=user_id,
        trans_date=trans_date,
        trans_time=trans_time,
        payment_method=payment_method,
        trans_type=trans_type,
        category=category,
        amount=amount,
        note=note
    )

    flash("บันทึกรายการสำเร็จเรียบร้อยแล้ว", "success")
    return redirect(url_for("transactions"))


# 10. Route: แก้ไขรายการ (Edit Transaction)
@app.route("/transactions/edit/<trans_id>", methods=["GET", "POST"])
@login_required
def edit_transaction(trans_id):
    user_id = session["user_id"]

    if request.method == "POST":
        trans_date = request.form.get("trans_date", "").strip()
        trans_time = request.form.get("trans_time", "").strip()
        payment_method = request.form.get("payment_method", "โอนเงิน").strip()
        trans_type = request.form.get("type", "").strip()
        category = request.form.get("category", "").strip()
        amount_str = request.form.get("amount", "").strip()
        note = request.form.get("note", "").strip()

        if not trans_date or trans_type not in ["income", "expense"] or not category:
            flash("กรุณากรอกข้อมูลให้ครบถ้วน", "danger")
            return redirect(url_for("edit_transaction", trans_id=trans_id))

        try:
            amount = float(amount_str)
            if amount <= 0:
                flash("จำนวนเงินต้องมากกว่า 0 บาท", "danger")
                return redirect(url_for("edit_transaction", trans_id=trans_id))
        except ValueError:
            flash("จำนวนเงินไม่ถูกต้อง", "danger")
            return redirect(url_for("edit_transaction", trans_id=trans_id))

        success = db_service.update_transaction(
            user_id=user_id,
            trans_id=trans_id,
            trans_date=trans_date,
            trans_time=trans_time,
            payment_method=payment_method,
            trans_type=trans_type,
            category=category,
            amount=amount,
            note=note
        )

        if success:
            flash("แก้ไขรายการสำเร็จเรียบร้อยแล้ว", "success")
        else:
            flash("ไม่สามารถแก้ไขรายการได้ หรือไม่มีสิทธิ์เข้าถึง", "danger")
        return redirect(url_for("transactions"))

    # ดึงข้อมูลเดิมมาแสดงในแบบฟอร์ม (ตรวจสอบสิทธิ์ User)
    trans = db_service.get_transaction(user_id=user_id, trans_id=trans_id)
    if not trans:
        flash("ไม่พบรายการที่ต้องการแก้ไข หรือคุณไม่มีสิทธิ์เข้าถึงรายการนี้", "danger")
        return redirect(url_for("transactions"))

    return render_template("edit_transaction.html", trans=trans)


# 11. Route: ลบรายการ (Delete Transaction)
@app.route("/transactions/delete/<trans_id>", methods=["POST"])
@login_required
def delete_transaction(trans_id):
    user_id = session["user_id"]
    success = db_service.delete_transaction(user_id=user_id, trans_id=trans_id)

    if success:
        flash("ลบรายการเรียบร้อยแล้ว", "success")
    else:
        flash("ไม่สามารถลบรายการได้ หรือไม่มีสิทธิ์เข้าถึง", "danger")
    return redirect(url_for("transactions"))


# 12. Route: หน้ารายงานสรุป (Reports)
@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    today = date.today()
    period_type = request.args.get("period_type", "monthly")
    selected_month = request.args.get("selected_month", today.strftime("%Y-%m"))
    selected_date = request.args.get("selected_date", today.strftime("%Y-%m-%d"))
    selected_year = request.args.get("selected_year", str(today.year))

    rep = db_service.get_report_data(
        user_id=user_id,
        period_type=period_type,
        selected_month=selected_month,
        selected_date=selected_date,
        selected_year=selected_year
    )

    return render_template(
        "reports.html",
        period_type=period_type,
        selected_month=selected_month,
        selected_date=selected_date,
        selected_year=selected_year,
        period_income=rep["period_income"],
        period_expense=rep["period_expense"],
        period_profit=rep["period_profit"],
        income_by_category=rep["income_by_category"],
        expense_by_category=rep["expense_by_category"],
        timeline_rows=rep["timeline_rows"],
    )


# 12. Route: ศูนย์ช่วยเหลือและติดต่อผู้ดูแลระบบ (Help & Support System)
@app.route("/support", methods=["GET", "POST"])
@login_required
def support():
    user_id = session["user_id"]
    business_name = session.get("business_name", session.get("username", "สมาชิก SME"))

    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        message = request.form.get("message", "").strip()
        contact_info = request.form.get("contact_info", "").strip()

        if not topic or not message:
            flash("กรุณาเลือกหัวข้อปัญหาและกรอกรายละเอียด", "danger")
            return redirect(url_for("support"))

        db_service.create_support_ticket(
            user_id=user_id,
            business_name=business_name,
            topic=topic,
            message=message,
            contact_info=contact_info
        )

        flash("ส่งคำขอความช่วยเหลือเรียบร้อยแล้ว เจ้าหน้าที่หรือผู้ดูแลระบบจะรีบตรวจสอบและติดต่อกลับโดยเร็วที่สุดครับ", "success")
        return redirect(url_for("support"))

    # ดึงประวัติคำขอความช่วยเหลือของ User
    tickets = db_service.get_user_tickets(user_id=user_id)

    return render_template("support.html", tickets=tickets)


# 13. สำหรับการทดสอบในเครื่อง Local
if __name__ == "__main__":
    app.run(debug=True)
