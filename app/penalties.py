from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Penalty, Employee, User
from app.decorators import role_required
from datetime import datetime

bp = Blueprint('penalties', __name__)


@bp.route('/')
@login_required
@role_required(['director', 'accountant'])
def list_penalties():
    """Danh sách biên bản phạt"""
    # Filter
    employee_filter = request.args.get('employee', '')
    status_filter = request.args.get('status', 'all')
    month_filter = request.args.get('month', '')

    query = Penalty.query

    if employee_filter:
        query = query.filter(Penalty.employee_name.ilike(f'%{employee_filter}%'))

    if status_filter == 'pending':
        query = query.filter_by(is_deducted=False)
    elif status_filter == 'deducted':
        query = query.filter_by(is_deducted=True)

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            query = query.filter(
                db.extract('month', Penalty.penalty_date) == month,
                db.extract('year', Penalty.penalty_date) == year
            )
        except:
            pass

    penalties = query.order_by(Penalty.penalty_date.desc()).all()

    # Tính tổng
    total_amount = sum(p.amount for p in penalties)
    pending_amount = sum(p.amount for p in penalties if not p.is_deducted)

    return render_template('penalties/list.html',
                           penalties=penalties,
                           employee_filter=employee_filter,
                           status_filter=status_filter,
                           month_filter=month_filter,
                           total_amount=total_amount,
                           pending_amount=pending_amount)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def create_penalty():
    """Tạo biên bản phạt mới"""
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
                return redirect(url_for('penalties.create_penalty'))

            penalty_date_str = request.form.get('penalty_date')
            amount = float(request.form.get('amount', 0))
            reason = request.form.get('reason', '').strip()
            notes = request.form.get('notes', '').strip()

            if not penalty_date_str or amount <= 0 or not reason:
                flash('Vui lòng điền đầy đủ thông tin.', 'danger')
                return redirect(url_for('penalties.create_penalty'))

            penalty_date = datetime.strptime(penalty_date_str, '%Y-%m-%d').date()

            penalty = Penalty(
                employee_id=employee_id,
                employee_name=employee_name,
                penalty_date=penalty_date,
                amount=amount,
                reason=reason,
                notes=notes if notes else None,
                created_by=current_user.id
            )

            db.session.add(penalty)
            db.session.commit()

            flash('Tạo biên bản phạt thành công.', 'success')
            return redirect(url_for('penalties.penalty_detail', penalty_id=penalty.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('penalties.create_penalty'))

    # GET
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.full_name).all()
    return render_template('penalties/create.html', employees=employees)


@bp.route('/<int:penalty_id>')
@login_required
@role_required(['director', 'accountant'])
def penalty_detail(penalty_id):
    """Chi tiết biên bản phạt"""
    penalty = Penalty.query.get_or_404(penalty_id)
    return render_template('penalties/detail.html', penalty=penalty)


@bp.route('/<int:penalty_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def edit_penalty(penalty_id):
    """Chỉnh sửa biên bản phạt"""
    penalty = Penalty.query.get_or_404(penalty_id)

    # Không cho sửa nếu đã trừ lương
    if penalty.is_deducted:
        flash('Không thể sửa biên bản đã trừ lương.', 'danger')
        return redirect(url_for('penalties.penalty_detail', penalty_id=penalty_id))

    if request.method == 'POST':
        try:
            penalty_date_str = request.form.get('penalty_date')
            amount = float(request.form.get('amount', 0))
            reason = request.form.get('reason', '').strip()
            notes = request.form.get('notes', '').strip()

            if not penalty_date_str or amount <= 0 or not reason:
                flash('Vui lòng điền đầy đủ thông tin.', 'danger')
                return redirect(url_for('penalties.edit_penalty', penalty_id=penalty_id))

            penalty.penalty_date = datetime.strptime(penalty_date_str, '%Y-%m-%d').date()
            penalty.amount = amount
            penalty.reason = reason
            penalty.notes = notes if notes else None
            penalty.updated_at = datetime.utcnow()

            db.session.commit()

            flash('Cập nhật biên bản phạt thành công.', 'success')
            return redirect(url_for('penalties.penalty_detail', penalty_id=penalty.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('penalties.edit_penalty', penalty_id=penalty_id))

    return render_template('penalties/edit.html', penalty=penalty)


@bp.route('/<int:penalty_id>/delete', methods=['POST'])
@login_required
@role_required(['director', 'accountant'])
def delete_penalty(penalty_id):
    """Xóa biên bản phạt"""
    penalty = Penalty.query.get_or_404(penalty_id)

    # Không cho xóa nếu đã trừ lương
    if penalty.is_deducted:
        flash('Không thể xóa biên bản đã trừ lương.', 'danger')
        return redirect(url_for('penalties.penalty_detail', penalty_id=penalty_id))

    try:
        db.session.delete(penalty)
        db.session.commit()
        flash('Đã xóa biên bản phạt.', 'success')
        return redirect(url_for('penalties.list_penalties'))
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
        return redirect(url_for('penalties.penalty_detail', penalty_id=penalty_id))


# ========== API ==========
@bp.route('/api/pending-by-employee/<employee_name>')
@login_required
def api_pending_penalties(employee_name):
    """API lấy các khoản phạt chưa trừ của nhân viên"""
    penalties = Penalty.query.filter_by(
        employee_name=employee_name,
        is_deducted=False
    ).order_by(Penalty.penalty_date).all()

    return jsonify([{
        'id': p.id,
        'penalty_date': p.penalty_date.strftime('%d-%m-%Y'),
        'amount': p.amount,
        'reason': p.reason
    } for p in penalties])