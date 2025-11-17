from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Employee, SalaryGrade, Salary
from app.decorators import role_required
from datetime import datetime

bp = Blueprint('employees', __name__)


@bp.route('/')
@login_required
@role_required(['director', 'accountant'])
def list_employees():
    """Danh sách nhân viên"""
    # Filter
    name_filter = request.args.get('name', '')
    grade_filter = request.args.get('grade', '')
    status_filter = request.args.get('status', 'active')

    query = Employee.query

    if name_filter:
        query = query.filter(Employee.full_name.ilike(f'%{name_filter}%'))

    if grade_filter:
        query = query.filter_by(salary_grade_id=int(grade_filter))

    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)

    employees = query.order_by(Employee.full_name).all()
    grades = SalaryGrade.query.filter_by(is_active=True).order_by(SalaryGrade.name).all()

    return render_template('employees/list.html',
                           employees=employees,
                           grades=grades,
                           name_filter=name_filter,
                           grade_filter=grade_filter,
                           status_filter=status_filter)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def create_employee():
    """Tạo nhân viên mới"""
    if request.method == 'POST':
        try:
            full_name = request.form.get('full_name', '').strip()
            employee_code = request.form.get('employee_code', '').strip()
            salary_grade_id = request.form.get('salary_grade_id')
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            department = request.form.get('department', '').strip()
            position = request.form.get('position', '').strip()
            hire_date_str = request.form.get('hire_date')
            notes = request.form.get('notes', '').strip()

            if not full_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('employees.create_employee'))

            # Check duplicate employee code
            if employee_code:
                existing = Employee.query.filter_by(employee_code=employee_code).first()
                if existing:
                    flash(f'Mã nhân viên "{employee_code}" đã tồn tại.', 'danger')
                    return redirect(url_for('employees.create_employee'))

            hire_date = None
            if hire_date_str:
                try:
                    hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
                except:
                    pass

            employee = Employee(
                full_name=full_name,
                employee_code=employee_code if employee_code else None,
                salary_grade_id=int(salary_grade_id) if salary_grade_id else None,
                email=email if email else None,
                phone=phone if phone else None,
                department=department if department else None,
                position=position if position else None,
                hire_date=hire_date,
                notes=notes if notes else None,
                created_by=current_user.id
            )

            db.session.add(employee)
            db.session.commit()

            flash('Tạo nhân viên thành công.', 'success')
            return redirect(url_for('employees.employee_detail', employee_id=employee.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('employees.create_employee'))

    grades = SalaryGrade.query.filter_by(is_active=True).order_by(SalaryGrade.name).all()
    return render_template('employees/create.html', grades=grades)


@bp.route('/<int:employee_id>')
@login_required
@role_required(['director', 'accountant'])
def employee_detail(employee_id):
    """Chi tiết nhân viên"""
    employee = Employee.query.get_or_404(employee_id)

    # Lấy lịch sử lương
    salaries = Salary.query.filter_by(employee_name=employee.full_name) \
        .order_by(Salary.month.desc()).limit(12).all()

    return render_template('employees/detail.html',
                           employee=employee,
                           salaries=salaries)


@bp.route('/<int:employee_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def edit_employee(employee_id):
    """Chỉnh sửa thông tin nhân viên"""
    employee = Employee.query.get_or_404(employee_id)

    if request.method == 'POST':
        try:
            full_name = request.form.get('full_name', '').strip()
            employee_code = request.form.get('employee_code', '').strip()
            salary_grade_id = request.form.get('salary_grade_id')
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            department = request.form.get('department', '').strip()
            position = request.form.get('position', '').strip()
            hire_date_str = request.form.get('hire_date')
            notes = request.form.get('notes', '').strip()

            if not full_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('employees.edit_employee', employee_id=employee_id))

            # Check duplicate employee code (exclude current)
            if employee_code:
                existing = Employee.query.filter(
                    Employee.employee_code == employee_code,
                    Employee.id != employee_id
                ).first()
                if existing:
                    flash(f'Mã nhân viên "{employee_code}" đã tồn tại.', 'danger')
                    return redirect(url_for('employees.edit_employee', employee_id=employee_id))

            hire_date = employee.hire_date
            if hire_date_str:
                try:
                    hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
                except:
                    pass

            employee.full_name = full_name
            employee.employee_code = employee_code if employee_code else None
            employee.salary_grade_id = int(salary_grade_id) if salary_grade_id else None
            employee.email = email if email else None
            employee.phone = phone if phone else None
            employee.department = department if department else None
            employee.position = position if position else None
            employee.hire_date = hire_date
            employee.notes = notes if notes else None
            employee.updated_at = datetime.utcnow()

            db.session.commit()

            flash('Cập nhật thông tin nhân viên thành công.', 'success')
            return redirect(url_for('employees.employee_detail', employee_id=employee.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('employees.edit_employee', employee_id=employee_id))

    grades = SalaryGrade.query.filter_by(is_active=True).order_by(SalaryGrade.name).all()
    return render_template('employees/edit.html', employee=employee, grades=grades)


@bp.route('/<int:employee_id>/deactivate', methods=['POST'])
@login_required
@role_required(['director'])
def deactivate_employee(employee_id):
    """Vô hiệu hóa nhân viên"""
    employee = Employee.query.get_or_404(employee_id)
    employee.is_active = False
    db.session.commit()

    flash(f'Đã vô hiệu hóa nhân viên {employee.full_name}.', 'success')
    return redirect(url_for('employees.employee_detail', employee_id=employee_id))


@bp.route('/<int:employee_id>/activate', methods=['POST'])
@login_required
@role_required(['director'])
def activate_employee(employee_id):
    """Kích hoạt lại nhân viên"""
    employee = Employee.query.get_or_404(employee_id)
    employee.is_active = True
    db.session.commit()

    flash(f'Đã kích hoạt lại nhân viên {employee.full_name}.', 'success')
    return redirect(url_for('employees.employee_detail', employee_id=employee_id))


@bp.route('/api/employee/<int:employee_id>')
@login_required
def api_get_employee(employee_id):
    """API lấy thông tin nhân viên (cho auto-fill)"""
    employee = Employee.query.get_or_404(employee_id)

    result = {
        'id': employee.id,
        'full_name': employee.full_name,
        'employee_code': employee.employee_code,
        'salary_grade_id': employee.salary_grade_id,
        'salary_info': None
    }

    if employee.salary_grade:
        result['salary_info'] = {
            'grade_name': employee.salary_grade.name,
            'basic_salary': employee.salary_grade.basic_salary,
            'responsibility_salary': employee.salary_grade.responsibility_salary,
            'capacity_bonuses': employee.salary_grade.get_capacity_bonuses()
        }

    return jsonify(result)


@bp.route('/api/search')
@login_required
def api_search_employees():
    """API tìm kiếm nhân viên (cho autocomplete)"""
    query = request.args.get('q', '')

    if len(query) < 2:
        return jsonify([])

    employees = Employee.query.filter(
        Employee.is_active == True,
        Employee.full_name.ilike(f'%{query}%')
    ).order_by(Employee.full_name).limit(10).all()

    return jsonify([{
        'id': e.id,
        'full_name': e.full_name,
        'employee_code': e.employee_code,
        'salary_grade_name': e.salary_grade.name if e.salary_grade else None
    } for e in employees])


@bp.route('/<int:employee_id>/delete', methods=['POST'])
@login_required
@role_required(['director'])
def delete_employee(employee_id):
    """Xóa vĩnh viễn nhân viên (Giám đốc có toàn quyền)"""
    employee = Employee.query.get_or_404(employee_id)

    # Kiểm tra số lượng bảng lương (chỉ để thông báo)
    salary_count = Salary.query.filter_by(employee_name=employee.full_name).count()

    employee_name = employee.full_name

    try:
        # 1. Xóa tất cả salary_share_links liên quan đến các bảng lương của nhân viên này
        if salary_count > 0:
            from app.models import SalaryShareLink

            # Lấy danh sách ID của các bảng lương
            salary_ids = [s.id for s in Salary.query.filter_by(employee_name=employee.full_name).all()]

            # Xóa tất cả share links liên quan
            if salary_ids:
                share_link_count = SalaryShareLink.query.filter(
                    SalaryShareLink.salary_id.in_(salary_ids)
                ).delete(synchronize_session=False)

                if share_link_count > 0:
                    print(f"Đã xóa {share_link_count} liên kết chia sẻ")

            # 2. Xóa tất cả bảng lương
            Salary.query.filter_by(employee_name=employee.full_name).delete()

        # 3. Xóa nhân viên
        db.session.delete(employee)
        db.session.commit()

        if salary_count > 0:
            flash(f'Đã xóa nhân viên "{employee_name}" và {salary_count} bảng lương liên quan khỏi hệ thống.',
                  'success')
        else:
            flash(f'Đã xóa nhân viên "{employee_name}" khỏi hệ thống.', 'success')

        return redirect(url_for('employees.list_employees'))

    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi khi xóa nhân viên: {str(e)}', 'danger')
        return redirect(url_for('employees.employee_detail', employee_id=employee_id))