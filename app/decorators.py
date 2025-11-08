from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def role_required(roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('Bạn không có quyền truy cập trang này.', 'danger')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def roles_hierarchy(min_priority):
    """Decorator to require minimum role priority"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.get_priority() < min_priority:
                flash('Bạn không có quyền truy cập trang này.', 'danger')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator