from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

# THÊM: Import scheduler
scheduler = None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'

    # Create upload folder
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # THÊM: Register built-in Python functions to Jinja2
    app.jinja_env.globals.update(min=min, max=max)

    # Register template filters for timezone
    from app.utils import utc_to_vn
    from datetime import datetime

    @app.template_filter('vn_datetime')
    def vn_datetime_filter(dt, format='%d/%m/%Y %H:%M'):
        """Convert UTC to VN time and format"""
        if dt is None:
            return ''
        vn_dt = utc_to_vn(dt)
        return vn_dt.strftime(format)

    @app.template_filter('vn_date')
    def vn_date_filter(dt, format='%d/%m/%Y'):
        """Format date in VN format"""
        if dt is None:
            return ''
        if hasattr(dt, 'strftime'):
            return dt.strftime(format)
        return str(dt)

    @app.template_filter('is_overdue')
    def is_overdue_filter(task):
        """Check if task is overdue"""
        if not task.due_date:
            return False
        if task.status in ['DONE', 'CANCELLED']:
            return False
        # So sánh UTC với UTC
        return task.due_date < datetime.utcnow()

    @app.template_filter('status_vn')
    def status_vn_filter(status):
        """Convert status to Vietnamese"""
        status_map = {
            'PENDING': 'Chờ xác nhận',
            'IN_PROGRESS': 'Đang thực hiện',
            'DONE': 'Hoàn thành',
            'CANCELLED': 'Đã hủy'
        }
        return status_map.get(status, status)

    @app.template_filter('status_badge')
    def status_badge_filter(status):
        """Get Bootstrap badge class for status"""
        badge_map = {
            'PENDING': 'warning',
            'IN_PROGRESS': 'info',
            'DONE': 'success',
            'CANCELLED': 'secondary'
        }
        return badge_map.get(status, 'secondary')

    @app.template_filter('role_vn')
    def role_vn_filter(role):
        """Convert role to Vietnamese"""
        role_map = {
            'director': 'Giám đốc',
            'manager': 'Trưởng phòng',
            'accountant': 'Kế toán',
            'hr': 'Nhân viên'
        }
        return role_map.get(role, role)

    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')

    from app.files import bp as files_bp
    app.register_blueprint(files_bp, url_prefix='/files')

    from app.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    from app.notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from app.salaries import bp as salaries_bp
    app.register_blueprint(salaries_bp, url_prefix='/salaries')

    # Dashboard route
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('tasks.dashboard'))
        return redirect(url_for('auth.login'))

    # THÊM: Khởi động scheduler (chỉ chạy khi không phải debug mode hoặc reloader)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        global scheduler
        if scheduler is None:
            from app.scheduler import start_scheduler
            scheduler = start_scheduler(app)

    return app


from app import models