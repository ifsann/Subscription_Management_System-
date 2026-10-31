from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from sqlalchemy.exc import IntegrityError
from models import db, Invoice, Payment, Subscription
from auth import login_required, role_required

bp = Blueprint("billing", __name__)
TAX_RATE = 0.18          # TODO: replace with Tax table if time allows
DUE_DAYS = 7

def add_period(d, period):
    return d + {"daily": timedelta(days=1), "weekly": timedelta(weeks=1),
                "monthly": relativedelta(months=1), "yearly": relativedelta(years=1)}[period]

def discount_for(sub, subtotal):
    """Hook for the discounts part. Return the amount to subtract. 0 for now."""
    return 0.0

def generate_invoices(today=None):
    """Bill every Active subscription that is due. Safe to run repeatedly:
    next_billing_date moves forward AND a DB unique constraint blocks duplicates."""
    today = today or date.today()
    created = skipped = 0
    due = Subscription.query.filter(Subscription.status == "Active",
                                    Subscription.next_billing_date <= today).all()
    for s in due:
        # catch up on every missed period, so nothing is skipped
        while s.next_billing_date <= today and (not s.expiry_date or s.next_billing_date <= s.expiry_date):
            start = s.next_billing_date
            end = add_period(start, s.plan.billing_period) - timedelta(days=1)
            subtotal = round(s.plan.price * s.quantity, 2)
            disc = round(min(discount_for(s, subtotal), subtotal), 2)
            tax = round((subtotal - disc) * TAX_RATE, 2)
            inv = Invoice(subscription_id=s.id, customer_id=s.customer_id,
                          period_start=start, period_end=end, subtotal=subtotal,
                          discount=disc, tax=tax, total=round(subtotal - disc + tax, 2),
                          due_date=start + timedelta(days=DUE_DAYS), status="Draft")
            try:
                with db.session.begin_nested():
                    db.session.add(inv); db.session.flush()
                    inv.number = f"INV-{inv.id:05d}"
                created += 1
            except IntegrityError:
                skipped += 1      # already billed for this period
            s.next_billing_date = add_period(start, s.plan.billing_period)
    db.session.commit()
    return created, skipped

def get_invoice_or_403(iid):
    inv = db.get_or_404(Invoice, iid)
    if g.user.role == "customer" and inv.customer_id != g.user.id: abort(403)
    return inv

@bp.route("/")
@login_required
def invoices():
    q = Invoice.query
    if g.user.role == "customer": q = q.filter_by(customer_id=g.user.id)   # own data only
    status = request.args.get("status")
    if status == "Overdue":
        q = q.filter(Invoice.status == "Confirmed", Invoice.due_date < date.today())
    elif status:
        q = q.filter_by(status=status)
    page = request.args.get("page", 1, type=int)
    p = q.order_by(Invoice.id.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("invoices.html", p=p, status=status)

@bp.route("/invoices/<int:iid>")
@login_required
def invoice_detail(iid):
    return render_template("invoice_detail.html", inv=get_invoice_or_403(iid))

@bp.route("/billing/run", methods=["POST"])
@role_required("admin", "staff")
def run_billing():
    c, s = generate_invoices()
    flash(f"Billing run complete: {c} invoice(s) created, {s} already billed.")
    return redirect(url_for("billing.invoices"))

@bp.route("/invoices/<int:iid>/<action>", methods=["POST"])
@role_required("admin", "staff")
def invoice_action(iid, action):
    inv = db.get_or_404(Invoice, iid)
    if action == "confirm" and inv.status == "Draft": inv.status = "Confirmed"
    elif action == "cancel" and inv.status in ("Draft", "Confirmed"): inv.status = "Cancelled"
    else: flash(f"Cannot {action} an invoice that is {inv.status}.")
    db.session.commit()
    return redirect(url_for("billing.invoice_detail", iid=iid))

@bp.route("/invoices/<int:iid>/pay", methods=["POST"])
@role_required("admin", "staff")
def record_payment(iid):
    inv = db.get_or_404(Invoice, iid)
    if inv.status != "Confirmed":
        flash("Only Confirmed invoices can take payments."); return redirect(url_for("billing.invoice_detail", iid=iid))
    try: amt = round(float(request.form["amount"]), 2)
    except ValueError: amt = 0
    if amt <= 0 or amt > inv.balance:
        flash(f"Amount must be between 0.01 and the balance ({inv.balance})."); return redirect(url_for("billing.invoice_detail", iid=iid))
    db.session.add(Payment(invoice_id=inv.id, method=request.form["method"], amount=amt,
                           note=request.form.get("note", "")))
    db.session.flush(); db.session.refresh(inv)
    if inv.balance <= 0: inv.status = "Paid"      # auto Paid when fully covered
    db.session.commit()
    flash("Payment recorded.")
    return redirect(url_for("billing.invoice_detail", iid=iid))
