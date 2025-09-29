from fastapi import APIRouter, Depends, HTTPException,FastAPI
from flask import app
from auth.auth import TOKEN_EXPIRE_DAYS, create_access_token, verify_password, get_current_user
from config.config import get_db_connection, get_db_cursor, release_db_connection
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user: Optional[dict] = None

class VerifyResponse(BaseModel):
    success: bool
    message: str
    user: Optional[dict] = None
    
    

router = APIRouter()
app.include_router(router)

@router.post("/api/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        cursor.execute("SELECT id, email, password_hash, role, full_name FROM users WHERE email = %s", (login_data.email,))
        user = cursor.fetchone()

        if not user or not verify_password(login_data.password, user[2]):
            return LoginResponse(
                success=False,
                message="Wrong email or password"
            )

        user_id, email, password_hash, role, full_name = user
        access_token = create_access_token({
            "sub": email,
            "role": role,
            "full_name": full_name,
            "user_id": user_id
        })

        return LoginResponse(
            success=True,
            message="Login successful",
            token=access_token,
            user={
                "id": user_id,
                "email": email,
                "role": role,
                "full_name": full_name
            }
        )
    except Exception as e:
        return LoginResponse(
            success=False,
            message=f"Login error: {str(e)}"
        )
    finally:
        release_db_connection(conn)

@router.get("/api/verify", response_model=VerifyResponse)
async def verify_token(current_user = Depends(get_current_user)):
    """Verify if the current token is valid"""
    return VerifyResponse(
        success=True,
        message="Token is valid",
        user=current_user
    )