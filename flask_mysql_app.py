import os
import io
import zipfile
import hashlib
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "postgresql://localhost/docagram"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    files = db.relationship("File", backref="uploader", lazy=True)


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    compressed_size = db.Column(db.Integer, nullable=False)
    compressed_data = db.Column(db.LargeBinary, nullable=False)
    file_hash = db.Column(db.String(64))
    download_count = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(255))


def compress_file_to_zip(file_data, filename):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(
        memory_file, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zipf:
        zipf.writestr(filename, file_data)
    return memory_file.getvalue()


def decompress_zip_file(compressed_data):
    with zipfile.ZipFile(io.BytesIO(compressed_data), "r") as zipf:
        original_filename = zipf.namelist()[0]
        original_data = zipf.read(original_filename)
        return original_data, original_filename


def sha256_hash(data):
    return hashlib.sha256(data).hexdigest()


@app.route("/")
def index():
    files = File.query.filter_by(is_public=True).order_by(File.upload_date.desc()).all()
    return render_template("index_mysql.html", files=files)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return redirect(url_for("register"))
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("Registration successful!")
        return redirect(url_for("login"))
    return render_template("register_mysql.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("index"))
        flash("Invalid credentials")
    return render_template("login_mysql.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        file = request.files["file"]
        description = request.form.get("description", "")
        is_public = bool(request.form.get("is_public"))
        if file:
            file_data = file.read()
            compressed_data = compress_file_to_zip(file_data, file.filename)
            file_hash = sha256_hash(file_data)
            new_file = File(
                original_filename=file.filename,
                file_size=len(file_data),
                compressed_size=len(compressed_data),
                compressed_data=compressed_data,
                file_hash=file_hash,
                uploaded_by=session["user_id"],
                is_public=is_public,
                description=description,
            )
            db.session.add(new_file)
            db.session.commit()
            flash("File uploaded and compressed successfully!")
            return redirect(url_for("my_files"))
    return render_template("upload_mysql.html")


@app.route("/my_files")
def my_files():
    if "user_id" not in session:
        return redirect(url_for("login"))
    files = (
        File.query.filter_by(uploaded_by=session["user_id"])
        .order_by(File.upload_date.desc())
        .all()
    )
    return render_template("my_files_mysql.html", files=files)


@app.route("/download/<int:file_id>")
def download(file_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    file = File.query.get_or_404(file_id)
    original_data, original_filename = decompress_zip_file(file.compressed_data)
    file.download_count += 1
    db.session.commit()
    return send_file(
        io.BytesIO(original_data), as_attachment=True, download_name=original_filename
    )


@app.route("/delete/<int:file_id>")
def delete(file_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    file = File.query.get_or_404(file_id)
    if file.uploaded_by != session["user_id"]:
        flash("You can only delete your own files.")
        return redirect(url_for("my_files"))
    db.session.delete(file)
    db.session.commit()
    flash("File deleted successfully!")
    return redirect(url_for("my_files"))


@app.route("/preview/<int:file_id>")
def preview(file_id):
    file = File.query.get_or_404(file_id)
    if not file.is_public and "user_id" not in session:
        return redirect(url_for("login"))
    original_data, original_filename = decompress_zip_file(file.compressed_data)
    from mimetypes import guess_type
    content_type = guess_type(original_filename)[0] or 'application/octet-stream'
    return send_file(
        io.BytesIO(original_data), mimetype=content_type, as_attachment=False, download_name=original_filename
    )


@app.route("/stats")
def stats():
    total_files = File.query.count()
    total_users = User.query.count()
    total_storage = db.session.query(func.sum(File.compressed_size)).scalar() or 0
    top_users = (
        db.session.query(User.username, func.count(File.id))
        .join(File)
        .group_by(User.id)
        .order_by(func.count(File.id).desc())
        .limit(5)
        .all()
    )
    return render_template(
        "stats_mysql.html",
        total_files=total_files,
        total_users=total_users,
        total_storage=total_storage,
        top_users=top_users,
    )


@app.route("/search")
def search():
    query = request.args.get("q", "")
    files = (
        File.query.filter(File.original_filename.like(f"%{query}%")).all()
        if query
        else []
    )
    return render_template("index_mysql.html", files=files, search=query)


if __name__ == "__main__":
    app.run(debug=True)
