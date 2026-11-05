from sqlalchemy import select
from app.database import SessionLocal
from app.models import TrainingWebsite

def seed_demo_website() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(TrainingWebsite).where(TrainingWebsite.id == "demo-1"))
        if existing:
            return
        db.add(TrainingWebsite(
            id="demo-1",
            name="SauceDemo",
            base_url="https://www.saucedemo.com",
            environment_type="demo",
            allowed_domains=["www.saucedemo.com"],
            policy={
                "mode": "observe",
                "max_pages": 30,
                "max_depth": 3,
                "external_navigation": False,
                "form_submission": False,
            },
        ))
        db.commit()
    finally:
        db.close()
