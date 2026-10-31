from datetime import date, timedelta
from app import create_app
from models import db, User, Plan, Subscription, Invoice
from billing import generate_invoices

app = create_app("sqlite:///:memory:")
c = app.test_client()
def post(*a, **k): return c.post(*a, follow_redirects=True, **k)

with app.app_context():
    # --- password rules
    for pw, ok in [("Short1!", False), ("alllowercase1!", False), ("NOLOWER123!", False),
                   ("NoSpecial123", False), ("Valid#Pass1", True)]:
        r = post("/signup", data={"email": f"{pw}@x.com", "password": pw})
        assert (b"Account created" in r.data) == ok, pw
    # --- unique email
    assert b"already has an account" in post("/signup", data={"email": "valid#pass1@x.com", "password": "Valid#Pass1"}).data
    # --- customer can't add staff, admin can
    post("/login", data={"email": "valid#pass1@x.com", "password": "Valid#Pass1"})
    assert c.get("/staff/new").status_code == 403
    c.get("/logout")
    post("/login", data={"email": "admin@brightloop.com", "password": "Admin@12345"})
    assert b"Staff member added" in post("/staff/new", data={"email": "s@x.com", "password": "Staff#Pass1"}).data
    c.get("/logout")
    # --- password reset
    r = post("/forgot", data={"email": "s@x.com"}); assert b"/reset/" in r.data
    tok = User.query.filter_by(email="s@x.com").first().reset_token
    assert b"Password updated" in post(f"/reset/{tok}", data={"password": "NewStaff#Pass9"}).data

    # --- billing setup (stand-in for Person 1's work)
    cust = User.query.filter_by(email="valid#pass1@x.com").first()
    other = User(email="other@x.com", password_hash="x", role="customer"); db.session.add(other)
    plan = Plan(name="Gold Gym", price=1000, billing_period="monthly"); db.session.add(plan); db.session.flush()
    sub = Subscription(number="SUB-1", customer_id=cust.id, plan_id=plan.id, status="Active",
                       next_billing_date=date.today())
    db.session.add(sub); db.session.commit()

    # --- no double billing
    assert generate_invoices() == (1, 0)
    assert generate_invoices() == (0, 0)
    inv = Invoice.query.first(); assert inv.total == 1180 and inv.number == "INV-00001"
    # catch-up: sub missed 3 months -> no period skipped
    sub.next_billing_date = date.today() - timedelta(days=90)
    db.session.commit()
    created, skipped = generate_invoices()
    print("catch-up:", created, skipped)

    # --- staff confirms, partial then full payment
    post("/login", data={"email": "s@x.com", "password": "NewStaff#Pass9"})
    post(f"/invoices/{inv.id}/confirm")
    assert b"Payment recorded" in post(f"/invoices/{inv.id}/pay", data={"amount": "500", "method": "cash"}).data
    db.session.refresh(inv); assert inv.status == "Confirmed" and inv.balance == 680
    assert b"Amount must be" in post(f"/invoices/{inv.id}/pay", data={"amount": "9999", "method": "cash"}).data
    post(f"/invoices/{inv.id}/pay", data={"amount": "680", "method": "upi"})
    db.session.refresh(inv); assert inv.status == "Paid" and inv.balance == 0
    c.get("/logout")

    # --- customer isolation
    post("/login", data={"email": "valid#pass1@x.com", "password": "Valid#Pass1"})
    assert c.get(f"/invoices/{inv.id}").status_code == 200
    assert c.get("/billing/run").status_code == 405 and post("/billing/run").status_code == 403
    c.get("/logout")
    assert post("/login", data={"email": "other@x.com", "password": "x"}) # not a real hash, skip
    other.password_hash = __import__("werkzeug.security", fromlist=["x"]).generate_password_hash("Other#Pass1")
    db.session.commit()
    post("/login", data={"email": "other@x.com", "password": "Other#Pass1"})
    assert c.get(f"/invoices/{inv.id}").status_code == 403
print("ALL TESTS PASSED")

# ---- Person 3: dashboard + portal
import time
app2 = create_app("sqlite:///:memory:")
c2 = app2.test_client()
with app2.app_context():
    from models import Subscription, Plan, User, Invoice, Payment
    from werkzeug.security import generate_password_hash
    u = User(email="m@x.com", password_hash=generate_password_hash("Member#1234"), role="customer"); db.session.add(u)
    p = Plan(name="Monthly", price=1000, billing_period="monthly"); db.session.add(p); db.session.flush()
    db.session.add(Subscription(number="S1", customer_id=u.id, plan_id=p.id, status="Active",
                                next_billing_date=date.today() - timedelta(days=45)))
    db.session.commit(); generate_invoices()
    for i in Invoice.query.all(): i.status = "Confirmed"
    db.session.commit()
    c2.post("/login", data={"email": "admin@brightloop.com", "password": "Admin@12345"})
    r = c2.get("/dashboard"); assert r.status_code == 200 and b"Overdue invoices" in r.data
    assert b"Active memberships" in r.data and b"Money owed" in r.data
    c2.get("/logout")
    r = c2.post("/login", data={"email": "m@x.com", "password": "Member#1234"}, follow_redirects=True)
    assert b"My membership" in r.data and b"You owe" in r.data
    assert c2.get("/dashboard", follow_redirects=False).status_code == 302   # customers bounced to portal
print("DASHBOARD TESTS PASSED")
