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
        # Add missing columns to user table
        db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
        db.session.execute(text("ALTER TABLE user ADD COLUMN ban_until DATETIME NULL"))
        db.session.commit()
        print("User table updated successfully.")
    except Exception as e:
        print(f"Error updating user table: {str(e)}")

    try:
        # Create Tag table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS tag (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL
            )
        """))
        db.session.commit()
        print("Tag table created successfully.")
    except Exception as e:
        print(f"Error creating tag table: {str(e)}")

    try:
        # Create file_tags association table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS file_tags (
                file_id INT NOT NULL,
                tag_id INT NOT NULL,
                PRIMARY KEY (file_id, tag_id),
                FOREIGN KEY (file_id) REFERENCES file(id),
                FOREIGN KEY (tag_id) REFERENCES tag(id)
            )
        """))
        db.session.commit()
        print("file_tags table created successfully.")
    except Exception as e:
        print(f"Error creating file_tags table: {str(e)}")

    try:
        # Create DownloadLog table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS download_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_id INT NOT NULL,
                user_id INT NULL,
                download_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                FOREIGN KEY (file_id) REFERENCES file(id),
                FOREIGN KEY (user_id) REFERENCES user(id)
            )
        """))
        db.session.commit()
        print("DownloadLog table created successfully.")
    except Exception as e:
        print(f"Error creating download_log table: {str(e)}")

    try:
        # Create ActivityLog table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                action VARCHAR(50) NOT NULL,
                file_id INT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details VARCHAR(255),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (file_id) REFERENCES file(id)
            )
        """))
        db.session.commit()
        print("ActivityLog table created successfully.")
    except Exception as e:
        print(f"Error creating activity_log table: {str(e)}")

    try:
        # Create ShareLink table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS share_link (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_id INT NOT NULL,
                token VARCHAR(64) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NULL,
                expiry_time DATETIME NULL,
                allow_download BOOLEAN DEFAULT FALSE,
                created_by INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES file(id),
                FOREIGN KEY (created_by) REFERENCES user(id)
            )
        """))
        db.session.commit()
        print("ShareLink table created successfully.")
    except Exception as e:
        print(f"Error creating share_link table: {str(e)}")

    print("Database migration completed.")
