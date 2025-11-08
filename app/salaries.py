from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Salary, User
from app.decorators import role_required
from datetime import datetime
import json

bp = Blueprint('salaries', __name__)


@bp.route('/')
@login_required
@role_required(['director', 'manager', 'accountant'])
def list_salaries():
    """Danh sách bảng lương"""
    # Filter by month and employee name
    month_filter = request.args.get('month', '')
    name_filter = request.args.get('employee_name', '')

    query = Salary.query

    if month_filter:
        query = query.filter_by(month=month_filter)

    if name_filter:
        query = query.filter(Salary.employee_name.ilike(f'%{name_filter}%'))

    salaries = query.all()

    def sort_key(s):
        try:
            parts = s.month.split('-')
            if len(parts) == 2:
                return f"{parts[1]}-{parts[0]}"
        except:
            pass
        return s.month

    salaries.sort(key=sort_key, reverse=True)

    return render_template('salaries/list.html',
                           salaries=salaries,
                           month_filter=month_filter,
                           name_filter=name_filter)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'manager', 'accountant'])
def create_salary():
    """Tạo bảng lương mới"""
    if request.method == 'POST':
        try:
            employee_name = request.form.get('employee_name', '').strip()

            # Validate employee name
            if not employee_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('salaries.create_salary'))

            month = request.form.get('month')
            work_days_in_month = float(request.form.get('work_days_in_month'))
            actual_work_days = float(request.form.get('actual_work_days'))
            basic_salary = float(request.form.get('basic_salary'))
            responsibility_salary = float(request.form.get('responsibility_salary', 0))

            # Parse capacity bonuses
            capacity_contents = request.form.getlist('capacity_content[]')
            capacity_amounts = request.form.getlist('capacity_amount[]')
            capacity_bonuses = []
            for i in range(len(capacity_contents)):
                if capacity_contents[i].strip():
                    capacity_bonuses.append({
                        'content': capacity_contents[i],
                        'amount': float(capacity_amounts[i]) if capacity_amounts[i] else 0
                    })

            # Parse deductions
            deduction_contents = request.form.getlist('deduction_content[]')
            deduction_amounts = request.form.getlist('deduction_amount[]')
            deductions = []
            for i in range(len(deduction_contents)):
                if deduction_contents[i].strip():
                    deductions.append({
                        'content': deduction_contents[i],
                        'amount': float(deduction_amounts[i]) if deduction_amounts[i] else 0
                    })

            # Check if salary for this employee and month already exists
            existing = Salary.query.filter_by(employee_name=employee_name, month=month).first()
            if existing:
                flash(f'Bảng lương cho nhân viên {employee_name} trong tháng {month} đã tồn tại.', 'danger')
                return redirect(url_for('salaries.create_salary'))

            # Create salary
            salary = Salary(
                employee_name=employee_name,
                month=month,
                work_days_in_month=work_days_in_month,
                actual_work_days=actual_work_days,
                basic_salary=basic_salary,
                responsibility_salary=responsibility_salary,
                created_by=current_user.id
            )

            salary.set_capacity_bonuses(capacity_bonuses)
            salary.set_deductions(deductions)
            salary.calculate()

            db.session.add(salary)
            db.session.commit()

            flash('Tạo bảng lương thành công.', 'success')
            return redirect(url_for('salaries.salary_detail', salary_id=salary.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('salaries.create_salary'))

    # GET request
    return render_template('salaries/create.html')


@bp.route('/<int:salary_id>')
@login_required
@role_required(['director', 'manager', 'accountant'])
def salary_detail(salary_id):
    """Chi tiết bảng lương"""
    salary = Salary.query.get_or_404(salary_id)
    return render_template('salaries/detail.html', salary=salary)


@bp.route('/<int:salary_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'manager', 'accountant'])
def edit_salary(salary_id):
    """Chỉnh sửa bảng lương"""
    salary = Salary.query.get_or_404(salary_id)

    if request.method == 'POST':
        try:
            employee_name = request.form.get('employee_name', '').strip()

            # Validate employee name
            if not employee_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('salaries.edit_salary', salary_id=salary_id))

            salary.employee_name = employee_name
            salary.month = request.form.get('month')
            salary.work_days_in_month = float(request.form.get('work_days_in_month'))
            salary.actual_work_days = float(request.form.get('actual_work_days'))
            salary.basic_salary = float(request.form.get('basic_salary'))
            salary.responsibility_salary = float(request.form.get('responsibility_salary', 0))

            # Parse capacity bonuses
            capacity_contents = request.form.getlist('capacity_content[]')
            capacity_amounts = request.form.getlist('capacity_amount[]')
            capacity_bonuses = []
            for i in range(len(capacity_contents)):
                if capacity_contents[i].strip():
                    capacity_bonuses.append({
                        'content': capacity_contents[i],
                        'amount': float(capacity_amounts[i]) if capacity_amounts[i] else 0
                    })

            # Parse deductions
            deduction_contents = request.form.getlist('deduction_content[]')
            deduction_amounts = request.form.getlist('deduction_amount[]')
            deductions = []
            for i in range(len(deduction_contents)):
                if deduction_contents[i].strip():
                    deductions.append({
                        'content': deduction_contents[i],
                        'amount': float(deduction_amounts[i]) if deduction_amounts[i] else 0
                    })

            salary.set_capacity_bonuses(capacity_bonuses)
            salary.set_deductions(deductions)
            salary.calculate()
            salary.updated_at = datetime.utcnow()

            db.session.commit()

            flash('Cập nhật bảng lương thành công.', 'success')
            return redirect(url_for('salaries.salary_detail', salary_id=salary.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('salaries.edit_salary', salary_id=salary_id))

    # GET request
    return render_template('salaries/edit.html', salary=salary)


@bp.route('/<int:salary_id>/delete', methods=['POST'])
@login_required
@role_required(['director', 'manager', 'accountant'])
def delete_salary(salary_id):
    """Xóa bảng lương"""
    salary = Salary.query.get_or_404(salary_id)

    # Only creator, director or accountant can delete
    if current_user.role not in ['director', 'accountant'] and salary.created_by != current_user.id:
        flash('Bạn không có quyền xóa bảng lương này.', 'danger')
        return redirect(url_for('salaries.salary_detail', salary_id=salary_id))

    db.session.delete(salary)
    db.session.commit()

    flash('Đã xóa bảng lương thành công.', 'success')
    return redirect(url_for('salaries.list_salaries'))