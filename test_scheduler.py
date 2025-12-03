from run import app
from app.scheduler import create_recurring_tasks
from datetime import datetime

print(f"🕐 Giờ hiện tại: {datetime.now().strftime('%A %d/%m/%Y %H:%M')}")
print(f"📅 Thứ hiện tại: {datetime.now().weekday()} (0=Thứ 2, 1=Thứ 3, 6=Chủ nhật)")
print()

# Chạy scheduler
create_recurring_tasks(app)

print()
print("=" * 50)

# Kiểm tra kết quả
from app.models import Task

with app.app_context():
    # Tìm task gốc (task vừa tạo)
    parent = Task.query.filter_by(recurrence_type='weekly').first()

    if parent:
        print(f"✅ Task gốc tìm thấy:")
        print(f"   ID: {parent.id}")
        print(f"   Tiêu đề: {parent.title}")
        print(f"   Ngày: {parent.recurrence_weekdays}")
        print(f"   Giờ: {parent.recurrence_time}")

        # Tìm task con (task được tự động tạo)
        children = Task.query.filter_by(parent_task_id=parent.id).all()

        if children:
            print(f"\n🎉 THÀNH CÔNG! Đã tạo {len(children)} task con:")
            for child in children:
                print(f"   - ID {child.id}: {child.title}")
                print(f"     Hạn: {child.due_date}")
        else:
            print(f"\n⚠️ Chưa tạo task con.")
            print(f"Lý do có thể:")
            print(f"   - Hôm nay không phải Thứ 2 hoặc Thứ 3")
            print(f"   - Chưa đến giờ (task set {parent.recurrence_time})")
    else:
        print("❌ Không tìm thấy task weekly nào!")
        print("Vui lòng tạo task qua web trước!")