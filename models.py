# Person 1 owns this file. This is a minimal version so Person 2's code runs.
# Merge: keep Person 1's real models, but keep the UniqueConstraint on Invoice
# and the fields that auth.py / billing.py use.
from datetime import date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="")
    email = db.Column(db.String(120), unique=True, nullable=False)  # DB-level unique
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="customer")  # admin|staff|customer
    reset_token = db.Column(db.String(64), index=True)
    reset_expiry = db.Column(db.DateTime)

class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    billing_period = db.Column(db.String(10), nullable=False)  # daily|weekly|monthly|yearly

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"))
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(12), default="Draft", index=True)  # Draft|Quotation|Confirmed|Active|Closed
    start_date = db.Column(db.Date, default=date.today)
    expiry_date = db.Column(db.Date)
    next_billing_date = db.Column(db.Date, index=True)
    customer = db.relationship("User")
    plan = db.relationship("Plan")

class Invoice(db.Model):
    __table_args__ = (db.UniqueConstraint("subscription_id", "period_start",
                                          name="uq_no_double_billing"),)
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"), index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), default="Draft", index=True)  # Draft|Confirmed|Paid|Cancelled
    subtotal = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    due_date = db.Column(db.Date, index=True)
    subscription = db.relationship("Subscription")
    customer = db.relationship("User")
    payments = db.relationship("Payment", backref="invoice")

    @property
    def paid_amount(self):
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def balance(self):
        return round(self.total - self.paid_amount, 2)

    @property
    def is_overdue(self):
        return self.status == "Confirmed" and self.due_date < date.today()

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), index=True)
    method = db.Column(db.String(20), nullable=False)  # cash|card|upi|bank
    amount = db.Column(db.Float, nullable=False)
    paid_on = db.Column(db.Date, default=date.today)
    note = db.Column(db.String(200), default="")
