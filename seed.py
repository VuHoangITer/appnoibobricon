from app import create_app, db
from app.models import User, Task, TaskAssignment, Note, Notification
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    # Drop all tables and recreate
    print("Dropping all tables...")
    db.drop_all()

    print("Creating all tables...")
    db.create_all()

    # Create users
    print("Creating users...")

    director = User(
        email='director@company.com',
        full_name='Nguyễn Văn A',
        role='director',
        is_active=True
    )
    director.set_password('director123')
    db.session.add(director)

    manager = User(
        email='manager@company.com',
        full_name='Trần Thị B',
        role='manager',
        is_active=True
    )
    manager.set_password('manager123')
    db.session.add(manager)

    accountant1 = User(
        email='accountant1@company.com',
        full_name='Lê Văn C',
        role='accountant',
        is_active=True
    )
    accountant1.set_password('accountant123')
    db.session.add(accountant1)

    accountant2 = User(
        email='accountant2@company.com',
        full_name='Phạm Thị D',
        role='accountant',
        is_active=True
    )
    accountant2.set_password('accountant123')
    db.session.add(accountant2)

    hr1 = User(
        email='hr1@company.com',
        full_name='Hoàng Văn E',
        role='hr',
        is_active=True
    )
    hr1.set_password('hr123')
    db.session.add(hr1)

    hr2 = User(
        email='hr2@company.com',
        full_name='Đỗ Thị F',
        role='hr',
        is_active=True
    )
    hr2.set_password('hr123')
    db.session.add(hr2)

    db.session.commit()
    print(f"Created {User.query.count()} users.")

    # Create sample tasks
    print("Creating sample tasks...")

    # Task 1: Director creates task and assigns to manager
    task1 = Task(
        title='Lập báo cáo tài chính Q4',
        description='Cần hoàn thành báo cáo tài chính quý 4 năm 2024',
        creator_id=director.id,
        due_date=datetime.utcnow().date() + timedelta(days=7),
        status='IN_PROGRESS'
    )
    db.session.add(task1)
    db.session.flush()

    assignment1 = TaskAssignment(
        task_id=task1.id,
        user_id=manager.id,
        assigned_by=director.id,
        accepted=True,
        accepted_at=datetime.utcnow()
    )
    db.session.add(assignment1)

    # Task 2: Manager creates task for accountant group (group assignment)
    task2 = Task(
        title='Kiểm tra sổ sách tháng 11',
        description='Rà soát và đối chiếu sổ sách kế toán tháng 11',
        creator_id=manager.id,
        due_date=datetime.utcnow().date() + timedelta(days=5),
        status='PENDING'
    )
    db.session.add(task2)
    db.session.flush()

    # Create group assignments for all accountants
    for acc in [accountant1, accountant2]:
        assignment = TaskAssignment(
            task_id=task2.id,
            user_id=acc.id,
            assigned_by=manager.id,
            assigned_group='accountant',
            accepted=False,
            seen=False
        )
        db.session.add(assignment)

        # Create notification
        notif = Notification(
            user_id=acc.id,
            type='task_assigned',
            title='Task mới cho nhóm kế toán',
            body=f'{manager.full_name} đã gán task "{task2.title}" cho nhóm kế toán. Vui lòng chấp nhận task.',
            link=f'/tasks/{task2.id}',
            read=False
        )
        db.session.add(notif)

    # Task 3: Accountant creates task for self
    task3 = Task(
        title='Cập nhật bảng lương nhân viên',
        description='Cập nhật thông tin lương tháng 11 vào hệ thống',
        creator_id=accountant1.id,
        due_date=datetime.utcnow().date() + timedelta(days=3),
        status='IN_PROGRESS'
    )
    db.session.add(task3)
    db.session.flush()

    assignment3 = TaskAssignment(
        task_id=task3.id,
        user_id=accountant1.id,
        assigned_by=accountant1.id,
        accepted=True,
        accepted_at=datetime.utcnow()
    )
    db.session.add(assignment3)

    # Task 4: Director creates task for HR group
    task4 = Task(
        title='Tuyển dụng nhân viên mới',
        description='Tuyển 3 nhân viên kinh doanh cho chi nhánh Hà Nội',
        creator_id=director.id,
        due_date=datetime.utcnow().date() + timedelta(days=14),
        status='PENDING'
    )
    db.session.add(task4)
    db.session.flush()

    # Create group assignments for HR
    for hr_user in [hr1, hr2]:
        assignment = TaskAssignment(
            task_id=task4.id,
            user_id=hr_user.id,
            assigned_by=director.id,
            assigned_group='hr',
            accepted=False,
            seen=False
        )
        db.session.add(assignment)

        notif = Notification(
            user_id=hr_user.id,
            type='task_assigned',
            title='Task mới cho nhóm HR',
            body=f'{director.full_name} đã gán task "{task4.title}" cho nhóm HR. Vui lòng chấp nhận task.',
            link=f'/tasks/{task4.id}',
            read=False
        )
        db.session.add(notif)

    # Task 5: Completed task
    task5 = Task(
        title='Họp tổng kết tháng 10',
        description='Họp đánh giá kết quả kinh doanh tháng 10',
        creator_id=director.id,
        due_date=datetime.utcnow().date() - timedelta(days=5),
        status='DONE'
    )
    db.session.add(task5)
    db.session.flush()

    assignment5 = TaskAssignment(
        task_id=task5.id,
        user_id=manager.id,
        assigned_by=director.id,
        accepted=True,
        accepted_at=datetime.utcnow() - timedelta(days=6)
    )
    db.session.add(assignment5)

    db.session.commit()
    print(f"Created {Task.query.count()} tasks.")

    # Create sample notes
    print("Creating sample notes...")

    note1 = Note(
        user_id=accountant1.id,
        title='Ghi chú về hóa đơn tháng 11',
        content='Cần kiểm tra lại hóa đơn số 12345 của khách hàng ABC. Có vẻ như số tiền không khớp với đơn hàng.'
    )
    db.session.add(note1)

    note2 = Note(
        user_id=manager.id,
        title='Kế hoạch Q1 2025',
        content='Mục tiêu doanh thu Q1: 5 tỷ đồng. Cần tăng cường marketing và mở rộng kênh phân phối.'
    )
    db.session.add(note2)

    note3 = Note(
        user_id=hr1.id,
        title='Danh sách ứng viên phỏng vấn',
        content='Tuần tới phỏng vấn 5 ứng viên cho vị trí sale: Nguyễn A, Trần B, Lê C, Phạm D, Hoàng E.'
    )
    db.session.add(note3)

    db.session.commit()
    print(f"Created {Note.query.count()} notes.")

    print("\n" + "=" * 50)
    print("SEED DATA CREATED SUCCESSFULLY!")
    print("=" * 50)
    print("\nDefault accounts:")
    print("-" * 50)
    print("Director:")
    print("  Email: director@company.com")
    print("  Password: director123")
    print("\nManager:")
    print("  Email: manager@company.com")
    print("  Password: manager123")
    print("\nAccountant 1:")
    print("  Email: accountant1@company.com")
    print("  Password: accountant123")
    print("\nAccountant 2:")
    print("  Email: accountant2@company.com")
    print("  Password: accountant123")
    print("\nHR 1:")
    print("  Email: hr1@company.com")
    print("  Password: hr123")
    print("\nHR 2:")
    print("  Email: hr2@company.com")
    print("  Password: hr123")
    print("=" * 50)