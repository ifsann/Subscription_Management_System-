import re, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from models import db, User

bp = Blueprint("auth", __name__)

def password_error(pw):
    """Brief rules: MORE than 8 chars, upper, lower, special."""
    if len(pw) <= 8: return "Password must be more than 8 characters."
    if not re.search(r"[A-Z]", pw): return "Password needs an uppercase letter."
    if not re.search(r"[a-z]", pw): return "Password needs a lowercase letter."
    if not re.search(r"[^A-Za-z0-9]", pw): return "Password needs a special character."
    return None

@bp.before_app_request
def load_user():
    g.user = db.session.get(User, session["uid"]) if "uid" in session else None

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user: return redirect(url_for("auth.login"))
        return f(*a, **k)
    return w

def role_required(*roles):
    """Enforced on the server, not just hidden in the UI."""
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if not g.user: return redirect(url_for("auth.login"))
            if g.user.role not in roles: abort(403)
            return f(*a, **k)
        return w
    return deco

@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        err = password_error(pw)
        if err: flash(err); return render_template("signup.html")
        db.session.add(User(name=request.form.get("name", ""), email=email,
                            password_hash=generate_password_hash(pw), role="customer"))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback(); flash("That email already has an account.")
            return render_template("signup.html")
        flash("Account created. Please log in.")
        return redirect(url_for("auth.login"))
    return render_template("signup.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            session.clear(); session["uid"] = u.id
            return redirect(url_for("billing.invoices"))
        flash("Wrong email or password.")
    return render_template("login.html")

@bp.route("/logout")
def logout():
    session.clear(); return redirect(url_for("auth.login"))

@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    link = None
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if u:
            u.reset_token = secrets.token_urlsafe(32)
            u.reset_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            link = url_for("auth.reset", token=u.reset_token, _external=True)
            print("RESET LINK:", link)  # demo: swap for Flask-Mail if time allows
        flash("If that email exists, a reset link was sent.")
    return render_template("forgot.html", link=link)  # link shown on page for demo only

@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    u = User.query.filter_by(reset_token=token).first()
    if not u or u.reset_expiry < datetime.utcnow():
        flash("Reset link is invalid or expired."); return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        err = password_error(request.form["password"])
        if err: flash(err); return render_template("reset.html")
        u.password_hash = generate_password_hash(request.form["password"])
        u.reset_token = None; u.reset_expiry = None
        db.session.commit(); flash("Password updated."); return redirect(url_for("auth.login"))
    return render_template("reset.html")

@bp.route("/staff/new", methods=["GET", "POST"])
@role_required("admin")          # only admin can add staff
def new_staff():
    if request.method == "POST":
        err = password_error(request.form["password"])
        if err: flash(err); return render_template("staff_new.html")
        db.session.add(User(name=request.form.get("name", ""),
                            email=request.form["email"].strip().lower(),
                            password_hash=generate_password_hash(request.form["password"]),
                            role="staff"))
        try:
            db.session.commit(); flash("Staff member added.")
        except IntegrityError:
            db.session.rollback(); flash("Email already in use.")
    return render_template("staff_new.html")
