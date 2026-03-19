from flask import Flask
from flask_pymongo import PyMongo
from pymongo import ASCENDING

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://Vercel-Admin-atlas-amber-compass:hOVMjEKLebuU3C07@atlas-amber-compass.57nlolp.mongodb.net/?retryWrites=true&w=majority"

mongo = PyMongo(app)

with app.app_context():
    db = mongo.db

    # Create unique indexes (similar to MySQL constraints)
    db.users.create_index("username", unique=True)
    db.files.create_index([("id", ASCENDING)], unique=True)
    db.files.create_index([("uploaded_by", ASCENDING)])
    db.download_logs.create_index([("file_id", ASCENDING)])
    db.activity_logs.create_index([("user_id", ASCENDING)])

    print("MongoDB indexes created/ensured.")
