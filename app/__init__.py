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

    # Create upload folder
    upload_path = app.config['UPLOAD_FOLDER']
    news_images_path = os.path.join(upload_path, 'news_images')
    os.makedirs(upload_path, exist_ok=True)
    os.makedirs(news_images_path, exist_ok=True)

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
            'PENDING': 'Chưa Làm',
            'IN_PROGRESS': 'Đang Làm',
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

    from app.news import bp as news_bp
    app.register_blueprint(news_bp, url_prefix='/news')

    from app.workflow import bp as workflow_bp
    app.register_blueprint(workflow_bp, url_prefix='/workflow')

    from app.tts import bp as tts_bp
    app.register_blueprint(tts_bp, url_prefix='/tts')
    csrf.exempt(tts_bp)

    from app.performance import bp as performance_bp
    app.register_blueprint(performance_bp, url_prefix='/performance')

    from app.salary_grades import bp as salary_grades_bp
    app.register_blueprint(salary_grades_bp, url_prefix='/salary-grades')

    from app.employees import bp as employees_bp
    app.register_blueprint(employees_bp, url_prefix='/employees')

    from app.work_days import bp as work_days_bp
    app.register_blueprint(work_days_bp, url_prefix='/work-days')

    from app.penalties import bp as penalties_bp
    app.register_blueprint(penalties_bp, url_prefix='/penalties')

    from app.advances import bp as advances_bp
    app.register_blueprint(advances_bp, url_prefix='/advances')

    # Dashboard route
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('tasks.dashboard'))
        return redirect(url_for('auth.login'))

    # THÊM: Khởi động scheduler (chỉ chạy khi không phải debug mode hoặc reloader)
    if os.environ.get('ENABLE_SCHEDULER') == 'true':
        global scheduler
        if scheduler is None:
            from app.scheduler import start_scheduler
            scheduler = start_scheduler(app)
            print("Scheduler enabled in Flask app")
    else:
        print("Scheduler disabled - run separately via systemd service")

    return app


from app import models