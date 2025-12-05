from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import MarqueeConfig

bp = Blueprint('marquee_config', __name__, url_prefix='/marquee-config')


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Cài đặt chữ chạy ngang"""
    config = MarqueeConfig.get_config()

    if request.method == 'POST':
        try:
            # Cập nhật config
            config.text = request.form.get('text', '').strip()
            config.icon = request.form.get('icon', 'bi-info-circle-fill')
            config.is_enabled = request.form.get('is_enabled') == 'on'
            config.theme = request.form.get('theme', 'default')
            config.speed = request.form.get('speed', 'normal')

            # ✅ THÊM MỚI: Lấy custom colors
            config.custom_bg_color = request.form.get('custom_bg_color', '#ffffff')
            config.custom_text_color = request.form.get('custom_text_color', '#111827')
            config.custom_icon_color = request.form.get('custom_icon_color', '#111827')

            config.updated_by = current_user.id

            # Validate
            if not config.text:
                flash('Vui lòng nhập nội dung thông báo!', 'error')
                return redirect(url_for('marquee_config.settings'))

            db.session.commit()
            flash('Đã cập nhật cài đặt thông báo chạy ngang!', 'success')
            return redirect(url_for('marquee_config.settings'))

        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi: {str(e)}', 'error')
            return redirect(url_for('marquee_config.settings'))

    # GET request
    return render_template('marquee_config/settings.html', config=config)


@bp.route('/preview')
@login_required
def preview():
    """Preview marquee với config hiện tại"""
    config = MarqueeConfig.get_config()
    return render_template('marquee_config/preview.html', config=config)