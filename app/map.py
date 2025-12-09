from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import DistrictTarget
from app.decorators import role_required
from datetime import datetime
import json

bp = Blueprint('map', __name__)

# Danh sách cities hỗ trợ
SUPPORTED_CITIES = ['TP.HCM', 'Đồng Nai']


@bp.route('/')
@login_required
def view_map():
    """Xem bản đồ với các chỉ tiêu - HỖ TRỢ MULTI-CITY"""
    # Lấy city từ query param, default là TP.HCM
    current_city = request.args.get('city', 'TP.HCM')

    # Validate city
    if current_city not in SUPPORTED_CITIES:
        current_city = 'TP.HCM'

    # Lấy targets theo city
    targets = DistrictTarget.query.filter_by(
        is_active=True,
        city=current_city
    ).all()

    targets_dict = {}
    for target in targets:
        targets_dict[target.district_code] = {
            'name': target.district_name,
            'targets': target.get_targets(),
            'notes': target.notes
        }

    return render_template('map/view.html',
                           targets_dict=targets_dict,
                           current_city=current_city,
                           supported_cities=SUPPORTED_CITIES,
                           can_edit=current_user.role == 'director')


@bp.route('/manage')
@login_required
@role_required(['director'])
def manage_targets():
    """Quản lý chỉ tiêu (chỉ giám đốc) - HỖ TRỢ MULTI-CITY"""
    city = request.args.get('city', 'TP.HCM')

    # Validate city
    if city not in SUPPORTED_CITIES:
        city = 'TP.HCM'

    targets = DistrictTarget.query.filter_by(city=city).order_by(
        DistrictTarget.district_name
    ).all()

    return render_template('map/manage.html',
                           targets=targets,
                           city=city,
                           supported_cities=SUPPORTED_CITIES)


@bp.route('/target/<int:target_id>')
@login_required
@role_required(['director'])
def target_detail(target_id):
    """Chi tiết chỉ tiêu"""
    target = DistrictTarget.query.get_or_404(target_id)
    return render_template('map/detail.html', target=target)


@bp.route('/target/create', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def create_target():
    """Tạo chỉ tiêu mới - HỖ TRỢ MULTI-CITY"""
    # Lấy city từ query param hoặc form
    default_city = request.args.get('city', 'TP.HCM')

    if request.method == 'POST':
        try:
            ward_code = request.form.get('ward_code', '').strip()
            ward_name = request.form.get('ward_name', '').strip()
            district_name = request.form.get('district_name', '').strip()
            city = request.form.get('city', 'TP.HCM').strip()
            notes = request.form.get('notes', '').strip()

            if not ward_code or not ward_name:
                flash('Vui lòng nhập đầy đủ mã và tên phường.', 'danger')
                return redirect(url_for('map.create_target', city=city))

            # Check duplicate - CHO PHÉP CÙNG CODE KHÁC CITY
            existing = DistrictTarget.query.filter_by(
                district_code=ward_code,
                city=city
            ).first()

            if existing:
                flash(f'Mã phường "{ward_code}" đã tồn tại trong {city}.', 'danger')
                return redirect(url_for('map.create_target', city=city))

            # Parse targets từ form
            targets = []
            target_count = int(request.form.get('target_count', 0))

            for i in range(target_count):
                name = request.form.get(f'target_name_{i}', '').strip()
                value = request.form.get(f'target_value_{i}', '').strip()
                unit = request.form.get(f'target_unit_{i}', '').strip()

                if name:
                    target_item = {'name': name}
                    if value:
                        target_item['value'] = value
                    if unit:
                        target_item['unit'] = unit
                    targets.append(target_item)

            # Tạo record mới
            target = DistrictTarget(
                district_code=ward_code,
                district_name=ward_name,
                city=city,
                notes=notes if notes else None,
                created_by=current_user.id
            )

            target.set_targets(targets)

            db.session.add(target)
            db.session.commit()

            flash(f'Tạo chỉ tiêu cho "{ward_name}" ({city}) thành công.', 'success')
            return redirect(url_for('map.target_detail', target_id=target.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('map.create_target', city=default_city))

    return render_template('map/create.html',
                           default_city=default_city,
                           supported_cities=SUPPORTED_CITIES)


@bp.route('/target/<int:target_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def edit_target(target_id):
    """Chỉnh sửa chỉ tiêu - CHỈ CHO PHÉP SỬA CHỈ TIÊU VÀ GHI CHÚ"""
    target = DistrictTarget.query.get_or_404(target_id)

    if request.method == 'POST':
        try:
            notes = request.form.get('notes', '').strip()

            # Parse targets từ form
            targets = []
            target_count = int(request.form.get('target_count', 0))

            for i in range(target_count):
                name = request.form.get(f'target_name_{i}', '').strip()
                value = request.form.get(f'target_value_{i}', '').strip()
                unit = request.form.get(f'target_unit_{i}', '').strip()

                if name:
                    target_item = {'name': name}
                    if value:
                        target_item['value'] = value
                    if unit:
                        target_item['unit'] = unit
                    targets.append(target_item)

            # CHỈ CẬP NHẬT GHI CHÚ VÀ CHỈ TIÊU
            target.notes = notes if notes else None
            target.set_targets(targets)
            target.updated_at = datetime.utcnow()

            db.session.commit()

            flash(f'Cập nhật chỉ tiêu cho "{target.district_name}" thành công.', 'success')
            return redirect(url_for('map.target_detail', target_id=target.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('map.edit_target', target_id=target_id))

    return render_template('map/edit.html', target=target)


@bp.route('/target/<int:target_id>/delete', methods=['POST'])
@login_required
@role_required(['director'])
def delete_target(target_id):
    """Xóa chỉ tiêu"""
    target = DistrictTarget.query.get_or_404(target_id)

    district_name = target.district_name
    city = target.city

    try:
        db.session.delete(target)
        db.session.commit()

        flash(f'Đã xóa chỉ tiêu cho "{district_name}".', 'success')
        return redirect(url_for('map.manage_targets', city=city))

    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi khi xóa: {str(e)}', 'danger')
        return redirect(url_for('map.target_detail', target_id=target_id))


@bp.route('/api/targets')
@login_required
def api_get_targets():
    """API lấy tất cả chỉ tiêu (cho map) - HỖ TRỢ MULTI-CITY"""
    city = request.args.get('city', 'TP.HCM')

    targets = DistrictTarget.query.filter_by(
        is_active=True,
        city=city
    ).all()

    result = {}
    for target in targets:
        result[target.district_code] = {
            'name': target.district_name,
            'targets': target.get_targets(),
            'notes': target.notes
        }

    return jsonify(result)


@bp.route('/api/target/<district_code>')
@login_required
def api_get_target_by_code(district_code):
    """API lấy chi tiết chỉ tiêu theo mã phường - HỖ TRỢ MULTI-CITY"""
    city = request.args.get('city', 'TP.HCM')

    target = DistrictTarget.query.filter_by(
        district_code=district_code,
        city=city,
        is_active=True
    ).first()

    if not target:
        return jsonify({'error': 'Không tìm thấy chỉ tiêu'}), 404

    return jsonify({
        'id': target.id,
        'district_code': target.district_code,
        'district_name': target.district_name,
        'city': target.city,
        'targets': target.get_targets(),
        'notes': target.notes
    })