from flask import Flask, render_template, request, session
from flask import redirect, url_for
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import os
import time
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib
matplotlib.use('Agg')
import glob
from flask import jsonify
from flask import send_file

from models import db, User
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask import Flask

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ✅ CREATE FOLDER IF NOT EXISTS
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def clean_static_folder(folder="static", max_age_seconds=300):
    now = time.time()
    
    for file in glob.glob(f"{folder}/*"):
        if os.path.isfile(file):
            file_age = now - os.path.getmtime(file)
            
            if file_age > max_age_seconds:
                try:
                    os.remove(file)
                except:
                    pass

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        email = request.form.get("email")

        # 🔒 check duplicate
        existing = User.query.filter_by(username=username).first()
        if existing:
            return "Username already exists"

        hashed = generate_password_hash(password)

        user = User(
            username=username,
            password=hashed,
            full_name=full_name,
            email=email
        )

        db.session.add(user)
        db.session.commit()

        return "Registered! Now login."

    return render_template("register.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):

        current_agent = request.headers.get('User-Agent')

        if not user.user_agent:
            user.user_agent = current_agent
            db.session.commit()

        elif user.user_agent != current_agent:
            return jsonify({"status": "error", "message": "Account already used on another device"})

        login_user(user)
        return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "Invalid credentials"})

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))



@app.route("/", methods=["GET", "POST"])
#@login_required
def index():
    if not current_user.is_authenticated:
        return render_template("index.html",
                               result="",
                               graph="",
                               columns=[],
                               file_path=None,
                               username=None)
    result = ""
    graph_path = ""
    columns = []
    file_path = None

   # if request.method == "POST":
    if request.method == "POST":
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if "report" not in session:
            session["report"] = []
            
        clean_static_folder()

        # 🔹 Upload CSV
        if request.form.get("upload") == "1":
            file = request.files.get("file")

            if file and file.filename != "":
                filename = f"{time.time()}_{file.filename}"
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                print("Saved file path:", file_path)

                # ✅ SAVE in session (VERY IMPORTANT)
                session["file_path"] = file_path

                # ✅ FIX: READ FILE AFTER SAVING
                data = pd.read_csv(file_path)
                data.columns = data.columns.str.strip()
                columns = list(data.columns)

                print("UPLOAD SUCCESS:", columns)

        # 🔹 Run Analysis
        elif "analyze" in request.form:
            graph_path = ""
            session["report"] = []
            file_path = session.get("file_path")

            if file_path:
                data = pd.read_csv(file_path)
                data.columns = data.columns.str.strip()
                columns = list(data.columns)

                test_type = request.form.get("test")
                
                selected_cols = request.form.getlist("anova_cols")
                col1 = request.form.get("col1")
                col2 = request.form.get("col2")

                # 🔴 VALIDATION LOGIC
                if test_type == "ttest":
                    if not col1 or not col2:
                        result = "❌ Please select exactly 2 columns for T-test"
                        return render_template("index.html",
                                               result=result,
                                               columns=columns,
                                               file_path=file_path)

                if test_type == "correlation":
                    if not col1 or not col2:
                        result = "❌ Please select exactly 2 columns for Correlation"
                        return render_template("index.html",
                                               result=result,
                                               columns=columns,
                                               file_path=file_path)

                if test_type == "anova":
                    if len(selected_cols) < 3:
                        result = "❌ Please select at least 3 columns for ANOVA"
                        return render_template("index.html",
                                               result=result,
                                               columns=columns,
                                               file_path=file_path)

                if test_type == "ttest":
                    col1 = request.form.get("col1")
                    col2 = request.form.get("col2")
                    
                    g1 = pd.to_numeric(data[col1], errors='coerce').dropna()
                    g2 = pd.to_numeric(data[col2], errors='coerce').dropna()

                    if len(g1) == 0 or len(g2) == 0:
                        result = "Selected columns have no numeric data"
                        return render_template("index.html",
                                               result=result,
                                               graph=graph_path,
                                               columns=columns,
                                               file_path=file_path)
            
                    t, p = stats.ttest_ind(g1, g2)
                    result = f"T={t:.3f}, p={p:.4f}"
                    
                    plt.figure(figsize=(6,4))
                    plt.bar([col1, col2], [g1.mean(), g2.mean()], width=0.4)
                    plt.tight_layout()
                    filename = f"ttest_{time.time()}.png"
                    full_path = os.path.join("static", filename)
                    plt.savefig(full_path)
                    plt.close()
                    graph_path = f"/static/{filename}"
                    plt.savefig(filename)
                    
                    report = session.get("report", [])
                    
                    report.append({
                        "title": "T-Test",
                        "text": result,
                        "image": full_path
                    })
                    
                    session["report"] = report

                elif test_type == "correlation":
                    col1 = request.form.get("col1")
                    col2 = request.form.get("col2")

                    x = pd.to_numeric(data[col1], errors='coerce').dropna()
                    y = pd.to_numeric(data[col2], errors='coerce').dropna()

                    min_len = min(len(x), len(y))
                    x = x[:min_len]
                    y = y[:min_len]
                    
                    if min_len == 0:
                        result = "Columns do not contain valid numeric data"
                        return render_template("index.html",
                                               result=result,
                                               graph=graph_path,
                                               columns=columns,
                                               file_path=file_path) 

                    r, p = stats.pearsonr(x, y)
                    result = f"r={r:.3f}, p={p:.4f}"
                    
                    
                    plt.figure(figsize=(6,4))
                    plt.scatter(x, y)
                    plt.tight_layout()
                    filename = f"corr_{time.time()}.png"
                    full_path = os.path.join("static", filename)
                    plt.savefig(full_path)
                    graph_path = f"/static/{filename}"
                    plt.savefig(filename)
                    
                    report = session.get("report", [])
                    
                    report.append({
                        "title": "Correlation",
                        "text": result,
                        "image": full_path
                    })
                    
                    session["report"] = report

                elif test_type == "anova":
      #              selected_cols = request.form.getlist("anova_cols")

                    groups = []
                    valid_cols = []

                    for c in selected_cols:
                        g = pd.to_numeric(data[c], errors='coerce').dropna()
                        if len(g) > 0:
                            groups.append(g)
                            valid_cols.append(c)

                    if len(groups) < 3:
                        result = "Need at least 3 valid numeric columns"
                        return render_template("index.html",
                                               result=result,
                                               graph=graph_path,
                                               columns=columns,
                                               file_path=file_path)

                    # ✅ NOW runs correctly
                    f, p = stats.f_oneway(*groups)
                    result = f"F={f:.3f}, p={p:.4f}"

                    plt.figure(figsize=(6,4))
                    means = [g.mean() for g in groups]
                    plt.bar(valid_cols, means, width=0.4)
                    plt.tight_layout()
                    filename = f"anova_{time.time()}.png"
                    full_path = os.path.join("static", filename)
                    plt.savefig(full_path)
                    graph_path = f"/static/{filename}"
                    plt.savefig(filename)

                    
                    report = session.get("report", [])

                    report.append({
                        "title": "ANOVA",
                        "text": result,
                        "image": full_path
                    })
                    
                    session["report"] = report
                    
    return render_template("index.html",
                           result=result,
                           graph=graph_path,
                           columns=columns,
                           file_path=session.get("file_path"),
                           username=current_user.username)


@app.route("/download")
def download_pdf():
    file_path = "static/report.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("PsychStats Report", styles['Title']))
    content.append(Spacer(1, 20))
    
    report = session.get("report", [])

    for section in report:
        content.append(Paragraph(section["title"], styles['Heading2']))
        content.append(Spacer(1, 10))

        for line in section["text"].split("\n"):
            content.append(Paragraph(line, styles['Normal']))
            content.append(Spacer(1, 5))

        content.append(Spacer(1, 10))

        if section["image"] and os.path.exists(section["image"]):
            content.append(Image(section["image"], width=400, height=300))

        content.append(Spacer(1, 20))

    doc.build(content)

    # ✅ DIRECT DOWNLOAD (NO EXTRA PAGE)
    return send_file(file_path, as_attachment=True, download_name="PsychStats_Report.pdf")


#app.run(debug=True)

with app.app_context():
    db.create_all()
 
#@app.route("/create-user")
#def create_user():
    # 🔥 DELETE ALL USERS FIRST
#    User.query.delete()
#    db.session.commit()

#    username = "swaraj_admin"
#    password = generate_password_hash("Swaraj@123")

#    user = User(username=username, password=password)
#    db.session.add(user)
#    db.session.commit()

#    return "User reset and created!"    
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)