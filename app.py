from flask import Flask
from werkzeug.security import generate_password_hash
from models import db, User
import auth, billing

def create_app(db_uri="sqlite:///brightloop.db"):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="change-me-for-hackathon", SQLALCHEMY_DATABASE_URI=db_uri)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(billing.bp)
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role="admin").first():
            db.session.add(User(name="Admin", email="admin@brightloop.com", role="admin",
                                password_hash=generate_password_hash("Admin@12345")))
            db.session.commit()
    return app

if __name__ == "__main__":
    create_app().run(debug=True)
