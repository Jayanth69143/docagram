from datetime import datetime
import io
import zipfile

from flask import Flask, request, session, redirect, url_for, render_template, flash, send_file, abort
from flask_pymongo import PyMongo
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["MONGO_URI"] = "mongodb+srv://Vercel-Admin-atlas-amber-compass:hOVMjEKLebuU3C07@atlas-amber-compass.57nlolp.mongodb.net/?retryWrites=true&w=majority"

mongo = PyMongo(app)


def decompress_zip_file(data: bytes):
    """Return (file_bytes, filename) for the first file inside the ZIP."""
    with io.BytesIO(data) as bio:
        with zipfile.ZipFile(bio, "r") as zf:
            names = zf.namelist()
            if not names:
                return b"", ""
            filename = names[0]
            return zf.read(filename), filename


def get_file_or_404(file_id: int):
    file_doc = mongo.db.files.find_one({"id": file_id})
    if not file_doc:
        abort(404)
    return file_doc


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


if __name__ == "__main__":
    # Use the built-in Flask dev server (not for production)
    app.run(host="0.0.0.0", port=5000, debug=True)
