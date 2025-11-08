from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User
from app.decorators import role_required
from werkzeug.urls import url_parse

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('tasks.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash('Email hoặc mật khẩu không đúng.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Tài khoản của bạn đã bị vô hiệu hóa.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('tasks.dashboard')
        return redirect(next_page)

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bạn đã đăng xuất thành công.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        role = request.form.get('role')

        if User.query.filter_by(email=email).first():
            flash('Email đã tồn tại.', 'danger')
            return redirect(url_for('auth.register'))

        if role not in ['director', 'manager', 'accountant', 'hr']:
            flash('Role không hợp lệ.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(email=email, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'Tạo tài khoản {email} thành công.', 'success')
        return redirect(url_for('auth.users'))

    return render_template('register.html')


@bp.route('/users')
@login_required
@role_required(['director'])
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users.html', users=all_users)


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        password = request.form.get('password')

        # Check if email already exists (except current user)
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != user_id:
            flash('Email đã tồn tại.', 'danger')
            return redirect(url_for('auth.edit_user', user_id=user_id))

        if role not in ['director', 'manager', 'accountant', 'hr']:
            flash('Role không hợp lệ.', 'danger')
            return redirect(url_for('auth.edit_user', user_id=user_id))

        # Update user info
        user.email = email
        user.full_name = full_name
        user.role = role

        # Update password if provided
        if password and password.strip():
            user.set_password(password)

        db.session.commit()

        flash(f'Cập nhật tài khoản {email} thành công.', 'success')
        return redirect(url_for('auth.users'))

    return render_template('edit_user.html', user=user)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required(['director'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('Bạn không thể xóa chính mình.', 'danger')
        return redirect(url_for('auth.users'))

    db.session.delete(user)
    db.session.commit()
    flash(f'Đã xóa người dùng {user.email}.', 'success')
    return redirect(url_for('auth.users'))


@bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@role_required(['director'])
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('Bạn không thể vô hiệu hóa chính mình.', 'danger')
        return redirect(url_for('auth.users'))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'kích hoạt' if user.is_active else 'vô hiệu hóa'
    flash(f'Đã {status} người dùng {user.email}.', 'success')
    return redirect(url_for('auth.users'))