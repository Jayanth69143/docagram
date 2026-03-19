from datetime import datetime, timedelta
import io
import zipfile
import secrets
import hashlib
import os
import sys

from flask import Flask, request, session, redirect, url_for, render_template, flash, send_file, abort
from flask_pymongo import PyMongo
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your_secret_key")
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb+srv://Vercel-Admin-atlas-amber-compass:hOVMjEKLebuU3C07@atlas-amber-compass.57nlolp.mongodb.net/?retryWrites=true&w=majority")

try:
    mongo = PyMongo(app)
    # Test connection
    mongo.db.command('ping')
    print("✅ MongoDB connected successfully")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}", file=sys.stderr)
    mongo = None


@app.route("/")
def index():
    return render_template("index_mysql.html")


@app.route("/favicon.ico")
def favicon():
    return "", 204


# ============ AUTHENTICATION ROUTES ============

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        user = mongo.db.users.find_one({"username": username})
        if not user:
            flash("Invalid username or password.")
            return redirect(url_for("login"))
        
        # Check if user is banned
        if user.get("ban_until"):
            ban_until = user["ban_until"]
            if isinstance(ban_until, str):
                ban_until = datetime.fromisoformat(ban_until)
            if datetime.utcnow() < ban_until:
                hours_left = (ban_until - datetime.utcnow()).total_seconds() / 3600
                flash(f"Your account is banned for {hours_left:.1f} more hours.")
                return redirect(url_for("login"))
            else:
                # Unban user if ban expired
                mongo.db.users.update_one({"_id": user["_id"]}, {"$set": {"ban_until": None}})
        
        if not check_password_hash(user.get("password_hash", ""), password):
            flash("Invalid username or password.")
            return redirect(url_for("login"))
        
        session["user_id"] = str(user["_id"])
        session["username"] = user["username"]
        session["role"] = user.get("role", "user")
        
        return redirect(url_for("my_files"))
    
    return render_template("login_mysql.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not mongo:
            flash("Database connection failed. Please try again later.")
            return redirect(url_for("register"))
        
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))
        
        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("register"))
        
        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists.")
            return redirect(url_for("register"))
        
        try:
            mongo.db.users.insert_one({
                "username": username,
                "password_hash": generate_password_hash(password),
                "role": "user",
                "created_at": datetime.utcnow(),
                "ban_until": None
            })
            
            flash("Registration successful! Please log in.")
            return redirect(url_for("login"))
        except Exception as e:
            print(f"Registration error: {e}", file=sys.stderr)
            flash("Registration failed. Please try again.")
            return redirect(url_for("register"))
    
    return render_template("register_mysql.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# ============ FILE OPERATIONS ============

def decompress_zip_file(data: bytes):
    """Return (file_bytes, filename) for the first file inside the ZIP."""
    with io.BytesIO(data) as bio:
        with zipfile.ZipFile(bio, "r") as zf:
            names = zf.namelist()
            if not names:
                return b"", ""
            filename = names[0]
            return zf.read(filename), filename


def generate_low_quality_image(data: bytes):
    """Generate a low-quality preview image from uploaded data."""
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((200, 200))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=30)
        return img_byte_arr.getvalue()
    except:
        return b""


def compress_to_zip(file_data: bytes, original_filename: str):
    """Compress file data into a ZIP archive."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(original_filename, file_data)
    return zip_buffer.getvalue()


def get_user_or_redirect():
    """Check if user is logged in, redirect to login if not."""
    if "user_id" not in session:
        flash("Please log in first.")
        return None, redirect(url_for("login"))
    return session, None


def get_file_or_404(file_id: int):
    file_doc = mongo.db.files.find_one({"id": file_id})
    if not file_doc:
        abort(404)
    return file_doc


@app.route("/upload", methods=["GET", "POST"])
def upload():
    user_session, redirect_response = get_user_or_redirect()
    if redirect_response:
        return redirect_response
    
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.")
            return redirect(url_for("upload"))
        
        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.")
            return redirect(url_for("upload"))
        
        file_data = file.read()
        original_filename = file.filename
        file_size = len(file_data)
        
        # Compress to ZIP
        compressed_data = compress_to_zip(file_data, original_filename)
        compressed_size = len(compressed_data)
        
        # Get next file ID
        last_file = mongo.db.files.find_one({}, sort=[("id", -1)])
        next_id = (last_file["id"] + 1) if last_file else 1
        
        # Generate file hash
        file_hash = hashlib.sha256(file_data).hexdigest()
        
        # Handle file password
        password_hash = None
        if request.form.get("password"):
            password_hash = generate_password_hash(request.form.get("password"))
        
        # Insert into database
        mongo.db.files.insert_one({
            "id": next_id,
            "original_filename": original_filename,
            "file_size": file_size,
            "compressed_size": compressed_size,
            "compressed_data": compressed_data,
            "file_hash": file_hash,
            "download_count": 0,
            "upload_date": datetime.utcnow(),
            "uploaded_by": session["user_id"],
            "is_public": request.form.get("is_public") == "on",
            "description": request.form.get("description", ""),
            "password_hash": password_hash
        })
        
        # Log activity
        mongo.db.activity_logs.insert_one({
            "user_id": session["user_id"],
            "action": "upload",
            "file_id": next_id,
            "details": f"Uploaded {original_filename}",
            "timestamp": datetime.utcnow()
        })
        
        flash(f"File '{original_filename}' uploaded successfully!")
        return redirect(url_for("my_files"))
    
    return render_template("upload_mysql.html")


@app.route("/my_files")
def my_files():
    user_session, redirect_response = get_user_or_redirect()
    if redirect_response:
        return redirect_response
    
    files = list(mongo.db.files.find({"uploaded_by": session["user_id"]}))
    return render_template("my_files_mysql.html", files=files)


@app.route("/preview/<int:file_id>")
def preview(file_id):
    file = get_file_or_404(file_id)
    
    # Check file password if set
    if file.get("password_hash"):
        if request.method == "POST":
            password = request.form.get("password", "")
            if not check_password_hash(file.get("password_hash"), password):
                flash("Incorrect password.")
                return render_template("file_password.html", file_id=file_id, action="preview")
        else:
            return render_template("file_password.html", file_id=file_id, action="preview")
    
    original_data, original_filename = decompress_zip_file(file.get("compressed_data", b""))
    
    # Try to generate preview image
    preview_image = generate_low_quality_image(original_data)
    preview_b64 = preview_image.hex() if preview_image else ""
    
    # Log activity
    mongo.db.activity_logs.insert_one({
        "user_id": session.get("user_id"),
        "action": "preview",
        "file_id": file_id,
        "details": f"Previewed {original_filename}",
        "timestamp": datetime.utcnow()
    })
    
    return render_template("preview.html", file=file, preview_b64=preview_b64, filename=original_filename)


@app.route("/download/<int:file_id>", methods=["GET", "POST"])
def download(file_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    file = get_file_or_404(file_id)

    # Check file password if set
    if file.get("password_hash"):
        if request.method == "POST":
            password = request.form.get("password", "")
            if not check_password_hash(file.get("password_hash"), password):
                flash("Incorrect password.")
                return render_template("file_password.html", file_id=file_id, action="download")
        else:
            return render_template("file_password.html", file_id=file_id, action="download")

    original_data, original_filename = decompress_zip_file(file.get("compressed_data", b""))

    # Update counter
    mongo.db.files.update_one({"id": file_id}, {"$inc": {"download_count": 1}})

    # Log download
    mongo.db.download_logs.insert_one({
        "file_id": file_id,
        "user_id": session.get("user_id"),
        "ip_address": request.remote_addr,
        "timestamp": datetime.utcnow(),
    })

    # Log activity
    mongo.db.activity_logs.insert_one({
        "user_id": session.get("user_id"),
        "action": "download",
        "file_id": file_id,
        "details": f"Downloaded {original_filename}",
        "timestamp": datetime.utcnow(),
    })

    return send_file(
        io.BytesIO(original_data), as_attachment=True, download_name=original_filename
    )


@app.route("/delete/<int:file_id>", methods=["POST"])
def delete_file(file_id):
    user_session, redirect_response = get_user_or_redirect()
    if redirect_response:
        return redirect_response
    
    file = get_file_or_404(file_id)
    
    # Check ownership
    if file["uploaded_by"] != session["user_id"] and session.get("role") != "admin":
        flash("You do not have permission to delete this file.")
        return redirect(url_for("my_files"))
    
    mongo.db.files.delete_one({"id": file_id})
    mongo.db.download_logs.delete_many({"file_id": file_id})
    mongo.db.activity_logs.insert_one({
        "user_id": session["user_id"],
        "action": "delete",
        "file_id": file_id,
        "details": f"Deleted {file['original_filename']}",
        "timestamp": datetime.utcnow()
    })
    
    flash("File deleted successfully.")
    return redirect(url_for("my_files"))


# ============ SHARING ============

@app.route("/create_share_link/<int:file_id>", methods=["POST"])
def create_share_link(file_id):
    user_session, redirect_response = get_user_or_redirect()
    if redirect_response:
        return redirect_response
    
    file = get_file_or_404(file_id)
    
    if file["uploaded_by"] != session["user_id"] and session.get("role") != "admin":
        flash("You do not have permission to share this file.")
        return redirect(url_for("my_files"))
    
    token = secrets.token_urlsafe(32)
    password_hash = None
    
    if request.form.get("share_password"):
        password_hash = generate_password_hash(request.form.get("share_password"))
    
    mongo.db.share_links.insert_one({
        "file_id": file_id,
        "token": token,
        "password_hash": password_hash,
        "expiry_time": None,
        "allow_download": request.form.get("allow_download") == "on",
        "created_by": session["user_id"],
        "created_at": datetime.utcnow()
    })
    
    flash(f"Share link created: /shared/{token}")
    return redirect(url_for("my_files"))


@app.route("/shared/<token>", methods=["GET", "POST"])
def shared_file(token):
    share_link = mongo.db.share_links.find_one({"token": token})
    if not share_link:
        abort(404)
    
    # Check password if required
    if share_link.get("password_hash"):
        if request.method == "POST":
            password = request.form.get("password", "")
            if not check_password_hash(share_link.get("password_hash"), password):
                flash("Incorrect password.")
                return render_template("shared_password.html", token=token)
        else:
            return render_template("shared_password.html", token=token)
    
    file = mongo.db.files.find_one({"id": share_link["file_id"]})
    if not file:
        abort(404)
    
    original_data, original_filename = decompress_zip_file(file.get("compressed_data", b""))
    preview_image = generate_low_quality_image(original_data)
    preview_b64 = preview_image.hex() if preview_image else ""
    
    return render_template("shared.html", file=file, share_link=share_link, preview_b64=preview_b64, filename=original_filename)


@app.route("/shared_download/<token>")
def shared_download(token):
    share_link = mongo.db.share_links.find_one({"token": token})
    if not share_link or not share_link.get("allow_download"):
        abort(404)
    
    file = mongo.db.files.find_one({"id": share_link["file_id"]})
    if not file:
        abort(404)
    
    original_data, original_filename = decompress_zip_file(file.get("compressed_data", b""))
    
    mongo.db.download_logs.insert_one({
        "file_id": file["id"],
        "user_id": None,
        "ip_address": request.remote_addr,
        "timestamp": datetime.utcnow()
    })
    
    return send_file(
        io.BytesIO(original_data), as_attachment=True, download_name=original_filename
    )


# ============ ADMIN ROUTES ============

@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        flash("Admin access required.")
        return redirect(url_for("index"))
    
    users = list(mongo.db.users.find())
    files = list(mongo.db.files.find())
    download_logs = list(mongo.db.download_logs.find())
    
    return render_template("admin.html", users=users, files=files, download_logs=download_logs)


@app.route("/activity_log")
def activity_log():
    if session.get("role") != "admin":
        flash("Admin access required.")
        return redirect(url_for("index"))
    
    logs = list(mongo.db.activity_logs.find().sort("timestamp", -1).limit(100))
    return render_template("activity_log.html", logs=logs)


@app.route("/stats")
def stats():
    if session.get("role") != "admin":
        flash("Admin access required.")
        return redirect(url_for("index"))
    
    total_users = mongo.db.users.count_documents({})
    total_files = mongo.db.files.count_documents({})
    total_downloads = mongo.db.download_logs.count_documents({})
    
    return render_template("stats_mysql.html", total_users=total_users, total_files=total_files, total_downloads=total_downloads)


@app.route("/ban_user/<user_id>", methods=["POST"])
def ban_user(user_id):
    if session.get("role") != "admin":
        flash("Admin access required.")
        return redirect(url_for("index"))
    
    hours = int(request.form.get("hours", 24))
    ban_until = datetime.utcnow() + timedelta(hours=hours)
    
    mongo.db.users.update_one({"_id": user_id}, {"$set": {"ban_until": ban_until}})
    
    mongo.db.activity_logs.insert_one({
        "user_id": session["user_id"],
        "action": "ban_user",
        "details": f"Banned user {user_id} for {hours} hours",
        "timestamp": datetime.utcnow()
    })
    
    flash(f"User banned for {hours} hours.")
    return redirect(url_for("admin"))


@app.route("/unban_user/<user_id>", methods=["POST"])
def unban_user(user_id):
    if session.get("role") != "admin":
        flash("Admin access required.")
        return redirect(url_for("index"))
    
    mongo.db.users.update_one({"_id": user_id}, {"$set": {"ban_until": None}})
    
    mongo.db.activity_logs.insert_one({
        "user_id": session["user_id"],
        "action": "unban_user",
        "details": f"Unbanned user {user_id}",
        "timestamp": datetime.utcnow()
    })
    
    flash("User unbanned.")
    return redirect(url_for("admin"))


@app.route("/delete_user/<user_id>", methods=["POST"])
def delete_user(user_id):
    if session.get("role") != "admin":
        flash("Admin access required.")
        return redirect(url_for("index"))
    
    # Delete user's files
    mongo.db.files.delete_many({"uploaded_by": user_id})
    # Delete user
    mongo.db.users.delete_one({"_id": user_id})
    
    mongo.db.activity_logs.insert_one({
        "user_id": session["user_id"],
        "action": "delete_user",
        "details": f"Deleted user {user_id}",
        "timestamp": datetime.utcnow()
    })
    
    flash("User and their files deleted.")
    return redirect(url_for("admin"))


# ============ SEARCH ============

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    
    if not query:
        return render_template("index_mysql.html", files=[])
    
    # Search in public files and user's own files
    files = list(mongo.db.files.find({
        "$or": [
            {"is_public": True, "original_filename": {"$regex": query, "$options": "i"}},
            {"uploaded_by": session.get("user_id"), "original_filename": {"$regex": query, "$options": "i"}}
        ]
    }))
    
    return render_template("index_mysql.html", files=files, search_query=query)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
