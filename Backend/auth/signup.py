import re
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime, timedelta
from auth.auth import hash_password, create_access_token
from config.config import get_db_cursor, get_db_connection, release_db_connection

router = APIRouter()
templates = Jinja2Templates(directory="/static/templates")

class UserSignup(BaseModel):
    email: str
    password: str
    full_name: str
    company_name: str
    company_website: str  # Add this field

@router.get("/signup")
@router.get("/signup_page")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


def validate_website(url):
    """Validate website URL format"""
    if not url:
        return True  # Empty is allowed
    
    # Basic URL validation
    url_pattern = re.compile(
        r'^(https?://)?'  # http:// or https://
        r'(([A-Z0-9][A-Z0-9_-]*)(\.[A-Z0-9][A-Z0-9_-]*)+)'  # domain
        r'(:[0-9]{1,5})?'  # optional port
        r'(/.*)?$',  # optional path
        re.IGNORECASE
    )
    
    # LinkedIn pattern
    linkedin_pattern = re.compile(
        r'^(https?://)?(www\.)?linkedin\.com/.*',
        re.IGNORECASE
    )
    
    return bool(url_pattern.match(url)) or bool(linkedin_pattern.match(url))

# Add phone validation function to signup.py as well
def validate_phone(phone_number):
    """Validate phone number format (allows spaces, parentheses, dashes, dots)"""
    if not phone_number:
        return True  # Empty is allowed
    
    # Flexible phone validation - allows various formatting characters
    phone_pattern = re.compile(
        r'^\+?[0-9]{1,4}?[-.\s()]*[0-9]{1,4}?[-.\s()]*[0-9]{1,4}[-.\s()]*[0-9]{1,4}[-.\s()]*[0-9]{1,9}$'
    )
    
    return bool(phone_pattern.match(phone_number))

@router.post("/signup")
def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    company_name: str = Form(...),
    company_website: str = Form(""),
    company_phone: str = Form("")
):
    # Validate website format
    if company_website and not validate_website(company_website):
        raise HTTPException(status_code=400, detail="Invalid website URL format")
    
    # Validate phone number format
    if company_phone and not validate_phone(company_phone):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    # Check if email already exists
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            # Return JSON error response instead of raising HTTPException
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,
                content={"detail": "Email already registered"}
            )
    finally:
        release_db_connection(conn)
    
    # If email doesn't exist, proceed with setting cookies and redirect
    response = RedirectResponse("/plan", status_code=303)
    response.set_cookie("signup_email", email)
    response.set_cookie("signup_password", password)
    response.set_cookie("signup_full_name", full_name)
    response.set_cookie("signup_company_name", company_name)
    response.set_cookie("signup_company_website", company_website)
    response.set_cookie("signup_company_phone", company_phone)
    return response

def calculate_plan_dates(plan: str):
    """Calculate plan dates with 30-day intervals"""
    now = datetime.now()
    if plan == 'free':
        return None, None  # Free plan has no payments
    elif plan in ('plus', 'pro'):
        end_date = now + timedelta(days=30)
        next_payment_date = now + timedelta(days=30)
        return end_date, next_payment_date
    return None, None

def calculate_plan_end_date(plan: str):
    """Calculate when the plan expires based on the selected plan"""
    if plan == 'free':
        return None  # Free plan never expires
    elif plan == 'plus':
        return datetime.now() + timedelta(days=30)  # 1 month
    elif plan == 'pro':
        return datetime.now() + timedelta(days=30)  # 1 month
    return None

@router.get("/plan")
def plan_selection(request: Request):
    return templates.TemplateResponse("plans.html", {"request": request})

def check_and_renew_subscriptions():
    """Check for expired subscriptions and renew them"""
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Get subscriptions that need renewal
        cursor.execute("""
            SELECT us.user_id, us.plan 
            FROM user_subscriptions us
            JOIN users u ON us.user_id = u.id
            WHERE us.next_payment_date <= %s
            AND u.is_subscription_active = TRUE
        """, (datetime.now(),))
        
        subscriptions = cursor.fetchall()
        
        for sub in subscriptions:
            user_id, plan = sub
            new_end_date, new_payment_date = calculate_plan_dates(plan)
            
            # Create new subscription record
            cursor.execute("""
                INSERT INTO user_subscriptions 
                (user_id, plan, amount, payment_status, start_date, end_date, next_payment_date) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                plan,
                50 if plan == 'plus' else 100,
                'paid',
                datetime.now(),
                new_end_date,
                new_payment_date
            ))
            
            # Update user's next payment date
            cursor.execute("""
                UPDATE users 
                SET next_payment_date = %s 
                WHERE id = %s
            """, (new_payment_date, user_id))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        release_db_connection(conn)
        
@router.post("/process_plan")
def process_plan(
    request: Request,
    plan: str = Form(...),
    card_name: str = Form(None),
    card_type: str = Form(None),
    card_number: str = Form(None),
    expiry_date: str = Form(None),
    cvv: str = Form(None),
    postcode: str = Form(None)
):
    # Get the signup data from cookies
    email = request.cookies.get("signup_email")
    password = request.cookies.get("signup_password")
    full_name = request.cookies.get("signup_full_name")
    company_name = request.cookies.get("signup_company_name")
    company_website = request.cookies.get("signup_company_website", "")  # Get website from cookie
    company_phone = request.cookies.get("signup_company_phone", "")  # Get phone from cookie
    
    if not all([email, password, full_name, company_name]):
        raise HTTPException(status_code=400, detail="Missing signup data")
    
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create user
        hashed_pwd = hash_password(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, full_name, plan, is_subscription_active) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", 
            (email, hashed_pwd, 'user', full_name, plan, plan != 'free')
        )
        user_id = cursor.fetchone()[0]  # This defines the user_id variable
        
        # Calculate plan dates using both functions
        plan_end_date, next_payment_date = calculate_plan_dates(plan)
        plan_expires_at = calculate_plan_end_date(plan)
        
        # Determine payment status - free plans should not be marked as "paid"
        payment_status = 'free' if plan == 'free' else 'paid'
        
        # Create subscription record
        cursor.execute("""
            INSERT INTO user_subscriptions 
            (user_id, plan, amount, payment_status, start_date, end_date, next_payment_date) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,  # Now properly defined
            plan,
            0 if plan == 'free' else (50 if plan == 'plus' else 100),
            payment_status,  # Use the correct status
            datetime.now(),
            plan_end_date,
            next_payment_date
        ))
        
        # Update user with plan details
        cursor.execute("""
            UPDATE users 
            SET plan = %s,
                is_subscription_active = %s,
                next_payment_date = %s
            WHERE id = %s
        """, (
            plan,
            plan != 'free',
            next_payment_date,
            user_id
        ))
        
        # Update user with plan details if not free
        if plan != 'free':
            # Mask card number for display (last 4 digits)
            masked_card = f"{card_type} **** **** {card_number[-4:]}" if card_number else None
            
            cursor.execute(
                """UPDATE users 
                SET plan_expires_at = %s, 
                    payment_method = %s
                WHERE id = %s""",
                (plan_expires_at, masked_card, user_id)
            )
        
        conn.commit()
        
        # Create access token
        access_token = create_access_token(data={
            "sub": email,
            "role": 'user',
            "user_id": user_id,
            "full_name": full_name,
            "plan": plan
        })

        response = RedirectResponse("/Company_form", status_code=303)
        response.set_cookie("token", access_token, httponly=True)
        response.set_cookie("pending_company_name", company_name)
        response.set_cookie("pending_company_website", company_website)  # Add this cookie
        response.set_cookie("pending_company_phone", company_phone)  # Add phone cookie
        
        # Clear the temporary signup cookies
        response.delete_cookie("signup_email")
        response.delete_cookie("signup_password")
        response.delete_cookie("signup_full_name")
        response.delete_cookie("signup_company_name")
        response.delete_cookie("signup_company_website")  # Clear website cookie
        response.delete_cookie("signup_company_phone")  # Clear phone cookie
        
        return response
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        release_db_connection(conn)
@router.get("/cron/daily_subscription_check")
def daily_subscription_check():
    """Endpoint to be called daily (e.g., via cron job) to check and renew subscriptions"""
    try:
        check_and_renew_subscriptions()
        return {"status": "success", "message": "Subscription check completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))        