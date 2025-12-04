from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models import SystemConfig
from app.decorators import role_required
from werkzeug.utils import secure_filename
import os

bp = Blueprint('system_config', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def system_settings():
    """Cài đặt hệ thống - CHỈ Director"""
    config = SystemConfig.get_config()

    if request.method == 'POST':
        try:
            # ===== XỬ LÝ UPLOAD LOGO =====
            if 'logo' in request.files:
                logo_file = request.files['logo']
                if logo_file and logo_file.filename != '' and allowed_image_file(logo_file.filename):
                    # Xóa logo cũ (nếu có và không phải default)
                    if config.logo_filename and config.logo_filename != 'logo.png':
                        old_logo_path = os.path.join(
                            current_app.root_path,
                            'static',
                            'images',
                            config.logo_filename
                        )
                        if os.path.exists(old_logo_path):
                            try:
                                os.remove(old_logo_path)
                            except Exception as e:
                                print(f"⚠️ Không thể xóa logo cũ: {e}")

                    # Lưu logo mới
                    filename = secure_filename(logo_file.filename)
                    ext = filename.rsplit('.', 1)[1].lower()
                    new_filename = f'logo.{ext}'

                    logo_path = os.path.join(
                        current_app.root_path,
                        'static',
                        'images',
                        new_filename
                    )
                    logo_file.save(logo_path)
                    config.logo_filename = new_filename

                    flash('✅ Đã cập nhật logo thành công!', 'success')

            # ===== XỬ LÝ UPLOAD BACKGROUND =====
            if 'background' in request.files:
                bg_file = request.files['background']
                if bg_file and bg_file.filename != '' and allowed_image_file(bg_file.filename):
                    # Xóa background cũ (nếu có)
                    if config.hub_background_filename:  # ← CHECK None trước
                        old_bg_path = os.path.join(
                            current_app.root_path,
                            'static',
                            'images',
                            config.hub_background_filename
                        )
                        if os.path.exists(old_bg_path):
                            try:
                                os.remove(old_bg_path)
                            except Exception as e:
                                print(f"⚠️ Không thể xóa background cũ: {e}")

                    # Lưu background mới
                    filename = secure_filename(bg_file.filename)
                    ext = filename.rsplit('.', 1)[1].lower()
                    new_filename = f'hinh-nen.{ext}'

                    bg_path = os.path.join(
                        current_app.root_path,
                        'static',
                        'images',
                        new_filename
                    )
                    bg_file.save(bg_path)
                    config.hub_background_filename = new_filename

                    flash('✅ Đã cập nhật background thành công!', 'success')

            # ===== LƯU DATABASE =====
            config.updated_by = current_user.id
            db.session.commit()

            return redirect(url_for('system_config.system_settings'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Lỗi: {str(e)}', 'danger')
            return redirect(url_for('system_config.system_settings'))

    # GET request
    return render_template('system_config/settings.html', config=config)


@bp.route('/reset-logo', methods=['POST'])
@login_required
@role_required(['director'])
def reset_logo():
    """Reset logo về mặc định (logo.png)"""
    config = SystemConfig.get_config()

    # Xóa logo custom (nếu có và KHÔNG phải logo.png)
    if config.logo_filename and config.logo_filename != 'logo.png':
        logo_path = os.path.join(
            current_app.root_path,
            'static',
            'images',
            config.logo_filename
        )
        if os.path.exists(logo_path):
            try:
                os.remove(logo_path)
            except Exception as e:
                print(f"⚠️ Không thể xóa file: {e}")

    # Set về logo.png mặc định
    config.logo_filename = 'logo.png'
    config.updated_by = current_user.id
    db.session.commit()

    flash('✅ Đã reset logo về mặc định!', 'success')
    return redirect(url_for('system_config.system_settings'))


@bp.route('/reset-background', methods=['POST'])
@login_required
@role_required(['director'])
def reset_background():
    """Reset background về mặc định (xóa background, để nền xám)"""
    config = SystemConfig.get_config()

    # Xóa background custom (nếu có)
    if config.hub_background_filename:  # ← CHECK None trước
        bg_path = os.path.join(
            current_app.root_path,
            'static',
            'images',
            config.hub_background_filename
        )
        if os.path.exists(bg_path):
            try:
                os.remove(bg_path)
            except Exception as e:
                print(f"⚠️ Không thể xóa file: {e}")

    # Set về None để hiển thị nền xám
    config.hub_background_filename = None
    config.updated_by = current_user.id
    db.session.commit()

    flash('✅ Đã xóa background, hiển thị nền xám mặc định!', 'success')
    return redirect(url_for('system_config.system_settings'))