# MongoDB Student File Sharing App Setup Guide

This guide covers installation and configuration steps to run the DocAgram app using **MongoDB** instead of MySQL.

## 1. Install MongoDB

1. Download and install MongoDB Community Server from https://www.mongodb.com/try/download/community.
2. Start the MongoDB server (e.g., `mongod`).

## 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure the app

The app expects MongoDB to be running on `localhost:27017` and uses the `docagram` database by default.

If you need to change the connection string, edit `flask_mysql_app.py` and update:

```python
app.config["MONGO_URI"] = "mongodb+srv://Vercel-Admin-atlas-amber-compass:hOVMjEKLebuU3C07@atlas-amber-compass.57nlolp.mongodb.net/?retryWrites=true&w=majority"
```

## 4. Run the app

```bash
python flask_mysql_app.py
```

## 5. Notes

- The app stores files and metadata in MongoDB collections:
  - `files`
  - `download_logs`
  - `activity_logs`

- If your data was previously stored in MySQL, you will need to migrate it manually.
