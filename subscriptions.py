# Plans, subscriptions, lines and discounts: staff pages. Server checks roles.
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db, User, Plan, Subscription, SubscriptionLine, Discount
from auth import role_required

bp = Blueprint("subs", __name__)
NEXT = {"Draft": "Quotation", "Quotation": "Confirmed",
        "Confirmed": "Active", "Active": "Closed"}
PERIODS = ["daily", "weekly", "monthly", "yearly"]

def num(field, default=None, cast=float):
    try: return cast(request.form[field])
    except (KeyError, ValueError): return default

@bp.route("/plans", methods=["GET", "POST"])
@role_required("admin", "staff")
def plans():
    if request.method == "POST":
        if g.user.role != "admin": flash("Only admin can add plans."); return redirect(url_for("subs.plans"))
        price, mq = num("price"), num("min_qty", 1, int)
        name, per = request.form.get("name", "").strip(), request.form.get("billing_period")
        if not name or price is None or price < 0 or per not in PERIODS or mq < 1:
            flash("Check the plan: name, price (0 or more), period, min quantity (1 or more).")
        else:
            db.session.add(Plan(name=name, price=price, billing_period=per, min_qty=mq))
            db.session.commit(); flash("Plan added.")
        return redirect(url_for("subs.plans"))
    return render_template("plans.html", plans=Plan.query.order_by(Plan.id).all(), periods=PERIODS)

@bp.route("/subscriptions")
@role_required("admin", "staff")
def subscriptions():
    q = Subscription.query
    status = request.args.get("status")
    if status: q = q.filter_by(status=status)
    p = q.order_by(Subscription.id.desc()).paginate(page=request.args.get("page", 1, type=int),
                                                     per_page=25, error_out=False)
    return render_template("subscriptions.html", p=p, status=status,
                           plans=Plan.query.all(), statuses=list(NEXT) + ["Closed"])

@bp.route("/subscriptions/new", methods=["POST"])
@role_required("admin", "staff")
def new_subscription():
    cust = User.query.filter_by(email=request.form.get("email", "").strip().lower(),
                                role="customer").first()
    plan = db.session.get(Plan, num("plan_id", 0, int))
    qty = num("quantity", 1, int)
    if not cust: flash("No customer with that email.")
    elif not plan: flash("Pick a plan.")
    elif qty < (plan.min_qty or 1): flash(f"Minimum quantity for this plan is {plan.min_qty}.")
    else:
        s = Subscription(customer_id=cust.id, plan_id=plan.id, quantity=qty,
                         start_date=date.today(), expiry_date=date.today() + timedelta(days=365))
        db.session.add(s); db.session.flush()
        s.number = f"SUB{s.id:04d}"
        db.session.commit(); flash(f"Subscription {s.number} created as Draft.")
    return redirect(url_for("subs.subscriptions"))

@bp.route("/subscriptions/<int:sid>/advance", methods=["POST"])
@role_required("admin", "staff")
def advance(sid):
    s = db.get_or_404(Subscription, sid)
    if s.status not in NEXT: flash("Already closed.")
    else:
        s.status = NEXT[s.status]
        if s.status == "Active" and not s.next_billing_date:
            s.next_billing_date = s.start_date or date.today()   # billing run needs this
        db.session.commit(); flash(f"{s.number} is now {s.status}.")
    return redirect(url_for("subs.subscriptions"))

@bp.route("/subscriptions/<int:sid>/lines", methods=["POST"])
@role_required("admin", "staff")
def add_line(sid):
    s = db.get_or_404(Subscription, sid)
    qty, price, tax = num("quantity", 0, int), num("unit_price"), num("tax_percent", 0)
    name = request.form.get("product_name", "").strip()
    if not name or qty < 1 or price is None or price < 0 or not 0 <= tax <= 100:
        flash("Check the line: name, quantity 1+, price 0+, tax 0-100.")
    else:
        db.session.add(SubscriptionLine(subscription_id=s.id, product_name=name,
                                        quantity=qty, unit_price=price, tax_percent=tax))
        db.session.commit(); flash(f"Line added to {s.number}.")
    return redirect(url_for("subs.subscriptions"))

@bp.route("/discounts", methods=["GET", "POST"])
@role_required("admin")
def discounts():
    if request.method == "POST":
        try:
            kind, val = request.form["kind"], float(request.form["value"])
            start = date.fromisoformat(request.form["start_date"])
            end = date.fromisoformat(request.form["end_date"])
            limit = request.form.get("usage_limit")
            limit = int(limit) if limit else None
            if kind not in ("percent", "fixed") or val <= 0 or end < start or (kind == "percent" and val > 100):
                raise ValueError
            db.session.add(Discount(name=request.form["name"].strip(), kind=kind, value=val,
                                    min_amount=num("min_amount", 0), start_date=start,
                                    end_date=end, usage_limit=limit))
            db.session.commit(); flash("Discount added.")
        except (KeyError, ValueError):
            flash("Check the discount: value above 0 (max 100 for percent), valid dates, end after start.")
        return redirect(url_for("subs.discounts"))
    return render_template("discounts.html", ds=Discount.query.order_by(Discount.id.desc()).all(),
                           today=date.today())
