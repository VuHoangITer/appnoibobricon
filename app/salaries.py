from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import Salary, User, SalaryShareLink, SalaryShareLinkAccess
from app.decorators import role_required
from datetime import datetime, timedelta
from app.models import Employee, SalaryGrade, WorkDaysConfig, Penalty, Advance
import json

bp = Blueprint('salaries', __name__)


# ========== HELPER FUNCTIONS (giữ nguyên) ==========
def get_client_ip(request):
    """Lấy địa chỉ IP thực của client"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    elif request.headers.get('CF-Connecting-IP'):
        ip = request.headers.get('CF-Connecting-IP')
    else:
        ip = request.remote_addr
    return ip or 'Unknown'


def parse_user_agent(user_agent_string):
    """Parse user agent để lấy thông tin thiết bị"""
    if not user_agent_string:
        return {
            'browser': 'Unknown',
            'browser_version': '',
            'os': 'Unknown',
            'device_type': 'desktop',
            'device_brand': ''
        }

    try:
        from user_agents import parse as ua_parse
        ua = ua_parse(user_agent_string)

        if ua.is_mobile:
            device_type = 'mobile'
        elif ua.is_tablet:
            device_type = 'tablet'
        else:
            device_type = 'desktop'

        browser = ua.browser.family if ua.browser.family else 'Unknown'
        browser_version = ua.browser.version_string if ua.browser.version_string else ''
        os = ua.os.family if ua.os.family else 'Unknown'

        device_brand = ''
        if ua.device.brand:
            device_brand = ua.device.brand
        elif ua.device.family and ua.device.family != 'Other':
            device_brand = ua.device.family

        return {
            'browser': browser,
            'browser_version': browser_version,
            'os': os,
            'device_type': device_type,
            'device_brand': device_brand
        }
    except:
        return {
            'browser': 'Unknown',
            'browser_version': '',
            'os': 'Unknown',
            'device_type': 'desktop',
            'device_brand': ''
        }


def log_share_link_access(share_link, request):
    """Ghi log truy cập link chia sẻ"""
    try:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get('User-Agent', '')
        device_info = parse_user_agent(user_agent)

        access_log = SalaryShareLinkAccess(
            share_link_id=share_link.id,
            ip_address=ip_address,
            user_agent=user_agent,
            browser=device_info['browser'],
            browser_version=device_info['browser_version'],
            os=device_info['os'],
            device_type=device_info['device_type'],
            device_brand=device_info['device_brand'],
            referer=request.headers.get('Referer')
        )

        db.session.add(access_log)
        db.session.commit()

        return access_log
    except Exception as e:
        print(f"Error logging access: {str(e)}")
        return None


def process_and_mark_deductions(employee_name, deductions, salary_id):
    """Xử lý và đánh dấu penalties/advances đã trừ lương"""
    try:
        pending_penalties = Penalty.query.filter_by(
            employee_name=employee_name,
            is_deducted=False
        ).all()

        pending_advances = Advance.query.filter_by(
            employee_name=employee_name,
            is_deducted=False
        ).all()

        for penalty in pending_penalties:
            penalty.mark_as_deducted(salary_id)

        for advance in pending_advances:
            advance.mark_as_deducted(salary_id)

        db.session.commit()

        total_marked = len(pending_penalties) + len(pending_advances)
        if total_marked > 0:
            print(f"Marked {len(pending_penalties)} penalties and {len(pending_advances)} advances as deducted for {employee_name}")

    except Exception as e:
        print(f"Error processing deductions: {str(e)}")
        db.session.rollback()


# ========== ROUTES ==========
@bp.route('/')
@login_required
@role_required(['director', 'accountant'])
def list_salaries():
    """Danh sách bảng lương"""
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
@role_required(['director', 'accountant'])
def create_salary():
    """Tạo bảng lương mới"""
    if request.method == 'POST':
        try:
            employee_id = request.form.get('employee_id')
            employee_name = request.form.get('employee_name', '').strip()

            if employee_id:
                employee = Employee.query.get(int(employee_id))
                if employee:
                    employee_name = employee.full_name

            if not employee_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('salaries.create_salary'))

            month = request.form.get('month')
            work_days_in_month = float(request.form.get('work_days_in_month'))
            actual_work_days = float(request.form.get('actual_work_days'))
            basic_salary = float(request.form.get('basic_salary'))

            # ===== MỚI: Parse RESPONSIBILITIES =====
            responsibility_contents = request.form.getlist('responsibility_content[]')
            responsibility_amounts = request.form.getlist('responsibility_amount[]')
            responsibilities = []
            for i in range(len(responsibility_contents)):
                if responsibility_contents[i].strip():
                    responsibilities.append({
                        'content': responsibility_contents[i],
                        'amount': float(responsibility_amounts[i]) if responsibility_amounts[i] else 0
                    })

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

            # Check existing
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
                created_by=current_user.id
            )

            # ===== MỚI: Set responsibilities =====
            salary.set_responsibilities(responsibilities)
            salary.set_capacity_bonuses(capacity_bonuses)
            salary.set_deductions(deductions)
            salary.calculate()

            db.session.add(salary)
            db.session.commit()

            process_and_mark_deductions(employee_name, deductions, salary.id)

            flash('Tạo bảng lương thành công.', 'success')
            return redirect(url_for('salaries.salary_detail', salary_id=salary.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('salaries.create_salary'))

    # GET request
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.full_name).all()
    salary_grades = SalaryGrade.query.filter_by(is_active=True).order_by(SalaryGrade.name).all()

    return render_template('salaries/create.html',
                           employees=employees,
                           salary_grades=salary_grades)


@bp.route('/quick-create/<int:employee_id>', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def quick_create_salary(employee_id):
    """Tạo lương nhanh cho nhân viên đã có trong hệ thống"""
    employee = Employee.query.get_or_404(employee_id)

    if not employee.salary_grade:
        flash('Nhân viên chưa được gán cấp bậc lương.', 'danger')
        return redirect(url_for('employees.employee_detail', employee_id=employee_id))

    if request.method == 'POST':
        try:
            month = request.form.get('month')
            actual_work_days = float(request.form.get('actual_work_days'))

            # Parse capacity bonuses (có thể chỉnh sửa)
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

            # Check existing
            existing = Salary.query.filter_by(
                employee_name=employee.full_name,
                month=month
            ).first()
            if existing:
                flash(f'Bảng lương tháng {month} đã tồn tại.', 'danger')
                return redirect(url_for('salaries.quick_create_salary', employee_id=employee_id))

            # Get work days config
            month_int, year_int = map(int, month.split('-'))
            work_days_in_month = WorkDaysConfig.get_work_days(month_int, year_int)

            # Get salary from grade
            grade = employee.salary_grade

            # Create salary
            salary = Salary(
                employee_name=employee.full_name,
                month=month,
                work_days_in_month=work_days_in_month,
                actual_work_days=actual_work_days,
                basic_salary=grade.basic_salary,
                created_by=current_user.id
            )

            # ===== MỚI: Set responsibilities từ grade =====
            salary.set_responsibilities(grade.get_responsibilities())
            salary.set_capacity_bonuses(capacity_bonuses)
            salary.set_deductions(deductions)
            salary.calculate()

            db.session.add(salary)
            db.session.commit()

            process_and_mark_deductions(employee.full_name, deductions, salary.id)

            flash('Tạo bảng lương thành công.', 'success')
            return redirect(url_for('salaries.salary_detail', salary_id=salary.id))

        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('salaries.quick_create_salary', employee_id=employee_id))

    return render_template('salaries/quick_create.html', employee=employee)


@bp.route('/<int:salary_id>')
@login_required
@role_required(['director', 'accountant'])
def salary_detail(salary_id):
    """Chi tiết bảng lương"""
    salary = Salary.query.get_or_404(salary_id)

    # Tìm nhân viên theo tên để lấy mã nhân viên
    employee = Employee.query.filter_by(full_name=salary.employee_name).first()

    return render_template('salaries/detail.html',
                           salary=salary,
                           employee=employee)


@bp.route('/<int:salary_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'accountant'])
def edit_salary(salary_id):
    """Chỉnh sửa bảng lương"""
    salary = Salary.query.get_or_404(salary_id)

    if request.method == 'POST':
        try:
            employee_name = request.form.get('employee_name', '').strip()

            if not employee_name:
                flash('Vui lòng nhập tên nhân viên.', 'danger')
                return redirect(url_for('salaries.edit_salary', salary_id=salary_id))

            salary.employee_name = employee_name
            salary.month = request.form.get('month')
            salary.work_days_in_month = float(request.form.get('work_days_in_month'))
            salary.actual_work_days = float(request.form.get('actual_work_days'))
            salary.basic_salary = float(request.form.get('basic_salary'))

            # ===== MỚI: Parse RESPONSIBILITIES =====
            responsibility_contents = request.form.getlist('responsibility_content[]')
            responsibility_amounts = request.form.getlist('responsibility_amount[]')
            responsibilities = []
            for i in range(len(responsibility_contents)):
                if responsibility_contents[i].strip():
                    responsibilities.append({
                        'content': responsibility_contents[i],
                        'amount': float(responsibility_amounts[i]) if responsibility_amounts[i] else 0
                    })

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

            # ===== MỚI: Set responsibilities =====
            salary.set_responsibilities(responsibilities)
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

    return render_template('salaries/edit.html', salary=salary)


@bp.route('/<int:salary_id>/delete', methods=['POST'])
@login_required
@role_required(['director', 'accountant'])
def delete_salary(salary_id):
    """Xóa bảng lương"""
    salary = Salary.query.get_or_404(salary_id)

    if current_user.role not in ['director', 'accountant'] and salary.created_by != current_user.id:
        flash('Bạn không có quyền xóa bảng lương này.', 'danger')
        return redirect(url_for('salaries.salary_detail', salary_id=salary_id))

    db.session.delete(salary)
    db.session.commit()

    flash('Đã xóa bảng lương thành công.', 'success')
    return redirect(url_for('salaries.list_salaries'))


# ========== SHARE LINK ROUTES (giữ nguyên toàn bộ) ==========
@bp.route('/<int:salary_id>/share-links')
@login_required
@role_required(['director', 'accountant'])
def manage_share_links(salary_id):
    salary = Salary.query.get_or_404(salary_id)
    share_links = SalaryShareLink.query.filter_by(
        salary_id=salary_id
    ).order_by(SalaryShareLink.created_at.desc()).all()

    return render_template('salaries/share_links.html',
                           salary=salary,
                           share_links=share_links,
                           now=datetime.utcnow())


@bp.route('/<int:salary_id>/create-share-link', methods=['POST'])
@login_required
@role_required(['director', 'accountant'])
def create_share_link(salary_id):
    salary = Salary.query.get_or_404(salary_id)

    try:
        days = int(request.form.get('days', 3))
        max_views = request.form.get('max_views')

        if days < 1 or days > 30:
            flash('Số ngày phải từ 1 đến 30.', 'danger')
            return redirect(url_for('salaries.manage_share_links', salary_id=salary_id))

        if max_views:
            max_views = int(max_views)
            if max_views < 1:
                flash('Số lượt xem phải lớn hơn 0.', 'danger')
                return redirect(url_for('salaries.manage_share_links', salary_id=salary_id))
        else:
            max_views = None

        expires_at = datetime.utcnow() + timedelta(days=days)

        share_link = SalaryShareLink(
            salary_id=salary_id,
            created_by=current_user.id,
            expires_at=expires_at,
            max_views=max_views
        )

        db.session.add(share_link)
        db.session.commit()

        flash('Tạo link chia sẻ thành công!', 'success')
        return redirect(url_for('salaries.manage_share_links', salary_id=salary_id))

    except Exception as e:
        flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
        return redirect(url_for('salaries.manage_share_links', salary_id=salary_id))


@bp.route('/share-link/<int:link_id>/revoke', methods=['POST'])
@login_required
@role_required(['director', 'accountant'])
def revoke_share_link(link_id):
    share_link = SalaryShareLink.query.get_or_404(link_id)

    if current_user.role not in ['director', 'accountant'] and share_link.created_by != current_user.id:
        flash('Bạn không có quyền vô hiệu hóa link này.', 'danger')
        return redirect(url_for('salaries.manage_share_links', salary_id=share_link.salary_id))

    share_link.is_active = False
    db.session.commit()

    flash('Đã vô hiệu hóa link chia sẻ.', 'success')
    return redirect(url_for('salaries.manage_share_links', salary_id=share_link.salary_id))


@bp.route('/share-link/<int:link_id>/delete', methods=['POST'])
@login_required
@role_required(['director', 'accountant'])
def delete_share_link(link_id):
    share_link = SalaryShareLink.query.get_or_404(link_id)

    if current_user.role not in ['director', 'accountant'] and share_link.created_by != current_user.id:
        flash('Bạn không có quyền xóa link này.', 'danger')
        return redirect(url_for('salaries.manage_share_links', salary_id=share_link.salary_id))

    salary_id = share_link.salary_id
    db.session.delete(share_link)
    db.session.commit()

    flash('Đã xóa link chia sẻ.', 'success')
    return redirect(url_for('salaries.manage_share_links', salary_id=salary_id))


@bp.route('/share-link/<int:link_id>/access-logs')
@login_required
@role_required(['director', 'accountant'])
def view_access_logs(link_id):
    share_link = SalaryShareLink.query.get_or_404(link_id)

    if current_user.role not in ['director', 'accountant'] and share_link.created_by != current_user.id:
        flash('Bạn không có quyền xem lịch sử này.', 'danger')
        return redirect(url_for('salaries.manage_share_links', salary_id=share_link.salary_id))

    access_logs = share_link.access_logs.all()

    return render_template('salaries/access_logs.html',
                           share_link=share_link,
                           access_logs=access_logs,
                           salary=share_link.salary,
                           now=datetime.utcnow())


@bp.route('/shared/<token>')
def view_shared_salary(token):
    share_link = SalaryShareLink.query.filter_by(token=token).first()

    if not share_link:
        return render_template('salaries/share_error.html',
                               error='Link không tồn tại hoặc đã bị xóa.')

    if datetime.utcnow() > share_link.expires_at:
        db.session.delete(share_link)
        db.session.commit()
        return render_template('salaries/share_error.html',
                               error='Link đã hết hạn và đã bị xóa tự động.')

    if not share_link.is_valid():
        reason = ''
        if not share_link.is_active:
            reason = 'Link đã bị vô hiệu hóa.'
        elif share_link.max_views and share_link.view_count >= share_link.max_views:
            db.session.delete(share_link)
            db.session.commit()
            reason = 'Link đã hết lượt xem và đã bị xóa tự động.'

        return render_template('salaries/share_error.html', error=reason)

    log_share_link_access(share_link, request)
    share_link.increment_view()

    if share_link.max_views and share_link.view_count >= share_link.max_views:
        salary = share_link.salary
        db.session.delete(share_link)
        db.session.commit()

        time_left = share_link.expires_at - datetime.utcnow()
        hours_left = int(time_left.total_seconds() / 3600)

        return render_template('salaries/shared_view.html',
                               salary=salary,
                               share_link=share_link,
                               hours_left=hours_left,
                               is_last_view=True)

    salary = share_link.salary
    time_left = share_link.expires_at - datetime.utcnow()
    hours_left = int(time_left.total_seconds() / 3600)

    return render_template('salaries/shared_view.html',
                           salary=salary,
                           share_link=share_link,
                           hours_left=hours_left,
                           is_last_view=False)