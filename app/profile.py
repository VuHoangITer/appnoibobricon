from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User
from werkzeug.utils import secure_filename
import os
import uuid

bp = Blueprint('profile', __name__)

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_avatar_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def save_avatar(file):
    """Lưu file avatar và trả về tên file"""
    if file and allowed_avatar_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"

        avatars_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
        os.makedirs(avatars_folder, exist_ok=True)

        filepath = os.path.join(avatars_folder, filename)
        file.save(filepath)

        return filename
    return None


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Trang cài đặt tài khoản cá nhân"""
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'change_password':
            return handle_change_password()
        elif action == 'change_avatar':
            return handle_change_avatar()
        elif action == 'remove_avatar':
            return handle_remove_avatar()

    return render_template('profile/settings.html')


def handle_change_password():
    """Xử lý đổi mật khẩu"""
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not current_password:
        flash('Vui lòng nhập mật khẩu hiện tại.', 'danger')
        return redirect(url_for('profile.settings'))

    if not current_user.check_password(current_password):
        flash('Mật khẩu hiện tại không đúng.', 'danger')
        return redirect(url_for('profile.settings'))

    if not new_password:
        flash('Vui lòng nhập mật khẩu mới.', 'danger')
        return redirect(url_for('profile.settings'))

    if len(new_password) < 6:
        flash('Mật khẩu mới phải có ít nhất 6 ký tự.', 'danger')
        return redirect(url_for('profile.settings'))

    if new_password != confirm_password:
        flash('Xác nhận mật khẩu không khớp.', 'danger')
        return redirect(url_for('profile.settings'))

    current_user.set_password(new_password)
    db.session.commit()

    flash('Đổi mật khẩu thành công!', 'success')
    return redirect(url_for('profile.settings'))


def handle_change_avatar():
    """Xử lý đổi avatar"""
    if 'avatar' not in request.files:
        flash('Vui lòng chọn file ảnh.', 'danger')
        return redirect(url_for('profile.settings'))

    file = request.files['avatar']

    if file.filename == '':
        flash('Vui lòng chọn file ảnh.', 'danger')
        return redirect(url_for('profile.settings'))

    if not allowed_avatar_file(file.filename):
        flash('Định dạng file không hợp lệ. Chỉ chấp nhận: PNG, JPG, JPEG, GIF, WEBP.', 'danger')
        return redirect(url_for('profile.settings'))

    # Xóa avatar cũ nếu có
    if current_user.avatar:
        old_avatar_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'avatars',
            current_user.avatar
        )
        if os.path.exists(old_avatar_path):
            try:
                os.remove(old_avatar_path)
            except:
                pass

    filename = save_avatar(file)
    if filename:
        current_user.avatar = filename
        db.session.commit()
        flash('Cập nhật ảnh đại diện thành công!', 'success')
    else:
        flash('Có lỗi khi lưu ảnh. Vui lòng thử lại.', 'danger')

    return redirect(url_for('profile.settings'))


def handle_remove_avatar():
    """Xử lý xóa avatar"""
    if current_user.avatar:
        avatar_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'avatars',
            current_user.avatar
        )
        if os.path.exists(avatar_path):
            try:
                os.remove(avatar_path)
            except:
                pass

        current_user.avatar = None
        db.session.commit()
        flash('Đã xóa ảnh đại diện.', 'success')

    return redirect(url_for('profile.settings'))


@bp.route('/avatar/<filename>')
def get_avatar(filename):
    """Serve avatar file"""
    from flask import send_from_directory
    avatars_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
    return send_from_directory(avatars_folder, filename)