from datetime import date
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, g
from sqlalchemy import func
from models import db, Subscription, Invoice, Payment
from auth import login_required, role_required

bp = Blueprint("dashboard", __name__)

@bp.app_template_filter("money")
def money(v):
    return "₹{:,.2f}".format(v or 0)

@bp.app_template_filter("money0")
def money0(v):
    return "₹{:,.0f}".format(v or 0)

def _sum(q):
    return q.scalar() or 0

@bp.route("/dashboard")
@login_required
def home():
    if g.user.role == "customer":
        return redirect(url_for("dashboard.account"))
    today = date.today()
    d_from = request.args.get("from") or today.replace(day=1).isoformat()
    d_to = request.args.get("to") or today.isoformat()

    # All four numbers are SQL aggregates, no Python loops over rows.
    active = Subscription.query.filter_by(status="Active").count()
    revenue = _sum(db.session.query(func.sum(Payment.amount))
                   .filter(Payment.paid_on >= d_from, Payment.paid_on <= d_to))
    conf_total = _sum(db.session.query(func.sum(Invoice.total)).filter(Invoice.status == "Confirmed"))
    conf_paid = _sum(db.session.query(func.sum(Payment.amount)).join(Invoice)
                     .filter(Invoice.status == "Confirmed"))
    owed = round(conf_total - conf_paid, 2)
    overdue_q = Invoice.query.filter(Invoice.status == "Confirmed", Invoice.due_date < today)
    overdue_n = overdue_q.count()

    # revenue for the last 6 months (SQLite strftime; on Postgres use to_char)
    first = today.replace(day=1) - relativedelta(months=5)
    rows = dict(db.session.query(func.strftime("%Y-%m", Payment.paid_on), func.sum(Payment.amount))
                .filter(Payment.paid_on >= first).group_by(func.strftime("%Y-%m", Payment.paid_on)).all())
    months = []
    for i in range(6):
        m = first + relativedelta(months=i)
        months.append((m.strftime("%b"), rows.get(m.strftime("%Y-%m"), 0)))
    top = max([v for _, v in months] + [1])

    overdue_list = overdue_q.order_by(Invoice.due_date).limit(8).all()
    recent = Payment.query.order_by(Payment.id.desc()).limit(8).all()
    return render_template("dashboard.html", active=active, revenue=revenue, owed=owed,
                           overdue_n=overdue_n, months=months, top=top, d_from=d_from, d_to=d_to,
                           overdue_list=overdue_list, recent=recent, today=today)

@bp.route("/account")
@role_required("customer")
def account():
    subs = Subscription.query.filter_by(customer_id=g.user.id).order_by(Subscription.id.desc()).all()
    invs = Invoice.query.filter_by(customer_id=g.user.id).order_by(Invoice.id.desc()).limit(10).all()
    due = [i for i in Invoice.query.filter_by(customer_id=g.user.id, status="Confirmed").all()]
    balance = round(sum(i.balance for i in due), 2)
    overdue = sum(1 for i in due if i.is_overdue)
    return render_template("account.html", subs=subs, invs=invs, balance=balance, overdue=overdue)
