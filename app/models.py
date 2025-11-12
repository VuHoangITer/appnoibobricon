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
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # SỬA: Dùng back_populates thay vì backref
    creator = db.relationship(
        'User',
        foreign_keys=[creator_id],
        back_populates='created_tasks'
    )

    assignments = db.relationship(
        'TaskAssignment',
        foreign_keys='TaskAssignment.task_id',
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


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))