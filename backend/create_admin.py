import argparse
from app.db import Base, engine, SessionLocal
from app import models
from app.models import User
from app.security import hash_password
Base.metadata.create_all(bind=engine)
p=argparse.ArgumentParser(); p.add_argument('--name',required=True); p.add_argument('--email',required=True); p.add_argument('--password',required=True); a=p.parse_args()
db=SessionLocal()
try:
    if db.query(User).filter_by(email=a.email.lower()).first(): raise SystemExit('Email already exists')
    db.add(User(name=a.name,email=a.email.lower(),password_hash=hash_password(a.password),role='admin')); db.commit(); print('Admin created:',a.email)
finally: db.close()
