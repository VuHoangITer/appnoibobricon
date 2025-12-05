from app import create_app, db
from app.models import User

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
        full_name='Vũ Văn Hoàng',
        role='director',
        is_active=True
    )
    director.set_password('123')
    db.session.add(director)

    manager = User(
        email='manager@company.com',
        full_name='Linh',
        role='manager',
        is_active=True
    )
    manager.set_password('manager123')
    db.session.add(manager)

    accountant1 = User(
        email='accountant1@company.com',
        full_name='Chi',
        role='accountant',
        is_active=True
    )
    accountant1.set_password('accountant123')
    db.session.add(accountant1)

    accountant2 = User(
        email='accountant2@company.com',
        full_name='Hạnh',
        role='accountant',
        is_active=True
    )
    accountant2.set_password('accountant123')
    db.session.add(accountant2)

    hr1 = User(
        email='hr1@company.com',
        full_name='Dũng',
        role='hr',
        is_active=True
    )
    hr1.set_password('hr123')
    db.session.add(hr1)

    hr2 = User(
        email='hr2@company.com',
        full_name='Dung',
        role='hr',
        is_active=True
    )
    hr2.set_password('hr123')
    db.session.add(hr2)

    db.session.commit()
    print(f"✓ Created {User.query.count()} users successfully!")

    print("\n" + "=" * 50)
    print("SEED DATA CREATED SUCCESSFULLY!")
    print("=" * 50)
    print("\nDefault accounts:")
    print("-" * 50)
    print("Director:")
    print("  Email: director@company.com")
    print("  Password: 123")
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