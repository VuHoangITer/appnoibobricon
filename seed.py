from app import create_app, db
from app.models import (
    User, Task, TaskAssignment, File, Notification, Note,
    Salary, News, NewsComment, NewsConfirmation, TaskCompletionReport
)
from datetime import datetime, timedelta
import random
import json

app = create_app()


def vn_to_utc(vn_datetime):
    """Convert Vietnam time to UTC (VN = UTC+7)"""
    return vn_datetime - timedelta(hours=7)


with app.app_context():
    print("=" * 60)
    print("🌱 SEEDING SAMPLE DATA FOR TESTING")
    print("=" * 60)

    # Lấy users hiện có
    director = User.query.filter_by(email='director@company.com').first()
    manager = User.query.filter_by(email='manager@company.com').first()
    accountant1 = User.query.filter_by(email='accountant1@company.com').first()
    accountant2 = User.query.filter_by(email='accountant2@company.com').first()
    hr1 = User.query.filter_by(email='hr1@company.com').first()
    hr2 = User.query.filter_by(email='hr2@company.com').first()

    if not all([director, manager, accountant1, accountant2, hr1, hr2]):
        print("❌ ERROR: Users not found! Please run seed_user.py first!")
        exit(1)

    all_users = [director, manager, accountant1, accountant2, hr1, hr2]
    employees = [accountant1, accountant2, hr1, hr2]

    print(f"\n✓ Found {len(all_users)} users")

    # ========================================
    # 1. TASKS - Nhiệm vụ với nhiều trạng thái
    # ========================================
    print("\n📋 Creating Tasks...")

    now = datetime.utcnow()
    tasks_data = [
        # DONE - Đúng hạn
        {
            'title': 'Báo cáo doanh thu tháng 10',
            'description': 'Tổng hợp báo cáo doanh thu chi tiết tháng 10/2024',
            'creator': director,
            'assignees': [accountant1],
            'status': 'DONE',
            'due_date': now - timedelta(days=10),
            'is_urgent': False,
            'is_important': True,
            'completed_overdue': False,
            'rating': 'good'
        },
        {
            'title': 'Cập nhật hợp đồng lao động mới',
            'description': 'Review và cập nhật hợp đồng theo quy định mới',
            'creator': manager,
            'assignees': [hr1],
            'status': 'DONE',
            'due_date': now - timedelta(days=7),
            'is_urgent': False,
            'is_important': True,
            'completed_overdue': False,
            'rating': 'good'
        },
        # DONE - Quá hạn
        {
            'title': 'Kiểm tra sổ sách kế toán Q3',
            'description': 'Đối chiếu và kiểm tra toàn bộ sổ sách quý 3',
            'creator': director,
            'assignees': [accountant2],
            'status': 'DONE',
            'due_date': now - timedelta(days=15),
            'is_urgent': True,
            'is_important': True,
            'completed_overdue': True,
            'rating': 'bad'
        },
        {
            'title': 'Chuẩn bị tài liệu đào tạo nhân viên mới',
            'description': 'Soạn tài liệu onboarding cho nhân viên mới',
            'creator': manager,
            'assignees': [hr2],
            'status': 'DONE',
            'due_date': now - timedelta(days=5),
            'is_urgent': False,
            'is_important': False,
            'completed_overdue': True,
            'rating': None  # Chưa đánh giá
        },
        # IN_PROGRESS - Đúng hạn
        {
            'title': 'Lập kế hoạch tuyển dụng Q1/2025',
            'description': 'Xây dựng kế hoạch tuyển dụng cho quý 1 năm 2025',
            'creator': director,
            'assignees': [hr1],
            'status': 'IN_PROGRESS',
            'due_date': now + timedelta(days=15),
            'is_urgent': False,
            'is_important': True,
            'completed_overdue': False
        },
        {
            'title': 'Thanh toán hóa đơn nhà cung cấp',
            'description': 'Xử lý thanh toán các hóa đơn tháng 11',
            'creator': manager,
            'assignees': [accountant1],
            'status': 'IN_PROGRESS',
            'due_date': now + timedelta(days=5),
            'is_urgent': True,
            'is_important': True,
            'completed_overdue': False
        },
        # IN_PROGRESS - Quá hạn (!)
        {
            'title': 'Đối chiếu công nợ khách hàng',
            'description': 'Kiểm tra và đối chiếu công nợ với các khách hàng lớn',
            'creator': director,
            'assignees': [accountant2],
            'status': 'IN_PROGRESS',
            'due_date': now - timedelta(days=2),
            'is_urgent': True,
            'is_important': True,
            'completed_overdue': False
        },
        # PENDING - Đúng hạn
        {
            'title': 'Cập nhật chính sách nghỉ phép',
            'description': 'Review và cập nhật chính sách nghỉ phép theo luật mới',
            'creator': manager,
            'assignees': [hr2],
            'status': 'PENDING',
            'due_date': now + timedelta(days=20),
            'is_urgent': False,
            'is_important': True,
            'completed_overdue': False
        },
        {
            'title': 'Lập báo cáo thuế tháng 11',
            'description': 'Chuẩn bị và nộp báo cáo thuế tháng 11/2024',
            'creator': director,
            'assignees': [accountant1, accountant2],
            'status': 'PENDING',
            'due_date': now + timedelta(days=10),
            'is_urgent': True,
            'is_important': True,
            'completed_overdue': False,
            'is_recurring': True
        },
        # PENDING - Quá hạn (!)
        {
            'title': 'Tổ chức sự kiện team building',
            'description': 'Lên kế hoạch và tổ chức sự kiện team building cuối năm',
            'creator': manager,
            'assignees': [hr1, hr2],
            'status': 'PENDING',
            'due_date': now - timedelta(days=3),
            'is_urgent': True,
            'is_important': False,
            'completed_overdue': False
        },
        {
            'title': 'Kiểm tra hệ thống kế toán',
            'description': 'Audit hệ thống và quy trình kế toán hiện tại',
            'creator': director,
            'assignees': [accountant1],
            'status': 'PENDING',
            'due_date': now - timedelta(days=1),
            'is_urgent': True,
            'is_important': True,
            'completed_overdue': False
        },
        # Tasks không gán cho ai (Director tự làm)
        {
            'title': 'Họp với Ban Giám Đốc',
            'description': 'Cuộc họp chiến lược quý 4',
            'creator': director,
            'assignees': [director],
            'status': 'IN_PROGRESS',
            'due_date': now + timedelta(days=2),
            'is_urgent': True,
            'is_important': True,
            'completed_overdue': False
        },
        # Tasks của Manager tự giao cho mình
        {
            'title': 'Review hiệu suất phòng ban',
            'description': 'Đánh giá hiệu suất làm việc của các thành viên',
            'creator': manager,
            'assignees': [manager],
            'status': 'PENDING',
            'due_date': now + timedelta(days=7),
            'is_urgent': False,
            'is_important': True,
            'completed_overdue': False
        },
    ]

    created_tasks = []
    for task_data in tasks_data:
        task = Task(
            title=task_data['title'],
            description=task_data['description'],
            creator_id=task_data['creator'].id,
            status=task_data['status'],
            due_date=task_data['due_date'],
            is_urgent=task_data.get('is_urgent', False),
            is_important=task_data.get('is_important', False),
            is_recurring=task_data.get('is_recurring', False),
            completed_overdue=task_data.get('completed_overdue', False),
            created_at=now - timedelta(days=random.randint(1, 30))
        )

        # Nếu DONE thì set updated_at
        if task.status == 'DONE':
            task.updated_at = task.due_date + timedelta(hours=random.randint(1, 48))

            # Nếu có rating
            if task_data.get('rating'):
                task.performance_rating = task_data['rating']
                task.rated_by = task_data['creator'].id
                task.rated_at = task.updated_at + timedelta(hours=2)

        db.session.add(task)
        db.session.flush()

        # Tạo assignments
        for assignee in task_data['assignees']:
            assignment = TaskAssignment(
                task_id=task.id,
                user_id=assignee.id,
                assigned_by=task_data['creator'].id,
                accepted=True,
                accepted_at=task.created_at + timedelta(hours=1),
                seen=True,
                created_at=task.created_at
            )
            db.session.add(assignment)

            # Nếu task DONE, tạo completion report
            if task.status == 'DONE':
                completion_time = int((task.updated_at - task.created_at).total_seconds() / 60)
                report = TaskCompletionReport(
                    task_id=task.id,
                    completed_by=assignee.id,
                    completion_note=f'Đã hoàn thành {task.title}',
                    completed_at=task.updated_at,
                    was_overdue=task.completed_overdue,
                    completion_time=completion_time
                )
                db.session.add(report)

        created_tasks.append(task)

    db.session.commit()
    print(f"✓ Created {len(created_tasks)} tasks with assignments and reports")

    # ========================================
    # 2. NOTES - Ghi chú cá nhân
    # ========================================
    print("\n📝 Creating Notes...")

    notes_data = [
        {'user': director, 'title': 'Ý tưởng mở rộng thị trường',
         'content': 'Nghiên cứu thị trường miền Bắc, tập trung vào Hà Nội và Hải Phòng.'},
        {'user': director, 'title': 'Danh sách đối tác tiềm năng',
         'content': 'Công ty A, Công ty B, Công ty C cần liên hệ trong tháng 12.'},
        {'user': manager, 'title': 'Cải tiến quy trình làm việc',
         'content': 'Áp dụng Agile/Scrum cho team. Họp daily standup 9h sáng.'},
        {'user': manager, 'title': 'Checklist tháng 11',
         'content': '- Review KPI\n- Đánh giá nhân viên\n- Lập kế hoạch tháng 12'},
        {'user': accountant1, 'title': 'Lưu ý về thuế TNCN',
         'content': 'Kiểm tra lại mức giảm trừ gia cảnh theo quy định mới.'},
        {'user': hr1, 'title': 'Danh sách ứng viên phỏng vấn',
         'content': 'Tuần sau: 3 ứng viên vị trí Developer, 2 ứng viên Marketing.'},
    ]

    for note_data in notes_data:
        note = Note(
            user_id=note_data['user'].id,
            title=note_data['title'],
            content=note_data['content'],
            created_at=now - timedelta(days=random.randint(1, 15)),
            updated_at=now - timedelta(days=random.randint(0, 10))
        )
        db.session.add(note)

    db.session.commit()
    print(f"✓ Created {len(notes_data)} notes")

    # ========================================
    # 3. NEWS - Tin tức công ty
    # ========================================
    print("\n📰 Creating News Posts...")

    news_data = [
        {
            'title': '🎉 Công ty đạt doanh thu kỷ lục tháng 10/2024',
            'content': '''<p>Chúng tôi vui mừng thông báo rằng công ty đã đạt được doanh thu kỷ lục trong tháng 10/2024 với mức tăng trưởng 45% so với cùng kỳ năm ngoái!</p>
            <p>Đây là thành quả của sự nỗ lực không ngừng nghỉ từ tất cả các phòng ban. Ban lãnh đạo xin gửi lời cảm ơn chân thành đến toàn thể nhân viên.</p>
            <p><strong>Phần thưởng:</strong> Tất cả nhân viên sẽ nhận được bonus 1 tháng lương!</p>''',
            'author': director
        },
        {
            'title': '🏢 Chính sách làm việc từ xa (WFH) mới',
            'content': '''<p>Kể từ ngày 01/12/2024, công ty sẽ áp dụng chính sách WFH linh hoạt:</p>
            <ul>
                <li>Nhân viên được làm việc từ xa tối đa 2 ngày/tuần</li>
                <li>Cần đăng ký trước 1 ngày với quản lý trực tiếp</li>
                <li>Phải có mặt tại văn phòng vào các ngày họp quan trọng</li>
            </ul>
            <p>Mọi thắc mắc vui lòng liên hệ phòng Nhân sự.</p>''',
            'author': manager
        },
        {
            'title': '⚠️ Bảo trì hệ thống ngày 25/11/2024',
            'content': '''<p><strong>THÔNG BÁO QUAN TRỌNG:</strong></p>
            <p>Hệ thống sẽ được bảo trì nâng cấp vào:</p>
            <ul>
                <li>📅 Ngày: 25/11/2024</li>
                <li>⏰ Thời gian: 22:00 - 02:00 sáng ngày 26/11</li>
                <li>🚫 Không thể truy cập: Email, ERP, File Server</li>
            </ul>
            <p>Vui lòng hoàn thành công việc trước 22:00. Xin lỗi vì sự bất tiện này!</p>''',
            'author': director
        }
    ]

    created_news = []
    for idx, news_item in enumerate(news_data):
        news = News(
            title=news_item['title'],
            content=news_item['content'],
            author_id=news_item['author'].id,
            created_at=now - timedelta(days=len(news_data) - idx),
            updated_at=now - timedelta(days=len(news_data) - idx)
        )
        db.session.add(news)
        db.session.flush()

        # Một số người đã confirm đọc
        for user in random.sample(all_users, random.randint(2, 4)):
            confirmation = NewsConfirmation(
                news_id=news.id,
                user_id=user.id,
                confirmed_at=news.created_at + timedelta(hours=random.randint(1, 24))
            )
            db.session.add(confirmation)

        # Một số comments
        if random.random() > 0.5:
            comment = NewsComment(
                news_id=news.id,
                user_id=random.choice(employees).id,
                content=random.choice([
                    'Thông tin rất hữu ích, cảm ơn Ban lãnh đạo!',
                    'Đã đọc và nắm được nội dung.',
                    'Chính sách này rất tốt cho nhân viên!',
                    'Cảm ơn công ty đã quan tâm đến phúc lợi nhân viên.'
                ]),
                created_at=news.created_at + timedelta(hours=random.randint(2, 48))
            )
            db.session.add(comment)

        created_news.append(news)

    db.session.commit()
    print(f"✓ Created {len(created_news)} news posts with confirmations and comments")

    # ========================================
    # 4. SALARIES - Bảng lương
    # ========================================
    print("\n💰 Creating Salary Records...")

    # Tháng hiện tại và tháng trước
    current_month = now.strftime('%Y-%m')
    last_month = (now - timedelta(days=30)).strftime('%Y-%m')

    salary_data = [
        # Tháng trước
        {
            'employee': 'Chi (Kế toán)',
            'month': last_month,
            'work_days': 22,
            'actual_days': 22,
            'basic_salary': 15000000,
            'responsibility_salary': 3000000,
            'bonuses': [
                {'description': 'Thưởng hiệu suất', 'amount': 2000000},
                {'description': 'Thưởng chuyên cần', 'amount': 500000}
            ],
            'deductions': [
                {'description': 'Bảo hiểm xã hội', 'amount': 1350000},
                {'description': 'Bảo hiểm y tế', 'amount': 225000}
            ]
        },
        {
            'employee': 'Hạnh (Kế toán)',
            'month': last_month,
            'work_days': 22,
            'actual_days': 21,  # Nghỉ 1 ngày
            'basic_salary': 14000000,
            'responsibility_salary': 2500000,
            'bonuses': [
                {'description': 'Thưởng hiệu suất', 'amount': 1500000}
            ],
            'deductions': [
                {'description': 'Bảo hiểm xã hội', 'amount': 1260000},
                {'description': 'Bảo hiểm y tế', 'amount': 210000},
                {'description': 'Nghỉ không phép', 'amount': 750000}
            ]
        },
        {
            'employee': 'Dũng (Nhân sự)',
            'month': last_month,
            'work_days': 22,
            'actual_days': 22,
            'basic_salary': 12000000,
            'responsibility_salary': 2000000,
            'bonuses': [
                {'description': 'Thưởng tuyển dụng', 'amount': 3000000},
                {'description': 'Thưởng chuyên cần', 'amount': 500000}
            ],
            'deductions': [
                {'description': 'Bảo hiểm xã hội', 'amount': 1080000},
                {'description': 'Bảo hiểm y tế', 'amount': 180000}
            ]
        },
        {
            'employee': 'Dung (Nhân sự)',
            'month': last_month,
            'work_days': 22,
            'actual_days': 20,  # Nghỉ 2 ngày
            'basic_salary': 11000000,
            'responsibility_salary': 1800000,
            'bonuses': [
                {'description': 'Thưởng hiệu suất', 'amount': 1000000}
            ],
            'deductions': [
                {'description': 'Bảo hiểm xã hội', 'amount': 990000},
                {'description': 'Bảo hiểm y tế', 'amount': 165000},
                {'description': 'Nghỉ không phép', 'amount': 1200000}
            ]
        },
        # Tháng hiện tại
        {
            'employee': 'Chi (Kế toán)',
            'month': current_month,
            'work_days': 22,
            'actual_days': 15,  # Đang giữa tháng
            'basic_salary': 15000000,
            'responsibility_salary': 3000000,
            'bonuses': [],
            'deductions': [
                {'description': 'Bảo hiểm xã hội', 'amount': 1350000},
                {'description': 'Bảo hiểm y tế', 'amount': 225000}
            ]
        },
        {
            'employee': 'Linh (Trưởng phòng)',
            'month': last_month,
            'work_days': 22,
            'actual_days': 22,
            'basic_salary': 25000000,
            'responsibility_salary': 8000000,
            'bonuses': [
                {'description': 'Thưởng quản lý', 'amount': 5000000},
                {'description': 'Thưởng hiệu suất', 'amount': 3000000}
            ],
            'deductions': [
                {'description': 'Bảo hiểm xã hội', 'amount': 2250000},
                {'description': 'Bảo hiểm y tế', 'amount': 375000},
                {'description': 'Thuế TNCN', 'amount': 4500000}
            ]
        }
    ]

    for salary_info in salary_data:
        salary = Salary(
            employee_name=salary_info['employee'],
            month=salary_info['month'],
            work_days_in_month=salary_info['work_days'],
            actual_work_days=salary_info['actual_days'],
            basic_salary=salary_info['basic_salary'],
            responsibility_salary=salary_info['responsibility_salary'],
            created_by=director.id,
            created_at=now - timedelta(days=random.randint(5, 20))
        )

        salary.set_capacity_bonuses(salary_info['bonuses'])
        salary.set_deductions(salary_info['deductions'])
        salary.calculate()

        db.session.add(salary)

    db.session.commit()
    print(f"✓ Created {len(salary_data)} salary records")

    # ========================================
    # 5. NOTIFICATIONS - Thông báo
    # ========================================
    print("\n🔔 Creating Notifications...")

    # Tạo một số thông báo mẫu
    notifications_data = [
        {
            'user': accountant1,
            'type': 'task_assigned',
            'title': 'Nhiệm vụ mới được giao',
            'body': f'{director.full_name} đã giao nhiệm vụ "Lập báo cáo thuế tháng 11" cho bạn.',
            'link': '/tasks/9',
            'read': False
        },
        {
            'user': hr1,
            'type': 'task_completed',
            'title': '✅ Nhiệm vụ hoàn thành ĐÚNG HẠN',
            'body': 'Bạn đã hoàn thành: Cập nhật hợp đồng lao động mới',
            'link': '/tasks/2',
            'read': True
        },
        {
            'user': accountant2,
            'type': 'task_rated',
            'title': 'Đánh giá nhiệm vụ của bạn',
            'body': f'{director.full_name} đã đánh giá nhiệm vụ "Kiểm tra sổ sách kế toán Q3" là CẦN CẢI THIỆN 👎',
            'link': '/tasks/3',
            'read': False
        },
        {
            'user': manager,
            'type': 'task_needs_rating',
            'title': '🌟 Cần đánh giá hiệu suất',
            'body': f'Nhiệm vụ "Chuẩn bị tài liệu đào tạo nhân viên mới" đã hoàn thành bởi {hr2.full_name}. Vui lòng đánh giá!',
            'link': '/tasks/4',
            'read': False
        },
        {
            'user': director,
            'type': 'news',
            'title': 'Bài đăng mới: Chính sách WFH',
            'body': f'{manager.full_name} đã đăng tin tức mới.',
            'link': '/news/2',
            'read': True
        }
    ]

    for notif_data in notifications_data:
        notification = Notification(
            user_id=notif_data['user'].id,
            type=notif_data['type'],
            title=notif_data['title'],
            body=notif_data['body'],
            link=notif_data['link'],
            read=notif_data['read'],
            created_at=now - timedelta(hours=random.randint(1, 72))
        )
        db.session.add(notification)

    db.session.commit()
    print(f"✓ Created {len(notifications_data)} notifications")

    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 60)
    print("✅ SAMPLE DATA SEEDED SUCCESSFULLY!")
    print("=" * 60)

    print("\n📊 SUMMARY:")
    print("-" * 60)
    print(f"Tasks:          {Task.query.count()}")
    print(f"  - DONE:       {Task.query.filter_by(status='DONE').count()}")
    print(f"  - IN_PROGRESS: {Task.query.filter_by(status='IN_PROGRESS').count()}")
    print(f"  - PENDING:    {Task.query.filter_by(status='PENDING').count()}")
    print(
        f"  - Overdue:    {Task.query.filter(Task.due_date < now, Task.status.in_(['PENDING', 'IN_PROGRESS'])).count()}")
    print(f"\nNotes:          {Note.query.count()}")
    print(f"News Posts:     {News.query.count()}")
    print(f"Salaries:       {Salary.query.count()}")
    print(f"Notifications:  {Notification.query.count()}")
    print("-" * 60)

    print("\n🎯 TESTING SCENARIOS:")
    print("-" * 60)
    print("✓ Tasks với nhiều trạng thái (DONE, IN_PROGRESS, PENDING)")
    print("✓ Tasks quá hạn và đúng hạn")
    print("✓ Tasks có đánh giá TỐT/KÉM và chưa đánh giá")
    print("✓ Tasks với các thẻ: Khẩn cấp, Quan trọng, Lặp lại")
    print("✓ Tasks giao cho cá nhân và nhóm")
    print("✓ Ghi chú cá nhân cho từng user")
    print("✓ Tin tức với xác nhận đọc và bình luận")
    print("✓ Bảng lương nhiều tháng với bonus/deduction")
    print("✓ Thông báo đã đọc và chưa đọc")
    print("-" * 60)

    print("\n💡 NEXT STEPS:")
    print("-" * 60)
    print("1. Login với bất kỳ tài khoản nào (đã có trong seed_user.py)")
    print("2. Kiểm tra Dashboard để xem thống kê và thông báo thông minh")
    print("3. Test các tính năng:")
    print("   - Kanban Board: Kéo thả tasks")
    print("   - Đánh giá hiệu suất: Rate tasks đã hoàn thành")
    print("   - Filter & Search: Lọc theo user, tags, dates")
    print("   - Notifications: Xem thông báo")
    print("   - News: Đọc tin, comment, confirm")
    print("   - Salaries: Xem bảng lương, tạo link chia sẻ")
    print("   - Notes: Tạo/sửa/xóa ghi chú")
    print("-" * 60)
    print("\n🚀 Happy Testing!")
    print("=" * 60)