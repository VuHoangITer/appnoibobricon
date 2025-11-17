from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import WorkDaysConfig
from app.decorators import role_required
from datetime import datetime

bp = Blueprint('work_days', __name__)


@bp.route('/')
@login_required
@role_required(['director', 'accountant'])
def list_configs():
    """Danh sách cấu hình số công"""
    configs = WorkDaysConfig.query.order_by(
        WorkDaysConfig.year.desc(),
        WorkDaysConfig.month.desc()
    ).all()

    return render_template('work_days/list.html', configs=configs)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def create_config():
    """Tạo cấu hình số công mới"""
    if request.method == 'POST':
        try:
            month = int(request.form.get('month'))
            year = int(request.form.get('year'))
            work_days = float(request.form.get('work_days'))
            notes = request.form.get('notes', '').strip()

            # Check if already exists
            existing = WorkDaysConfig.query.filter_by(month=month, year=year).first()
            if existing:
                flash(f'Cấu hình cho tháng {month}/{year} đã tồn tại.', 'danger')
                return redirect(url_for('work_days.create_config'))

            config = WorkDaysConfig(
                month=month,
                year=year,
                work_days=work_days,
                notes=notes if notes else None,
                created_by=current_user.id
            )

            db.session.add(config)
            db.session.commit()

            flash(f'Tạo cấu hình số công cho tháng {month}/{year} thành công.', 'success')
            return redirect(url_for('work_days.list_configs'))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('work_days.create_config'))

    return render_template('work_days/create.html')


@bp.route('/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def edit_config(config_id):
    """Chỉnh sửa cấu hình số công"""
    config = WorkDaysConfig.query.get_or_404(config_id)

    if request.method == 'POST':
        try:
            work_days = float(request.form.get('work_days'))
            notes = request.form.get('notes', '').strip()

            config.work_days = work_days
            config.notes = notes if notes else None
            config.updated_at = datetime.utcnow()

            db.session.commit()

            flash(f'Cập nhật cấu hình tháng {config.month}/{config.year} thành công.', 'success')
            return redirect(url_for('work_days.list_configs'))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('work_days.edit_config', config_id=config_id))

    return render_template('work_days/edit.html', config=config)


@bp.route('/<int:config_id>/delete', methods=['POST'])
@login_required
@role_required(['director'])
def delete_config(config_id):
    """Xóa cấu hình số công"""
    config = WorkDaysConfig.query.get_or_404(config_id)

    db.session.delete(config)
    db.session.commit()

    flash(f'Đã xóa cấu hình tháng {config.month}/{config.year}.', 'success')
    return redirect(url_for('work_days.list_configs'))


@bp.route('/api/work-days')
@login_required
def api_get_work_days():
    """API lấy số công theo tháng/năm"""
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    if not month or not year:
        return jsonify({'error': 'Missing month or year'}), 400

    work_days = WorkDaysConfig.get_work_days(month, year)

    return jsonify({
        'month': month,
        'year': year,
        'work_days': work_days
    })