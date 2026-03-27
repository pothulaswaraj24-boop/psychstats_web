from flask import Flask, render_template, request
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import os
import time
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib
matplotlib.use('Agg')

final_report = []

app = Flask(__name__)

UPLOAD_FOLDER = "static"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    graph_path = ""
    columns = []
    file_path = None

    if request.method == "POST":

        # 🔹 Upload CSV
        if request.form.get("upload") == "1":
            file = request.files.get("file")

            if file and file.filename != "":
                filename = f"{time.time()}_{file.filename}"
                file_path = os.path.join("static", filename)
                file.save(file_path)

                # ✅ FIX: READ FILE AFTER SAVING
                data = pd.read_csv(file_path)
                data.columns = data.columns.str.strip()
                columns = list(data.columns)

                print("UPLOAD SUCCESS:", columns)

        # 🔹 Run Analysis
        elif "analyze" in request.form:
            graph_path = ""
            final_report.clear()
            file_path = request.form.get("file_path")

            if file_path:
                data = pd.read_csv(file_path)
                data.columns = data.columns.str.strip()
                columns = list(data.columns)

                test_type = request.form.get("test")

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
                    
                    plt.figure()
                    plt.bar([col1, col2], [g1.mean(), g2.mean()])
                    filename = f"static/ttest_{time.time()}.png"
                    plt.savefig(filename)
                    plt.clf()
                    plt.close()
                    graph_path = filename
                    
                    final_report.append({
                        "title": "T-Test",
                        "text": result,
                        "image": graph_path
                    })

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
                    
                    
                    plt.figure()
                    plt.scatter(x, y)
                    filename = f"static/corr_{time.time()}.png"
                    plt.savefig(filename)
                    plt.clf()
                    plt.close()
                    graph_path = filename
                    
                    final_report.append({
                        "title": "Correlation",
                        "text": result,
                        "image": graph_path
                    })

                elif test_type == "anova":
                    selected_cols = request.form.getlist("anova_cols")

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

                    plt.figure()
                    means = [g.mean() for g in groups]
                    plt.bar(valid_cols, means)
                    filename = f"static/anova_{time.time()}.png"
                    plt.savefig(filename)
                    plt.clf()
                    plt.close()

                    graph_path = filename

                    final_report.append({
                        "title": "ANOVA",
                        "text": result,
                        "image": graph_path
                    })


    return render_template("index.html",
                           result=result,
                           graph=graph_path,
                           columns=columns,
                           file_path=file_path)


@app.route("/download")
def download_pdf():
    file_path = "static/report.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("PsychStats Report", styles['Title']))
    content.append(Spacer(1, 20))

    for section in final_report:
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

    return f'<a href="/{file_path}" download>Click here to download PDF</a>'



if __name__ == "__main__":
    app.run(debug=True)