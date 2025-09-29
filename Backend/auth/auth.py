from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# Security settings
SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImF6aXpAYXppei5jb20iLCJwYXNzd29yZF9oYXNoIjoiYXppejEyMyIsInJvbGUiOiJ1c2VyIn0.JRT5Ii_wHqMHAcDrktwOE8GSdEavwOXw6PH7OWx3y3s"
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30  # Token valid for 30 days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    """Create a long-lived access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token from Authorization header"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "email": payload.get("sub"),
            "full_name": payload.get("full_name"),
            "user_id": payload.get("user_id"),
            "role": payload.get("role")
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")