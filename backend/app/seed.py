from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserRole


def seed_users(db: Session) -> None:
    users = [
        {
            "email": "admin@modelops.local",
            "full_name": "Platform Admin",
            "password": "admin1234",
            "role": UserRole.admin,
        },
        {
            "email": "viewer@modelops.local",
            "full_name": "Read Only Viewer",
            "password": "viewer1234",
            "role": UserRole.viewer,
        },
    ]

    for record in users:
        exists = db.query(User).filter(User.email == record["email"]).first()
        if exists:
            continue
        db.add(
            User(
                email=record["email"],
                full_name=record["full_name"],
                hashed_password=hash_password(record["password"]),
                role=record["role"],
            )
        )
    db.commit()
