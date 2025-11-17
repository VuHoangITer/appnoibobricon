from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Salary, User, SalaryShareLink, SalaryShareLinkAccess, Employee, SalaryGrade, WorkDaysConfig
from app.decorators import role_required
from datetime import datetime, timedelta
import json

bp = Blueprint('salary_grades', __name__)


@bp.route('/')
@login_required
@role_required(['director'])
def list_grades():
    """Danh sách cấp bậc lương (chỉ giám đốc)"""
    grades = SalaryGrade.query.filter_by(is_active=True).order_by(SalaryGrade.name).all()
    return render_template('salary_grades/list.html', grades=grades)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def create_grade():
    """Tạo cấp bậc lương mới"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            basic_salary = float(request.form.get('basic_salary', 0))
            responsibility_salary = float(request.form.get('responsibility_salary', 0))
            description = request.form.get('description', '').strip()

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

            # Check if grade name already exists
            existing = SalaryGrade.query.filter_by(name=name).first()
            if existing:
                flash(f'Cấp bậc lương "{name}" đã tồn tại.', 'danger')
                return redirect(url_for('salary_grades.create_grade'))

            grade = SalaryGrade(
                name=name,
                basic_salary=basic_salary,
                responsibility_salary=responsibility_salary,
                description=description,
                created_by=current_user.id
            )

            grade.set_capacity_bonuses(capacity_bonuses)

            db.session.add(grade)
            db.session.commit()

            flash('Tạo cấp bậc lương thành công.', 'success')
            return redirect(url_for('salary_grades.list_grades'))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('salary_grades.create_grade'))

    return render_template('salary_grades/create.html')


@bp.route('/<int:grade_id>')
@login_required
@role_required(['director'])
def grade_detail(grade_id):
    """Chi tiết cấp bậc lương"""
    grade = SalaryGrade.query.get_or_404(grade_id)
    return render_template('salary_grades/detail.html', grade=grade)


@bp.route('/<int:grade_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director'])
def edit_grade(grade_id):
    """Chỉnh sửa cấp bậc lương"""
    grade = SalaryGrade.query.get_or_404(grade_id)

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            basic_salary = float(request.form.get('basic_salary', 0))
            responsibility_salary = float(request.form.get('responsibility_salary', 0))
            description = request.form.get('description', '').strip()

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

            # Check duplicate name (exclude current)
            existing = SalaryGrade.query.filter(
                SalaryGrade.name == name,
                SalaryGrade.id != grade_id
            ).first()
            if existing:
                flash(f'Cấp bậc lương "{name}" đã tồn tại.', 'danger')
                return redirect(url_for('salary_grades.edit_grade', grade_id=grade_id))

            grade.name = name
            grade.basic_salary = basic_salary
            grade.responsibility_salary = responsibility_salary
            grade.description = description
            grade.set_capacity_bonuses(capacity_bonuses)
            grade.updated_at = datetime.utcnow()

            db.session.commit()

            flash('Cập nhật cấp bậc lương thành công.', 'success')
            return redirect(url_for('salary_grades.grade_detail', grade_id=grade.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('salary_grades.edit_grade', grade_id=grade_id))

    return render_template('salary_grades/edit.html', grade=grade)


@bp.route('/<int:grade_id>/delete', methods=['POST'])
@login_required
@role_required(['director'])
def delete_grade(grade_id):
    """Xóa (vô hiệu hóa) cấp bậc lương"""
    grade = SalaryGrade.query.get_or_404(grade_id)

    # Kiểm tra xem có nhân viên nào đang dùng cấp bậc này không
    employee_count = grade.employees.count()
    if employee_count > 0:
        flash(f'Không thể xóa cấp bậc này vì có {employee_count} nhân viên đang sử dụng.', 'danger')
        return redirect(url_for('salary_grades.grade_detail', grade_id=grade_id))

    grade.is_active = False
    db.session.commit()

    flash('Đã vô hiệu hóa cấp bậc lương.', 'success')
    return redirect(url_for('salary_grades.list_grades'))


@bp.route('/api/grade/<int:grade_id>')
@login_required
def api_get_grade(grade_id):
    """API lấy thông tin cấp bậc lương (cho auto-fill)"""
    grade = SalaryGrade.query.get_or_404(grade_id)

    return jsonify({
        'id': grade.id,
        'name': grade.name,
        'basic_salary': grade.basic_salary,
        'responsibility_salary': grade.responsibility_salary,
        'capacity_bonuses': grade.get_capacity_bonuses()
    })


@bp.route('/api/all')
@login_required
def api_get_all_grades():
    """API lấy tất cả cấp bậc lương active"""
    grades = SalaryGrade.query.filter_by(is_active=True).order_by(SalaryGrade.name).all()

    return jsonify([{
        'id': g.id,
        'name': g.name,
        'basic_salary': g.basic_salary,
        'responsibility_salary': g.responsibility_salary
    } for g in grades])