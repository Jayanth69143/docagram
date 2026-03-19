from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:root@localhost/docagram"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE user ADD COLUMN ban_until DATETIME NULL"))
        db.session.commit()
        print("Database updated successfully.")
    except Exception as e:
        print(f"Error updating database: {str(e)}")
