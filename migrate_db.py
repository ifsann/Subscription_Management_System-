from sqlalchemy import inspect, text
from app import create_app
from models import db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("plan")]

    if "min_qty" not in columns:
        db.session.execute(
            text("ALTER TABLE plan ADD COLUMN min_qty INTEGER NOT NULL DEFAULT 1")
        )
        db.session.commit()
        print("SUCCESS: min_qty column added!")
    else:
        print("min_qty column already exists.")