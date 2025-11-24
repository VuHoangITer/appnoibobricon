#!/usr/bin/env python
"""
Run script for Flask application
Usage: python run.py (development) or gunicorn run:app (production)
"""

from gevent import monkey
monkey.patch_all()
print(" Gevent patched early in run.py (including SSL)")

from app import create_app, db
import os

# Tạo Flask app instance
app = create_app()

# Tạo thư mục uploads khi khởi động (cho cả development và production)
upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)
    print(f"Created upload folder: {upload_folder}")


@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized!")


if __name__ == '__main__':
    # Chỉ chạy development server khi chạy trực tiếp file này
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