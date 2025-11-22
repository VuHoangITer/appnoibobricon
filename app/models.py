from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import secrets

# Role priorities
ROLE_PRIORITIES = {
    'director': 100,
    'manager': 80,
    'accountant': 30,
    'hr': 30
}


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    avatar = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships - SỬA: Xóa backref, thay bằng back_populates
    created_tasks = db.relationship(
        'Task',
        foreign_keys='Task.creator_id',
        back_populates='creator',
        lazy='dynamic'
    )

    task_assignments = db.relationship(
        'TaskAssignment',
        foreign_keys='TaskAssignment.user_id',
        back_populates='user',
        lazy='dynamic'
    )

    assigned_tasks = db.relationship(
        'TaskAssignment',
        foreign_keys='TaskAssignment.assigned_by',
        back_populates='assigner',
        lazy='dynamic'
    )

    notifications = db.relationship(
        'Notification',
        foreign_keys='Notification.user_id',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    notes = db.relationship(
        'Note',
        foreign_keys='Note.user_id',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    uploaded_files = db.relationship(
        'File',
        foreign_keys='File.uploader_id',
        back_populates='uploader',
        lazy='dynamic'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_priority(self):
        return ROLE_PRIORITIES.get(self.role, 0)

    def can_manage_user(self, target_user):
        if self.role == 'director':
            return True
        if self.role == 'manager':
            return target_user.role != 'director'
        return False

    def can_upload_files(self):
        return self.role in ['director', 'manager']

    def can_create_users(self):
        return self.role == 'director'

    def can_assign_tasks(self):
        return self.role in ['director', 'manager']

    def __repr__(self):
        return f'<User {self.email}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)

    # ===== Thông tin chính =====
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='PENDING')

    is_urgent = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)

    # ===== Hiệu suất =====
    performance_rating = db.Column(db.String(10), nullable=True)
    rated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rated_at = db.Column(db.DateTime, nullable=True)

    # ===== Hoàn thành quá hạn =====
    completed_overdue = db.Column(db.Boolean, default=False)

    # ===== Recurring Task (lặp lại) =====
    recurrence_enabled = db.Column(db.Boolean, default=False)
    recurrence_interval_days = db.Column(db.Integer, default=7)
    last_recurrence_date = db.Column(db.DateTime, nullable=True)
    parent_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)

    # Quan hệ đệ quy (task cha – task con)
    child_tasks = db.relationship(
        'Task',
        backref=db.backref('parent_task', remote_side=[id]),
        lazy='dynamic'
    )

    # ===== Thời gian =====
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ===== Relation =====
    creator = db.relationship(
        'User',
        foreign_keys=[creator_id],
        back_populates='created_tasks'
    )

    rater = db.relationship(
        'User',
        foreign_keys=[rated_by]
    )

    assignments = db.relationship(
        'TaskAssignment',
        foreign_keys='TaskAssignment.task_id',
        back_populates='task',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    completion_reports = db.relationship(
        'TaskCompletionReport',
        back_populates='task',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Task {self.title}>'



class TaskAssignment(db.Model):
    __tablename__ = 'task_assignments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_group = db.Column(db.String(20))
    accepted = db.Column(db.Boolean, default=False)
    accepted_at = db.Column(db.DateTime)
    seen = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SỬA: Thêm back_populates
    task = db.relationship(
        'Task',
        foreign_keys=[task_id],
        back_populates='assignments'
    )

    user = db.relationship(
        'User',
        foreign_keys=[user_id],
        back_populates='task_assignments'
    )

    assigner = db.relationship(
        'User',
        foreign_keys=[assigned_by],
        back_populates='assigned_tasks'
    )

    def __repr__(self):
        return f'<TaskAssignment task={self.task_id} user={self.user_id}>'


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SỬA: Thêm back_populates
    uploader = db.relationship(
        'User',
        foreign_keys=[uploader_id],
        back_populates='uploaded_files'
    )

    def __repr__(self):
        return f'<File {self.original_filename}>'


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # SỬA: Thêm back_populates
    user = db.relationship(
        'User',
        foreign_keys=[user_id],
        back_populates='notifications'
    )

    def __repr__(self):
        return f'<Notification {self.title}>'


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # SỬA: Thêm back_populates
    user = db.relationship(
        'User',
        foreign_keys=[user_id],
        back_populates='notes'
    )

    def __repr__(self):
        return f'<Note {self.title}>'


class Salary(db.Model):
    __tablename__ = 'salaries'

    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(200), nullable=False)
    month = db.Column(db.String(7), nullable=False)
    work_days_in_month = db.Column(db.Float, nullable=False)
    actual_work_days = db.Column(db.Float, nullable=False)

    basic_salary = db.Column(db.Float, nullable=False)
    responsibility_salary = db.Column(db.Float, default=0)

    capacity_bonuses = db.Column(db.Text)
    deductions = db.Column(db.Text)

    basic_salary_per_day = db.Column(db.Float)
    responsibility_salary_per_day = db.Column(db.Float)
    main_salary = db.Column(db.Float)
    total_capacity_bonus = db.Column(db.Float)
    total_income = db.Column(db.Float)
    total_deduction = db.Column(db.Float)
    net_salary = db.Column(db.Float)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - GIỮ NGUYÊN vì không có conflict
    creator = db.relationship('User', foreign_keys=[created_by])
    share_links = db.relationship(
        'SalaryShareLink',
        backref='salary',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def get_capacity_bonuses(self):
        if self.capacity_bonuses:
            try:
                return json.loads(self.capacity_bonuses)
            except:
                return []
        return []

    def set_capacity_bonuses(self, bonuses_list):
        self.capacity_bonuses = json.dumps(bonuses_list)

    def get_deductions(self):
        if self.deductions:
            try:
                return json.loads(self.deductions)
            except:
                return []
        return []

    def set_deductions(self, deductions_list):
        self.deductions = json.dumps(deductions_list)

    def calculate(self):
        self.basic_salary_per_day = self.basic_salary / self.work_days_in_month if self.work_days_in_month > 0 else 0
        self.responsibility_salary_per_day = self.responsibility_salary / self.work_days_in_month if self.work_days_in_month > 0 else 0
        self.main_salary = (self.basic_salary_per_day + self.responsibility_salary_per_day) * self.actual_work_days

        bonuses = self.get_capacity_bonuses()
        self.total_capacity_bonus = sum(item.get('amount', 0) for item in bonuses)
        self.total_income = self.main_salary + self.total_capacity_bonus

        deductions = self.get_deductions()
        self.total_deduction = sum(item.get('amount', 0) for item in deductions)
        self.net_salary = self.total_income - self.total_deduction

    def __repr__(self):
        return f'<Salary {self.employee_name} - {self.month}>'


class SalaryShareLink(db.Model):
    __tablename__ = 'salary_share_links'

    id = db.Column(db.Integer, primary_key=True)
    salary_id = db.Column(db.Integer, db.ForeignKey('salaries.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    max_views = db.Column(db.Integer, nullable=True)
    view_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    creator = db.relationship('User', foreign_keys=[created_by])

    # THÊM MỚI: Relationship với access logs
    access_logs = db.relationship(
        'SalaryShareLinkAccess',
        back_populates='share_link',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='SalaryShareLinkAccess.accessed_at.desc()'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.token:
            self.token = secrets.token_urlsafe(32)

    def is_valid(self):
        if not self.is_active:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        if self.max_views and self.view_count >= self.max_views:
            return False
        return True

    def increment_view(self):
        self.view_count += 1
        db.session.commit()

    def __repr__(self):
        return f'<SalaryShareLink {self.token[:8]}...>'


# ============================================================
# THÊM MỚI: Model tracking truy cập link chia sẻ lương
# ============================================================
class SalaryShareLinkAccess(db.Model):
    """Lưu lịch sử truy cập link chia sẻ lương"""
    __tablename__ = 'salary_share_link_accesses'

    id = db.Column(db.Integer, primary_key=True)
    share_link_id = db.Column(db.Integer, db.ForeignKey('salary_share_links.id'), nullable=False)

    # Thông tin IP và thiết bị
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 max length = 45
    user_agent = db.Column(db.String(500))  # Full user agent string

    # Parse từ user agent
    browser = db.Column(db.String(50))  # Chrome, Firefox, Safari, etc.
    browser_version = db.Column(db.String(20))
    os = db.Column(db.String(50))  # Windows, MacOS, Android, iOS, etc.
    device_type = db.Column(db.String(20))  # desktop, mobile, tablet
    device_brand = db.Column(db.String(50))  # Apple, Samsung, etc.

    # Thông tin bổ sung
    referer = db.Column(db.String(500))  # URL nguồn (nếu có)
    accessed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Geolocation (optional - cần API bên ngoài)
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))

    # Relationship
    share_link = db.relationship(
        'SalaryShareLink',
        back_populates='access_logs'
    )

    def __repr__(self):
        return f'<SalaryShareLinkAccess {self.ip_address} at {self.accessed_at}>'

    def get_device_icon(self):
        """Trả về icon phù hợp với loại thiết bị"""
        if self.device_type == 'mobile':
            return 'bi-phone'
        elif self.device_type == 'tablet':
            return 'bi-tablet'
        else:
            return 'bi-laptop'

    def get_os_icon(self):
        """Trả về icon phù hợp với hệ điều hành"""
        if self.os:
            os_lower = self.os.lower()
            if 'windows' in os_lower:
                return 'bi-windows'
            elif 'mac' in os_lower or 'ios' in os_lower:
                return 'bi-apple'
            elif 'android' in os_lower:
                return 'bi-android2'
            elif 'linux' in os_lower:
                return 'bi-ubuntu'
        return 'bi-question-circle'


class News(db.Model):
    """Bài đăng tin tức nội bộ"""
    __tablename__ = 'news'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    image_filename = db.Column(db.String(255))  # Tên file ảnh đính kèm
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', backref='news_posts', foreign_keys=[author_id])
    comments = db.relationship(
        'NewsComment',
        back_populates='news',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='NewsComment.created_at.desc()'
    )
    confirmations = db.relationship(
        'NewsConfirmation',
        back_populates='news',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<News {self.title}>'

    def get_confirmation_count(self):
        """Đếm số người đã xác nhận đọc"""
        return self.confirmations.count()

    def is_confirmed_by(self, user_id):
        """Kiểm tra user đã xác nhận đọc chưa"""
        return self.confirmations.filter_by(user_id=user_id).first() is not None


class NewsComment(db.Model):
    """Bình luận trên bài đăng tin tức"""
    __tablename__ = 'news_comments'

    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    news = db.relationship('News', back_populates='comments')
    user = db.relationship('User', backref='news_comments', foreign_keys=[user_id])

    def __repr__(self):
        return f'<NewsComment {self.id} by {self.user_id}>'


class NewsConfirmation(db.Model):
    """Xác nhận đã đọc tin tức"""
    __tablename__ = 'news_confirmations'

    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    confirmed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    news = db.relationship('News', back_populates='confirmations')
    user = db.relationship('User', backref='news_confirmations', foreign_keys=[user_id])

    # Unique constraint: mỗi user chỉ confirm 1 lần cho 1 bài
    __table_args__ = (
        db.UniqueConstraint('news_id', 'user_id', name='unique_news_user_confirmation'),
    )

    def __repr__(self):
        return f'<NewsConfirmation news={self.news_id} user={self.user_id}>'


class TaskCompletionReport(db.Model):
    """Báo cáo hoàn thành nhiệm vụ"""
    __tablename__ = 'task_completion_reports'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    completion_note = db.Column(db.Text)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    was_overdue = db.Column(db.Boolean, default=False)
    completion_time = db.Column(db.Integer)

    task = db.relationship('Task', foreign_keys=[task_id], back_populates='completion_reports')
    completer = db.relationship('User', foreign_keys=[completed_by])

    def __repr__(self):
        return f'<TaskCompletionReport task={self.task_id}>'


class SalaryGrade(db.Model):
    """Cấp bậc lương - chỉ giám đốc quản lý"""
    __tablename__ = 'salary_grades'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    basic_salary = db.Column(db.Float, nullable=False)
    responsibility_salary = db.Column(db.Float, default=0)
    capacity_bonuses = db.Column(db.Text)  # JSON
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])
    employees = db.relationship(
        'Employee',
        back_populates='salary_grade',
        lazy='dynamic'
    )

    def get_capacity_bonuses(self):
        if self.capacity_bonuses:
            try:
                return json.loads(self.capacity_bonuses)
            except:
                return []
        return []

    def set_capacity_bonuses(self, bonuses_list):
        self.capacity_bonuses = json.dumps(bonuses_list)

    def __repr__(self):
        return f'<SalaryGrade {self.name}>'


class Employee(db.Model):
    """Nhân viên"""
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False, index=True)
    employee_code = db.Column(db.String(50), unique=True, index=True)
    salary_grade_id = db.Column(db.Integer, db.ForeignKey('salary_grades.id'))

    # Thông tin liên hệ
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))

    # Thông tin công việc
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))
    hire_date = db.Column(db.Date)

    is_active = db.Column(db.Boolean, default=True, index=True)
    notes = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])
    salary_grade = db.relationship('SalaryGrade', back_populates='employees')

    def __repr__(self):
        return f'<Employee {self.full_name}>'

    def get_current_salary_info(self):
        """Lấy thông tin lương hiện tại từ cấp bậc"""
        if self.salary_grade:
            return {
                'grade_name': self.salary_grade.name,
                'basic_salary': self.salary_grade.basic_salary,
                'responsibility_salary': self.salary_grade.responsibility_salary,
                'capacity_bonuses': self.salary_grade.get_capacity_bonuses()
            }
        return None


class WorkDaysConfig(db.Model):
    """Cấu hình số công theo tháng"""
    __tablename__ = 'work_days_config'

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    work_days = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(200))

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint('month', 'year', name='unique_month_year'),
    )

    def __repr__(self):
        return f'<WorkDaysConfig {self.month}/{self.year}: {self.work_days} days>'

    @staticmethod
    def get_work_days(month, year):
        """Lấy số công của tháng, nếu chưa có thì tính mặc định"""
        config = WorkDaysConfig.query.filter_by(month=month, year=year).first()
        if config:
            return config.work_days

        # Tính số ngày làm việc mặc định (trừ chủ nhật)
        import calendar
        from datetime import date, timedelta

        num_days = calendar.monthrange(year, month)[1]
        work_days = 0

        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            # Trừ chủ nhật (weekday() == 6)
            if current_date.weekday() != 6:
                work_days += 1

        return float(work_days)


class Penalty(db.Model):
    """Biên bản phạt nhân viên"""
    __tablename__ = 'penalties'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    employee_name = db.Column(db.String(200), nullable=False, index=True)

    penalty_date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)

    # Trạng thái đã trừ lương chưa
    is_deducted = db.Column(db.Boolean, default=False, index=True)
    deducted_in_salary_id = db.Column(db.Integer, db.ForeignKey('salaries.id'), nullable=True)
    deducted_at = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])
    employee = db.relationship('Employee', foreign_keys=[employee_id])
    deducted_salary = db.relationship('Salary', foreign_keys=[deducted_in_salary_id])

    def __repr__(self):
        return f'<Penalty {self.employee_name} - {self.amount}>'

    def mark_as_deducted(self, salary_id):
        """Đánh dấu đã trừ lương"""
        self.is_deducted = True
        self.deducted_in_salary_id = salary_id
        self.deducted_at = datetime.utcnow()


class Advance(db.Model):
    """Tạm ứng lương nhân viên"""
    __tablename__ = 'advances'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    employee_name = db.Column(db.String(200), nullable=False, index=True)

    advance_date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)

    # Trạng thái đã trừ lương chưa
    is_deducted = db.Column(db.Boolean, default=False, index=True)
    deducted_in_salary_id = db.Column(db.Integer, db.ForeignKey('salaries.id'), nullable=True)
    deducted_at = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])
    employee = db.relationship('Employee', foreign_keys=[employee_id])
    deducted_salary = db.relationship('Salary', foreign_keys=[deducted_in_salary_id])

    def __repr__(self):
        return f'<Advance {self.employee_name} - {self.amount}>'

    def mark_as_deducted(self, salary_id):
        """Đánh dấu đã trừ lương"""
        self.is_deducted = True
        self.deducted_in_salary_id = salary_id
        self.deducted_at = datetime.utcnow()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))