from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Advance, Employee, User
from app.decorators import role_required
from datetime import datetime

bp = Blueprint('advances', __name__)


@bp.route('/')
@login_required
@role_required(['director', 'accountant'])
def list_advances():
    """Danh sách tạm ứng"""
    # Filter
    employee_filter = request.args.get('employee', '')
    status_filter = request.args.get('status', 'all')
    month_filter = request.args.get('month', '')

    query = Advance.query

    if employee_filter:
        query = query.filter(Advance.employee_name.ilike(f'%{employee_filter}%'))

    if status_filter == 'pending':
        query = query.filter_by(is_deducted=False)
    elif status_filter == 'deducted':
        query = query.filter_by(is_deducted=True)

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            query = query.filter(
                db.extract('month', Advance.advance_date) == month,
                db.extract('year', Advance.advance_date) == year
            )
        except:
            pass

    advances = query.order_by(Advance.advance_date.desc()).all()

    # Tính tổng
    total_amount = sum(a.amount for a in advances)
    pending_amount = sum(a.amount for a in advances if not a.is_deducted)

    return render_template('advances/list.html',
                           advances=advances,
                           employee_filter=employee_filter,
                           status_filter=status_filter,
                           month_filter=month_filter,
                           total_amount=total_amount,
                           pending_amount=pending_amount)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def create_advance():
    """Tạo tạm ứng mới"""
    if request.method == 'POST':
        try:
            employee_id = request.form.get('employee_id')
            employee_name = request.form.get('employee_name', '').strip()

            # Nếu chọn từ danh sách
            if employee_id:
                employee = Employee.query.get(int(employee_id))
                if employee:
                    employee_name = employee.full_name
                    employee_id = employee.id
                else:
                    employee_id = None
            else:
                employee_id = None

            if not employee_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('advances.create_advance'))

            advance_date_str = request.form.get('advance_date')
            amount = float(request.form.get('amount', 0))
            reason = request.form.get('reason', '').strip()
            notes = request.form.get('notes', '').strip()

            if not advance_date_str or amount <= 0 or not reason:
                flash('Vui lòng điền đầy đủ thông tin.', 'danger')
                return redirect(url_for('advances.create_advance'))

            advance_date = datetime.strptime(advance_date_str, '%Y-%m-%d').date()

            advance = Advance(
                employee_id=employee_id,
                employee_name=employee_name,
                advance_date=advance_date,
                amount=amount,
                reason=reason,
                notes=notes if notes else None,
                created_by=current_user.id
            )

            db.session.add(advance)
            db.session.commit()

            flash('Tạo tạm ứng thành công.', 'success')
            return redirect(url_for('advances.advance_detail', advance_id=advance.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('advances.create_advance'))

    # GET
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.full_name).all()
    return render_template('advances/create.html', employees=employees)


@bp.route('/<int:advance_id>')
@login_required
@role_required(['director', 'accountant'])
def advance_detail(advance_id):
    """Chi tiết tạm ứng"""
    advance = Advance.query.get_or_404(advance_id)
    return render_template('advances/detail.html', advance=advance)


@bp.route('/<int:advance_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def edit_advance(advance_id):
    """Chỉnh sửa tạm ứng"""
    advance = Advance.query.get_or_404(advance_id)

    # Không cho sửa nếu đã trừ lương
    if advance.is_deducted:
        flash('Không thể sửa tạm ứng đã trừ lương.', 'danger')
        return redirect(url_for('advances.advance_detail', advance_id=advance_id))

    if request.method == 'POST':
        try:
            advance_date_str = request.form.get('advance_date')
            amount = float(request.form.get('amount', 0))
            reason = request.form.get('reason', '').strip()
            notes = request.form.get('notes', '').strip()

            if not advance_date_str or amount <= 0 or not reason:
                flash('Vui lòng điền đầy đủ thông tin.', 'danger')
                return redirect(url_for('advances.edit_advance', advance_id=advance_id))

            advance.advance_date = datetime.strptime(advance_date_str, '%Y-%m-%d').date()
            advance.amount = amount
            advance.reason = reason
            advance.notes = notes if notes else None
            advance.updated_at = datetime.utcnow()

            db.session.commit()

            flash('Cập nhật tạm ứng thành công.', 'success')
            return redirect(url_for('advances.advance_detail', advance_id=advance.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('advances.edit_advance', advance_id=advance_id))

    return render_template('advances/edit.html', advance=advance)


@bp.route('/<int:advance_id>/delete', methods=['POST'])
@login_required
@role_required(['director', 'accountant'])
def delete_advance(advance_id):
    """Xóa tạm ứng"""
    advance = Advance.query.get_or_404(advance_id)

    # Không cho xóa nếu đã trừ lương
    if advance.is_deducted:
        flash('Không thể xóa tạm ứng đã trừ lương.', 'danger')
        return redirect(url_for('advances.advance_detail', advance_id=advance_id))

    try:
        db.session.delete(advance)
        db.session.commit()
        flash('Đã xóa tạm ứng.', 'success')
        return redirect(url_for('advances.list_advances'))
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
        return redirect(url_for('advances.advance_detail', advance_id=advance_id))


# ========== API ==========
@bp.route('/api/pending-by-employee/<employee_name>')
@login_required
def api_pending_advances(employee_name):
    """API lấy các khoản tạm ứng chưa trừ của nhân viên"""
    advances = Advance.query.filter_by(
        employee_name=employee_name,
        is_deducted=False
    ).order_by(Advance.advance_date).all()

    return jsonify([{
        'id': a.id,
        'advance_date': a.advance_date.strftime('%d-%m-%Y'),
        'amount': a.amount,
        'reason': a.reason
    } for a in advances])