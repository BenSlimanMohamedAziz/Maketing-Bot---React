import os
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime, timedelta
from auth.auth import hash_password, verify_password, get_current_user
from config.config import get_db_connection, get_db_cursor, release_db_connection
import asyncio

from typing import List, Optional
from fastapi import Query

from .linkedin_oauth import LinkedInOAuth

from .meta_oauth import MetaOAuth

router = APIRouter()
templates = Jinja2Templates(directory="/static/templates")

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode() # LinkedIn Link Account

linkedin_oauth = LinkedInOAuth(ENCRYPTION_KEY) # LinkedIn Link Account

meta_oauth = MetaOAuth(ENCRYPTION_KEY)  # Meta Link Account

class UserUpdate(BaseModel):
    email: str
    full_name: str
    current_password: str
    new_password: str = None
    confirm_password: str = None

async def check_subscription_expiry(user_id: int):
    """Check if subscription has expired and handle accordingly"""
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        cursor.execute("""
            SELECT plan, plan_expires_at, payment_method, is_subscription_active
            FROM users WHERE id = %s
        """, (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return
        
        plan, expires_at, payment_method, is_active = user_data
        
        # Only check for paid plans
        if plan != 'free' and expires_at and expires_at <= datetime.now():
            if is_active and payment_method:
                # Update existing subscription record with new dates
                new_expires_at = expires_at + timedelta(days=30)
                cursor.execute("""
                    UPDATE user_subscriptions 
                    SET end_date = %s,
                        payment_status = 'paid'
                    WHERE user_id = %s 
                    AND end_date = %s
                    RETURNING id
                """, (new_expires_at, user_id, expires_at))
                
                if not cursor.fetchone():
                    # If no existing record found, create new one
                    amount = 50 if plan == 'plus' else 100
                    cursor.execute("""
                        INSERT INTO user_subscriptions (
                            user_id, plan, amount, payment_status, 
                            start_date, end_date
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user_id, plan, amount, 'paid',
                        expires_at, new_expires_at
                    ))
                
                # Update user record
                cursor.execute("""
                    UPDATE users 
                    SET plan_expires_at = %s,
                        next_payment_date = %s
                    WHERE id = %s
                """, (new_expires_at, new_expires_at, user_id))
            else:
                # Downgrade to free
                cursor.execute("""
                    UPDATE users 
                    SET plan = 'free',
                        is_subscription_active = FALSE,
                        plan_expires_at = NULL,
                        next_payment_date = NULL
                    WHERE id = %s
                """, (user_id,))
            
            conn.commit()
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

async def check_pending_subscriptions():
    """Check for pending subscriptions that need to be activated"""
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Get pending subscriptions that should start now
        cursor.execute("""
            SELECT us.id, us.user_id, us.plan, u.payment_method, us.start_date
            FROM user_subscriptions us
            JOIN users u ON us.user_id = u.id
            WHERE us.payment_status = 'pending'
            AND us.start_date <= %s
        """, (datetime.now(),))
        
        pending_subs = cursor.fetchall()
        
        for sub in pending_subs:
            sub_id, user_id, plan, payment_method, start_date = sub
            
            if payment_method:
                # Process payment (in real app, call payment processor)
                end_date = start_date + timedelta(days=30)
                amount = 50 if plan == 'plus' else 100
                
                # Update the pending subscription to active
                cursor.execute("""
                    UPDATE user_subscriptions 
                    SET payment_status = 'paid',
                        end_date = %s,
                        amount = %s
                    WHERE id = %s
                """, (end_date, amount, sub_id))
                
                # Update user
                cursor.execute("""
                    UPDATE users 
                    SET plan = %s,
                        is_subscription_active = TRUE,
                        plan_expires_at = %s,
                        next_payment_date = %s
                    WHERE id = %s
                """, (plan, end_date, end_date, user_id))
            else:
                # No payment method - cancel the pending subscription
                cursor.execute("""
                    DELETE FROM user_subscriptions 
                    WHERE id = %s
                """, (sub_id,))
                
                # Downgrade user to free
                cursor.execute("""
                    UPDATE users 
                    SET plan = 'free',
                        is_subscription_active = FALSE,
                        plan_expires_at = NULL,
                        next_payment_date = NULL
                    WHERE id = %s
                """, (user_id,))
        
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

async def check_upcoming_expirations():
    """Check for subscriptions expiring in 7 days and send notifications"""
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        seven_days_from_now = datetime.now() + timedelta(days=7)
        
        cursor.execute("""
            SELECT id, email, plan, plan_expires_at
            FROM users
            WHERE plan_expires_at BETWEEN %s AND %s
            AND plan != 'free'
            AND is_subscription_active = TRUE
        """, (datetime.now(), seven_days_from_now))
        
        users_to_notify = cursor.fetchall()
        
        # In a real app, you would send emails or store notifications in a database
        for user in users_to_notify:
            user_id, email, plan, expires_at = user
            days_left = (expires_at - datetime.now()).days
            print(f"User {user_id} ({email}) has {days_left} days left on their {plan} plan")
            
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.get("/user_settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: dict = Depends(get_current_user)):
    # Check subscription status before showing page
    await check_subscription_expiry(user["user_id"])
    await check_pending_subscriptions()
    
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Get user data
        cursor.execute("""
            SELECT email, full_name, plan, plan_expires_at, payment_method, 
                   is_subscription_active, next_payment_date
            FROM users 
            WHERE id = %s
        """, (user["user_id"],))
        user_data = cursor.fetchone()
        
        # Get current active subscription
        cursor.execute("""
            SELECT plan, amount, payment_status, start_date, end_date, canceled_at
            FROM user_subscriptions
            WHERE user_id = %s
            AND payment_status = 'paid'
            AND (canceled_at IS NULL OR canceled_at > NOW())
            ORDER BY end_date DESC
            LIMIT 1
        """, (user["user_id"],))
        current_sub = cursor.fetchone()
        
        # Get subscription history (only show completed subscriptions)
        cursor.execute("""
            SELECT plan, amount, payment_status, start_date, end_date, canceled_at
            FROM user_subscriptions
            WHERE user_id = %s
            AND (payment_status = 'paid' OR canceled_at IS NOT NULL)
            ORDER BY start_date DESC
        """, (user["user_id"],))
        subscriptions = cursor.fetchall()
        
        # Get pending subscription if exists
        cursor.execute("""
            SELECT plan, start_date 
            FROM user_subscriptions
            WHERE user_id = %s 
            AND payment_status = 'pending'
            ORDER BY start_date DESC LIMIT 1
        """, (user["user_id"],))
        pending_sub = cursor.fetchone()
        
        # Get companies data (same as in home route)
        cursor.execute("""
            SELECT 
                c.id, 
                c.name, 
                c.created_at,
                c.monthly_budget,
                COUNT(s.id) as strategy_count,
                SUM(CASE WHEN s.status = 'approved' THEN 1 ELSE 0 END) as approved_count,
                SUM(CASE WHEN s.status = 'archived' THEN 1 ELSE 0 END) as archived_count,
                SUM(CASE WHEN s.status NOT IN ('approved', 'archived') THEN 1 ELSE 0 END) as other_count
            FROM companies c
            LEFT JOIN strategies s ON c.id = s.company_id
            WHERE c.user_id = %s
            GROUP BY c.id, c.name, c.created_at, c.monthly_budget
            ORDER BY c.created_at DESC
        """, (user["user_id"],))
        
        companies = []
        for row in cursor.fetchall():
            monthly_budget = float(row[3]) if row[3] is not None else 0
            companies.append({
                "id": row[0],
                "name": row[1],
                "created_at": row[2].strftime("%Y-%m-%d"),
                "monthly_budget": monthly_budget,
                "strategy_count": row[4] or 0,
                "approved_count": row[5] or 0,
                "archived_count": row[6] or 0
            })
        
         # Get linked accounts
        cursor.execute("""
            SELECT id, platform, account_id, account_name, created_at
            FROM user_linked_accounts 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user["user_id"],))
        
        linked_accounts = [
            {
                "id": row[0],
                "platform": row[1],
                "account_id": row[2],
                "account_name": row[3],
                "created_at": row[4].strftime("%Y-%m-%d %H:%M") if row[4] else None
            } for row in cursor.fetchall()
        ]
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
            
        return templates.TemplateResponse("user_settings.html", {
            "request": request,
            "user": {
                "email": user_data[0],
                "full_name": user_data[1],
                "plan": user_data[2],
                "plan_expires_at": user_data[3],
                "payment_method": user_data[4],
                "is_subscription_active": user_data[5],
                "next_payment_date": user_data[6],
                "user_id": user["user_id"]
            },
            "current_subscription": {
                "plan": current_sub[0] if current_sub else None,
                "amount": float(current_sub[1]) if current_sub and current_sub[1] else 0,
                "payment_status": current_sub[2] if current_sub else None,
                "start_date": current_sub[3].strftime("%Y-%m-%d") if current_sub and current_sub[3] else None,
                "end_date": current_sub[4].strftime("%Y-%m-%d") if current_sub and current_sub[4] else None,
                "canceled_at": current_sub[5].strftime("%Y-%m-%d") if current_sub and current_sub[5] else None
            },
            "subscriptions": [
                {
                    "plan": sub[0],
                    "amount": float(sub[1]) if sub[1] else 0,
                    "payment_status": sub[2],
                    "start_date": sub[3].strftime("%Y-%m-%d") if sub[3] else None,
                    "end_date": sub[4].strftime("%Y-%m-%d") if sub[4] else None,
                    "canceled_at": sub[5].strftime("%Y-%m-%d") if sub[5] else None
                } for sub in subscriptions
            ],
            "pending_subscription": {
                "plan": pending_sub[0] if pending_sub else None,
                "start_date": pending_sub[1].strftime("%Y-%m-%d") if pending_sub else None
            },
            "companies": companies,  # Add this line to pass companies to the template
            "linked_accounts": linked_accounts # Return linked accounts
        })
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/update_profile")
async def update_profile(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    current_password: str = Form(None),
    new_password: str = Form(None),
    confirm_password: str = Form(None),
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Get current user data
        cursor.execute("SELECT email, full_name, password_hash, plan FROM users WHERE id = %s", (user["user_id"],))
        db_data = cursor.fetchone()
        current_email, current_full_name, db_password, current_plan = db_data
        
        # Check if email or password is being changed
        email_changed = email != current_email
        password_changed = new_password is not None and new_password.strip() != ""
        
        # Check if the new email already exists (only if email is being changed)
        if email_changed:
            cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user["user_id"]))
            if cursor.fetchone():
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "The new email is already registered by another user, Please type a different email!"}
                )
        
        # Only require current password if email or password is being changed
        if email_changed or password_changed:
            if not current_password:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Current password is required to change email or password"}
                )
            
            if not verify_password(current_password, db_password):
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Current password is incorrect"}
                )
        
        # Check if new password is provided and matches confirmation
        if password_changed:
            if new_password != confirm_password:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "New passwords don't match"}
                )
            
            hashed_password = hash_password(new_password)
            cursor.execute(
                "UPDATE users SET email = %s, full_name = %s, password_hash = %s WHERE id = %s",
                (email, full_name, hashed_password, user["user_id"])
            )
        else:
            cursor.execute(
                "UPDATE users SET email = %s, full_name = %s WHERE id = %s",
                (email, full_name, user["user_id"])
            )
        
        conn.commit()
        
        # Update the token with new information
        from auth.auth import create_access_token
        new_token = create_access_token(data={
            "sub": email,
            "role": 'user',
            "user_id": user["user_id"],
            "full_name": full_name,
            "plan": current_plan
        })
        
        response = JSONResponse(
            status_code=200,
            content={
                "status": "success", 
                "message": "Profile updated successfully"
            }
        )
        response.set_cookie("token", new_token, httponly=True)
        return response
        
    except Exception as e:
        conn.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/update_payment_method")
async def update_payment_method(
    request: Request,
    card_name: str = Form(...),
    card_type: str = Form(...),
    card_number: str = Form(...),
    expiry_date: str = Form(...),
    cvv: str = Form(...),
    postcode: str = Form(...),
    user: dict = Depends(get_current_user)
):
    masked_card = f"{card_type} **** **** {card_number[-4:]}" if card_number else None
    
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        cursor.execute(
            "UPDATE users SET payment_method = %s WHERE id = %s",
            (masked_card, user["user_id"])
        )
        
        # Check if there are pending subscriptions that can now be processed
        await check_pending_subscriptions()
        
        conn.commit()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Payment method updated successfully"}
        )
    except Exception as e:
        conn.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/remove_payment_method")
async def remove_payment_method(
    request: Request,
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Check if user has active subscription
        cursor.execute("""
            SELECT is_subscription_active FROM users WHERE id = %s
        """, (user["user_id"],))
        is_active = cursor.fetchone()[0]
        
        if is_active:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Cannot remove payment method with active subscription. Cancel subscription first."
                }
            )
            
        cursor.execute(
            "UPDATE users SET payment_method = NULL WHERE id = %s",
            (user["user_id"],)
        )
        conn.commit()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Payment method removed successfully"}
        )
    except Exception as e:
        conn.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/cancel_subscription")
async def cancel_subscription(
    request: Request,
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Get current subscription
        cursor.execute("""
            SELECT id, end_date FROM user_subscriptions 
            WHERE user_id = %s AND payment_status = 'paid' AND canceled_at IS NULL
            ORDER BY end_date DESC LIMIT 1
        """, (user["user_id"],))
        subscription = cursor.fetchone()
        
        if not subscription:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No active subscription found"}
            )
        
        sub_id, end_date = subscription
        
        # Mark subscription as canceled
        cursor.execute("""
            UPDATE user_subscriptions 
            SET canceled_at = %s 
            WHERE id = %s
        """, (datetime.now(), sub_id))
        
        # Cancel any pending subscriptions
        cursor.execute("""
            DELETE FROM user_subscriptions
            WHERE user_id = %s 
            AND payment_status = 'pending'
        """, (user["user_id"],))
        
        # Update user status (don't change plan yet - it will remain until end_date)
        cursor.execute("""
            UPDATE users 
            SET is_subscription_active = FALSE,
                next_payment_date = NULL
            WHERE id = %s
        """, (user["user_id"],))
        
        conn.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Subscription canceled successfully",
                "end_date": end_date.strftime("%Y-%m-%d") if end_date else None
            }
        )
    except Exception as e:
        conn.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/change_plan")
async def change_plan(
    request: Request,
    new_plan: str = Form(...),
    user: dict = Depends(get_current_user)
):
    if new_plan not in ["free", "plus", "pro"]:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid plan selected"}
        )
    
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Check if payment method exists for paid plans
        if new_plan != "free":
            cursor.execute("""
                SELECT payment_method FROM users WHERE id = %s
            """, (user["user_id"],))
            payment_method = cursor.fetchone()[0]
            
            if not payment_method:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "payment_required",
                        "message": "Please add a payment method first"
                    }
                )
        
        # Get current plan details
        cursor.execute("""
            SELECT plan, is_subscription_active, plan_expires_at
            FROM users 
            WHERE id = %s
        """, (user["user_id"],))
        current_plan, is_active, expires_at = cursor.fetchone()
        
        if new_plan == current_plan:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "You're already on this plan"}
            )
            
        if new_plan == "free":
            # Downgrade to free - cancel any active subscription
            if is_active:
                cursor.execute("""
                    UPDATE users 
                    SET is_subscription_active = FALSE,
                        next_payment_date = NULL
                    WHERE id = %s
                """, (user["user_id"],))
                
                # Mark current subscription as canceled
                cursor.execute("""
                    UPDATE user_subscriptions 
                    SET canceled_at = %s 
                    WHERE user_id = %s 
                    AND payment_status = 'paid'
                    AND (canceled_at IS NULL OR canceled_at > NOW())
                """, (datetime.now(), user["user_id"]))
                
            # Cancel any pending subscriptions
            cursor.execute("""
                DELETE FROM user_subscriptions
                WHERE user_id = %s 
                AND payment_status = 'pending'
            """, (user["user_id"],))
                
        else:
            # Upgrade/downgrade to paid plan
            if not is_active or current_plan == 'free':
                # No active subscription or coming from free - start new one immediately
                start_date = datetime.now()
                end_date = start_date + timedelta(days=30)
                amount = 50 if new_plan == "plus" else 100
                
                # First cancel any existing subscriptions
                cursor.execute("""
                    UPDATE user_subscriptions 
                    SET canceled_at = %s 
                    WHERE user_id = %s 
                    AND payment_status = 'paid'
                    AND (canceled_at IS NULL OR canceled_at > NOW())
                """, (datetime.now(), user["user_id"]))
                
                # Create new subscription
                cursor.execute("""
                    INSERT INTO user_subscriptions (
                        user_id, plan, amount, payment_status, 
                        start_date, end_date
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user["user_id"], new_plan, amount, 'paid',
                    start_date, end_date
                ))
                
                cursor.execute("""
                    UPDATE users 
                    SET plan = %s,
                        is_subscription_active = TRUE,
                        plan_expires_at = %s,
                        next_payment_date = %s
                    WHERE id = %s
                """, (new_plan, end_date, end_date, user["user_id"]))
                
            else:
                # Active paid subscription - schedule change for next billing cycle
                # First cancel any pending subscriptions
                cursor.execute("""
                    DELETE FROM user_subscriptions
                    WHERE user_id = %s 
                    AND payment_status = 'pending'
                """, (user["user_id"],))
                
                # Create pending subscription
                amount = 50 if new_plan == "plus" else 100
                cursor.execute("""
                    INSERT INTO user_subscriptions (
                        user_id, plan, amount, payment_status, 
                        start_date, end_date
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user["user_id"], new_plan, amount, 'pending',
                    expires_at, expires_at + timedelta(days=30)
                ))
        
        conn.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Plan changed successfully",
                "new_plan": new_plan,
                "is_active": new_plan != "free",
                "next_payment": expires_at.strftime("%Y-%m-%d") if expires_at else None
            }
        )
        
    except Exception as e:
        conn.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)


# LinkedIn Login Link Account Routes
@router.get("/linkedin/login")
async def linkedin_login(user: dict = Depends(get_current_user)):
    """Redirect to LinkedIn OAuth"""
    return RedirectResponse(url=linkedin_oauth.get_auth_url())

@router.get("/linkedin/callback")
async def linkedin_callback(
    request: Request,
    user: dict = Depends(get_current_user),
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None)
):
    """Handle LinkedIn OAuth callback"""
    conn = get_db_connection()
    cursor = None
    try:
        # Process callback
        linkedin_data = await linkedin_oauth.handle_callback(request, conn)
        
        # Store in database
        cursor = get_db_cursor(conn)
        cursor.execute("""
            INSERT INTO user_linked_accounts 
            (user_id, platform, account_id, account_name, access_token, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, platform, account_id) 
            DO UPDATE SET 
                account_name = EXCLUDED.account_name,
                access_token = EXCLUDED.access_token,
                created_at = EXCLUDED.created_at
            RETURNING id
        """, (
            user["user_id"], 
            linkedin_data['platform'],
            linkedin_data['account_id'],
            linkedin_data['account_name'],
            linkedin_data['access_token'],
            datetime.now()
        ))
        
        conn.commit()
        return RedirectResponse(url="/user_settings?linkedin_success=1")
        
    except HTTPException as e:
        conn.rollback()
        return RedirectResponse(url=f"/user_settings?error={str(e.detail)}")
    except Exception as e:
        conn.rollback()
        return RedirectResponse(url="/user_settings?error=linkedin_failed")
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/linkedin/disconnect")  # Changed from GET to POST
async def disconnect_linkedin(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Remove LinkedIn account connection"""
    conn = get_db_connection()
    cursor = None
    try:
        cursor = get_db_cursor(conn)
        cursor.execute("""
            DELETE FROM user_linked_accounts 
            WHERE user_id = %s AND platform = 'linkedin'
            RETURNING account_name
        """, (user["user_id"],))
        
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {
                "success": True,
                "message": "LinkedIn account disconnected",
                "platform": "linkedin"
            }
        return {
            "success": False,
            "error": "No LinkedIn account found"
        }
        
    except Exception as e:
        if cursor:
            cursor.close()
        conn.rollback()
        release_db_connection(conn)
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)


# Meta Link Account Routes
@router.get("/meta/login")
async def meta_login(user: dict = Depends(get_current_user)):
    """Redirect to Facebook OAuth"""
    return RedirectResponse(url=meta_oauth.get_auth_url())

@router.get("/meta/callback")
async def meta_callback(
    request: Request,
    user: dict = Depends(get_current_user),
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None)
):
    """Handle Facebook OAuth callback"""
    conn = get_db_connection()
    cursor = None
    try:
        # Process callback
        meta_data = await meta_oauth.handle_callback(request, conn)
        
        # Store accounts in database
        cursor = get_db_cursor(conn)
        for account in meta_data['accounts']:
            cursor.execute("""
                INSERT INTO user_linked_accounts 
                (user_id, platform, account_id, account_name, access_token, 
                 user_access_token, page_id, instagram_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, platform, account_id) 
                DO UPDATE SET
                    account_name = EXCLUDED.account_name,
                    access_token = EXCLUDED.access_token,
                    user_access_token = EXCLUDED.user_access_token,
                    page_id = EXCLUDED.page_id,
                    instagram_id = EXCLUDED.instagram_id,
                    created_at = EXCLUDED.created_at
            """, (
                user["user_id"],
                account['platform'],
                account['account_id'],
                account['account_name'],
                account['access_token'],
                account.get('user_access_token'),
                account.get('page_id'),
                account.get('instagram_id'),
                datetime.now()
            ))
        
        conn.commit()
        return RedirectResponse(url="/user_settings?meta_success=1")
        
    except HTTPException as e:
        conn.rollback()
        return RedirectResponse(url=f"/user_settings?error={str(e.detail)}")
    except Exception as e:
        conn.rollback()
        return RedirectResponse(url="/user_settings?error=meta_failed")
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)

@router.post("/meta/disconnect")
async def disconnect_meta(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Remove specific Facebook/Instagram account connection"""
    data = await request.json()
    account_id = data.get('account_id')
    
    conn = get_db_connection()
    cursor = None
    try:
        cursor = get_db_cursor(conn)
        
        if account_id:
            # Delete specific account
            cursor.execute("""
                DELETE FROM user_linked_accounts 
                WHERE id = %s AND user_id = %s AND platform IN ('facebook', 'instagram')
                RETURNING platform, account_name
            """, (account_id, user["user_id"]))
        else:
            # Delete all Meta accounts (fallback)
            cursor.execute("""
                DELETE FROM user_linked_accounts 
                WHERE user_id = %s AND platform IN ('facebook', 'instagram')
                RETURNING platform, account_name
            """, (user["user_id"],))
        
        result = cursor.fetchone()
        conn.commit()
        
        if result:
            return {
                "success": True,
                "message": f"{result[0].capitalize()} account disconnected",
                "platform": result[0]
            }
        return {
            "success": False,
            "error": "Account not found"
        }
        
    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if cursor:
            cursor.close()
        release_db_connection(conn)


@router.on_event("startup")
async def startup_event():
    # Schedule periodic checks
    async def run_periodic_checks():
        while True:
            # Get all active subscribers
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            try:
                cursor.execute("""
                    SELECT id FROM users 
                    WHERE is_subscription_active = TRUE
                    AND plan != 'free'
                """)
                user_ids = [row[0] for row in cursor.fetchall()]
            finally:
                if cursor:
                    cursor.close()
                release_db_connection(conn)
            
            # Check each user's subscription status
            for user_id in user_ids:
                await check_subscription_expiry(user_id)
            
            await check_pending_subscriptions()
            await check_upcoming_expirations()
            await asyncio.sleep(3600)  # Run every hour
    
    asyncio.create_task(run_periodic_checks())