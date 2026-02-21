"""
Seed script: creates demo users and an institution.
Run: python scripts/seed.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import AsyncSessionLocal, init_db
from db.models import User, Institution
from services.auth import hash_password
import uuid

INST = {"id": "inst-demo-0001", "name": "Demo University", "domain": "demo.edu"}
USERS = [
    {"email": "admin@demo.edu",   "password": "admin123",   "role": "admin",    "name": "Admin User"},
    {"email": "educator@demo.edu","password": "educator123","role": "educator", "name": "Prof. Smith"},
    {"email": "student@demo.edu", "password": "student123", "role": "student",  "name": "Jane Doe"},
]

async def main():
    print("Initializing DB...")
    await init_db()
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        r = await db.execute(select(Institution).where(Institution.id == INST["id"]))
        if not r.scalar_one_or_none():
            db.add(Institution(id=INST["id"], name=INST["name"], domain=INST["domain"]))
            print(f"  Created institution: {INST['name']}")
        for u in USERS:
            r = await db.execute(select(User).where(User.email == u["email"]))
            if not r.scalar_one_or_none():
                db.add(User(id=str(uuid.uuid4()), institution_id=INST["id"],
                    email=u["email"], hashed_password=hash_password(u["password"]),
                    role=u["role"], full_name=u["name"], is_active=True))
                print(f"  Created user: {u['email']} ({u['role']})")
            else:
                print(f"  Exists: {u['email']}")
        await db.commit()
    print("Done!")

asyncio.run(main())
