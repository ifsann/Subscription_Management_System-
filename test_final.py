from datetime import date
from app import create_app
from models import db, User, Invoice
from billing import generate_invoices
from werkzeug.security import generate_password_hash
app = create_app("sqlite:///:memory:")
c = app.test_client()
P = lambda *a, **k: c.post(*a, follow_redirects=True, **k)
with app.app_context():
    db.session.add(User(email="m@x.com", password_hash=generate_password_hash("Member#1234"), role="customer")); db.session.commit()
    P("/login", data={"email": "admin@brightloop.com", "password": "Admin@12345"})
    for url in ["/dashboard", "/plans", "/subscriptions", "/discounts", "/"]:
        assert c.get(url).status_code == 200, url
    assert b"Plan added" in P("/plans", data={"name": "Gold", "price": "500", "billing_period": "monthly", "min_qty": "1"}).data
    assert b"Check the plan" in P("/plans", data={"name": "", "price": "-1", "billing_period": "monthly", "min_qty": "1"}).data
    assert b"created as Draft" in P("/subscriptions/new", data={"email": "m@x.com", "plan_id": "1", "quantity": "1"}).data
    assert b"No customer" in P("/subscriptions/new", data={"email": "no@x.com", "plan_id": "1", "quantity": "1"}).data
    for _ in range(3): P("/subscriptions/1/advance")
    assert b"Line added" in P("/subscriptions/1/lines", data={"product_name": "Seats", "quantity": "3", "unit_price": "500", "tax_percent": "18"}).data
    assert b"Discount added" in P("/discounts", data={"name": "Bulk", "kind": "percent", "value": "10", "min_amount": "1000", "start_date": str(date.today()), "end_date": "2099-01-01", "usage_limit": "5"}).data
    assert b"Check the discount" in P("/discounts", data={"name": "Bad", "kind": "percent", "value": "150", "start_date": str(date.today()), "end_date": "2099-01-01"}).data
    assert b"1 invoice(s) created" in P("/billing/run").data
    assert b"0 invoice(s) created" in P("/billing/run").data
    inv = Invoice.query.first(); assert inv.total == 1593.0, inv.total
    c.get("/logout")
    P("/login", data={"email": "m@x.com", "password": "Member#1234"})
    for url in ["/plans", "/subscriptions", "/discounts"]:
        assert c.get(url).status_code == 403, url
    assert P("/subscriptions/1/advance").status_code == 403
    assert P("/plans", data={"name": "x", "price": "1", "billing_period": "daily"}).status_code == 403
    assert b"My membership" in c.get("/account").data
print("FINAL OK")
