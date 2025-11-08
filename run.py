#!/usr/bin/env python
"""
Run script for Flask application
Usage: python run.py
"""

from app import create_app, db
import os

# Tạo Flask app instance
app = create_app()


@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized!")

if __name__ == '__main__':
    # Tạo thư mục uploads nếu chưa có
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        print(f"Created upload folder: {upload_folder}")

    # Chạy development server
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'

    print("=" * 50)
    print(f"Starting Flask application...")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'production')}")
    print(f"Debug mode: {debug}")
    print(f"Port: {port}")
    print(f"URL: http://localhost:{port}")
    print("=" * 50)

    app.run(
        debug=debug,
        host='0.0.0.0',
        port=port
    )