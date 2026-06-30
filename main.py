from database import connect_db
from fastapi import FastAPI, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from reportlab.pdfgen import canvas
from openpyxl import Workbook
import shutil
import os
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import pandas as pd
from fastapi.responses import FileResponse
from reportlab.lib.colors import HexColor
from fastapi import Query

SECRET_KEY = os.getenv("SECRET_KEY")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=1800
)

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


failed_attempts = {}

@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    # Account lock after 5 wrong attempts
    if failed_attempts.get(username, 0) >= 5:
        return {"error": "Account locked. Try later."}

    conn = connect_db()

    if conn is None:
        return {"error": "Database connection failed"}

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM users
        WHERE username=%s OR mobile=%s
    """, (username, username))

    user = cursor.fetchone()
    conn.close()

    if user and bcrypt.checkpw(
        password.encode("utf-8"),
        user["password"].encode("utf-8")
    ):
        # Reset failed attempts after successful login
        failed_attempts[username] = 0

        user_role = str(user["role"]).strip().lower()

        request.session["user"] = user["username"]
        request.session["role"] = str(user["role"]).strip().lower()
        request.session["class_name"] = user.get("class_name", "")
        request.session["division"] = user.get("division", "")

        if user_role == "admin":
            return RedirectResponse(
            url="/admin_dashboard",
            status_code=303
        )  

        elif user_role == "teacher":
            return RedirectResponse(
            url="/teacher_dashboard",
            status_code=303
        )

        elif user_role == "parent":
            return RedirectResponse(
            url=f"/parent_dashboard/{user['student_id']}",
            status_code=303
        )

    # Increase failed attempts
    failed_attempts[username] = failed_attempts.get(username, 0) + 1

    return {"status": "Login Failed"}

@app.get("/students")
def get_students():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT student_name, class_name, mobile, yearly_fee
        FROM students
    """)

    students = cursor.fetchall()

    conn.close()

    return students


# ADD attendance FIRST
@app.post("/add-attendance")
def add_attendance(student_id: int, status: str):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO attendance (student_id, date, status)
        VALUES (%s, CURDATE(), %s)
    """, (student_id, status))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "Attendance Added"
    }


# GET attendance AFTER add route
@app.get("/attendance/{student_id}")
def get_attendance(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM attendance
        WHERE student_id=%s
    """, (student_id,))

    records = cursor.fetchall()

    conn.close()

    return records


@app.get("/fees/{student_id}")
def get_fees(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM fees
        WHERE student_id=%s
    """, (student_id,))

    fee = cursor.fetchone()

    conn.close()

    return fee

@app.post("/add-student")
def add_student(
    admission_no: str,
    student_name: str,
    class_name: str,
    father_name: str,
    mobile: str,
    yearly_fee: float,
    discount: float
):
    conn = connect_db()
    cursor = conn.cursor()

    final_fee = yearly_fee - discount

    cursor.execute("""
        INSERT INTO students
        (admission_no, student_name, class_name, father_name, mobile, yearly_fee, discount, final_fee)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        admission_no,
        student_name,
        class_name,
        father_name,
        mobile,
        yearly_fee,
        discount,
        final_fee
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "Student Added"
    }

@app.post("/add-marks")
def add_marks(
    student_id: int,
    subject: str,
    marks: float,
    total_marks: float
):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO exams
        (student_id, subject, marks, total_marks)
        VALUES (%s,%s,%s,%s)
    """, (
        student_id,
        subject,
        marks,
        total_marks
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "Marks Added"
    }

@app.get("/marks/{student_id}")
def get_marks(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT subject, marks, total_marks
        FROM exams
        WHERE student_id=%s
    """, (student_id,))

    result = cursor.fetchall()

    conn.close()

    return result

@app.delete("/delete_student/{student_id}")
def delete_student(student_id: int):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
    conn.commit()

    conn.close()

    return {"status": "success"}

@app.post("/update_student")
def update_student(
    id: int,
    name: str,
    class_name: str,
    mobile: str,
    fees: str
):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE students
        SET student_name=%s,
            class_name=%s,
            mobile=%s,
            yearly_fee=%s
        WHERE id=%s
    """, (name, class_name, mobile, fees, id))

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/web_students",
        status_code=303
    )

@app.post("/add_fee")
def add_fee(
    student_id: int,
    amount: float,
    paid_date: str,
    status: str
):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO fees (student_id, amount, paid_date, status)
        VALUES (%s,%s,%s,%s)
    """, (
        student_id,
        amount,
        paid_date,
        status
    ))

    conn.commit()
    conn.close()

    return {"status": "success"}

@app.post("/add_result")
def add_result(
    student_id: int,
    subject: str,
    marks: int,
    total_marks: int
):
    percentage = (marks / total_marks) * 100

    if percentage >= 35:
        result_status = "Pass"
    else:
        result_status = "Fail"

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO results
        (student_id, subject, marks, total_marks, percentage, result_status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        student_id,
        subject,
        marks,
        total_marks,
        percentage,
        result_status
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "percentage": percentage,
        "result_status": result_status

    }

@app.get("/result_list")
def result_list():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.student_name,
               r.subject,
               r.marks,
               r.total_marks,
               r.percentage,
               r.result_status
        FROM results r
        JOIN students s ON s.id = r.student_id
    """)

    result = cursor.fetchall()
    conn.close()

    return result

@app.get("/search_student")
def search_student(keyword: str):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM students
        WHERE student_name LIKE %s
        OR mobile LIKE %s
        OR admission_no LIKE %s
    """, (
        f"%{keyword}%",
        f"%{keyword}%",
        f"%{keyword}%"
    ))

    result = cursor.fetchall()
    conn.close()

    return result

@app.get("/parent_report/{student_id}")
def parent_report(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            s.student_name,
            s.class_name,
            s.mobile,
            f.total_fee,
            f.pending_fee,
            a.status AS attendance_status,
            r.percentage,
            r.result_status
        FROM students s
        LEFT JOIN fees f ON s.id = f.student_id
        LEFT JOIN attendance a ON s.id = a.student_id
        LEFT JOIN results r ON s.id = r.student_id
        WHERE s.id = %s
        LIMIT 1
    """, (student_id,))

    result = cursor.fetchone()
    conn.close()

    return result

@app.get("/dashboard_stats")
def dashboard_stats():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Total Students
    cursor.execute("SELECT COUNT(*) as total_students FROM students")
    total_students = cursor.fetchone()["total_students"]

    # Total Fees Collected
    cursor.execute("SELECT SUM(amount) AS total_fees FROM fees")
    total_fees = cursor.fetchone()["total_fees"] or 0

    # Pending Fees
    cursor.execute("SELECT SUM(pending_fee) as pending_fees FROM fees")
    pending_fees = cursor.fetchone()["pending_fees"] or 0

    # Today Attendance
    cursor.execute("""
        SELECT COUNT(*) as today_attendance
        FROM attendance
        WHERE date = CURDATE()
    """)
    today_attendance = cursor.fetchone()["today_attendance"]

    conn.close()

    return {
        "total_students": total_students,
        "total_fees": total_fees,
        "pending_fees": pending_fees,
        "today_attendance": today_attendance
    }

@app.post("/add_teacher")
def add_teacher(
    teacher_name: str,
    mobile: str,
    subject: str,
    salary: float,
    password: str,
    class_name: str
):
    conn = connect_db()
    cursor = conn.cursor()

    # teachers table मध्ये save
    cursor.execute("""
        INSERT INTO teachers
        (teacher_name, mobile, subject, salary, class_name)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        teacher_name,
        mobile,
        subject,
        salary,
        class_name
    ))

    # password hash
    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # users table मध्ये login साठी save
    cursor.execute("""
        INSERT INTO users
        (username, mobile, password, role, class_name)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        teacher_name,
        mobile,
        hashed_password,
        "teacher",
        class_name
    ))

    conn.commit()
    conn.close()

    return {"status": "success"}

@app.get("/teacher_list")
def teacher_list():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM teachers")

    result = cursor.fetchall()
    conn.close()

    return result

@app.post("/delete_teacher")
def delete_teacher(id: int):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM teachers WHERE id=%s",
        (id,)
    )

    conn.commit()
    conn.close()

    return {"status": "success"}

@app.get("/admin_dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request):

    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Students Count
    cursor.execute("SELECT COUNT(*) AS total_students FROM students")
    student_data = cursor.fetchone()
    students = student_data["total_students"]

    # Teachers Count
    cursor.execute("SELECT COUNT(*) AS total_teachers FROM teachers")
    teacher_data = cursor.fetchone()
    teachers = teacher_data["total_teachers"]

    # Fees Collected
    cursor.execute("SELECT SUM(amount) AS total_fees FROM fees")
    fee_data = cursor.fetchone()
    fees = fee_data["total_fees"] if fee_data["total_fees"] else 0

    # Results Count
    cursor.execute("SELECT COUNT(*) AS total_results FROM results")
    result_data = cursor.fetchone()
    results = result_data["total_results"]

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "students": students,
            "teachers": teachers,
            "fees": fees,
            "results": results
        }
    )

@app.get("/web_students", response_class=HTMLResponse)
def web_students(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    user_role = request.session.get("role")

    if user_role == "teacher":
        teacher_class = request.session.get("class_name")
        teacher_division = request.session.get("division")

        cursor.execute("""
            SELECT * FROM students
            WHERE class_name=%s AND division=%s
        """, (
            teacher_class,
            teacher_division
        ))
    else:
        cursor.execute("SELECT * FROM students")

    students = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="students.html",
        context={"students": students}
    )

@app.get("/add_student_web", response_class=HTMLResponse)
def add_student_web(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add_student.html",
        context={}
    )


@app.post("/save_student_web")
async def save_student_web(
    request: Request,
    photo: UploadFile = File(...)
):
    try:
        form = await request.form()
        print("Form Data:", form)

        admission_no = form.get("admission_no")
        student_name = form.get("student_name")
        student_class = form.get("class_name")
        division = form.get("division")
        father_name = form.get("father_name")
        mobile = form.get("mobile")
        yearly_fee = form.get("yearly_fee")
        discount = form.get("discount") or 0

        final_fee = float(yearly_fee) - float(discount)

        # File upload security
        if not photo.filename:
            return {"error": "No file selected"}

        allowed_extensions = ["jpg", "jpeg", "png"]
        file_ext = photo.filename.split(".")[-1].lower()

        if file_ext not in allowed_extensions:
            return {"error": "Only JPG, JPEG, PNG files allowed"}

        photo_path = f"static/uploads/{photo.filename}"
        print("Saving photo:", photo_path)

        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        conn = connect_db()

        if conn is None:
            return {"error": "Database connection failed"}

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO students
            (
                admission_no,
                student_name,
                class_name,
                division,
                father_name,
                mobile,
                yearly_fee,
                discount,
                final_fee,
                photo
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            admission_no,
            student_name,
            student_class,
            division,
            father_name,
            mobile,
            yearly_fee,
            discount,
            final_fee,
            photo_path
        ))

        conn.commit()
        conn.close()

        return RedirectResponse(
            "/web_students",
            status_code=303
        )

    except Exception as e:
        print("Student Save Error:", e)
        return {"error": str(e)}

@app.get("/delete_student_web/{student_id}")
def delete_student_web(student_id: int):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM students WHERE id=%s",
        (student_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/web_students",
        status_code=303
    )

@app.get("/edit_student_web/{student_id}", response_class=HTMLResponse)
def edit_student_web(
    request: Request,
    student_id: int
):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM students WHERE id=%s",
        (student_id,)
    )

    student = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="edit_student.html",
        context={
            "student": student
        }
    )

    
@app.post("/update_student_web/{student_id}")
def update_student_web(
    student_id: int,
    student_name: str = Form(...),
    class_name: str = Form(...),
    mobile: str = Form(...),
    yearly_fee: float = Form(...)
):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE students
        SET student_name=%s,
            class_name=%s,
            mobile=%s,
            yearly_fee=%s
        WHERE id=%s
    """, (
        student_name,
        class_name,
        mobile,
        yearly_fee,
        student_id
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/web_students",
        status_code=303
    )

@app.get("/web_teachers", response_class=HTMLResponse)
def web_teachers(request: Request):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="teachers.html",
        context={
            "teachers": teachers
        }
    )

@app.get("/add_teacher_web", response_class=HTMLResponse)
def add_teacher_web(
    request: Request,
    success: str = None
):
    return templates.TemplateResponse(
        request=request,
        name="add_teacher.html",
        context={
            "success": success
        }
    )

@app.post("/save_teacher_web")
def save_teacher_web(
    teacher_name: str = Form(...),
    mobile: str = Form(...),
    subject: str = Form(...),
    salary: float = Form(...),
    password: str = Form(...),
    class_name: str = Form(...),
    division: str = Form(...)
):
    conn = connect_db()
    cursor = conn.cursor()

    try:
        print("Teacher Save Start")
        print(
            teacher_name,
            mobile,
            subject,
            salary,
            class_name,
            division
        )

        # teachers table मध्ये save
        cursor.execute("""
            INSERT INTO teachers
            (teacher_name, mobile, subject, salary, class_name, division)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            teacher_name,
            mobile,
            subject,
            salary,
            class_name,
            division
        ))

        print("Teacher inserted")

        # password hash
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # users table मध्ये login साठी save
        cursor.execute("""
            INSERT INTO users
            (username, mobile, password, role, class_name, division)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            teacher_name,
            mobile,
            hashed_password,
            "teacher",
            class_name,
            division
        ))

        print("User inserted")

        conn.commit()
        print("Commit successful")

    except Exception as e:
        conn.rollback()
        print("Save Error:", e)

    finally:
        cursor.close()
        conn.close()

    return RedirectResponse(
        url="/add_teacher_web?success=1",
        status_code=303
    )

@app.get("/delete_teacher_web/{teacher_id}")
def delete_teacher_web(teacher_id: int):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM teachers WHERE id=%s",
        (teacher_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/web_teachers",
        status_code=303
   )

@app.get("/edit_teacher_web/{teacher_id}", response_class=HTMLResponse)
def edit_teacher_web(
    request: Request,
    teacher_id: int
):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM teachers WHERE id=%s",
        (teacher_id,)
    )

    teacher = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="edit_teacher.html",
        context={
            "teacher": teacher
        }
    )

@app.post("/update_teacher_web/{teacher_id}")
def update_teacher_web(
    teacher_id: int,
    teacher_name: str = Form(...),
    mobile: str = Form(...),
    subject: str = Form(...),
    salary: float = Form(...)
):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE teachers
        SET teacher_name=%s,
            mobile=%s,
            subject=%s,
            salary=%s
        WHERE id=%s
    """, (
        teacher_name,
        mobile,
        subject,
        salary,
        teacher_id
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/web_teachers",
        status_code=303
    )

@app.get("/web_fees", response_class=HTMLResponse)
def web_fees(request: Request):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT f.*, s.student_name
        FROM fees f
        JOIN students s ON f.student_id = s.id
    """)

    fees = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="fees.html",
        context={
            "fees": fees
        }
    )

@app.get("/add_fee_web", response_class=HTMLResponse)
def add_fee_web(
    request: Request,
    success: str = None
):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="add_fee.html",
        context={
            "students": students,
            "success": success,
        }
    )

@app.post("/save_fee_web")
def save_fee_web(
    student_id: int = Form(...),
    amount: float = Form(...),
    paid_date: str = Form(...),
    status: str = Form(...)
):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Student total fee fetch
    cursor.execute("""
        SELECT yearly_fee
        FROM students
        WHERE id=%s
    """, (student_id,))

    student = cursor.fetchone()

    total_fee = float(student["yearly_fee"])
    paid_fee = amount
    pending_fee = total_fee - paid_fee

    cursor.execute("""
        INSERT INTO fees
        (
            student_id,
            amount,
            paid_date,
            status,
            total_fee,
            paid_fee,
            pending_fee
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        student_id,
        amount,
        paid_date,
        status,
        total_fee,
        paid_fee,
        pending_fee
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/add_fee_web?success=1",
        status_code=303
    )

@app.get("/web_pending_fees", response_class=HTMLResponse)
def web_pending_fees(request: Request):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            s.id,
            s.student_name,
            s.yearly_fee,
            IFNULL(SUM(f.amount), 0) AS paid_amount
        FROM students s
        LEFT JOIN fees f ON s.id = f.student_id
        GROUP BY s.id
    """)

    fees = cursor.fetchall()

    for fee in fees:
        yearly_fee = fee["yearly_fee"] or 0
        paid_amount = fee["paid_amount"] or 0

        fee["pending_fee"] = float(yearly_fee) - float(paid_amount)

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="pending_fees.html",
        context={"fees": fees}
    )

@app.get("/web_attendance", response_class=HTMLResponse)
def web_attendance(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    user_role = request.session.get("role")

    if user_role == "teacher":
        teacher_class = request.session.get("class_name")
        teacher_division = request.session.get("division")

        cursor.execute("""
            SELECT * FROM students
            WHERE class_name=%s AND division=%s
        """, (teacher_class, teacher_division))

    else:
        cursor.execute("SELECT * FROM students")

    students = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="attendance.html",
        context={"students": students}
    )

@app.post("/save_attendance_web")
def save_attendance_web(
    student_id: int = Form(...),
    status: str = Form(...)
):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO attendance
        (student_id, date, status)
        VALUES (%s, CURDATE(), %s)
    """, (
        student_id,
        status
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        url="/web_attendance?success=1",
        status_code=303
    )

@app.get("/web_attendance_list", response_class=HTMLResponse)
def web_attendance_list(request: Request):

    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    if request.session.get("role") not in ["teacher", "admin"]:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.student_name,
               a.status,
               a.date
        FROM attendance a
        JOIN students s ON a.student_id = s.id
    """)

    attendance_list = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="attendance_list.html",
        context={
            "attendance_list": attendance_list
        }
    )

@app.get("/web_result", response_class=HTMLResponse)
def web_result(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    user_role = request.session.get("role")

    if user_role == "teacher":
        teacher_class = request.session.get("class_name")
        teacher_division = request.session.get("division")

        # Teacher चे students
        cursor.execute("""
            SELECT * FROM students
            WHERE class_name=%s AND division=%s
        """, (
            teacher_class,
            teacher_division
        ))
        students = cursor.fetchall()

        # Teacher चे results
        cursor.execute("""
            SELECT r.*, s.student_name
            FROM results r
            JOIN students s ON r.student_id = s.id
            WHERE s.class_name=%s AND s.division=%s
        """, (
            teacher_class,
            teacher_division
        ))
        results = cursor.fetchall()

    else:
        # Admin ला सर्व students
        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()

        # Admin ला सर्व results
        cursor.execute("""
            SELECT r.*, s.student_name
            FROM results r
            JOIN students s ON r.student_id = s.id
        """)
        results = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "students": students,
            "results": results
        }
    )

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"results": results}
    )

@app.post("/save_result_web")
async def save_result_web(request: Request):
    form = await request.form()

    student_id = form.get("student_id")
    exam_name = form.get("exam_name")
    class_name = form.get("class_name")
    division = form.get("division")

    subjects = form.getlist("subject[]")
    marks_list = form.getlist("marks[]")
    total_marks_list = form.getlist("total_marks[]")
    grades = form.getlist("grade[]")

    conn = connect_db()
    cursor = conn.cursor()

    for i in range(len(subjects)):

        subject = subjects[i]
        marks = float(marks_list[i])
        total_marks = float(total_marks_list[i])
        grade = grades[i]

        percentage = (marks / total_marks) * 100

        if percentage >= 35:
            result_status = "Pass"
        else:
            result_status = "Fail"

        cursor.execute("""
            INSERT INTO results
            (
                student_id,
                exam_name,
                class_name,
                division,
                subject,
                marks,
                total_marks,
                percentage,
                grade,
                result_status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            student_id,
            exam_name,
            class_name,
            division,
            subject,
            marks,
            total_marks,
            percentage,
            grade,
            result_status
        ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/web_result?success=1",
        status_code=303
    )

@app.get("/web_result_list", response_class=HTMLResponse)
def web_result_list(request: Request):

    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    if request.session.get("role") not in ["teacher", "admin"]:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.student_id,
               s.student_name,
               r.subject,
               r.marks,
               r.total_marks,
               r.percentage,
               r.result_status
        FROM results r
        JOIN students s ON r.student_id = s.id
    """)

    results = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="result_list.html",
        context={
            "results": results
        }
    )

@app.get("/parent_details")
def parent_details():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM students
        LIMIT 1
    """)

    student = cursor.fetchone()
    conn.close()

    return student

@app.get("/parent_fee_status")
def parent_fee_status():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT amount,
               paid_date,
               status
        FROM fees
        LIMIT 1
    """)

    fee = cursor.fetchone()
    conn.close()

    return fee

@app.get("/parent_attendance")
def parent_attendance():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT status, date
        FROM attendance
        LIMIT 5
    """)

    attendance = cursor.fetchall()
    conn.close()

    return attendance

@app.get("/parent_result")
def parent_result():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT subject,
               marks,
               total_marks,
               percentage,
               result_status
        FROM results
        LIMIT 5
    """)

    results = cursor.fetchall()
    conn.close()

    return results

@app.get("/fee_receipt/{student_id}")
def fee_receipt(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.id,
               s.student_name,
               s.class_name,
               s.mobile,
               s.yearly_fee,
               f.amount
        FROM fees f
        JOIN students s ON f.student_id = s.id
        WHERE s.id=%s
    """, (student_id,))

    fee = cursor.fetchone()

    if not fee:
        return {"error": "Fee not found"}

    conn.close()

    pending_fee = fee["yearly_fee"] - fee["amount"]

    file_name = f"receipt_{student_id}.pdf"
    c = canvas.Canvas(file_name)

    c.drawString(100, 800, "SCHOOL FEE RECEIPT")
    c.drawString(100, 760, f"Student Name: {fee['student_name']}")
    c.drawString(100, 730, f"Class: {fee['class_name']}")
    c.drawString(100, 700, f"Mobile: {fee['mobile']}")
    c.drawString(100, 670, f"Total Fee: {fee['yearly_fee']}")
    c.drawString(100, 640, f"Paid Fee: {fee['amount']}")
    c.drawString(100, 610, f"Pending Fee: {pending_fee}")

    c.save()

    return FileResponse(file_name)

@app.get("/marksheet/{student_id}")
def marksheet(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.id,
               s.student_name,
               s.class_name,
               s.mobile,
               r.subject,
               r.marks,
               r.total_marks,
               r.result_status
        FROM results r
        JOIN students s ON r.student_id = s.id
        WHERE s.id=%s
    """, (student_id,))

    results = cursor.fetchall()

    if not results:
        return {"error": "No results found"}

    conn.close()

    file_name = f"marksheet_{student_id}.pdf"
    c = canvas.Canvas(file_name)

    # प्रीमियम रंग व्याख्या (Color Definitions)
    primary_color = HexColor("#1e3a8a")    # Deep Royal Blue
    secondary_color = HexColor("#f8fafc")  # Soft Gray Background
    text_color = HexColor("#0f172a")       # Dark Charcoal Text
    muted_text = HexColor("#475569")       # Slate Gray
    border_color = HexColor("#cbd5e1")     # Light Border
    pass_color = HexColor("#15803d")       # Forest Green for Pass
    fail_color = HexColor("#b91c1c")       # Red for Fail

    # १. आऊटर बॉर्डर (Double Border for Premium Look)
    c.setStrokeColor(primary_color)
    c.setLineWidth(2)
    c.rect(35, 40, 525, 780)
    
    c.setStrokeColor(border_color)
    c.setLineWidth(0.5)
    c.rect(40, 45, 515, 770)

    # २. हेडर डिझाईन (School Header)
    c.setFillColor(primary_color)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(300, 775, "THE RISING STAR")

    c.setFillColor(muted_text)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(300, 755, "REPORT CARD (ACADEMIC SESSION : 2025-26)")

    # हेडर खाली एक सुंदर रेषा
    c.setStrokeColor(primary_color)
    c.setLineWidth(1.5)
    c.line(55, 740, 545, 740)

    # ३. विद्यार्थी माहिती विभाग (Student Info Box Background)
    c.setFillColor(secondary_color)
    c.setStrokeColor(border_color)
    c.setLineWidth(1)
    c.rect(55, 635, 490, 85, fill=1, stroke=1)

    c.setFillColor(text_color)
    # डावी बाजू
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, 695, "Admission No.")
    c.setFont("Helvetica", 11)
    c.drawString(175, 695, f":  {results[0]['id']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, 670, "Student Name")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(primary_color) # विद्यार्थ्याचे नाव उठून दिसण्यासाठी निळा रंग
    c.drawString(175, 670, f":  {results[0]['student_name'].upper()}")

    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, 645, "Class")
    c.setFont("Helvetica", 11)
    c.drawString(175, 645, f":  {results[0]['class_name']}")

    # उजवी बाजू
    c.setFont("Helvetica-Bold", 11)
    c.drawString(340, 695, "Roll No.")
    c.setFont("Helvetica", 11)
    c.drawString(440, 695, f":  {results[0]['id']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(340, 670, "Mobile")
    c.setFont("Helvetica", 11)
    c.drawString(440, 670, f":  {results[0]['mobile']}")

    from datetime import datetime
    today_date = datetime.now().strftime("%d/%m/%Y")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(340, 645, "Result Date")
    c.setFont("Helvetica", 11)
    c.drawString(440, 645, f":  {today_date}")

    # ४. गुणतालिका (Marks Table Header Background)
    table_top = 590
    c.setFillColor(primary_color)
    c.rect(55, table_top, 490, 25, fill=1, stroke=0)

    # टेबल हेडर टेक्स्ट
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, table_top + 8, "SUBJECT")
    c.drawCentredString(250, table_top + 8, "MARKS OBTAINED")
    c.drawCentredString(370, table_top + 8, "TOTAL MARKS")
    c.drawCentredString(485, table_top + 8, "STATUS")

    # विषयांच्या ओळी (Subject Rows Drawing)
    y = table_top - 25
    total_obtained = 0
    grand_total = 0
    row_count = 0

    for row in results:
        # अल्टरनेट ओळींना हलका राखाडी बॅकग्राउंड (Zebra Striping)
        if row_count % 2 == 0:
            c.setFillColor(HexColor("#f8fafc"))
            c.rect(55, y, 490, 25, fill=1, stroke=0)
        
        # ओळींची हलकी बॉर्डर
        c.setStrokeColor(HexColor("#f1f5f9"))
        c.setLineWidth(0.5)
        c.line(55, y, 545, y)

        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 11) if row_count % 2 == 0 else c.setFont("Helvetica", 11)
        c.drawString(75, y + 7, row['subject'].capitalize())
        
        c.setFont("Helvetica", 11)
        c.drawCentredString(250, y + 7, str(int(row['marks'])))
        c.drawCentredString(370, y + 7, str(int(row['total_marks'])))
        
        # पास किंवा फेलनुसार स्टेटसचा रंग बदलणे
        status_text = row['result_status'].strip()
        if status_text.lower() in ['pass', 'p']:
            c.setFillColor(pass_color)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(485, y + 7, "PASS")
        else:
            c.setFillColor(fail_color)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(485, y + 7, "FAIL")

        total_obtained += row['marks']
        grand_total += row['total_marks']
        y -= 25
        row_count += 1

    # टेबलचा संपूर्ण बाहेरील साचा पूर्ण करणे
    c.setStrokeColor(primary_color)
    c.setLineWidth(1)
    c.rect(55, y + 25, 490, table_top - y, fill=0, stroke=1)

    # ५. एकत्रित निकाल बॉक्स (Summary Statistics Card)
    summary_y = y - 25
    c.setFillColor(HexColor("#f1f5f9"))
    c.setStrokeColor(border_color)
    c.rect(55, summary_y, 490, 45, fill=1, stroke=1)

    final_percentage = (total_obtained / grand_total) * 100
    final_result = "PASS" if final_percentage >= 35 else "FAIL"
    result_text_color = pass_color if final_result == "PASS" else "fail_color"

    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, summary_y + 16, f"TOTAL MARKS :  {int(total_obtained)} / {int(grand_total)}")
    c.drawString(270, summary_y + 16, f"PERCENTAGE :  {round(final_percentage, 2)}%")
    
    c.setFillColor(result_text_color)
    c.drawString(450, summary_y + 16, f"RESULT :  {final_result}")

    # ६. रिमार्क आणि सहीचा भाग (Footer Block)
    c.setFillColor(muted_text)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(55, summary_y - 40, "Class Teacher Remark : ")
    c.setFont("Helvetica", 11)
    c.setStrokeColor(border_color)
    c.line(190, summary_y - 40, 545, summary_y - 40) # रिमार्कसाठी सरळ रेषा

    # स्वाक्षरी रेषा आणि मजकूर
    c.setStrokeColor(muted_text)
    c.setLineWidth(0.8)
    c.line(75, summary_y - 120, 200, summary_y - 120)
    c.line(400, summary_y - 120, 525, summary_y - 120)

    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(137, summary_y - 135, "CLASS TEACHER")
    c.drawCentredString(462, summary_y - 135, "PRINCIPAL SIGNATURE")

    c.save()
    return FileResponse(file_name)

@app.get("/id_card/{student_id}")
def id_card(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id,
               student_name,
               class_name,
               mobile,
               photo
        FROM students
        WHERE id=%s
    """, (student_id,))

    student = cursor.fetchone()
    conn.close()

    file_name = f"id_card_{student_id}.pdf"
    c = canvas.Canvas(file_name)

    # Blue Header
    c.setFillColorRGB(0.1, 0.3, 0.9)
    c.rect(40, 700, 520, 100, fill=1)

    # School Name
    c.setFillColorRGB(1, 1, 0)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(
        300,
        775,
        "RISING STAR ENGLISH MEDIUM SCHOOL"
    )

    # Address line 1
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 13)
    c.drawCentredString(
        300,
        752,
        "Nagar Jamkhed Road, Kolhewadi Phata"
    )

    # Address line 2
    c.drawCentredString(
        300,
        738,
        "Takali Kazi, Tal Dist Ahilyanagar - 414201"
    )

    # ID Title
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(300, 670, "IDENTITY CARD")

    # Photo Box
    c.rect(70, 450, 120, 160)

    if student["photo"]:
        c.drawImage(
            student["photo"],
            70,
            450,
            width=120,
            height=160
        )

    # Student Details
    c.setFont("Helvetica-Bold", 14)

    c.drawString(
        220,
        590,
        f"Student Name : {student['student_name']}"
    )

    c.drawString(
        220,
        550,
        f"Class Standard : {student['class_name']}"
    )

    c.drawString(
        220,
        510,
        f"Roll Number : {student['id']}"
    )

    c.drawString(
        220,
        470,
        f"Contact Number : {student['mobile']}"
    )

    # Footer Blue Box
    c.setFillColorRGB(0.1, 0.3, 0.9)
    c.rect(40, 100, 520, 120, fill=1)

    c.setFillColorRGB(1, 1, 1)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(70, 175, "School Address")

    c.setFont("Helvetica", 10)
    c.drawString(
        70,
        150,
        "Nagar Jamkhed Road, Kolhewadi Phata"
    )

    c.drawString(
        70,
        132,
        "Takali Kazi, Tal Dist Ahilyanagar - 414201"
    )

    c.setFont("Helvetica-Bold", 12)
    c.drawString(420, 140, "Principal")

    c.save()

    return FileResponse(file_name)

@app.get("/export_fees_excel")
def export_fees_excel():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM fees")
    fees = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Fees"

    ws.append([
        "ID",
        "Student ID",
        "Amount",
        "Paid Date",
        "Status"
    ])

    for fee in fees:
        ws.append([
            fee["id"],
            fee["student_id"],
            fee["amount"],
            str(fee["paid_date"]),
            fee["status"]
        ])

    file_name = "fees_report.xlsx"
    wb.save(file_name)

    return FileResponse(file_name, filename=file_name)

@app.get("/export_teachers_excel")
def export_teachers_excel():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Teachers"

    ws.append([
        "ID",
        "Teacher Name",
        "Mobile",
        "Subject",
        "Salary"
    ])

    for teacher in teachers:
        ws.append([
            teacher["id"],
            teacher["teacher_name"],
            teacher["mobile"],
            teacher["subject"],
            teacher["salary"]
        ])

    file_name = "teachers_report.xlsx"
    wb.save(file_name)

    return FileResponse(file_name, filename=file_name)


@app.get("/export_attendance_excel")
def export_attendance_excel():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM attendance")
    attendance = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    ws.append([
        "ID",
        "Student ID",
        "Date",
        "Status"
    ])

    for row in attendance:
        ws.append([
            row["id"],
            row["student_id"],
            row["date"],
            row["status"]
        ])

    file_name = "attendance_report.xlsx"
    wb.save(file_name)

    return FileResponse(file_name, filename=file_name)

@app.get("/export_results_excel")
def export_results_excel():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM results")
    results = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    ws.append([
        "ID",
        "Student ID",
        "Subject",
        "Marks",
        "Total Marks",
        "Percentage",
        "Result"
    ])

    for result in results:
        ws.append([
            result["id"],
            result["student_id"],
            result["subject"],
            result["marks"],
            result["total_marks"],
            result["percentage"],
            result["result_status"]
        ])

    file_name = "results_report.xlsx"
    wb.save(file_name)

    return FileResponse(file_name, filename=file_name)

@app.get("/attendance_report", response_class=HTMLResponse)
def attendance_report(request: Request):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.student_name,
               a.date,
               a.status
        FROM attendance a
        JOIN students s
        ON a.student_id = s.id
        ORDER BY a.date DESC
    """)

    records = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="records.html",
        context={
            "records": records
        }
    )

@app.get("/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        url="/",
        status_code=303
    )

@app.get("/parent_dashboard/{student_id}", response_class=HTMLResponse)
def parent_dashboard(
    request: Request,
    student_id: int
):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM students WHERE id=%s",
        (student_id,)
    )
    student = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM fees
        WHERE student_id=%s
        ORDER BY id DESC
        LIMIT 1
    """, (student_id,))
    fee = cursor.fetchone()

    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE student_id=%s
        ORDER BY date DESC
        LIMIT 5
    """, (student_id,))
    attendance = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM results
        WHERE student_id=%s
    """, (student_id,))
    results = cursor.fetchall()

    conn.close()

    if not student:
        return {"error": "Student not found"}

    if not fee:
        fee = {
            "total_fee": 0,
            "paid_fee": 0,
            "pending_fee": 0
        }

    return templates.TemplateResponse(
        request=request,
        name="parent_dashboard.html",
        context={
            "student": student,
            "fee": fee,
            "attendance": attendance,
            "results": results
        }
    )

@app.get("/teacher_dashboard", response_class=HTMLResponse)
def teacher_dashboard(request: Request):

    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    user_role = request.session.get("role", "").lower()

    if user_role != "teacher":
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    total_students = len(students)

    cursor.execute("SELECT COUNT(*) as total FROM attendance")
    today_attendance = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM homework")
    pending_homework = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM results")
    total_results = cursor.fetchone()["total"]

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="teacher_dashboard.html",
        context={
            "teacher_name": request.session["user"],
            "students": students,
            "total_students": total_students,
            "today_attendance": today_attendance,
            "pending_homework": pending_homework,
            "total_results": total_results
        }
    )
    
@app.get("/online_admission", response_class=HTMLResponse)
def online_admission_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="online_admission.html",
        context={}
    )

@app.post("/submit_admission")
async def submit_admission(
    request: Request,
    photo: UploadFile = File(...)
):
    try:
        form = await request.form()

        student_name = form.get("student_name")
        class_name = form.get("class_name")
        father_name = form.get("father_name")
        mother_name = form.get("mother_name")
        mobile = form.get("mobile")
        address = form.get("address")
        dob = form.get("dob")
        aadhaar = form.get("aadhaar")
        previous_school = form.get("previous_school")

        photo_path = f"static/uploads/{photo.filename}"

        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO online_admissions
            (
                student_name,
                class_name,
                father_name,
                mother_name,
                mobile,
                address,
                dob,
                aadhaar,
                previous_school,
                photo
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            student_name,
            class_name,
            father_name,
            mother_name,
            mobile,
            address,
            dob,
            aadhaar,
            previous_school,
            photo_path
        ))

        conn.commit()
        conn.close()

        return {"status": "Admission Submitted Successfully"}

    except Exception as e:
        return {"error": str(e)}

@app.get("/admission_requests", response_class=HTMLResponse)
def admission_requests(request: Request):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM online_admissions")
    admissions = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="admission_requests.html",
        context={"admissions": admissions}
    )

@app.get("/approve_admission/{admission_id}")
def approve_admission(admission_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM online_admissions WHERE id=%s",
        (admission_id,)
    )

    student = cursor.fetchone()

    cursor.execute("""
        INSERT INTO students
        (
            student_name,
            class_name,
            father_name,
            mobile,
            photo
        )
        VALUES (%s,%s,%s,%s,%s)
    """, (
        student["student_name"],
        student["class_name"],
        student["father_name"],
        student["mobile"],
        student["photo"]
    ))

    student_id = cursor.lastrowid

    # Parent login auto create
    parent_username = student["mobile"]
    parent_password = bcrypt.hashpw(
        "123456".encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    cursor.execute("""
        INSERT INTO users
        (
            username,
            password,
            role,
            student_id
        )
        VALUES (%s,%s,%s,%s)
    """, (
        parent_username,
        parent_password,
        "parent",
        student_id
    ))

    cursor.execute(
        "DELETE FROM online_admissions WHERE id=%s",
        (admission_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admission_requests",
        status_code=303
    )

@app.get("/change_password/{student_id}", response_class=HTMLResponse)
def change_password_page(request: Request, student_id: int):
    return templates.TemplateResponse(
        request=request,
        name="change_password.html",
        context={"student_id": student_id}
    )

@app.post("/update_password/{student_id}")
async def update_password(
    request: Request,
    student_id: int,
    new_password: str = Form(...)
):
    hashed_password = bcrypt.hashpw(
        new_password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET password=%s
        WHERE student_id=%s
        AND role='parent'
    """, (
        hashed_password,
        student_id
    ))

    conn.commit()
    conn.close()

    return {"status": "Password Changed Successfully"}

@app.get("/reject_admission/{admission_id}")
def reject_admission(admission_id: int):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM online_admissions WHERE id=%s",
        (admission_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admission_requests",
        status_code=303
    )

@app.get("/add_homework", response_class=HTMLResponse)
def add_homework_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add_homework.html",
        context={}
    )

@app.post("/save_homework")
async def save_homework(request: Request):
    form = await request.form()

    class_name = form.get("class_name")
    subject = form.get("subject")
    homework_text = form.get("homework_text")
    homework_date = form.get("homework_date")

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO homework
        (
            class_name,
            subject,
            homework_text,
            homework_date
        )
        VALUES (%s,%s,%s,%s)
    """, (
        class_name,
        subject,
        homework_text,
        homework_date
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/add_homework",
        status_code=303
    )

@app.get("/parent_homework/{student_id}", response_class=HTMLResponse)
def parent_homework(request: Request, student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT class_name FROM students WHERE id=%s",
        (student_id,)
    )

    student = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM homework WHERE class_name=%s",
        (student["class_name"],)
    )

    homework = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="parent_homework.html",
        context={"homework": homework}
    )

@app.get("/add_notice", response_class=HTMLResponse)
def add_notice_page(request: Request):

    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    if request.session.get("role") not in ["admin", "teacher"]:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="add_notice.html",
        context={}
    )

@app.post("/save_notice")
async def save_notice(request: Request):
    form = await request.form()

    title = form.get("title")
    message = form.get("message")

    conn = connect_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO notices (title, message, notice_date)
            VALUES (%s, %s, CURDATE())
        """, (title, message))

    except:
        cursor.execute("""
            INSERT INTO notices (title, notice_text, notice_date)
            VALUES (%s, %s, CURDATE())
        """, (title, message))

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/view_notices",
        status_code=303
    )

@app.get("/view_notices", response_class=HTMLResponse)
def view_notices(request: Request):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM notices ORDER BY id DESC")
    notices = cursor.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="view_notices.html",
        context={"notices": notices}
    )

@app.get("/notice/{notice_id}", response_class=HTMLResponse)
def notice_details(request: Request, notice_id: int):

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM notices WHERE id=%s",
        (notice_id,)
    )

    notice = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="notice_details.html",
        context={
            "notice": notice
        }
    )

@app.get("/delete_notice/{notice_id}")
def delete_notice(notice_id: int):

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM notices WHERE id=%s",
        (notice_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/view_notices",
        status_code=303
    )

@app.get("/edit_notice/{notice_id}", response_class=HTMLResponse)
def edit_notice(request: Request, notice_id: int):

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM notices WHERE id=%s",
        (notice_id,)
    )

    notice = cursor.fetchone()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="edit_notice.html",
        context={"notice": notice}
    )

@app.get("/export_students_excel")
def export_students_excel():

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id,
               student_name,
               class_name,
               father_name,
               mobile,
               yearly_fee
        FROM students
    """)

    students = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(students)

    file_name = "students.xlsx"
    df.to_excel(file_name, index=False)

    return FileResponse(
        path=file_name,
        filename=file_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/web_homework_list", response_class=HTMLResponse)
def web_homework_list(request: Request):

    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    if request.session.get("role") not in ["teacher", "admin"]:
        return RedirectResponse("/", status_code=303)

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM homework
        ORDER BY id DESC
    """)

    homework_list = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="homework_list.html",
        context={
            "homework_list": homework_list
        }
    )

@app.get("/teacher_reports", response_class=HTMLResponse)
def teacher_reports(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    if request.session.get("role") not in ["admin", "teacher"]:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="teacher_reports.html",
        context={}
    )

@app.get("/web_reports", response_class=HTMLResponse)
def web_reports(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/", status_code=303)

    if request.session.get("role") not in ["admin", "teacher"]:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="web_reports.html",
        context={}
    )

@app.get("/fix_db")
def fix_db():
    conn = connect_db()
    cursor = conn.cursor()

    queries = [
        "ALTER TABLE teachers ADD class_name VARCHAR(50)",
        "ALTER TABLE teachers ADD division VARCHAR(20)",
        "ALTER TABLE users ADD class_name VARCHAR(50)",
        "ALTER TABLE users ADD division VARCHAR(20)",
        "ALTER TABLE users ADD mobile VARCHAR(15)"
    ]

    for q in queries:
        try:
            cursor.execute(q)
        except Exception as e:
            print("Skipped:", e)

    conn.commit()
    conn.close()

    return {"status": "database fixed"}

@app.post("/save_attendance")
async def save_attendance(request: Request):
    form = await request.form()

    attendance_date = form.get("attendance_date")

    conn = connect_db()
    cursor = conn.cursor()

    for key in form.keys():
        if key.startswith("status_"):
            student_id = key.split("_")[1]
            status = form.get(key)

            cursor.execute("""
                INSERT INTO attendance
                (student_id, date, status)
                VALUES (%s, %s, %s)
            """, (
                student_id,
                attendance_date,
                status
            ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/web_attendance",
        status_code=303
    )

@app.post("/parent_login")
def parent_login(
    mobile: str = Query(...),
    password: str = Query(...)
):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    mobile = mobile.strip()

    cursor.execute("""
        SELECT * FROM users
        WHERE mobile=%s
    """, (mobile,))

    user = cursor.fetchone()

    print("Mobile Received:", mobile)
    print("User Found:", user)

    conn.close()

    if user is None:
        return {
            "status": "failed",
            "message": "Parent not found"
        }

    if bcrypt.checkpw(
        password.encode("utf-8"),
        user["password"].encode("utf-8")
    ):
        return {
            "status": "success",
            "role": user["role"],
            "student_id": user["student_id"]
        }

    return {
        "status": "failed",
        "message": "Wrong password"
    }

@app.get("/parent_dashboard_api/{student_id}")
def parent_dashboard_api(student_id: int):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM students WHERE id=%s",
        (student_id,)
    )
    student = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM fees WHERE student_id=%s",
        (student_id,)
    )
    fee = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM attendance WHERE student_id=%s",
        (student_id,)
    )
    attendance = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM results WHERE student_id=%s",
        (student_id,)
    )
    results = cursor.fetchall()

    conn.close()

    return {
        "student": student,
        "fee": fee,
        "attendance": attendance,
        "results": results
    }
