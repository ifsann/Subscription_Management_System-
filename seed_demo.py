"""Fills the database with demo data so the dashboard looks real.
Run once:  python seed_demo.py     (delete brightloop.db / instance/ first to reset)"""
import random
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from app import create_app
from models import db, User, Plan, Subscription, Invoice, Payment
from billing import generate_invoices

random.seed(7)
app = create_app()
with app.app_context():
    if Plan.query.first(): raise SystemExit("Already seeded.")
    plans = [Plan(name="Weekly Pass", price=300, billing_period="weekly"),
             Plan(name="Monthly Membership", price=1200, billing_period="monthly"),
             Plan(name="Annual Membership", price=12000, billing_period="yearly")]
    db.session.add_all(plans); db.session.flush()
    pw = generate_password_hash("Member#1234")
    users = []
    for n in range(1, 301):
        users.append(User(name=f"Member {n}", email=f"member{n}@example.com", password_hash=pw, role="customer"))
    db.session.add_all(users); db.session.flush()
    today = date.today()
    for n, u in enumerate(users, 1):
        plan = random.choices(plans, weights=[5, 80, 15])[0]
        start = today - timedelta(days=random.randint(0, 150))
        db.session.add(Subscription(number=f"SUB-{n:05d}", customer_id=u.id, plan_id=plan.id,
                                    quantity=1, status=random.choices(["Active", "Closed", "Draft"], [85, 10, 5])[0],
                                    start_date=start, next_billing_date=start))
    db.session.commit()
    print("invoices created:", generate_invoices())
    for inv in Invoice.query.all():
        inv.status = "Confirmed"
        r = random.random()
        paid_on = min(inv.period_start + timedelta(days=random.randint(0, 6)), today)
        old = (today - inv.period_start).days > 30
        if r < (0.93 if old else 0.55):
            db.session.add(Payment(invoice_id=inv.id, method=random.choice(["cash", "card", "upi"]), amount=inv.total, paid_on=paid_on))
            inv.status = "Paid"
        elif r < (0.97 if old else 0.70):
            db.session.add(Payment(invoice_id=inv.id, method="cash", amount=round(inv.total / 2, 2), paid_on=paid_on, note="part payment"))
    db.session.commit()
    print("done. members log in as member1@example.com / Member#1234")
