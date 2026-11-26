from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db import get_db
from app.models import User

pwd = CryptContext(schemes=["argon2"], deprecated="auto")
oauth = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def hash_password(password: str) -> str: return pwd.hash(password)
def verify_password(password: str, hashed: str) -> bool: return pwd.verify(password, hashed)
def make_token(user: User):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, settings.secret_key, algorithm="HS256")
def current_user(token: str = Depends(oauth), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise HTTPException(401, "Invalid or expired authentication token")
    user = db.get(User, user_id)
    if not user: raise HTTPException(401, "User no longer exists")
    return user
def require_roles(*roles):
    def checker(user: User = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403, "You do not have permission to perform this action")
        return user
    return checker
