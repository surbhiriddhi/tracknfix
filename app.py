from datetime import datetime
import io
from flask import Flask, request, jsonify, render_template, session, redirect, send_file
import psycopg2
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# ---------- Flask App Setup ----------
app = Flask(__name__, template_folder="templates")
app.secret_key = "random_secret_key_123"

# ---------- Database Config ----------
DB_CONFIG = {
    "host": "localhost",
    "database": "TechnFix",
    "user": "postgres",
    "password": "riddhi1826",
    "port": 5432
}

# ---------- SQLAlchemy Config ----------
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def get_db_connection():
    """Return a new database connection"""
    return psycopg2.connect(**DB_CONFIG)

# ---------- Email Config ----------
EMAIL_ADDRESS = "tracknfix7@gmail.com"
EMAIL_PASSWORD = "jrmk iase fuav furo"  # App password

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Email Error:", e)
        return False
    

    # ---------- Upload folder ----------
UPLOAD_FOLDER = "upload1"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


#---------- File Upload Route ----------
# ---------- Upload file ----------
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['photo']   # "photo" name form se aayega
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        return f"Photo saved successfully in folder: {filepath}"
    return " No file selected"


# ---------- Home / Login ----------
@app.route('/')
def home():
    return render_template("login.html")

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")
    except Exception as e:
        return jsonify({"status": "fail", "msg": f"Invalid JSON: {str(e)}"}), 400

    if not username or not password:
        return jsonify({"status": "fail", "msg": "Username and password required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username FROM users
            WHERE LOWER(username) = LOWER(%s) AND password = %s
        """, (username, password))
        user = cur.fetchone()
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

    if user:
        session["user_id"] = user[0]
        uname = user[1].upper()
        if uname.startswith("ADMIN"):
            redirect_url = "/admin_dashboard"
        elif uname.startswith("STU"):
            redirect_url = "/student_dashboard"
        elif uname.startswith("FAC"):
            redirect_url = "/student_dashboard"
        else:
            redirect_url = "/dashboard"
        return jsonify({"status": "success", "redirect": redirect_url})
    else:
        return jsonify({"status": "fail", "msg": "Invalid credentials"}), 401
    
#-----logout-----
@app.route("/logout")
def logout():
    # Clear the user session
    session.clear()
    # Redirect to login page
    return render_template("login.html")

# ---------- Dashboards ----------
@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route('/student_dashboard')
def student_dashboard():
    return render_template("student_dashboard.html")

@app.route('/staff_dashboard')
def staff_dashboard():
   return render_template("staff_dashboard.html")

@app.route('/dashboard')
def dashboard():
    return render_template("dashboard.html")

# ---------- Dashboard Stats ----------
@app.route("/dashboard/stats")
def dashboard_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='pending'")
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='in_process'")
    in_process = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='resolved'")
    resolved = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({
        "total": total,
        "pending": pending,
        "in_process": in_process,
        "resolved": resolved
    })

@app.route("/dashboard/categories")
def dashboard_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT category, COUNT(*) FROM complaints GROUP BY category")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"category": c, "count": cnt} for c, cnt in data])

# ---------- Pending Complaints ----------
@app.route("/pending")
def pending_page():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c_id, user_id, category, description, file_data, file_type, priority, status, created_at
        FROM complaints
        WHERE status='pending'
        ORDER BY created_at DESC
    """)
    complaints = [
        {
            "c_id": row[0],
            "user_id": row[1],
            "category": row[2],
            "description": row[3],
            "file_data": row[4],
            "file_type": row[5],
            "priority": row[6],
            "status": row[7],
            "created_at": row[8]
        }
        for row in cur.fetchall()
    ]
    cur.close()
    conn.close()
    return render_template("admin_pending.html", complaints=complaints)


# ---------- In Process ----------
@app.route("/inprocess")
def inprocess_page():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c_id, category, description, assigned_to, created_at
        FROM complaints
        WHERE status='in_process'
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    assign_map = {
        "academics": "Academic Officer",
        "infrastructure": "Maintenance Officer",
        "security": "Security Head",
        "cafeteria": "Canteen Manager"
    }

    complaints = []
    for row in rows:
        assigned_to = row[3] or assign_map.get(row[1].lower(), "General Admin")
        complaints.append({
            "c_id": row[0],
            "category": row[1],
            "description": row[2],
            "assigned_to": assigned_to,
            "created_at": row[4]
        })
    return render_template("admin_inprogress.html", complaints=complaints)

@app.route("/complaint/<int:c_id>/assign", methods=["POST"])
def assign_complaint(c_id):
    try:
        data = request.get_json() or {}
        category = data.get("category")
        assign_map = {
            "academics": "Academic Officer",
            "infrastructure": "Maintenance Officer",
            "security": "Security Head",
            "cafeteria": "Canteen Manager"
        }
        assigned_to = assign_map.get(category.lower(), "General Admin") if category else "General Admin"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE complaints
            SET status='in_process', assigned_to=%s
            WHERE c_id=%s
        """, (assigned_to, c_id))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "assigned_to": assigned_to})
    except Exception as e:
        return jsonify({"status": "fail", "msg": str(e)})

# ---------- Resolved ----------
@app.route('/complaint/<int:c_id>/solve', methods=['POST'])
def mark_complaint_resolved(c_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE complaints
            SET status='resolved', resolved_at=NOW()
            WHERE c_id=%s
        """, (c_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "msg": "Complaint moved to resolved"})
    except Exception as e:
        return jsonify({"status": "fail", "msg": str(e)}), 500

@app.route('/resolved')
def resolved_page():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
       SELECT c.c_id, c.category, c.description, c.assigned_to, c.resolved_at, u.username, u.email
FROM complaints c
JOIN users u ON c.user_id = u.id
WHERE c.status='resolved'
ORDER BY c.resolved_at DESC;
    """)
    rows = cur.fetchall()
    complaints = [
        {
            "c_id": r[0],
            "category": r[1],
            "description": r[2],
            "assigned_to": r[3] or "General Admin",
            "resolved_at": r[4],
            "username": r[5],
            "email": r[6]
        }
        for r in rows
    ]
    cur.close()
    conn.close()
    return render_template("admin_resolve.html", complaints=complaints)

@app.route('/complaint/<int:c_id>/solve_and_notify', methods=['POST'])
def solve_and_notify(c_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE complaints
            SET status='resolved', resolved_at=NOW()
            WHERE c_id=%s
        """, (c_id,))
        conn.commit()

        cur.execute("""
            SELECT u.email, c.category, c.description
            FROM complaints c
            JOIN users u ON c.user_id = u.id
            WHERE c.c_id=%s
        """, (c_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            to_email, category, desc = row
            subject = f"Complaint #{c_id} Resolved ✅"
            body = f"""Dear User,

Your complaint '{category}' has been resolved.

Details:
{desc}

Regards,
TechnFix Team
"""
            if send_email(to_email, subject, body):
                return jsonify({"status": "success", "msg": f"Resolved & notified {to_email}"})
            else:
                return jsonify({"status": "fail", "msg": "Resolved but email failed"}), 500
        else:
            return jsonify({"status": "fail", "msg": "Complaint not found"}), 404
    except Exception as e:
        return jsonify({"status": "fail", "msg": str(e)}), 500

# ---------- Notify ----------
@app.route('/complaint/<int:c_id>/notify', methods=['POST'])
def notify_user(c_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.email, c.category, c.description
            FROM complaints c
            JOIN users u ON c.user_id = u.id
            WHERE c.c_id=%s
        """, (c_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            to_email, category, desc = row
            subject = f"Complaint #{c_id} Resolved ✅"
            body = f"""Dear User,

Your complaint '{category}' has been resolved.

Details:
{desc}

Regards,
TechnFix Team
"""
            if send_email(to_email, subject, body):
                return jsonify({"status": "success", "msg": f"Notification sent to {to_email}"})
            else:
                return jsonify({"status": "fail", "msg": "Email sending failed"}), 500
        else:
            return jsonify({"status": "fail", "msg": "Complaint not found"}), 404
    except Exception as e:
        return jsonify({"status": "fail", "msg": str(e)}), 500

# ---------- Feedback ----------
@app.route('/feedback')
def feedback_page():
    if "user_id" not in session:
        return redirect("/")
    
    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT c_id FROM complaints WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
    row = cur.fetchone()
    last_complaint_id = row[0] if row else None
    cur.close()
    conn.close()
    return render_template("feedback.html", last_complaint_id=last_complaint_id)

@app.route('/api/feedback', methods=['POST'])
def feedback_api():
    if "user_id" not in session:
        return jsonify({"status": "fail", "message": "User not logged in"}), 401

    user_id = session["user_id"]
    rating = request.form.get("rating")
    description = request.form.get("description")
    complaint_id = request.form.get("complaint_id")

    if not rating:
        return jsonify({"status": "fail", "message": "Rating is required"}), 400

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return jsonify({"status": "fail", "message": "Rating must be 1-5"}), 400
    except ValueError:
        return jsonify({"status": "fail", "message": "Invalid rating"}), 400

    complaint_id = int(complaint_id) if complaint_id else None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO feedback (user_id, complaint_id, rating, description)
            VALUES (%s, %s, %s, %s)
        """, (user_id, complaint_id, rating, description))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return jsonify({"status": "success", "message": "Feedback submitted successfully!"})

# ---------- User Complaints ----------
@app.route('/complaints')
def complaints_page():
    if "user_id" not in session:
        return redirect("/")
    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c_id, category, status, description, created_at
        FROM complaints
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    complaints = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("complaints.html", complaints=complaints)

# ---------- Submit Complaint ----------
@app.route('/submit_complaint', methods=['GET','POST'])
def submit_complaint_api():
    if "user_id" not in session:
        # Redirect to login instead of returning JSON for GET
        if request.method == "GET":
            return redirect("/")
        return jsonify({"status": "fail", "message": "Not logged in"}), 401

    if request.method == "POST":
        user_id = session["user_id"]
        category = request.form.get("category")
        description = request.form.get("description")
        file = request.files.get("file")

        if not category or not description:
            return jsonify({"status": "fail", "message": "Category and description are required"}), 400

        file_data = file.read() if file else None
        file_type = file.content_type if file else None

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO complaints (user_id, category, description, file_data, file_type)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, category, description, file_data, file_type))
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return jsonify({
            "status": "success",
            "message": "Complaint submitted successfully!",
            "redirect": "/student_tracking.html"
        })

    # GET method: just render the form
    return render_template("submit_complaint.html")

@app.route("/complaint_file/<int:complaint_id>")
def complaint_file(complaint_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT file_data, file_type FROM complaints WHERE c_id = %s", (complaint_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            file_data, file_type = row
            return send_file(BytesIO(file_data), mimetype=file_type)
        else:
            return "No file attached", 404
    except Exception as e:
        return f"Error: {str(e)}", 500
#--------------
@app.route("/student_tracking")
def student_tracking():
    if "user_id" not in session:
        return redirect("/")
    return render_template("student_tracking.html")

#------- student complaint tracking api -----
#------- student complaint tracking API -----
@app.route("/api/student_complaints")
def api_student_complaints():
    if "user_id" not in session:
        return jsonify([])

    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c_id, category, status, description
        FROM complaints
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    
    # Include description in the response
    complaints = [
        {"c_id": r[0], "category": r[1], "status": r[2], "description": r[3]}
        for r in cur.fetchall()
    ]
    
    cur.close()
    conn.close()
    return jsonify(complaints)

#------add user------
@app.route('/add_user', methods=['POST'])
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        created_at = datetime.now()  # current date & time

        cur.execute("""
    INSERT INTO users (username, email, password, created_at) 
    VALUES (%s, %s, %s, %s)
""", (username, email, password, created_at))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "message": "User added successfully!"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
#---------------------
@app.route('/download/<int:c_id>')
def download_file(c_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT file_data, file_type FROM complaints WHERE c_id = %s", (c_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row and row[0]:
        file_data,file_type = row
        if file_type.startswith("image/"):
            # Display image in browser
            return send_file(
                io.BytesIO(file_data),
                mimetype=file_type,
                as_attachment=False  # <- open in browser
            )
        else:
            # Force download for other files
            return send_file(
                io.BytesIO(file_data),
                mimetype=file_type,
                as_attachment=True
            )
    return "No file found", 404


# ---------- Run Server ----------
if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=5000)