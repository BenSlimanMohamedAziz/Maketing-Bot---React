from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from auth.auth import verify_token

router = APIRouter()

@router.post("/api/logout")
def logout():
    """
    Handle user logout - Since we're using JWT tokens stored in localStorage,
    the actual logout happens on the client side by removing the token.
    This endpoint can be used for server-side cleanup if needed.
    """
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Logout successful. Please remove token from client storage."
        }
    )

@router.get("/api/verify")
def verify_token_endpoint(credentials = Depends(verify_token)):
    """Verify if token is still valid"""
    return {
        "success": True,
        "message": "Token is valid",
        "user": {
            "email": credentials.get("sub"),
            "full_name": credentials.get("full_name"),
            "user_id": credentials.get("user_id"),
            "role": credentials.get("role")
        }
    }