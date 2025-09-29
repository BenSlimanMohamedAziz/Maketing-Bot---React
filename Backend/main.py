import json
import random
import re
import shutil
import tempfile
import time
import traceback
from fastapi import FastAPI, File, HTTPException, Depends, Form, Query, Request, UploadFile
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from fastapi.staticfiles import StaticFiles
import os
import psycopg2
import requests
from urllib3 import Retry

# Auth
from auth.login import router as login_router
from auth.signup import router as signup_router
from auth.logout import router as logout_router
from auth.auth import get_current_user

from auth.user_settings import router as settings_router

# DB
from config.config import get_db_connection, get_db_cursor, release_db_connection,settings

# Company router 
from components.company.company_router import router as company_router


# Insights 
from components.insightsBIData.insights_platforms_data import (
    get_facebook_analytics, 
    get_instagram_analytics,
    get_linkedin_analytics
)


# For web scraping 
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import asyncio
import logging


# For Img Gen 
# === Image Generation ===
from fastapi.responses import JSONResponse
from together import Together
import uuid


# For Posting / Uploading Cloud : 
import cloudinary
import cloudinary.uploader
   

# For mailing : 
from components.Mail.mails import send_influencer_emails

# For Linked Accounts : 
import os
from cryptography.fernet import Fernet
from auth.meta_oauth import MetaOAuth
from auth.linkedin_oauth import LinkedInOAuth

# Import Groq client
from groq import Groq

# === App Setup ===
app = FastAPI()


# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")
#Front Templates
templates = Jinja2Templates(directory="/static/templates")


# API keys and endpoints LLAMA
LLAMA_API_KEY = settings.LLAMA_API_KEY
LLAMA_API_URL = settings.LLAMA_API_URL


# API keys and endpoints Groq Models
GROQ_API_KEY = settings.GROQ_API_KEY_1
TAVILY_API_KEY = settings.TAVILY_API_KEY_2
TAVILY_API_URL = settings.TAVILY_API_URL
FIRECRAWL_API_KEY= settings.FIRECRAWL_API_KEY_2
FIRECRAWL_API_URL= settings.FIRECRAWL_API_KEY_2
client = Groq(api_key=GROQ_API_KEY)


# Cloud Upload Config
cloudinary.config( 
    cloud_name = settings.CLOUDINARY_CLOUD_NAME,
    api_key = settings.CLOUDINARY_API_KEY,
    api_secret = settings.CLOUDINARY_API_SECRET,
    secure=True,
    # Add this to enable video uploads
    video_upload_options={
        'resource_type': 'video',
        'chunk_size': 6000000,
        'eager': [
            {'width': 300, 'height': 300, 'crop': 'pad', 'audio_codec': 'none'},
            {'width': 160, 'height': 100, 'crop': 'crop', 'gravity': 'south', 'audio_codec': 'none'}
        ]
    }
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === DB Setup ===
conn = get_db_connection()
cursor = get_db_cursor(conn)

# === Auth ===
# Include auth routers
app.include_router(login_router)
app.include_router(signup_router)
app.include_router(logout_router)

# Include the company router
app.include_router(company_router) 

app.include_router(settings_router)
@app.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# === Home Page ===
#@app.get("/home", response_class=HTMLResponse)
#def home(request: Request, user: dict = Depends(get_current_user)):
    # Fetch companies for this user
 #   cursor.execute("""
  #      SELECT c.id, c.name, c.created_at,monthly_budget, COUNT(s.id) as strategy_count
   #     FROM companies c
    #    LEFT JOIN strategies s ON c.id = s.company_id
     #   WHERE c.user_id = %s
      #  GROUP BY c.id, c.name, c.created_at
       # ORDER BY c.created_at DESC
    # """, (user["user_id"],))
     
   # companies = []
    #for row in cursor.fetchall():
     #   companies.append({
      #      "id": row[0],
       #     "name": row[1],
        #    "created_at": row[2].strftime("%Y-%m-%d"),
        #    "monthly_budget": row[3],
         #   "strategy_count": row[4]
        #})
    
   # return templates.TemplateResponse("home.html", {"request": request, "user": user, "companies": companies})

@app.get("/api/home")
async def home_api(user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    
    try:
        # Fetch companies with accurate strategy counts
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
        total_strategies = 0
        total_approved = 0
        total_archived = 0
        
        for row in cursor.fetchall():
            monthly_budget = float(row[3]) if row[3] is not None else 0
            strategy_count = row[4] or 0
            approved_count = row[5] or 0
            archived_count = row[6] or 0
            
            total_strategies += strategy_count
            total_approved += approved_count
            total_archived = total_strategies - total_approved
            
            companies.append({
                "id": row[0],
                "name": row[1],
                "created_at": row[2].strftime("%Y-%m-%d"),
                "monthly_budget": monthly_budget,
                "strategy_count": strategy_count,
                "approved_count": approved_count,
                "archived_count": archived_count
            })
        
        return {
            "success": True,
            "user": user,
            "companies": companies,
            "total_strategies": total_strategies,
            "total_approved": total_approved,
            "total_archived": total_archived,
            "total_budget": sum(company['monthly_budget'] for company in companies)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        release_db_connection(conn)


@app.get("/home", response_class=HTMLResponse)
def home(request: Request, user: dict = Depends(get_current_user)):
    # Fetch companies with accurate strategy counts
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
    total_strategies = 0
    total_approved = 0
    total_archived = 0
    
    for row in cursor.fetchall():
        monthly_budget = float(row[3]) if row[3] is not None else 0
        strategy_count = row[4] or 0
        approved_count = row[5] or 0
        archived_count = row[6] or 0
        
        total_strategies += strategy_count
        total_approved += approved_count
        total_archived = total_strategies-total_approved
        
        companies.append({
            "id": row[0],
            "name": row[1],
            "created_at": row[2].strftime("%Y-%m-%d"),
            "monthly_budget": monthly_budget,
            "strategy_count": strategy_count,
            "approved_count": approved_count,
            "archived_count": archived_count
        })
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "companies": companies,
        "total_strategies": total_strategies,
        "total_approved": total_approved,
        "total_archived": total_archived,
        "total_budget": sum(company['monthly_budget'] for company in companies)
    })



#Insights :

# Simple endpoints that won't block
@app.get("/get_facebook_analytics")
async def get_facebook_analytics_endpoint(
    days: int = Query(default=30, ge=1, le=90),
    user: dict = Depends(get_current_user)
):
    return await get_facebook_analytics(user["user_id"], cursor, days)

@app.get("/get_instagram_analytics")
async def get_instagram_analytics_endpoint(
    days: int = Query(default=14, ge=1, le=90),
    user: dict = Depends(get_current_user)
):
    return await get_instagram_analytics(user["user_id"], cursor, days)

@app.get("/get_linkedin_analytics")
async def get_linkedin_analytics_endpoint(
    days: int = Query(default=30, ge=1, le=90),
    user: dict = Depends(get_current_user)
):
    return await get_linkedin_analytics(user["user_id"], days)





# Route for the loading page
@app.get("/strategy/new/{company_id}", response_class=HTMLResponse)
def new_strategy_page(request: Request, company_id: int, user: dict = Depends(get_current_user)):
    # Check if company belongs to user
    cursor.execute("SELECT name FROM companies WHERE id = %s AND user_id = %s", (company_id, user["user_id"]))
    company = cursor.fetchone()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Pass company details for loading page
    return templates.TemplateResponse("strategy.html", {
        "request": request,
        "user": user,
        "company_id": company_id,
        "company_name": company[0],
        "should_generate": True
    })









#---------------------------------------------------------------------------------------



def format_events_text(events):
    if not events:
        return "No upcoming events identified"
    text = "\nUPCOMING EVENTS:\n"
    for event in events:
        text += f"- {event['title']} ({event['date']}): Participation recommendations...\n"
    return text



#---------------------------------------------------------------------------------------



# === Strategy Generation ===
from components.strategies.prompts.marketing_calendar import generate_marketing_calendar
from components.strategies.prompts.digital_marketing import generate_platform_strategies,save_content_items_to_db
from components.strategies.prompts.executive_summary import generate_executive_summary
from components.strategies.prompts.maketing_advices_tips import generate_advices_and_tips
from components.strategies.prompts.influencer_email_marketing import generate_influencer_recommendations,extract_and_save_influencers
from components.strategies.prompts.marketing_budget_plan import generate_budget_plan
from components.strategies.prompts.events_marketing_collabs import generate_event_strategy

@app.post("/generate_strategy/{company_id}")
async def generate_strategy(company_id: int, user: dict = Depends(get_current_user)):
    # Format target audience - NOW INCLUDES GEOGRAPHICS
    # Web Scraping for events
    scrape_task = asyncio.create_task(scrape_events_data(company_id))
    relevant_events = get_relevant_events(company_id)
    
    
    # Format events text
    events_text = format_events_text(relevant_events)
    
    try:
        await asyncio.wait_for(scrape_task, timeout=10) 
        relevant_events = get_relevant_events(company_id)
    except asyncio.TimeoutError:
        logger.warning("Event scraping timed out, using existing events")
    
    try:
        # Get company data
        cursor.execute("""
            SELECT id, name, slogan, description, website, phone_number, products, services,
                   marketing_goals, target_age_groups, target_audience_types,
                   target_business_types, target_geographics, preferred_platforms, 
                   special_events, brand_tone, monthly_budget, logo_url
            FROM companies WHERE id = %s AND user_id = %s
        """, (company_id, user["user_id"]))
        
        company = cursor.fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        company_data = {
            'id': company[0],
            'name': company[1],
            'slogan': company[2],
            'description': company[3],
            'website' :company[4],
            'phone_number' :company[5],
            'products': company[6],
            'services': company[7],
            'marketing_goals': company[8],
            'target_age_groups': company[9],
            'target_audience_types': company[10],
            'target_business_types': company[11],
            'target_geographics': company[12],
            'preferred_platforms': company[13],
            'special_events': company[14],
            'brand_tone': company[15],
            'monthly_budget': company[16],
            'logo_url': company[17]
        }
            # Format target audience - NOW INCLUDES GEOGRAPHICS
    # Format target audience
        target_audience = f"""
        - Age Groups: {company_data.get('target_age_groups', 'Not specified')}
        - Audience Types: {company_data.get('target_audience_types', 'Not specified')}
        - Business Types: {company_data.get('target_business_types', 'Not specified')}
        - Geographic Targets: {company_data.get('target_geographics', 'Not specified')}
        """
        # Get additional data
        current_date = datetime.now()
        logo_description = get_logo_description(company_data['logo_url']) if company_data['logo_url'] else ""
        relevant_events = get_relevant_events(company_id)
        
        # Generate each section
      
        print("Generating executive summary")
        executive_summary = generate_executive_summary(company_data, current_date, logo_description)
        print("Done executive summary")
 
        
        print("Generating budget plan")
        budget_plan = generate_budget_plan(company_data, current_date, relevant_events)
        print("Done budget plan")
        

        
        print("Generating event marketing")
        events_marketing = generate_event_strategy(company_data, events_text, current_date)
        print("Done event marketing")
        

        
        print("Generating content calendar")
        content_calendar = generate_marketing_calendar(company_data, current_date, logo_description, company_id)
        print("Done content calendar")
  
        
        print("Generating influencer recommendations")
        influencer_section = generate_influencer_recommendations(
            company_data,
            target_audience,
            company_data['products'],
            company_data['services']
        )
        print("Done influencer recommendations")
        

        print("Generating platform strategies")
        platform_strategies = generate_platform_strategies(company_data, current_date, logo_description)
        print("Done platform strategies")
        

        
        print("Generating advice and tips")
        advices_tips = generate_advices_and_tips(company_data, current_date, logo_description)
        print("Done advice and tips")
        
        
        # Combine all sections
        full_strategy = f"""
        <div class="marketing-strategy">
            {executive_summary}
            {budget_plan}
            {content_calendar}
            {events_marketing}
            {influencer_section}
            {platform_strategies}
            {advices_tips}
        </div>
        """
        
        # Save to database
        cursor.execute("""
            INSERT INTO strategies (company_id, content, created_at, status)
            VALUES (%s, %s, NOW(), 'new')
            RETURNING id
        """, (company_id, full_strategy))
        
        strategy_id = cursor.fetchone()[0]
        
        conn.commit()
        
        return RedirectResponse(url=f"/strategy/{strategy_id}", status_code=303)
        
        #return {
        #    "redirect_url": f"/strategy/{strategy_id}"
        #}
        
    except Exception as e:
        logger.error(f"Strategy generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === View Strategy Page ===
@app.get("/strategy/{strategy_id}", response_class=HTMLResponse)
def view_strategy(request: Request, strategy_id: int, user: dict = Depends(get_current_user)):
    cursor.execute("""
        SELECT s.id, s.content, s.created_at, s.status, s.approved_at, s.archived_at,
            c.id as company_id, c.name as company_name
        FROM strategies s
        JOIN companies c ON s.company_id = c.id
        WHERE s.id = %s AND c.user_id = %s
    """, (strategy_id, user["user_id"]))

    
    strategy = cursor.fetchone()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy_dict = {
        "id": strategy[0],
        "content": strategy[1], 
        "created_at": strategy[2],
        "status": strategy[3],
        "approved_at": strategy[4],
        "archived_at": strategy[5],
        "company_id": strategy[6],
        "company_name": strategy[7]
    }
    
    
    return templates.TemplateResponse("strategy.html", {
        "request": request,
        "user": user,
        "strategy": strategy_dict
    })



#New
# New endpoint to approve strategy
@app.post("/approve_strategy/{strategy_id}")
async def approve_strategy(request: Request, strategy_id: int, user: dict = Depends(get_current_user)):
    # First get the strategy content before archiving others
    cursor.execute("""
        SELECT id, content, company_id FROM strategies 
        WHERE id = %s
    """, (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    
    # --------------- New Email ------------------ 
        # Get the form data which includes edited emails
    form_data = await request.form()
    
    # Debug: Print all form data
    print("=== FORM DATA DEBUG ===")
    for key, value in form_data.items():
        print(f"{key}: {len(str(value))} characters - {str(value)[:100]}...")
    print("=== END DEBUG ===")
    
    # Parse the original strategy content
    soup = BeautifulSoup(strategy[1], 'html.parser')
    
    # Update ALL email textareas with the form data
    email_textareas = soup.find_all('textarea', class_='editable-email')
    print(f"Found {len(email_textareas)} textareas in HTML")
    
    for idx, textarea in enumerate(email_textareas):
        email_key = f"email_{idx}"
        if email_key in form_data:
            print(f"Updating textarea {idx} with {len(form_data[email_key])} characters")
            # Clear and update textarea content
            textarea.clear()
            from bs4 import NavigableString
            textarea.append(NavigableString(form_data[email_key]))
        else:
            print(f"No form data found for {email_key}")
    
    # Get the updated strategy content
    updated_strategy_content = str(soup)
    
    # --------------------------------------------
    
    
    # Extract image prompts from strategy content
    #strategy_content = strategy[1]
    image_prompts = extract_image_prompts(updated_strategy_content)
    
    # Archive any existing approved strategy for this company
    cursor.execute("""
        UPDATE strategies 
        SET status = 'denied - archived', archived_at = NOW()
        WHERE company_id = %s 
        AND status = 'approved'
    """, (strategy[2],))
    
    # Then approve the selected strategy
    cursor.execute("""
        UPDATE strategies 
        SET content = %s, status = 'approved', approved_at = NOW()
        WHERE id = %s
        RETURNING company_id
    """, (updated_strategy_content, strategy_id))
    
    company_id = cursor.fetchone()[0]
    
    # Now save the content items to database
    save_content_items_to_db(strategy_id, company_id, user["user_id"], updated_strategy_content)
    
    # Save extracted image prompts
    for prompt_type, prompt_text in image_prompts.items():
        cursor.execute("""
            INSERT INTO image_prompts (strategy_id, company_id, user_id, prompt_text, prompt_type)
            VALUES (%s, %s, %s, %s, %s)
        """, (strategy_id, company_id, user["user_id"], prompt_text, prompt_type))
        
    # Extract and save influencers - using strategy_content instead of full_strategy
    print("About to extract influencers...")
    extract_and_save_influencers(strategy_id, company_id, user["user_id"], updated_strategy_content)
    
    conn.commit()
    
    return RedirectResponse(url=f"/company/{company_id}", status_code=303)





# New endpoint to generate alternative strategy
@app.post("/archive_and_regenerate/{strategy_id}")
def archive_and_regenerate(strategy_id: int, user: dict = Depends(get_current_user)):
    # Archive the current strategy
    cursor.execute("""
        UPDATE strategies 
        SET status = 'denied - archived', archived_at = NOW()
        WHERE id = %s AND company_id IN (
            SELECT id FROM companies WHERE user_id = %s
        )
        RETURNING company_id
    """, (strategy_id, user["user_id"]))
    
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    company_id = result[0]
    conn.commit()
    
    return RedirectResponse(url=f"/strategy/new/{company_id}", status_code=303)



# === Edit Strategy Page ===
@app.get("/edit_strategy/{strategy_id}", response_class=HTMLResponse)
def edit_strategy_form(request: Request, strategy_id: int, user: dict = Depends(get_current_user)):
    cursor.execute("""
        SELECT s.id, s.content, s.created_at, c.id as company_id, c.name as company_name
        FROM strategies s
        JOIN companies c ON s.company_id = c.id
        WHERE s.id = %s AND c.user_id = %s
    """, (strategy_id, user["user_id"]))
    
    strategy = cursor.fetchone()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy_dict = {
        "id": strategy[0],
        "content": strategy[1],
        "created_at": strategy[2].strftime("%Y-%m-%d %H:%M"),
        "company_id": strategy[3],
        "company_name": strategy[4]
    }
    
    return templates.TemplateResponse("edit_strategy.html", {
        "request": request,
        "user": user,
        "strategy": strategy_dict
    })

@app.post("/update_strategy/{strategy_id}")
def update_strategy(
    strategy_id: int,
    content: str = Form(...),
    user: dict = Depends(get_current_user)
):
    # Check if strategy belongs to user
    cursor.execute("""
        SELECT s.id
        FROM strategies s
        JOIN companies c ON s.company_id = c.id
        WHERE s.id = %s AND c.user_id = %s
    """, (strategy_id, user["user_id"]))
    
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    cursor.execute("UPDATE strategies SET content = %s WHERE id = %s", (content, strategy_id))
    conn.commit()
    
    return RedirectResponse(url=f"/strategy/{strategy_id}", status_code=303)

# === Delete Strategy ===
@app.post("/delete_strategy/{strategy_id}")
def delete_strategy(strategy_id: int, user: dict = Depends(get_current_user)):
    # Check if strategy belongs to user and get company_id
    cursor.execute("""
        SELECT s.id, c.id as company_id
        FROM strategies s
        JOIN companies c ON s.company_id = c.id
        WHERE s.id = %s AND c.user_id = %s
    """, (strategy_id, user["user_id"]))
    
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    company_id = result[1]
    
    cursor.execute("DELETE FROM strategies WHERE id = %s", (strategy_id,))
    conn.commit()
    
    return RedirectResponse(url=f"/company/{company_id}", status_code=303)










#Web Scraping

async def scrape_events_data(company_id: int):
    """Scrape events Data from website and store in database"""
    url = "https://www.discovertunisia.com/en/evenements"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        logger.info(f"Starting event scraping for company {company_id}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        event_rows = soup.select('div.view-content div.views-row')
        
        if not event_rows:
            logger.warning("No events found on the page")
            return 0
            
        events_added = 0
        today = datetime.now().date()
        
        for row in event_rows:
            try:
                # Extract event details
                title = row.select_one('div.field-title a')
                date_day = row.select_one('span.date-day')
                date_month = row.select_one('span.date-month')
                image = row.select_one('img[data-src]')
                link = row.select_one('div.field-title a')
                read_more = row.select_one('div.field-link-readmore a')
                
                if not (title and link):
                    continue
                    
                # Parse the date
                event_date = None
                day = date_day.get_text(strip=True) if date_day else None
                month = date_month.get_text(strip=True) if date_month else None
                
                month_map = {
                    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
                }
                
                if day and month and month.upper() in month_map:
                    current_year = today.year
                    month_num = month_map[month.upper()]
                    try:
                        event_date = datetime(current_year, month_num, int(day)).date()
                        # If event date is in past, skip it
                        if event_date < today:
                            continue
                    except ValueError:
                        continue
                
                # Insert event if it doesn't exist
                cursor.execute("""
                    INSERT INTO scraped_events (
                        company_id, title, event_date, date_day, date_month, 
                        image_url, event_url, read_more_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_id, event_url) DO NOTHING
                """, (
                    company_id,
                    title.get_text(strip=True),
                    event_date,
                    day,
                    month,
                    image['data-src'] if image else None,
                    'https://www.discovertunisia.com' + link['href'],
                    'https://www.discovertunisia.com' + read_more['href'] if read_more else None
                ))
                
                if cursor.rowcount > 0:
                    events_added += 1
                    
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                continue
                
        conn.commit()
        logger.info(f"Added {events_added} new events for company {company_id}")
        return events_added
        
    except Exception as e:
        logger.error(f"Error scraping events: {e}")
        return 0

def get_relevant_events(company_id: int, limit: int = 3) -> list:
    """Get relevant upcoming events for a company"""
    today = datetime.now().date()
    cursor.execute("""
        SELECT title, event_date, event_url
        FROM scraped_events
        WHERE company_id = %s AND (event_date >= %s OR event_date IS NULL)
        ORDER BY event_date ASC
        LIMIT %s
    """, (company_id, today, limit))
    
    events = []
    for title, event_date, event_url in cursor.fetchall():
        date_str = event_date.strftime("%Y-%m-%d") if event_date else "Date not specified"
        events.append({
            "title": title,
            "date": date_str,
            "url": event_url
        })
    
    return events




#Img Gen : 

# Initialize Together client
together_client = Together(api_key=LLAMA_API_KEY)

# Ensure the image directory exists
os.makedirs("/static/imgs/generated_campagin_img", exist_ok=True)

from image_analyzer import get_logo_description 
    
    
# Alternative version for testing - Use a public image URL instead
# Modified Instagram posting endpoint to use Cloudinary


def upload_image_to_cloudinary(image_data, public_id=None, resource_type="image"):
    """
    Upload media to Cloudinary and return its direct URL
    
    Args:
        image_data: Can be a file path, file-like object, or base64 string
        public_id: Optional custom public ID for the media
        resource_type: Type of resource ("image" or "video")
    
    Returns:
        Direct URL to the uploaded media
    """
    try:
        upload_result = cloudinary.uploader.upload(
            image_data,
            public_id=public_id,
            overwrite=True,
            resource_type=resource_type  # This now accepts either "image" or "video"
        )
        # Return the secure URL which is directly accessible
        return upload_result["secure_url"]
    except Exception as e:
        logger.error(f"Cloudinary upload error: {str(e)}")
        raise e
   

# Update the upload_video_to_cloudinary function to handle Cloudinary video format issues
# Update the upload_video_to_cloudinary function
def upload_video_to_cloudinary(file_path, public_id=None):
    """
    Upload a video file to Cloudinary with proper video settings
    """
    try:
        print(f"Uploading video to Cloudinary: {file_path}")      
        
        # Upload the video with proper video settings
        upload_result = cloudinary.uploader.upload(
            file_path,
            public_id=public_id,
            resource_type="video",
            overwrite=True,
            timeout=120,
            # Ensure proper video format
            format="mp4"
        )
        
        print(f"✅ Video uploaded successfully: {upload_result['secure_url']}")
        return upload_result['secure_url']
        
    except Exception as e:
        print(f"ERROR:Cloudinary video upload error: {str(e)}")
        raise e


#New
def extract_image_prompts(content):
    """Extract image prompts from strategy content"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    prompts = {}
    
    prompt_section = soup.find('section', class_='image-prompts')
    if prompt_section:
        for card in prompt_section.find_all('div', class_='prompt-card'):
            prompt_type = card.find('h3').get_text(strip=True)
            prompt_text = card.find('code').get_text(strip=True)
            prompts[prompt_type] = prompt_text
    
    return prompts


# Logo Description
@app.get("/analyze_logo/{company_id}")
def analyze_company_logo(company_id: int, user: dict = Depends(get_current_user)):
    # Get company logo URL
    cursor.execute("SELECT logo_url FROM companies WHERE id = %s AND user_id = %s", 
                  (company_id, user["user_id"]))
    company = cursor.fetchone()
    if not company or not company[0]:
        raise HTTPException(status_code=404, detail="Company or logo not found")
    
    logo_url = company[0]
    description = get_logo_description(logo_url)
    
    return {"logo_url": logo_url, "analysis": description}    
      
      
@app.get("/launch_strategy/{strategy_id}", response_class=HTMLResponse)
def launch_strategy_page(request: Request, strategy_id: int, user: dict = Depends(get_current_user)):
    # Get strategy and associated company info
    cursor.execute("""
        SELECT s.id, s.company_id, c.name as company_name, c.logo_url
        FROM strategies s
        JOIN companies c ON s.company_id = c.id
        WHERE s.id = %s AND c.user_id = %s AND s.status = 'approved'
    """, (strategy_id, user["user_id"]))
    
    strategy = cursor.fetchone()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found or not approved")

    # Get Instagram content items grouped by type
    cursor.execute("""
        SELECT id, content_type, caption, hashtags, image_prompt, 
               video_idea, video_placeholder, story_idea
        FROM content_items 
        WHERE strategy_id = %s AND platform = 'Instagram'
        ORDER BY CASE 
            WHEN content_type = 'Feed Image Posts' THEN 1
            WHEN content_type = 'Instagram Stories' THEN 2
            WHEN content_type = 'Instagram Reels' THEN 3
            ELSE 4
        END
    """, (strategy_id,))
    
    content_items = {
        'feed_posts': [],
        'stories': [],
        'reels': []
    }
    
    for row in cursor.fetchall():
        item = {
            "id": row[0],
            "type": row[1],
            "caption": row[2],
            "hashtags": row[3],
            "image_prompt": row[4],
            "video_idea": row[5],
            "video_placeholder": row[6],
            "story_idea": row[7]
        }
        
        if row[1] == 'Feed Image Posts':
            content_items['feed_posts'].append(item)
        elif row[1] == 'Instagram Stories':
            content_items['stories'].append(item)
        elif row[1] == 'Instagram Reels':
            content_items['reels'].append(item)

    # Get Facebook content items grouped by type
    cursor.execute("""
        SELECT id, content_type, caption, hashtags, image_prompt, 
               video_idea, video_placeholder, story_idea
        FROM content_items 
        WHERE strategy_id = %s AND platform = 'Facebook'
        ORDER BY CASE 
            WHEN content_type = 'Text Posts (Status Updates / Announcements)' THEN 1
            WHEN content_type = 'Image Posts' THEN 2
            WHEN content_type = 'Video Posts' THEN 3
            ELSE 4
        END
    """, (strategy_id,))
    
    facebook_content = {
        'text_posts': [],
        'image_posts': [],
        'video_posts': []
    }
    
    for row in cursor.fetchall():
        item = {
            "id": row[0],
            "type": row[1],
            "caption": row[2],
            "hashtags": row[3],
            "image_prompt": row[4],
            "video_idea": row[5],
            "video_placeholder": row[6],
            "story_idea": row[7]
        }
        
        if row[1] == 'Text Posts (Status Updates / Announcements)':
            facebook_content['text_posts'].append(item)
        elif row[1] == 'Image Posts':
            facebook_content['image_posts'].append(item)
        elif row[1] == 'Video Posts':
            facebook_content['video_posts'].append(item)
    
    return templates.TemplateResponse("launch_strategy.html", {
        "request": request,
        "user": user,
        "strategy": {
            "id": strategy[0],
            "company_id": strategy[1],
            "company_name": strategy[2],
            "logo_url": strategy[3]
        },
        "content_items": content_items,  # Keep this for backward compatibility
        "instagram_content": content_items,  # Same as content_items
        "facebook_content": facebook_content
    })
 
    
    

# ---------- Universal Frame Builder ----------
import io
import os
import cv2
import uuid
import numpy as np
import requests
import tempfile
import shutil
from typing import Optional, List, Tuple
from collections import Counter
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont, ImageOps
from sklearn.cluster import KMeans
import replicate
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

# Set up Replicate API token
os.environ['REPLICATE_API_TOKEN'] = "r8_1kslnW8cJhxvkVjomgq4hlW5LNFvc8g4XHo8T"

class UniversalSocialFramer:
    """
    Builds frames for social media posts with dynamic colors from logo:
    - Dynamic canvas sizes based on platform
    - Side rails using dominant logo color (optional based on platform)
    - White content area
    - Logo placement
    - Text overlay with drop shadow on main image with rounded corners
    - All images with rounded corners
    """
    def __init__(self):
        # Initialize color variables (will be set from logo analysis)
        self.BRAND_ColorDom = None   # Dominant color from logo
        self.BRAND_ColorSec = None   # Secondary color from logo
        self.additional_colors = []  # For logos with more than 2 colors
        self.TEXT_DARK = (60, 60, 60, 255)     # dark gray for text
        self.TEXT_LIGHT = (120, 120, 120, 255) # light gray for subtle text
        self.CORNER_RADIUS = 15      # 15px rounded corners

    # -------- Platform-specific dimensions --------
    def get_platform_dimensions(self, platform, content_type):
        """Return appropriate dimensions for each platform and content type"""
        if platform == "Instagram":
            if content_type in ["feed", "Feed Image Posts"]:
                return (1080, 1080)  # Square 1:1
            elif content_type == "Instagram Stories":
                return (1080, 1920)  # Vertical 9:16
        elif platform == "Facebook":
            if content_type == "Image Posts":
                return (1200, 1500)  # 4:5 aspect ratio
        elif platform == "LinkedIn":
            if content_type == "LinkedIn Image Posts":
                return (1200, 1350)  # Portrait
        
        # Default to square if no specific dimensions found
        return (1200, 1200)

    # -------- Color Detection Utilities --------
    def _get_dominant_colors(self, img: Image.Image, num_colors: int = 3) -> List[Tuple[int, int, int, int]]:
        """Extract dominant colors from logo using K-means clustering."""
        img = img.convert("RGBA")
        resize_factor = 100 / min(img.size)
        small_img = img.resize(
            (int(img.width * resize_factor), int(img.height * resize_factor)),
            Image.Resampling.LANCZOS
        )
        
        arr = np.array(small_img)
        arr = arr.reshape((-1, 4))
        arr = arr[arr[:, 3] > 200]  # Filter out transparent pixels
        
        if len(arr) < num_colors:
            return [(0, 179, 173, 255), (44, 27, 71, 255)]  # Fallback colors
        
        rgb = arr[:, :3]
        kmeans = KMeans(n_clusters=num_colors, random_state=42)
        kmeans.fit(rgb)
        
        counts = Counter(kmeans.labels_)
        sorted_colors = sorted(
            [(color, count) for color, count in zip(kmeans.cluster_centers_, counts.values())],
            key=lambda x: -x[1]
        )
        
        return [(int(r), int(g), int(b), 255) for (r, g, b), _ in sorted_colors]

    def _set_colors_from_logo(self, logo_image: Image.Image):
        """Analyze logo and set color variables."""
        colors = self._get_dominant_colors(logo_image)
        
        if len(colors) >= 1:
            self.BRAND_ColorDom = colors[0]
        else:
            self.BRAND_ColorDom = (0, 179, 173, 255)  # Fallback teal
            
        if len(colors) >= 2:
            self.BRAND_ColorSec = colors[1]
        else:
            self.BRAND_ColorSec = (44, 27, 71, 255)  # Fallback purple
            
        if len(colors) > 2:
            self.additional_colors = colors[2:]

    # -------- Image Processing Utilities --------
    def _add_rounded_corners(self, img: Image.Image, radius: int = 15) -> Image.Image:
        """Add rounded corners to an image with transparency."""
        # Create a mask for rounded corners
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Draw white rounded rectangle on black background
        draw.rounded_rectangle([(0, 0), img.size], radius, fill=255)
        
        # Apply the mask to the image
        result = img.copy()
        result.putalpha(mask)
        
        return result

    # -------- Advanced Text Overlay with Multiple Enhancement Techniques --------
    def _add_text_with_drop_shadow(self, frame: Image.Image, x: int, y: int, width: int, height: int, text: str, 
                                   text_color: tuple = (255, 255, 255, 255), 
                                   shadow_color: tuple = (0, 0, 0, 176),
                                   shadow_offset: tuple = (5, 5),
                                   shadow_blur: int = 3,
                                   overlay_opacity: float = 0.10):
        """
        Add text with multiple enhancement techniques for maximum visibility:
        - Light overlay background with rounded corners
        - Multiple shadow layers for depth
        - Thick black stroke outline
        - Subtle background glow
        - Enhanced font weight
        """
        # Create overlay that matches the frame size
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Draw light overlay with rounded corners covering the fitted image area
        # Color #F1EEE9 converted to RGB
        overlay_color = (241, 238, 233, int(255 * overlay_opacity))
        overlay_draw.rounded_rectangle(
            [x, y, x + width, y + height], 
            radius=self.CORNER_RADIUS,
            fill=overlay_color
        )
        
        # Composite overlay onto frame first
        frame_with_overlay = Image.alpha_composite(frame.convert("RGBA"), overlay)
        frame.paste(frame_with_overlay, (0, 0))
        
        # Calculate font size based on image dimensions
        base_font_size = max(32, min(width, height) // 18)
        font = self.get_font(base_font_size, bold=True)
        
        # Create a temporary image for all text effects
        temp_img = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Get text dimensions for centering
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Calculate text position (centered in the fitted image area)
        text_x = x + (width - text_width) // 2
        text_y = y + (height - text_height) // 2
        
        # Layer 1: Create a subtle background glow (large blur)
        glow_color = (0, 0, 0, 120)
        for glow_offset in [(0, 0), (2, 2), (-2, -2), (2, -2), (-2, 2)]:
            glow_x = text_x + glow_offset[0]
            glow_y = text_y + glow_offset[1]
            temp_draw.text((glow_x, glow_y), text, font=font, fill=glow_color)
        
        # Apply heavy blur for glow effect
        temp_img = temp_img.filter(ImageFilter.GaussianBlur(radius=8))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Layer 2: Multiple shadow layers for depth
        shadow_layers = [
            ((7, 7), (0, 0, 0, 180), 5),    # Far shadow
            ((5, 5), (0, 0, 0, 200), 3),    # Mid shadow
            ((3, 3), (0, 0, 0, 220), 2),    # Near shadow
        ]
        
        for offset, color, blur in shadow_layers:
            shadow_temp = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_temp)
            
            shadow_x = text_x + offset[0]
            shadow_y = text_y + offset[1]
            shadow_draw.text((shadow_x, shadow_y), text, font=font, fill=color)
            
            if blur > 0:
                shadow_temp = shadow_temp.filter(ImageFilter.GaussianBlur(radius=blur))
            
            temp_img = Image.alpha_composite(temp_img, shadow_temp)
        
        # Redraw on the composite for final text
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Layer 3: Heavy black stroke outline for maximum contrast
        stroke_width = max(3, base_font_size // 12)
        stroke_color = (0, 0, 0, 255)
        
        # Draw thick outline by drawing text multiple times in a circle pattern
        outline_positions = []
        for angle in range(0, 360, 30):  # Every 30 degrees for smooth outline
            import math
            offset_x = int(stroke_width * math.cos(math.radians(angle)))
            offset_y = int(stroke_width * math.sin(math.radians(angle)))
            outline_positions.append((text_x + offset_x, text_y + offset_y))
        
        # Draw all outline positions
        for pos in outline_positions:
            temp_draw.text(pos, text, font=font, fill=stroke_color)
        
        # Layer 4: Additional stroke using PIL's built-in stroke (if available)
        temp_draw.text((text_x, text_y), text, font=font, fill=stroke_color, 
                      stroke_width=stroke_width, stroke_fill=stroke_color)
        
        # Layer 5: Final white text on top
        enhanced_text_color = (255, 255, 255, 255)  # Pure white for maximum contrast
        temp_draw.text((text_x, text_y), text, font=font, fill=enhanced_text_color)
        
        # Apply slight sharpening to make text crisp
        temp_img = temp_img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=2))
        
        # Composite the enhanced text onto the frame
        frame_with_text = Image.alpha_composite(frame.convert("RGBA"), temp_img)
        
        # Update the frame in place
        frame.paste(frame_with_text, (0, 0))

    # -------- Utilities --------
    def download_image(self, url: str) -> Image.Image:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        return img.convert("RGBA")

    def _fit_inside_box(self, img: Image.Image, box_w: int, box_h: int) -> Image.Image:
        """Resize img to fit within (box_w, box_h) preserving aspect ratio."""
        iw, ih = img.size
        img_ratio = iw / ih
        box_ratio = box_w / box_h

        if img_ratio > box_ratio:
            new_w = box_w
            new_h = int(new_w / img_ratio)
        else:
            new_h = box_h
            new_w = int(new_h * img_ratio)

        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    def get_font(self, size: int = 20, bold: bool = False):
        """Get default font with fallbacks"""
        try:
            return ImageFont.truetype("arial.ttf" if not bold else "arialbd.ttf", size)
        except:
            try:
                return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
            except:
                return ImageFont.load_default()

    # -------- Frame builder --------
    def build_frame_with_elements(
        self,
        main_image: Image.Image,
        logo_image: Image.Image,
        platform: str,
        content_type: str,
        company_id: int,  # Add company_id parameter
        overlay_text: str = " ",
        rail_w: int = 44,
        top_margin: int = 20,
        bottom_margin: int = 60,
        inner_pad_x: int = 40,
    ) -> Image.Image:
        """Create complete framed post with dynamic colors from logo."""
        # First analyze the logo to set our brand colors
        self._set_colors_from_logo(logo_image)
        
        # Get platform-specific dimensions
        W, H = self.get_platform_dimensions(platform, content_type)
        frame = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        draw = ImageDraw.Draw(frame)

        # Add side rails for LinkedIn and Facebook, but not for Instagram Stories
        if platform != "Instagram" or content_type != "Instagram Stories":
            draw.rectangle((0, 0, rail_w, H), fill=self.BRAND_ColorDom)
            draw.rectangle((W - rail_w, 0, W, H), fill=self.BRAND_ColorDom)

        # Calculate content area
        logo_height_space = 160  # Fixed height for logo area (like original test code)
        content_x = rail_w + inner_pad_x if platform != "Instagram" or content_type != "Instagram Stories" else inner_pad_x
        content_y = top_margin + logo_height_space
        content_w = W - 2 * (rail_w + inner_pad_x) if platform != "Instagram" or content_type != "Instagram Stories" else W - 2 * inner_pad_x
        content_h = H - content_y - bottom_margin - 40

        # Prepare and fit main image with rounded corners
        main_rgba = main_image.convert("RGBA")
        fitted_main = self._fit_inside_box(main_rgba, content_w, content_h)
        fitted_main = self._add_rounded_corners(fitted_main, self.CORNER_RADIUS)

        # Paste main image centered
        main_paste_x = content_x + (content_w - fitted_main.width) // 2
        main_paste_y = content_y + (content_h - fitted_main.height) // 2
        frame.paste(fitted_main, (main_paste_x, main_paste_y), fitted_main)

        # Add light overlay with enhanced text visibility (skip for Instagram Stories)
        if overlay_text and (platform != "Instagram" or content_type != "Instagram Stories"):
            self._add_text_with_drop_shadow(
                frame, 
                main_paste_x, 
                main_paste_y, 
                fitted_main.width, 
                fitted_main.height, 
                overlay_text,
                text_color=(255, 255, 255, 255),  # Pure white text
                shadow_color=(0, 0, 0, 176),      # Strong black shadow
                shadow_offset=(5, 5),             # Larger shadow offset
                shadow_blur=3,                    # More shadow blur
                overlay_opacity=0.10              # Light overlay opacity
            )

        # Add logo to top-left (skip for Instagram Stories to avoid clutter)
        if platform != "Instagram" or content_type != "Instagram Stories":
            # Make logo bigger like in the original test code
            max_logo_w = int(W * 0.55)  # 55% of width (like original test code)
            max_logo_h = logo_height_space
            logo_rgba = logo_image.convert("RGBA")
            logo_fitted = self._fit_inside_box(logo_rgba, max_logo_w, max_logo_h)
            logo_x = rail_w + inner_pad_x if platform != "Instagram" or content_type != "Instagram Stories" else inner_pad_x
            frame.paste(logo_fitted, (logo_x, top_margin), logo_fitted)

        # Add website in bottom right (skip for Instagram Stories)
        if platform != "Instagram" or content_type != "Instagram Stories":
            bottom_y = H - bottom_margin + 10
            website_font = self.get_font(30)  # Larger font like original
            # website_text = "nearshorepublic.com"
            # Get website from database
            cursor.execute("SELECT website FROM companies WHERE id = %s", (company_id,))
            company_data = cursor.fetchone()
            website_text = company_data[0] if company_data and company_data[0] else "CompanySite.com"
    
            # Calculate position for right alignment
            bbox = draw.textbbox((0, 0), website_text, font=website_font)
            website_x = W - rail_w - inner_pad_x - (bbox[2] - bbox[0]) if platform != "Instagram" or content_type != "Instagram Stories" else W - inner_pad_x - (bbox[2] - bbox[0])
            draw.text((website_x, bottom_y), website_text, font=website_font, fill=self.BRAND_ColorDom)

        return frame

    # -------- High-level helper --------
    def create_post_from_images(
    self,
    main_image: Image.Image,
    logo_image: Image.Image,
    platform: str,
    content_type: str,
    company_id: int,  # Add company_id parameter
    overlay_text: str = " ",
    ) -> Image.Image:
        return self.build_frame_with_elements(main_image, logo_image, platform, content_type, company_id, overlay_text=overlay_text)

# Initialize the framer
universal_framer = UniversalSocialFramer()

# -------- Video Generation Functions --------
def download_logo(logo_url):
    """Download the logo from the provided URL"""
    try:
        print("Downloading logo...")
        response = requests.get(logo_url)
        response.raise_for_status()
        
        # Create a temporary file
        temp_logo = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        temp_logo.write(response.content)
        temp_logo.close()
        
        print("✅ Logo downloaded successfully!")
        return temp_logo.name
    except Exception as e:
        print(f"❌ Error downloading logo: {e}")
        return None

def add_background_music(video_path, audio_path, output_path):
    """Add background music to video using moviepy"""
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
        
        print("Adding background music...")
        
        # Load video and audio
        video = VideoFileClip(video_path)
        
        # Check if audio file exists
        if not os.path.exists(audio_path):
            print(f"⚠️  Audio file {audio_path} not found, continuing without background music")
            # If audio doesn't exist, just copy the video
            shutil.copy2(video_path, output_path)
            return False
        
        audio = AudioFileClip(audio_path)
        
        # Loop audio if video is longer, or trim if audio is longer
        if audio.duration < video.duration:
            # Loop the audio to match video length
            loops_needed = int(video.duration / audio.duration) + 1
            audio_list = [audio] * loops_needed
            from moviepy.editor import concatenate_audioclips
            audio = concatenate_audioclips(audio_list)
            audio = audio.subclip(0, video.duration)
        else:
            # Trim audio to match video length
            audio = audio.subclip(0, video.duration)
        
        # Set audio volume to 30% to not overpower original video audio
        audio = audio.volumex(0.3)
        
        # Combine original audio with background music (if original video has audio)
        if video.audio is not None:
            final_audio = CompositeAudioClip([video.audio, audio])
        else:
            final_audio = audio
        
        # Set audio to video
        final_video = video.set_audio(final_audio)
        
        # Write final video
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            threads=4,  # Use multiple threads for faster processing
            preset='fast'  # Faster encoding
        )
        
        # Clean up
        video.close()
        audio.close()
        final_video.close()
        
        print("✅ Background music added successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error adding background music: {e}")
        print("Continuing without background music...")
        # If audio fails, just copy the video without audio processing
        shutil.copy2(video_path, output_path)
        return False

def create_logo_frame(width, height, logo_path):
    """Create a frame with logo using PIL and OpenCV"""
    # Create white background
    img = Image.new('RGB', (width, height), color='white')
    
    try:
        # Load logo with transparency support
        logo = Image.open(logo_path)
        
        # Convert to RGBA if not already
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        # Resize logo to fit (max 40% of width)
        max_width = int(width * 0.4)
        max_height = int(height * 0.4)
        
        logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Center the logo
        x = (width - logo.width) // 2
        y = (height - logo.height) // 2
        
        # Paste logo onto white background with transparency support
        img.paste(logo, (x, y), logo)  # The third parameter handles transparency
        
    except Exception as e:
        print(f"Warning: Could not process logo: {e}")
    
    # Convert to OpenCV format
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def apply_fade_effect(frame, fade_type, progress):
    """Apply fade in/out effect to a frame"""
    if fade_type == "out":
        alpha = 1.0 - progress
    else:  # fade in
        alpha = progress
    
    # Create fade effect
    faded = frame * alpha
    return faded.astype(np.uint8)

# Update the create_enhanced_video function to fix flickering
def create_enhanced_video(original_video_path, logo_path, output_path):
    """Add fadeout and logo to the original video using OpenCV"""
    cap = None
    out = None
    
    try:
        print("Starting video post-processing...")
        
        # Open original video
        cap = cv2.VideoCapture(original_video_path)
        
        if not cap.isOpened():
            print("❌ Error: Could not open video file")
            return False
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video properties: {width}x{height} at {fps} FPS, {total_frames} frames")
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            print("❌ Error: Could not create output video")
            return False
        
        # Process original video frames with fadeout at the end
        frames_processed = 0
        fadeout_start_frame = max(0, total_frames - fps)  # Start fadeout 1 second before end
        
        print("Processing original video frames...")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frames_processed += 1
            
            # Apply fadeout to last second only
            if frames_processed >= fadeout_start_frame:
                fade_progress = (frames_processed - fadeout_start_frame) / min(fps, total_frames - fadeout_start_frame)
                frame = apply_fade_effect(frame, "out", fade_progress)
            
            out.write(frame)
        
        print("✅ Original video processed with fadeout")
        
        # Release the original video capture
        cap.release()
        
        # Add logo scene (2 seconds) if logo exists - ONLY AFTER original video
        if logo_path and os.path.exists(logo_path):
            print("Adding logo scene...")
            logo_frames = fps * 2  # 2 seconds of logo
            logo_frame = create_logo_frame(width, height, logo_path)
            
            for i in range(logo_frames):
                frame = logo_frame.copy()
                
                # Apply fade in for first 0.5 seconds and fade out for last 0.5 seconds
                if i < fps // 2:  # First 0.5 seconds fade in
                    progress = i / (fps // 2)
                    frame = apply_fade_effect(frame, "in", progress)
                elif i > logo_frames - fps // 2:  # Last 0.5 seconds fade out
                    progress = (logo_frames - i) / (fps // 2)
                    frame = apply_fade_effect(frame, "out", progress)
                else:
                    # Middle section - no fade effect
                    frame = logo_frame.copy()
                
                out.write(frame)
            
            print("✅ Logo scene added")
        else:
            print("⚠️  Logo not available, skipping logo scene")
        
        print(f"🎉 Enhanced video saved as '{output_path}'")
        return True
        
    except Exception as e:
        print(f"❌ Error during video post-processing: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        if cap:
            cap.release()
        if out:
            out.release()
        cv2.destroyAllWindows()

# Update the generate_video_with_logo function to include background music
def generate_video_with_logo(prompt, logo_url):
    """Generate a video with the given prompt and add logo branding"""
    try:
        print(f"Generating video with prompt: {prompt}")
        
        # Generate video using Replicate
        output = replicate.run(
            "minimax/video-01",
            input={"prompt": prompt}
        )
        
        # Get the video URL
        video_url = str(output)
        print(f"Video generated successfully: {video_url}")
        
        # Download the original video
        print("Downloading original video...")
        response = requests.get(video_url)
        response.raise_for_status()
        
        # Create temporary files
        original_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        with open(original_video_path, "wb") as file:
            file.write(response.content)
        
        print("✅ Original video downloaded!")
        
        # Download logo
        logo_path = download_logo(logo_url)
        
        # Create enhanced video with post-processing
        enhanced_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        success = create_enhanced_video(
            original_video_path, 
            logo_path, 
            enhanced_video_path
        )
        
        # Add background music if available
        final_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        bg_music_path = "./sounds/bg_music.mp3"  # Audio file in the same directory as main.py
        
        # Check if background music file exists
        if os.path.exists(bg_music_path):
            print("Adding background music...")
            add_background_music(enhanced_video_path, bg_music_path, final_video_path)
        else:
            print("⚠️  Background music file not found, proceeding without music")
            shutil.copy2(enhanced_video_path, final_video_path)
        
        # Clean up temporary files
        try:
            os.remove(original_video_path)
            os.remove(enhanced_video_path)
            if logo_path and os.path.exists(logo_path):
                os.remove(logo_path)
        except:
            pass
        
        if success:
            return final_video_path
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error generating video: {e}")
        import traceback
        traceback.print_exc()
        return None

# Image Drame Random generated Overlay Text :
async def generate_overlay_text(company_id: int) -> str:
    """
    Generate a dynamic 4-word overlay text based on company profile
    """
    try:
        print(f"[INFO] Generating overlay text for company_id: {company_id}")
        
        # Fetch company data from database
        cursor.execute("""
            SELECT name, slogan, description, products, services, 
                   target_age_groups, target_audience_types, target_business_types, 
                   target_geographics, preferred_platforms, special_events, 
                   brand_tone, monthly_budget, marketing_goals, logo_url
            FROM companies 
            WHERE id = %s
        """, (company_id,))
        
        company_data = cursor.fetchone()
        if not company_data:
            print(f"[WARNING] Company not found, using fallback text")
            return "Company not found"
        
        # Unpack company data
        (name, slogan, description, products, services, target_age_groups, 
         target_audience_types, target_business_types, target_geographics, 
         preferred_platforms, special_events, brand_tone, monthly_budget, 
         marketing_goals, logo_url) = company_data
        
        # Get logo description if available
        logo_description = get_logo_description(logo_url) if logo_url else "No logo"
        
        # Build target audience string
        target_audience = f"""
        - Age Groups: {target_age_groups or 'Not specified'}
        - Audience Types: {target_audience_types or 'Not specified'}
        - Business Types: {target_business_types or 'Not specified'}
        - Geographic Targets: {target_geographics or 'Not specified'}
        """
        
        # Create company profile for AI
        company_profile = f"""
        - COMPANY PROFILE - INFO: 
        {{
            "NAME": "{name}", 
            "SLOGAN": "{slogan or ''}",
            "DESCRIPTION": "{description or ''}",
            "PRODUCTS": "{products or ''}",
            "SERVICES": "{services or ''}",
            "TARGET AUDIENCE": {target_audience},
            "PLATFORMS": "{preferred_platforms or ''}",
            "SPECIAL EVENTS": "{special_events or ''}", 
            "BRAND TONE": "{brand_tone or ''}",
            "BUDGET": "{monthly_budget or ''}",
            "MARKETING GOALS": "{marketing_goals or ''}",
            "LOGO": "{logo_url or 'No logo'}",
            "LOGO Description": "{logo_description}"
        }}
        """
        
        # Create AI prompt
        prompt = f"""
        Based on the following company profile, generate a compelling 4-word overlay text for a social media post image.

        {company_profile}

        Requirements:
        - EXACTLY 4 words maximum
        - Catchy and engaging
        - Reflects the company's brand and services
        - Suitable for social media overlay
        - Professional but memorable
        - Action-oriented when possible

        Generate only the 4-word text, nothing else.
        """
        
        # Call OpenAI API
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.6,
            max_completion_tokens=512,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            stop=None
        )
        
        # Extract and clean the response
        overlay_text = completion.choices[0].message.content.strip()
        
        # Validate the response (ensure it's roughly 4 words)
        words = overlay_text.split()
        if len(words) > 6:  # Allow some flexibility but cap it
            overlay_text = " ".join(words[:4])
        
        print(f"[INFO] Generated overlay text: '{overlay_text}'")
        return overlay_text
        
    except Exception as e:
        print(f"[ERROR] Failed to generate overlay text: {str(e)}")
        # Fallback to default text
        return "Error"


# -------- API Endpoint --------
@app.post("/generate_for_post_type/{content_id}")
async def generate_for_post_type(content_id: int, user: dict = Depends(get_current_user)):
    print(f"\n[INFO] Starting content generation for content_id: {content_id}")
    
    try:
        # Get content item details including platform
        print("[INFO] Fetching content details from database...")
        cursor.execute("""
            SELECT ci.platform, ci.content_type, ci.image_prompt, ci.video_placeholder, 
                   ci.caption, ci.hashtags, c.id as company_id, c.name as company_name, c.logo_url
            FROM content_items ci
            JOIN companies c ON ci.company_id = c.id
            WHERE ci.id = %s AND ci.user_id = %s
        """, (content_id, user["user_id"]))
        
        content_data = cursor.fetchone()
        if not content_data:
            print(f"[ERROR] Content not found for content_id: {content_id}")
            raise HTTPException(status_code=404, detail="Content not found")
        
        platform, content_type, image_prompt, video_placeholder, caption, hashtags, company_id, company_name, logo_url = content_data
        print(f"[INFO] Platform: {platform}, Content type: {content_type}, Company: {company_name}")
        
        media_url = None
        
        # Define platform-specific aspect ratio prompts
        aspect_ratio_prompts = {
            "Instagram": {
                "feed": "Square aspect ratio (1:1)",
                "Feed Image Posts": "Square aspect ratio (1:1)",
                "Instagram Stories": "Vertical aspect ratio (9:16)",
                "Story": "Vertical aspect ratio (9:16)",
                "Stories": "Vertical aspect ratio (9:16)",
                "Instagram Reels": "Vertical aspect ratio (9:16)",
                "Reel": "Vertical aspect ratio (9:16)"
            },
            "Facebook": {
                "Image Posts": "4:5 aspect ratio",
                "Video Posts": "4:5 aspect ratio",
                "Facebook Image Posts": "4:5 aspect ratio",
            },
            "LinkedIn": {
                "LinkedIn Image Posts": "Portrait aspect ratio (4:5)",
                "Video Posts": "Portrait aspect ratio (4:5)",
                "LinkedIn Video Posts": "Portrait aspect ratio (4:5)",
            }
        }
        
        # Get the appropriate aspect ratio prompt
        aspect_prompt = aspect_ratio_prompts.get(platform, {}).get(content_type, "")
        
        if platform in ['Instagram', 'Facebook', 'Linkedin','instagram', 'facebook', 'linkedin','FaceBook', 'LinkedIn'] and content_type in ['feed', 'Stories', 'Story', 'Image', 'Feed Image Posts', 'Instagram Stories', 'Image Posts', 'LinkedIn Image Posts','Facebook Image Posts']:
            print(f"[INFO] Generating {platform} {content_type} image...")
            logo_description = get_logo_description(logo_url) if logo_url else ""
            
            # Generate dynamic overlay text
            dynamic_overlay_text = await generate_overlay_text(company_id)
            
            # Add platform-specific aspect ratio to the prompt
            enhanced_prompt = f"{image_prompt} - IMPORTANT: {logo_description}. {aspect_prompt}"
            
            # Use different FLUX models based on aspect ratio needs
            flux_model = "black-forest-labs/FLUX.1-schnell-Free"
            
            response = together_client.images.generate(
                prompt=enhanced_prompt,
                model=flux_model,
                steps=4,
                n=1,
            )
            
            if not response.data:
                print("[ERROR] No image data received from API")
                return JSONResponse({"error": "No image data in response"}, status_code=500)
                
            first_image = response.data[0]
            
            if not hasattr(first_image, 'url') or not first_image.url:
                print("[ERROR] No image URL in response")
                return JSONResponse({"error": "No image URL in response"}, status_code=500)
            
            # Download the generated image
            img_response = requests.get(first_image.url)
            img_response.raise_for_status()
            
            # Load the generated image and logo
            generated_img = Image.open(io.BytesIO(img_response.content)).convert("RGBA")
            
            # Download the company logo
            logo_response = requests.get(logo_url)
            logo_response.raise_for_status()
            logo_img = Image.open(io.BytesIO(logo_response.content)).convert("RGBA")
            
            # Apply the universal frame
            framed_image = universal_framer.create_post_from_images(
                generated_img, 
                logo_img, 
                platform,
                content_type,
                company_id,  # Pass the company_id
                overlay_text = dynamic_overlay_text
            )
            
            # Save the framed image to a temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            filename = f"{platform.lower()}_{content_type.lower().replace(' ', '_')}_{company_id}_{timestamp}_{unique_id}.png"
            filepath = f"/static/imgs/generated_campagin_img/{filename}"
            
            framed_image.save(filepath, "PNG")
            
            # Verify the final image dimensions
            final_img = Image.open(filepath)
            expected_width, expected_height = universal_framer.get_platform_dimensions(platform, content_type)
            if final_img.size != (expected_width, expected_height):
                print(f"[WARNING] Final image size {final_img.size} doesn't match expected size {(expected_width, expected_height)}")
            
            # Upload to Cloudinary
            cloudinary_url = upload_image_to_cloudinary(
                filepath,
                public_id=f"{platform.lower()}_{content_type.lower().replace(' ', '_')}_{company_id}_{timestamp}_{unique_id}"
            )
            
            # Save the Cloudinary URL to database
            cursor.execute("""
                UPDATE content_items 
                SET media_link = %s
                WHERE id = %s
            """, (cloudinary_url, content_id))
            conn.commit()
            
            return JSONResponse({
                "image_url": cloudinary_url,
                "content_type": content_type.lower().replace(' ', '_'),
                "platform": platform.lower(),
                "dimensions": f"{expected_width}x{expected_height}"
            })
                
        elif content_type in ['Text Posts', 'Text Posts (Status Updates / Announcements)', 'Articles', 'Article', 'Text','Status']:
            print(f"[INFO] Generating {platform} Text Post...")
            # For text posts, we just return the caption and hashtags
            full_text = f"{caption}\n\n{hashtags}" if hashtags else caption
            
            return JSONResponse({
                "text_content": full_text,
                "content_type": "text",
                "platform": platform.lower()
            })
            
        # Then update the video section of your endpoint:
        # Update the video section of your endpoint to handle the Cloudinary URL properly
        # Update the video section of your endpoint to fix both issues
        # Update the video section of your endpoint
        elif content_type in ['Instagram Reels', 'Facebook Videos', 'Linkedin Videos','LinkedIn Videos', 'Reel', 'Reels', 'Video Post', 'Video Posts', 'Videos']:
            print(f"[INFO] Processing {platform} Video...")
            
            # Generate video using the video placeholder as prompt
            video_path = generate_video_with_logo(video_placeholder, logo_url)
            
            if not video_path:
                return JSONResponse({"error": "Failed to generate video"}, status_code=500)
            
            # Save the video locally first
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            filename = f"{platform.lower()}_{content_type.lower().replace(' ', '_')}_{company_id}_{timestamp}_{unique_id}.mp4"
            local_video_path = f"/static/vids/{filename}"
            
            # Copy the temporary video to our local storage
            shutil.copy2(video_path, local_video_path)
            print(f"✅ Video saved locally: {local_video_path}")
            
            # Upload to Cloudinary using the video-specific function
            public_id = f"{platform.lower()}_{content_type.lower().replace(' ', '_')}_{company_id}_{timestamp}_{unique_id}"
            cloudinary_url = None
            
            try:
                cloudinary_url = upload_video_to_cloudinary(local_video_path, public_id)
                print(f"✅ Video uploaded to Cloudinary: {cloudinary_url}")
                
                # Delete local video after successful Cloudinary upload
                try:
                    os.remove(local_video_path)
                    print(f"✅ Local video deleted after Cloudinary upload: {local_video_path}")
                except Exception as e:
                    print(f"⚠️  Could not delete local video: {e}")
                    
            except Exception as e:
                print(f"[ERROR] Failed to upload video to Cloudinary: {e}")
                # Use local path if Cloudinary fails
                cloudinary_url = f"/static/vids/{filename}"
            
            # Clean up temporary file
            try:
                os.remove(video_path)
            except Exception as e:
                print(f"⚠️  Could not delete temp video file: {e}")
            
            # Save the Cloudinary URL to database (not local path)
            try:
                cursor.execute("""
                    UPDATE content_items 
                    SET media_link = %s
                    WHERE id = %s
                """, (cloudinary_url, content_id))
                conn.commit()
                print(f"✅ Video URL saved to database: {cloudinary_url}")
            except Exception as e:
                print(f"❌ Failed to save video URL to database: {e}")
                return JSONResponse({"error": "Failed to save video URL to database"}, status_code=500)
            
            return JSONResponse({
                "video_url": cloudinary_url,  # This will be Cloudinary URL
                "content_type": "video",
                "platform": platform.lower(),
                "message": "Video generated successfully"
            })
            
        else:
            print(f"[ERROR] Unsupported platform: {platform}")
            return JSONResponse({"error": f"Unsupported platform: {platform}"}, status_code=400)
            
    except Exception as e:
        print(f"[ERROR] Content generation failed: {str(e)}")
        logger.error(f"Content generation error: {str(e)}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    
    
    
@app.post("/post_to_instagram/{company_id}")
async def post_to_instagram(
    company_id: int,
    content_id: int = Form(...),
    content_type: str = Form(...),
    filename: str = Form(None), 
    edited_caption: str = Form(None),  # Add this parameter
    user: dict = Depends(get_current_user)
):
    print(f"\n[INFO] Starting Instagram posting process for company_id: {company_id}")
    
    # Verify company belongs to user
    print("[INFO] Verifying company ownership...")
    cursor.execute("SELECT name FROM companies WHERE id = %s AND user_id = %s", (company_id, user["user_id"]))
    company = cursor.fetchone()
    if not company:
        print(f"[ERROR] Company not found or not owned by user: {company_id}")
        raise HTTPException(status_code=404, detail="Company not found")
    
    print(f"[INFO] Company verified: {company[0]}")
    
    try:
      
            
            
        if edited_caption:
                # Python-appropriate way to split caption and hashtags
            hashtags = re.findall(r'#\w+', edited_caption)
            clean_caption = re.sub(r'#\w+', '', edited_caption).strip()
                
            final_hashtags = ' '.join(hashtags) if hashtags else None

            cursor.execute("""
                    UPDATE content_items 
                    SET caption = %s, hashtags = %s
                    WHERE id = %s AND company_id = %s AND user_id = %s
                """, (clean_caption, final_hashtags, content_id, company_id, user["user_id"]))
            conn.commit()
                    
                
                
        # Instagram credentials
        print("[INFO] Setting up Instagram credentials...")
        instagram_account_id = '17841435754285253'
        # In production, this should be stored securely, not in code
        access_token = 'EAATo57EVzcIBOy2i7XFBHK79zrXAER9ZC6U8if1Sztc4EvMRCNwtvoKEsHQZBRhvFZCfZCiEZA9RSz9bZAG56oVmI6OqPSiLtmI6W7KZAZAXnnxWomtsiGcMuEntuSiyLyhWxBlOZBvMJtgJizep2WD4ZC2wU3YQPs31JZAZAOJzSeQd8kIPWlPIGesnf32x'
        
        # Get caption and hashtags
        print("[INFO] Fetching caption and hashtags...")
        cursor.execute("""
            SELECT caption, hashtags FROM content_items 
            WHERE id = %s AND company_id = %s AND user_id = %s
        """, (content_id, company_id, user["user_id"]))
        
        caption_data = cursor.fetchone()
        caption = ""
        if caption_data and caption_data[0]:
            caption = caption_data[0]
            if caption_data[1]:  # Add hashtags if they exist
                caption += f"\n\n{caption_data[1]}"
        
        print(f"[INFO] Caption prepared, length: {len(caption)} characters")
        
        success = False
        
        if content_type in ['feed', 'story']:
            # Handle image upload and posting
            image_path = f"/static/imgs/generated_campagin_img/{filename}"
            print(f"[INFO] Processing image at path: {image_path}")
            
            if not os.path.exists(image_path):
                print(f"[ERROR] Image file not found: {image_path}")
                return JSONResponse({"error": "Image file not found"}, status_code=404)
            
            print("[INFO] Uploading image to Cloudinary...")
            cloudinary_url = upload_image_to_cloudinary(
                image_path, 
                public_id=f"insta_{content_type}_{company_id}_{int(time.time())}"
            )
            print(f"[INFO] Image uploaded to Cloudinary successfully")
            
            if content_type == 'feed':
                print("[INFO] Publishing to Instagram feed...")
                success = publish_instagram_post(
                    account_id=instagram_account_id,
                    access_token=access_token,
                    image_url=cloudinary_url,
                    caption=caption
                )
            else:  # story
                print("[INFO] Publishing to Instagram story...")
                success = publish_instagram_story(
                    account_id=instagram_account_id,
                    access_token=access_token,
                    image_url=cloudinary_url
                )
                
        elif content_type == 'reel':
            # Post reel
            print("[INFO] Publishing Instagram reel...")
            success = publish_instagram_reel(
                account_id=instagram_account_id,
                access_token=access_token,
                video_url=filename,
                caption=caption
            )
        
        if success:
            print(f"[SUCCESS] Successfully posted {content_type} to Instagram!")
            return JSONResponse({
                "success": True,
                "message": f"Successfully posted {content_type} to Instagram!"
            })
        else:
            print(f"[ERROR] Failed to post {content_type} to Instagram")
            return JSONResponse({
                "error": f"Failed to post {content_type}"
            }, status_code=500)
            
    except Exception as e:
        print(f"[ERROR] Instagram posting failed: {str(e)}")
        logger.error(f"Instagram posting error: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)



def publish_instagram_post(account_id, access_token, image_url, caption):
    """Publish a regular post to Instagram"""
    # 1. Create Container
    create_container_url = f'https://graph.facebook.com/v22.0/{account_id}/media'
    payload = {
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token
    }
    
    container_response = requests.post(create_container_url, data=payload)
    container_data = container_response.json()
    
    if 'id' not in container_data:
        return False
    
    container_id = container_data['id']
    
    # 2. Publish Container
    publish_url = f'https://graph.facebook.com/v22.0/{account_id}/media_publish'
    publish_payload = {
        'creation_id': container_id,
        'access_token': access_token
    }
    
    time.sleep(5)  # Wait before publishing
    
    publish_response = requests.post(publish_url, data=publish_payload)
    publish_data = publish_response.json()
    
    return 'id' in publish_data

def publish_instagram_story(account_id, access_token, image_url):
    """Publish a story to Instagram"""
    create_container_url = f'https://graph.facebook.com/v22.0/{account_id}/media'
    
    payload = {
        'image_url': image_url,
        'media_type': 'STORIES',
        'access_token': access_token
    }
    
    container_response = requests.post(create_container_url, data=payload)
    container_data = container_response.json()
    
    if 'id' not in container_data:
        return False
    
    container_id = container_data['id']
    
    publish_url = f'https://graph.facebook.com/v22.0/{account_id}/media_publish'
    publish_payload = {
        'creation_id': container_id,
        'access_token': access_token
    }
    
    time.sleep(5)
    
    publish_response = requests.post(publish_url, data=publish_payload)
    publish_data = publish_response.json()
    
    return 'id' in publish_data

def publish_instagram_reel(account_id, access_token, video_url, caption, cover_url=None):
    """Publish a reel to Instagram"""
    create_container_url = f'https://graph.facebook.com/v22.0/{account_id}/media'
    
    payload = {
        'media_type': 'REELS',
        'video_url': video_url,
        'caption': caption,
        'access_token': access_token,
        'share_to_feed': True
    }
    
    if cover_url:
        payload['thumbnail_url'] = cover_url
    
    container_response = requests.post(create_container_url, data=payload)
    container_data = container_response.json()
    
    if 'id' not in container_data:
        return False
    
    container_id = container_data['id']
    
    # Check upload status
    status_url = f'https://graph.facebook.com/v22.0/{container_id}'
    status_payload = {
        'fields': 'status_code',
        'access_token': access_token
    }
    
    timeout = 60
    start_time = time.time()
    status_code = ''
    
    while status_code != 'FINISHED' and (time.time() - start_time) < timeout:
        time.sleep(5)
        status_response = requests.get(status_url, params=status_payload)
        status_data = status_response.json()
        
        if 'status_code' in status_data:
            status_code = status_data['status_code']
            if status_code == 'ERROR':
                return False
                
    if status_code != 'FINISHED':
        return False
    
    # Publish the reel
    publish_url = f'https://graph.facebook.com/v22.0/{account_id}/media_publish'
    publish_payload = {
        'creation_id': container_id,
        'access_token': access_token
    }
    
    publish_response = requests.post(publish_url, data=publish_payload)
    publish_data = publish_response.json()
    
    return 'id' in publish_data        


@app.post("/post_to_facebook/{company_id}")
async def post_to_facebook(
    company_id: int,
    content_id: int = Form(...),
    content_type: str = Form(...),
    edited_caption: str = Form(None),
    filename: str = Form(None),
    user: dict = Depends(get_current_user)
):
    try:
        if edited_caption:
            hashtags = re.findall(r'#\w+', edited_caption)
            clean_caption = re.sub(r'#\w+', '', edited_caption).strip()
            final_hashtags = ' '.join(hashtags) if hashtags else None

            cursor.execute("""
                UPDATE content_items 
                SET caption = %s, hashtags = %s
                WHERE id = %s AND company_id = %s AND user_id = %s
            """, (clean_caption, final_hashtags, content_id, company_id, user["user_id"]))
            conn.commit()
        
        # Verify company belongs to user
        cursor.execute("SELECT id FROM companies WHERE id = %s AND user_id = %s", 
                      (company_id, user["user_id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Get content details - ADD media_link TO THE SELECT
        cursor.execute("""
            SELECT platform, content_type, caption, hashtags, 
                   image_prompt, video_idea, video_placeholder, media_link
            FROM content_items 
            WHERE id = %s AND company_id = %s AND user_id = %s
        """, (content_id, company_id, user["user_id"]))
        
        content = cursor.fetchone()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        platform, content_type_db, caption, hashtags, image_prompt, video_idea, video_placeholder, media_link = content
        
        # Prepare the message/caption
        message = caption or ""
        if hashtags:
            message += f"\n\n{hashtags}"
        
        # Facebook credentials
        facebook_page_id = '603484142856231'
        access_token = 'EAATo57EVzcIBO9eJ7EE4XCZAZCYJAm5dW6o3mPEwIqnvx1gsznYMAk5MXFCAVtI8gDg07kwEgnjSC9Q1R6GZB7f2ZCrhSlXoxUadEqeabHykpXh0zfqIvSmaPl0oGIppjbKta6Ld1VmJwzNWWJcbnP5HwSnE6NSvb3kV9qKoGL5nP4lQODAcYoxy13zN'
        
        success = False
        
        if content_type_db == 'Text Posts (Status Updates / Announcements)':
            # Post text status
            success = publish_facebook_text_post(
                page_id=facebook_page_id,
                access_token=access_token,
                message=message
            )
        elif content_type_db == 'Image Posts':
            # Use media_link directly (Cloudinary URL)
            if not media_link:
                raise HTTPException(status_code=400, detail="No image URL found")
            
            print(f"[INFO] Posting image from URL: {media_link}")
            success = publish_facebook_image_post(
                page_id=facebook_page_id,
                access_token=access_token,
                image_url=media_link,  # Use the Cloudinary URL directly
                message=message
            )
            
        elif content_type_db == 'Video Posts':
            # Use video_placeholder directly
            if not video_placeholder:
                raise HTTPException(status_code=400, detail="No video URL found")
            
            print(f"[INFO] Posting video from URL: {video_placeholder}")
            success = publish_facebook_video_post(
                page_id=facebook_page_id,
                access_token=access_token,
                video_url=video_placeholder,
                title=message[:100],
                description=message
            )
        
        if success:
            return {"success": True, "message": "Posted to Facebook successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to post to Facebook")
            
    except Exception as e:
        logger.error(f"Facebook posting error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
def publish_facebook_text_post(page_id, access_token, message):
    """
    Publish a text-only post to a Facebook page
    Returns True if successful, False otherwise
    """
    print(f"[FB] Starting text post publication to page {page_id}")
    
    try:
        url = f'https://graph.facebook.com/v22.0/{page_id}/feed'
        
        payload = {
            'message': message,
            'access_token': access_token
        }
        
        print("[FB] Sending text post request...")
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        
        if 'id' in data:
            post_id = data['id']
            print(f"[FB] Text post published successfully! Post ID: {post_id}")
            return True
        else:
            print("[FB] Failed to publish text post. Response:", data)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[FB] Text post request failed: {str(e)}")
        return False
    except Exception as e:
        print(f"[FB] Unexpected error in text post: {str(e)}")
        return False


def publish_facebook_image_post(page_id, access_token, image_url, message=None):
    """
    Publish an image post to a Facebook page
    Returns True if successful, False otherwise
    """
    print(f"[FB] Starting image post publication to page {page_id}")
    print(f"[FB] Image URL: {image_url}")
    
    try:
        url = f'https://graph.facebook.com/v22.0/{page_id}/photos'
        
        payload = {
            'url': image_url,
            'access_token': access_token
        }
        
        if message:
            print("[FB] Adding caption to image post")
            payload['caption'] = message
        
        print("[FB] Sending image post request...")
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        
        if 'id' in data or 'post_id' in data:
            post_id = data.get('id') or data.get('post_id')
            print(f"[FB] Image post published successfully! Post ID: {post_id}")
            return True
        else:
            print("[FB] Failed to publish image post. Response:", data)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[FB] Image post request failed: {str(e)}")
        return False
    except Exception as e:
        print(f"[FB] Unexpected error in image post: {str(e)}")
        return False


def publish_facebook_video_post(page_id, access_token, video_url, title=None, description=None):
    """
    Publish a video post to a Facebook page
    Returns True if successful, False otherwise
    """
    print(f"[FB] Starting video post publication to page {page_id}")
    print(f"[FB] Video URL: {video_url}")
    
    try:
        url = f'https://graph.facebook.com/v22.0/{page_id}/videos'
        
        payload = {
            'file_url': video_url,
            'access_token': access_token
        }
        
        if title:
            print("[FB] Adding title to video post")
            payload['title'] = title
        
        if description:
            print("[FB] Adding description to video post")
            payload['description'] = description
        
        print("[FB] Sending video post request...")
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        
        if 'id' in data:
            video_id = data['id']
            print(f"[FB] Video post published successfully! Video ID: {video_id}")
            return True
        else:
            print("[FB] Failed to publish video post. Response:", data)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[FB] Video post request failed: {str(e)}")
        return False
    except Exception as e:
        print(f"[FB] Unexpected error in video post: {str(e)}")
        return False    




# New Function to save edited Influncers E-mails
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/save_email/{strategy_id}")
@limiter.limit("5/minute")
async def save_email(
    strategy_id: int, 
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Save individual email content for a strategy"""
    try:
        # Get the request data
        data = await request.json()
        email_index = data.get('email_index')
        email_content = data.get('email_content')
        
        if email_index is None or email_content is None:
            return {"success": False, "error": "Missing email_index or email_content"}
        
        # Verify strategy belongs to user
        cursor.execute("""
            SELECT s.id, s.content, s.status, c.user_id 
            FROM strategies s
            JOIN companies c ON s.company_id = c.id
            WHERE s.id = %s
        """, (strategy_id,))
        
        strategy = cursor.fetchone()
        if not strategy:
            return {"success": False, "error": "Strategy not found"}
        
        if strategy[3] != user["user_id"]:
            return {"success": False, "error": "Unauthorized"}
        
        # Only allow saving for approved strategies
        if strategy[2] != 'approved':
            return {"success": False, "error": "Can only save emails for approved strategies"}
        
        # Parse the strategy content
        soup = BeautifulSoup(strategy[1], 'html.parser')
        
        # Find all email textareas
        email_textareas = soup.find_all('textarea', class_='editable-email')
        
        if email_index >= len(email_textareas):
            return {"success": False, "error": "Invalid email index"}
        
        # Update the specific textarea
        textarea = email_textareas[email_index]
        textarea.clear()
        from bs4 import NavigableString
        textarea.append(NavigableString(email_content))
        
        # Update the strategy content in database
        updated_content = str(soup)
        cursor.execute("""
            UPDATE strategies 
            SET content = %s
            WHERE id = %s
        """, (updated_content, strategy_id))
        
        # Also update the influencer email in the influencers table
        cursor.execute("""
            UPDATE influencers 
            SET email_text = %s
            WHERE strategy_id = %s 
            AND id = (
                SELECT id FROM influencers 
                WHERE strategy_id = %s 
                ORDER BY id 
                LIMIT 1 OFFSET %s
            )
        """, (email_content, strategy_id, strategy_id, email_index))
        
        conn.commit()
        
        return {"success": True, "message": "Email saved successfully"}
        
    except psycopg2.Error as e:
        logger.error(f"Database error saving email: {str(e)}")
        return {"success": False, "error": "Database error - please try again"}
    except Exception as e:
        logger.error(f"Unexpected error saving email: {str(e)}")
        return {"success": False, "error": "Unexpected error"}
            
    #except Exception as e:
        #logger.error(f"Error saving email: {str(e)}")
        #return {"success": False, "error": str(e)}
     
    
 
    
 
# === Add these FIXED endpoints to your main.py ===

@app.get("/get_todays_posts/{company_id}")
def get_todays_posts(company_id: int, user: dict = Depends(get_current_user)):
    """Get all posts scheduled for today that need approval or posting from the approved strategy"""
    try:
        print(f"[DEBUG] Starting get_todays_posts for company_id: {company_id}, user_id: {user.get('user_id')}")
        
        # Verify company belongs to user - FIXED: Add proper error handling
        print(f"[DEBUG] Executing company verification query...")
        try:
            cursor.execute("SELECT id FROM companies WHERE id = %s AND user_id = %s", 
                          (company_id, user["user_id"]))
            print(f"[DEBUG] Company query executed, fetching result...")
            company_result = cursor.fetchone()
            print(f"[DEBUG] Company result: {company_result}")
        except psycopg2.Error as db_error:
            print(f"[ERROR] Database error during company verification: {db_error}")
            # Reset cursor state and try again
            conn.rollback()
            cursor.execute("SELECT id FROM companies WHERE id = %s AND user_id = %s", 
                          (company_id, user["user_id"]))
            company_result = cursor.fetchone()
        
        if not company_result:
            print(f"[DEBUG] Company not found for user")
            raise HTTPException(status_code=404, detail="Company not found")
        
        # First get the approved strategy for this company - FIXED: Add error handling
        print(f"[DEBUG] Executing strategy query...")
        try:
            cursor.execute("""
                SELECT id FROM strategies 
                WHERE company_id = %s AND status = 'approved'
                ORDER BY approved_at DESC 
                LIMIT 1
            """, (company_id,))
            
            print(f"[DEBUG] Strategy query executed, fetching result...")
            approved_strategy = cursor.fetchone()
            print(f"[DEBUG] Strategy result: {approved_strategy}")
        except psycopg2.Error as db_error:
            print(f"[ERROR] Database error during strategy query: {db_error}")
            conn.rollback()
            cursor.execute("""
                SELECT id FROM strategies 
                WHERE company_id = %s AND status = 'approved'
                ORDER BY approved_at DESC 
                LIMIT 1
            """, (company_id,))
            approved_strategy = cursor.fetchone()
        
        if not approved_strategy:
            print(f"[INFO] No approved strategy found for company {company_id}")
            return {"posts": []}  # No approved strategy, no posts to show
        
        strategy_id = approved_strategy[0]
        print(f"[INFO] Using approved strategy ID {strategy_id} for company {company_id}")
        
        # Get current day name and time
        now = datetime.now()
        current_day = now.strftime("%A")
        current_time = now.time()
        print(f"[DEBUG] Current day: {current_day}, Current time: {current_time}")
        
        # Get posts scheduled for today FROM THE APPROVED STRATEGY ONLY - FIXED: Add error handling
        print(f"[DEBUG] Executing posts query...")
        try:
            cursor.execute("""
                SELECT 
                    ci.id, ci.platform, ci.content_type, ci.caption, ci.hashtags, 
                    ci.image_prompt, ci.video_placeholder, ci.best_time,
                    ci.status, c.name as company_name, c.logo_url
                FROM content_items ci
                JOIN companies c ON ci.company_id = c.id
                WHERE ci.company_id = %s 
                AND ci.strategy_id = %s
                AND ci.best_time LIKE %s
                AND ci.status IN ('pending', 'needs_approval')
                ORDER BY 
                    CASE 
                        WHEN ci.status = 'needs_approval' THEN 0
                        WHEN ci.status = 'pending' THEN 1
                        ELSE 2
                    END,
                    ci.best_time
            """, (company_id, strategy_id, f"%{current_day}%"))
            
            print(f"[DEBUG] Posts query executed, fetching results...")
            rows = cursor.fetchall()
        except psycopg2.Error as db_error:
            print(f"[ERROR] Database error during posts query: {db_error}")
            conn.rollback()
            # Try the query again after rollback
            cursor.execute("""
                SELECT 
                    ci.id, ci.platform, ci.content_type, ci.caption, ci.hashtags, 
                    ci.image_prompt, ci.video_placeholder, ci.best_time,
                    ci.status, c.name as company_name, c.logo_url
                FROM content_items ci
                JOIN companies c ON ci.company_id = c.id
                WHERE ci.company_id = %s 
                AND ci.strategy_id = %s
                AND ci.best_time LIKE %s
                AND ci.status IN ('pending', 'needs_approval')
                ORDER BY 
                    CASE 
                        WHEN ci.status = 'needs_approval' THEN 0
                        WHEN ci.status = 'pending' THEN 1
                        ELSE 2
                    END,
                    ci.best_time
            """, (company_id, strategy_id, f"%{current_day}%"))
            rows = cursor.fetchall() or [] 
        
        # FIXED: Proper handling of empty results
        if not rows:
            print(f"[DEBUG] No pending/needs_approval posts found for today")
            return {"posts": []}
        
        print(f"[DEBUG] Found {len(rows)} rows")    
        posts = []
        
        for i, row in enumerate(rows):
            print(f"[DEBUG] Processing row {i+1}/{len(rows)}: {row[0]}")
            # Extract hour from best_time (e.g., "Monday 9AM" -> 9)
            time_str = row[7] if row[7] else ""
            scheduled_hour = None
            if time_str:
                try:
                    time_part = time_str.split()[1]  # Get "9AM" part
                    if 'AM' in time_part or 'PM' in time_part:
                        hour = int(time_part.replace('AM', '').replace('PM', ''))
                        if 'PM' in time_part and hour != 12:
                            hour += 12
                        elif 'AM' in time_part and hour == 12:
                            hour = 0
                        scheduled_hour = hour
                except (IndexError, ValueError) as e:
                    print(f"[WARNING] Could not parse time from '{time_str}': {e}")
                    pass
          
            should_show = False
            is_past_due = False
            
            if scheduled_hour is not None:
                current_hour = current_time.hour
                
                # Past due if current hour is greater than scheduled hour
                if current_hour > scheduled_hour:
                    should_show = True
                    is_past_due = True
                # Within 1 hour if current hour is exactly 1 hour before scheduled
                elif current_hour == scheduled_hour - 1 or current_hour == scheduled_hour:
                    should_show = True
            
            if should_show:
                posts.append({
                    "id": row[0],
                    "platform": row[1],
                    "content_type": row[2],
                    "caption": row[3],
                    "hashtags": row[4],
                    "image_prompt": row[5],
                    "video_placeholder": row[6],
                    "scheduled_time": row[7],
                    "status": row[8],
                    "company_name": row[9],
                    "logo_url": row[10],
                    "scheduled_hour": scheduled_hour,
                    "is_past_due": is_past_due,
                    "strategy_id": strategy_id  # Add strategy_id for reference
                })
        
        print(f"[DEBUG] Returning {len(posts)} posts")
        return {"posts": posts}
        
    except psycopg2.Error as e:
        print(f"[ERROR] Database error in get_todays_posts: {e}")
        # FIXED: Always rollback on database errors to reset cursor state
        conn.rollback()
        return {"posts": [], "error": "Database error occurred"}
    except Exception as e:
        print(f"[ERROR] Unexpected error in get_todays_posts: {e}")
        # FIXED: Rollback on any error to be safe
        conn.rollback()
        return {"posts": [], "error": "An unexpected error occurred"}

# FIXED: Changed to accept JSON object instead of raw body
@app.post("/approve_post/{content_id}")
def approve_post(
    content_id: int,
    request: dict,  # Changed from caption: str = Body(...)
    user: dict = Depends(get_current_user)
):
    """Approve a post and save caption changes using existing logic"""
    try:
        # Verify content belongs to user
        cursor.execute("""
            SELECT ci.id 
            FROM content_items ci
            JOIN companies c ON ci.company_id = c.id
            WHERE ci.id = %s AND c.user_id = %s
        """, (content_id, user["user_id"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Content not found")
        
        # Extract caption from request
        caption = request.get("caption", "")
        
        # Use your existing caption editing logic
        hashtags = re.findall(r'#\w+', caption)
        clean_caption = re.sub(r'#\w+', '', caption).strip()
        final_hashtags = ' '.join(hashtags) if hashtags else None
        
        # Update status to approved and save caption
        cursor.execute("""
            UPDATE content_items 
            SET status = 'approved', caption = %s, hashtags = %s
            WHERE id = %s
        """, (clean_caption, final_hashtags, content_id))
        
        conn.commit()  # Explicitly commit the transaction
        return {"success": True}
        
    except Exception as e:
        conn.rollback()  # Rollback on error
        logger.error(f"Error approving post: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reject_post/{content_id}")
def reject_post(
    content_id: int,
    user: dict = Depends(get_current_user)
):
    """Reject a post and mark it as rejected"""
    try:
        # Verify content belongs to user
        cursor.execute("""
            SELECT ci.id 
            FROM content_items ci
            JOIN companies c ON ci.company_id = c.id
            WHERE ci.id = %s AND c.user_id = %s
        """, (content_id, user["user_id"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Content not found")
        
        # Update status to rejected and set rejected_at timestamp
        cursor.execute("""
            UPDATE content_items 
            SET status = 'rejected', rejected_at = NOW()
            WHERE id = %s
        """, (content_id,))
        
        conn.commit()
        return {"success": True}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error rejecting post: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_approved_posts/{company_id}")
async def check_approved_posts(
    company_id: int, 
    user: dict = Depends(get_current_user)
):
    """Background endpoint to check for approved posts ready to post FROM APPROVED STRATEGY ONLY"""
    try:
        # Verify company belongs to user
        cursor.execute("SELECT id FROM companies WHERE id = %s AND user_id = %s", 
                      (company_id, user["user_id"]))
        company_result = cursor.fetchone()
        if not company_result:
            print(f"[BACKGROUND] Company {company_id} not found for user {user['user_id']}")
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Get the approved strategy for this company
        cursor.execute("""
            SELECT id FROM strategies 
            WHERE company_id = %s AND status = 'approved'
            ORDER BY approved_at DESC 
            LIMIT 1
        """, (company_id,))
        
        approved_strategy = cursor.fetchone()
        if not approved_strategy:
            print(f"[BACKGROUND] No approved strategy found for company {company_id}")
            return {"posts_posted": 0}  # No approved strategy
        
        strategy_id = approved_strategy[0]
        print(f"[BACKGROUND] Using approved strategy ID {strategy_id} for auto-posting (company {company_id})")
        
        now = datetime.now()
        current_day = now.strftime("%A")
        current_hour = now.hour
        
        # Get approved posts for current day and hour FROM THE APPROVED STRATEGY ONLY
        cursor.execute("""
            SELECT id, platform, content_type, best_time, status, caption, hashtags
            FROM content_items 
            WHERE company_id = %s 
            AND strategy_id = %s
            AND status = 'approved'
            AND best_time LIKE %s
        """, (company_id, strategy_id, f"%{current_day}%"))
        
        # FIXED: Check if there are results before processing
        posts_results = cursor.fetchall()
        if not posts_results:
            # No approved posts ready - this is normal, not an error
            return {"posts_posted": 0}
        
        posts_to_post = []
        for row in posts_results:
            content_id, platform, content_type, time_str, status, caption, hashtags = row
            
            # Extract scheduled hour
            try:
                time_part = time_str.split()[1]  # Get "9AM" part
                if 'AM' in time_part or 'PM' in time_part:
                    hour = int(time_part.replace('AM', '').replace('PM', ''))
                    if 'PM' in time_part and hour != 12:
                        hour += 12
                    elif 'AM' in time_part and hour == 12:
                        hour = 0
                    
                    # Post if current hour matches scheduled hour OR if past due
                    if current_hour >= hour:
                        posts_to_post.append({
                            "id": content_id,
                            "platform": platform,
                            "content_type": content_type,
                            "caption": caption,
                            "hashtags": hashtags,
                            "is_past_due": current_hour > hour,
                            "strategy_id": strategy_id,
                            "scheduled_time": time_str  # <-- This is the best_time value you fetched earlier
                        })
            except Exception as e:
                print(f"[BACKGROUND] Error parsing time for content {content_id}: {str(e)}")
                continue
        
        # Sort by past due first, then by scheduled time
        posts_to_post.sort(key=lambda x: (not x["is_past_due"], x["id"]))
        
        # Process posts with 5-second delay between past due posts
        posted_count = 0
        if posts_to_post:
            print(f"[BACKGROUND] Found {len(posts_to_post)} posts ready for auto-posting from strategy {strategy_id}")
        
        for i, post in enumerate(posts_to_post):
            try:
                success = await post_content_automatically(
                    company_id=company_id,
                    post=post,
                    current_user=user
                )
                
                if success:
                    posted_count += 1
                    print(f"[BACKGROUND] Successfully auto-posted content {post['id']}")
                    
                    # Add 5-second delay between past due posts
                    if post["is_past_due"] and i < len(posts_to_post) - 1:
                        await asyncio.sleep(5)
                        
            except Exception as e:
                print(f"[BACKGROUND] Error posting content {post['id']}: {str(e)}")
                continue
        
        if posted_count > 0:
            print(f"[BACKGROUND] Auto-posted {posted_count} posts for company {company_id}")
            
        #return {"posts_posted": posted_count}
        #New return
        return {
                "posts_posted": posted_count,
                "posted_posts": [
                    {
                        "id": post["id"],
                        "platform": post["platform"],
                        "content_type": post["content_type"],
                        "scheduled_time": post.get("scheduled_time"),
                        "was_past_due": post["is_past_due"]
                    }
                    for post in posts_to_post
                    if post.get("was_posted_successfully", True)  # Optional: mark posted successfully
                ]
            }
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        print(f"[BACKGROUND] Unexpected error in check_approved_posts: {str(e)}")
        # Don't rollback here - this is a read operation mostly
        return {"posts_posted": 0, "error": str(e)}

async def post_content_automatically(company_id: int, post: dict, current_user: dict):
    """Automatically post approved content using existing posting functions"""
    try:
        content_id = post["id"]
        platform = post["platform"].lower()
        content_type = post["content_type"]
        
        # Prepare the caption with hashtags
        full_caption = post["caption"] or ""
        if post["hashtags"]:
            full_caption += " " + post["hashtags"]
        
        # Get the media URL (Cloudinary URL)
        cursor.execute("""
            SELECT media_link, video_placeholder 
            FROM content_items WHERE id = %s
        """, (content_id,))
        result = cursor.fetchone()
        media_url = result[0] if result else None
        video_url = result[1] if result else None
        
        # Get the stored account credentials from database
        cursor.execute("""
            SELECT platform, account_id, account_name, access_token, page_id, instagram_id
            FROM user_linked_accounts 
            WHERE user_id = %s AND platform IN ('facebook', 'instagram','linkedin')
            ORDER BY created_at DESC
        """, (current_user["user_id"],))
        
        accounts = cursor.fetchall()
        facebook_account = next((acc for acc in accounts if acc[0] == 'facebook'), None)
        instagram_account = next((acc for acc in accounts if acc[0] == 'instagram'), None)
        linkedin_account = next((acc for acc in accounts if acc[0] == 'linkedin'), None)

        if platform == 'facebook' and not facebook_account:
            raise Exception("No Facebook account linked for this user")
        if platform == 'instagram' and not instagram_account:
            raise Exception("No Instagram account linked for this user")
        if platform == 'linkedin' and not linkedin_account:
            raise Exception("No Linkedin account linked for this user")

        success = False
        
        # Encryption For linked meta account
        ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
        meta_oauth = MetaOAuth(ENCRYPTION_KEY)
        linkedin_oauth = LinkedInOAuth(ENCRYPTION_KEY)
        
        if platform == 'facebook':
            # Use the Facebook API directly instead of calling the endpoint
            facebook_page_id = facebook_account[4]
            
            encrypted_access_token = facebook_account[3]  # access_token field
            decrypted_fb_access_token = meta_oauth._decrypt_token(encrypted_access_token)
            access_token = decrypted_fb_access_token
            
            success = False
            
            if not access_token:
                raise Exception("LinkedIn access token not found in environment variables")
            
            # Map content types to your Facebook posting system
            if 'Image' in content_type:
                if not media_url:
                    raise Exception("No image URL found for Facebook post")
                
                print(f"[INFO] Posting image from URL: {media_url}")
                success = publish_facebook_image_post(
                    page_id=facebook_page_id,
                    access_token=access_token,
                    image_url=media_url,
                    message=full_caption
                )
                
            elif 'Video' in content_type:
                if not video_url:
                    raise Exception("No video URL found for Facebook post")
                
                print(f"[INFO] Posting video from URL: {video_url}")
                success = publish_facebook_video_post(
                    page_id=facebook_page_id,
                    access_token=access_token,
                    video_url=video_url,
                    title=full_caption[:100],
                    description=full_caption
                )
                
            else:  # Text post
                print(f"[INFO] Posting text status: {full_caption}")
                success = publish_facebook_text_post(
                    page_id=facebook_page_id,
                    access_token=access_token,
                    message=full_caption
                )
            
        elif platform == 'instagram':
            # Instagram credentials
            instagram_account_id = instagram_account[5] 
            
            encrypted_access_token = instagram_account[3]  # access_token field
            decrypted_ig_access_token = meta_oauth._decrypt_token(encrypted_access_token)
            access_token = decrypted_ig_access_token
            
            success = False
            
            if not access_token:
                raise Exception("LinkedIn access token not found in environment variables")
            
            if 'Feed Image' in content_type:
                if not media_url:
                    raise Exception("No image URL found for Instagram post")
                
                print(f"[INFO] Posting Instagram feed image from URL: {media_url}")
                success = publish_instagram_post(
                    account_id=instagram_account_id,
                    access_token=access_token,
                    image_url=media_url,
                    caption=full_caption
                )
                
            elif 'Story' in content_type or 'Stories' in content_type or "Instagram Stories" in content_type :
                if not media_url:
                    print(f"[ERROR] No media_url found for Instagram story. Content ID: {content_id}")
                    print(f"[ERROR] Database result: media_link={media_url}, video_placeholder={video_url}")
                    raise Exception("No image URL found for Instagram story")
                
                print(f"[INFO] Posting Instagram story from URL: {media_url}")
                print(f"[DEBUG] Content type check: '{content_type}' contains 'Story' or 'Stories'")
                
                success = publish_instagram_story(
                    account_id=instagram_account_id,
                    access_token=access_token,
                    image_url=media_url
                )
                
            elif 'Reel' in content_type:
                if not video_url:
                    raise Exception("No video URL found for Instagram reel")
                
                print(f"[INFO] Posting Instagram reel from URL: {video_url}")
                success = publish_instagram_reel(
                    account_id=instagram_account_id,
                    access_token=access_token,
                    video_url=video_url,
                    caption=full_caption
                )
        elif platform == 'linkedin':
            
            # LinkedIn posting logic
            encrypted_access_token = linkedin_account[3] 
            decrypted_li_access_token = linkedin_oauth._decrypt_token(encrypted_access_token)
            access_token = decrypted_li_access_token
            
            success = False
            
            if not access_token:
                raise Exception("LinkedIn access token not found in environment variables")
            
            # Get LinkedIn user ID
            user_id = f"urn:li:person:{linkedin_account[1]}"
            
            if 'Image' in content_type:
                if not media_url:
                    raise Exception("No image URL found for LinkedIn post")
                
                print(f"[INFO] Posting image to LinkedIn from URL: {media_url}")
                success = publish_linkedin_image_post(
                    access_token=access_token,
                    user_id=user_id,
                    image_url=media_url,
                    text=full_caption
                )
                
            elif 'Video' in content_type:
                if not video_url:
                    raise Exception("No video URL found for LinkedIn post")
                
                print(f"[INFO] Posting video to LinkedIn from URL: {video_url}")
                success = publish_linkedin_video_post(
                    access_token=access_token,
                    user_id=user_id,
                    video_url=video_url,
                    text=full_caption
                )
                
            else:  # Text post
                print(f"[INFO] Posting text to LinkedIn: {full_caption}")
                success = publish_linkedin_text_post(
                    access_token=access_token,
                    user_id=user_id,
                    text=full_caption
                )
        
        if success:
            # Update status to posted
            cursor.execute("""
                UPDATE content_items 
                SET status = 'posted'
                WHERE id = %s
            """, (content_id,))
            conn.commit()
            print(f"[SUCCESS] Successfully posted content {content_id} to {platform}")
            return True
        else:
            # If posting fails, set back to needs_approval
            cursor.execute("""
                UPDATE content_items 
                SET status = 'needs_approval'
                WHERE id = %s
            """, (content_id,))
            conn.commit()
            print(f"[ERROR] Failed to post content {content_id} to {platform}")
            raise Exception(f"Failed to post content to {platform}")
            
    except Exception as e:
        conn.rollback()
        error_msg = f"Error in post_content_automatically for content {content_id}: {str(e)}"
        logger.error(error_msg)
        print(f"[ERROR] {error_msg}")
        raise e




    
#New    
# First, add this new endpoint to your FastAPI backend
@app.get("/get_strategy_content/{strategy_id}")
async def get_strategy_content(strategy_id: int, user: dict = Depends(get_current_user)):
    cursor.execute("""
        SELECT s.content 
        FROM strategies s
        JOIN companies c ON s.company_id = c.id
        WHERE s.id = %s AND c.user_id = %s AND s.status = 'approved'
    """, (strategy_id, user["user_id"]))
    
    strategy = cursor.fetchone()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found or not approved")
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(strategy[0], 'html.parser')
    
    # Extract events data
# Extract events data
    events_section = soup.find('section', class_='event-strategy')
    events = []
    if events_section:
        event_headings = events_section.find_all('h3')
        for heading in event_headings:
            # Get the date and place paragraph
            date_place_p = heading.find_next('p')
            date_place_text = date_place_p.text.strip() if date_place_p else ''
            
            # Extract date and place from the text
            date = ''
            place = ''
            if date_place_text and '• Date and Place:' in date_place_text:
                # Remove the bullet point and label: "• Date and Place: June 29, 2025, Dougga, Tunisia"
                content = date_place_text.replace('• Date and Place:', '').strip()
                
                # Split by comma: ["June 29", "2025", "Dougga", "Tunisia"]
                parts = [part.strip() for part in content.split(',')]
                
                if len(parts) >= 3:
                    # Reconstruct: date = "June 29, 2025", place = "Dougga, Tunisia"  
                    date = f"{parts[0]}, {parts[1]}"  # "June 29, 2025"
                    place = ', '.join(parts[2:])       # "Dougga, Tunisia"
            
            # Get description
            strategic_value_p = date_place_p.find_next('p') if date_place_p else None
            description = strategic_value_p.text.strip() if strategic_value_p else ''
            
            event = {
                'name': heading.text.strip(),
                'date': date,
                'place': place,  # "Dougga, Tunisia"
                'description': description
            }
            events.append(event)

    # Extract marketing blueprint data
    blueprint_section = soup.find('section', class_='marketing-calendar')
    blueprint_data = []
    if blueprint_section:
        rows = blueprint_section.find('tbody').find_all('tr') if blueprint_section.find('tbody') else []
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:  # Ensure we have all columns
                blueprint_data.append({
                    'dates': cells[0].text.strip(),
                    'theme': cells[1].text.strip(),
                    'actions': cells[2].text.strip(),
                    'platforms': cells[4].text.strip(),
                    'targets': cells[5].text.strip()
                })
    
    
    # Extract influencers data
    influencers_section = soup.find('section', class_='influencer-recommendations')
    influencers = []
    if influencers_section:
        influencer_cards = influencers_section.find_all('div', class_='influencer-card')
        for card in influencer_cards:
            name = card.find('h3').text.replace('INFLUENCER_NAME:', '').strip() if card.find('h3') else 'Unknown'
            email = card.find('p', string=lambda t: 'EMAIL:' in t).text.replace('EMAIL:', '').strip() if card.find('p', string=lambda t: 'EMAIL:' in t) else 'Email not provided'
            followers = card.find('p', string=lambda t: 'FOLLOWERS:' in t).text.replace('FOLLOWERS:', '').strip() if card.find('p', string=lambda t: 'FOLLOWERS:' in t) else 'Followers not specified'
            handle = card.find('p', string=lambda t: 'HANDLE:' in t).text.replace('HANDLE:', '').strip() if card.find('p', string=lambda t: 'HANDLE:' in t) else 'Handle not specified'
            niche = card.find('p', string=lambda t: 'NICHE:' in t).text.replace('NICHE:', '').strip() if card.find('p', string=lambda t: 'NICHE:' in t) else 'Niche not specified'
            
            # Extract budget from COLLABORATION_TYPE
            collab_text = card.find('p', string=lambda t: 'Price Range:' in t).text if card.find('p', string=lambda t: 'Price Range:' in t) else ''
            budget = 'Budget not specified'
            if 'Price Range:' in collab_text:
                budget = collab_text.split('Price Range:')[-1].strip()
            
            influencers.append({
                'name': name,
                'email': email,
                'followers': followers,
                'handle': handle,
                'niche': niche,
                'budget': budget,
                'email_sent': True
            })
    # Extract recommendations data - UPDATED TO MATCH YOUR HTML STRUCTURE
    recommendations_section = soup.find('section', class_='marketing-advice')
    recommendations = {
        'growth': [],
        'content': [],
        'advantage': [],
        'outreach': [],
        'budget': []
    }
    
    if recommendations_section:
        # Growth & Trends
        growth_section = recommendations_section.find('div', class_='growth')
        if growth_section:
            recommendations['growth'] = [li.text.strip() for li in growth_section.find_all('li')]
        
        # Content & Ads
        content_section = recommendations_section.find('div', class_='content')
        if content_section:
            recommendations['content'] = [li.text.strip() for li in content_section.find_all('li')]
        
        # Competitive Edge
        advantage_section = recommendations_section.find('div', class_='advantage')
        if advantage_section:
            recommendations['advantage'] = [li.text.strip() for li in advantage_section.find_all('li')]
        
        # Influencers & Events
        outreach_section = recommendations_section.find('div', class_='outreach')
        if outreach_section:
            recommendations['outreach'] = [li.text.strip() for li in outreach_section.find_all('li')]
        
        # Budget & Metrics
        budget_section = recommendations_section.find('div', class_='budget')
        if budget_section:
            recommendations['budget'] = [li.text.strip() for li in budget_section.find_all('li')]
    
    return {
        'events': events,
        'influencers': influencers,
        'blueprint': blueprint_data,
        'recommendations': recommendations
    }
    
    


# AUTO email send on launch
    
@app.post("/send_launch_emails/{company_id}")
async def send_launch_emails(company_id: int, user: dict = Depends(get_current_user)):
    try:
        # Get the approved strategy
        cursor.execute("""
            SELECT id FROM strategies 
            WHERE company_id = %s AND status = 'approved'
            ORDER BY approved_at DESC LIMIT 1
        """, (company_id,))
        
        strategy = cursor.fetchone()
        if not strategy:
            return {"success": False, "message": "No strategy found"}
            
        strategy_id = strategy[0]
        
        # Call your existing function
        #send_influencer_emails(strategy_id)
        
        return {"success": True, "message": "Emails sent successfully"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}
   
   
 
# --------------------------- LinkedIn ----------------------------------   
   
   
# Get user ID linkedIN 
   
#def get_linkedin_user_id(access_token: str) -> str:
 #   """Get LinkedIn member ID using OpenID Connect userinfo endpoint"""
  #  try:
        # Use the OpenID Connect userinfo endpoint
   #     url = "https://api.linkedin.com/v2/userinfo"
    #    headers = {
     #       'Authorization': f'Bearer {access_token}',
      #      'X-Restli-Protocol-Version': '2.0.0',
       #     'LinkedIn-Version': '202402'
       ## }
        
       # response = requests.get(url, headers=headers)
        #response.raise_for_status()
        #data = response.json()
        
        # The sub field contains the user ID in OpenID Connect
        #if 'sub' in data:
       #     return f"urn:li:person:{data['sub']}"
       # else:
        #    raise Exception("Could not find user ID in response")
            
    #except requests.exceptions.RequestException as e:
       # error_detail = str(e)
       # if hasattr(e, 'response') and e.response:
       #     error_detail += f"\nResponse: {e.response.text}"
       # raise Exception(f"Failed to get LinkedIn user ID: {error_detail}") 
 
   
   
# LinkedIn Publishing Functions (add these to your existing code)
def publish_linkedin_text_post(access_token: str, user_id: str, text: str):
    """Publish a text-only post to LinkedIn with enhanced error handling"""
    try:
        # Validate inputs
        if not user_id.startswith("urn:li:person:"):
            raise ValueError("Invalid user_id format. Must start with 'urn:li:person:'")
        if not text.strip():
            raise ValueError("Text content cannot be empty")
        
        url = "https://api.linkedin.com/v2/ugcPosts"
        
        payload = {
            "author": user_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202402'
        }
        
        print("[LINKEDIN] Creating text post...")
        response = requests.post(
            url, 
            headers=headers, 
            data=json.dumps(payload),
            timeout=10
        )
        
        if response.status_code != 201:
            raise Exception(f"API returned {response.status_code}: {response.text}")
        
        post_id = response.headers.get('X-RestLi-Id')
        print(f"[LINKEDIN] Text post published successfully! Post ID: {post_id}")
        return True
            
    except requests.exceptions.RequestException as e:
        error_detail = f"Request failed: {str(e)}"
        if hasattr(e, 'response') and e.response:
            error_detail += f"\nResponse: {e.response.text}"
        raise Exception(f"LinkedIn text post failed: {error_detail}")
    except Exception as e:
        raise Exception(f"Unexpected error in text post: {str(e)}")

def publish_linkedin_image_post(access_token: str, user_id: str, image_url: str, text: str):
    """Publish an image post to LinkedIn with improved reliability"""
    try:
        # Validate inputs
        if not user_id.startswith("urn:li:person:"):
            raise ValueError("Invalid user_id format. Must start with 'urn:li:person:'")
        if not image_url.startswith(('http://', 'https://')):
            raise ValueError("Invalid image URL format")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202402'
        }
        
        # 1. Register upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": user_id,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }]
            }
        }
        
        print("[LINKEDIN] Registering image upload...")
        register_response = requests.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=headers,
            data=json.dumps(register_payload),
            timeout=10
        )
        register_response.raise_for_status()
        register_data = register_response.json()
        
        upload_url = register_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
        asset_urn = register_data['value']['asset']
        
        # 2. Upload image with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with requests.Session() as session:
                    # Download image first
                    image_response = session.get(image_url, stream=True, timeout=30)
                    image_response.raise_for_status()
                    
                    # Upload to LinkedIn
                    upload_response = session.put(
                        upload_url,
                        headers={'Authorization': f'Bearer {access_token}'},
                        data=image_response.iter_content(chunk_size=8192),
                        timeout=30
                    )
                    upload_response.raise_for_status()
                break  # Success - exit retry loop
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
        # 3. Create post
        post_payload = {
            "author": user_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "description": {"text": text[:200]},
                        "media": asset_urn,
                        "title": {"text": "Shared Image"}
                    }]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        print("[LINKEDIN] Creating image post...")
        post_response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            data=json.dumps(post_payload),
            timeout=10
        )
        post_response.raise_for_status()
        
        return True
        
    except requests.exceptions.RequestException as e:
        error_detail = f"Request failed: {str(e)}"
        if e.response:
            error_detail += f"\nStatus: {e.response.status_code}\nResponse: {e.response.text[:500]}"
        raise Exception(f"LinkedIn image post failed: {error_detail}")
    except Exception as e:
        raise Exception(f"Unexpected error in image post: {str(e)}")

def publish_linkedin_video_post(access_token: str, user_id: str, video_url: str, text: str):
    """Publish a video post to LinkedIn with enhanced error handling"""
    try:
        # Validate inputs
        if not user_id.startswith("urn:li:person:"):
            raise ValueError("Invalid user_id format")
        if not video_url.startswith(('http://', 'https://')):
            raise ValueError("Invalid video URL")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202402'
        }
        
        # 1. Register upload
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                "owner": user_id,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }]
            }
        }
        
        register_response = requests.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=headers,
            data=json.dumps(register_payload),
            timeout=10
        )
        register_response.raise_for_status()
        register_data = register_response.json()
        
        upload_url = register_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
        asset_urn = register_data['value']['asset']
        
        # 2. Upload video with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with requests.Session() as session:
                    # Stream video upload in chunks
                    with session.get(video_url, stream=True, timeout=30) as video_response:
                        video_response.raise_for_status()
                        
                        upload_response = session.put(
                            upload_url,
                            headers={'Authorization': f'Bearer {access_token}'},
                            data=video_response.iter_content(chunk_size=8192),
                            timeout=30
                        )
                        upload_response.raise_for_status()
                
                break  # Success - exit retry loop
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
        # 3. Create post
        post_payload = {
            "author": user_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "VIDEO",
                    "media": [{
                        "status": "READY",
                        "description": {"text": text[:200]},
                        "media": asset_urn,
                        "title": {"text": "Shared Video"}
                    }]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        post_response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            data=json.dumps(post_payload),
            timeout=10
        )
        post_response.raise_for_status()
        
        return True
        
    except Exception as e:
        print(f"[LINKEDIN] Video post error: {str(e)}")
        raise Exception(f"LinkedIn video post failed: {str(e)}") 
    
    
    
@app.post("/upload_custom_media")
async def upload_custom_media(
    file: UploadFile = File(...),
    content_id: int = Form(...),
    is_video: bool = Form(False),
    user: dict = Depends(get_current_user)
):
    try:
        # Verify the content belongs to the user
        cursor.execute("""
            SELECT id FROM content_items 
            WHERE id = %s AND user_id = %s
        """, (content_id, user["user_id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Content not found")

        # Save the file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        # Upload to Cloudinary
        resource_type = "video" if is_video else "image"
        public_id = f"custom_{resource_type}_{content_id}_{int(time.time())}"
        
        cloudinary_url = upload_image_to_cloudinary(
            temp_path,
            public_id=public_id,
            resource_type=resource_type
        )

        # Update the content item in database
        if is_video:
            # For videos, update both media_link and video_placeholder
            cursor.execute("""
                UPDATE content_items 
                SET media_link = %s, video_placeholder = %s
                WHERE id = %s
            """, (cloudinary_url, cloudinary_url, content_id))
        else:
            # For images, just update media_link
            cursor.execute("""
                UPDATE content_items 
                SET media_link = %s
                WHERE id = %s
            """, (cloudinary_url, content_id))
        
        conn.commit()

        # Clean up temp file
        os.unlink(temp_path)

        return {"media_url": cloudinary_url}

    except Exception as e:
        logger.error(f"Custom media upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()
        
        

# === Content Items CRUD ===
@app.get("/get_content_items/{strategy_id}")
def get_content_items(strategy_id: int, user: dict = Depends(get_current_user)):
    try:
        print(f"Getting content items for strategy {strategy_id}, user {user['user_id']}")
        
        # Verify strategy belongs to user
        cursor.execute("""
            SELECT s.id 
            FROM strategies s
            JOIN companies c ON s.company_id = c.id
            WHERE s.id = %s AND c.user_id = %s
        """, (strategy_id, user["user_id"]))
        
        result = cursor.fetchone()
        print(f"Strategy verification result: {result}")
        
        if not result:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        # Get all content items for this strategy
        cursor.execute("""
            SELECT id, platform, content_type, caption, hashtags, 
                   media_link, video_placeholder, best_time, status
            FROM content_items
            WHERE strategy_id = %s
            ORDER BY 
                CASE 
                    WHEN status = 'pending' THEN 1
                    WHEN status = 'approved' THEN 2
                    WHEN status = 'posted' THEN 3
                    ELSE 4
                END,
                best_time
        """, (strategy_id,))
        
        content_items = []
        rows = cursor.fetchall()
        print(f"Found {len(rows)} content items")
        
        for row in rows:
            content_items.append({
                "id": row[0],
                "platform": row[1],
                "content_type": row[2],
                "caption": row[3],
                "hashtags": row[4],
                "media_link": row[5],
                "video_placeholder": row[6],
                "best_time": row[7],
                "status": row[8]
            })
        
        return {"content_items": content_items}
        
    except Exception as e:
        logger.error(f"Error getting content items: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")  # Add this for detailed error
        raise HTTPException(status_code=500, detail=str(e))

# Update the create_content_item endpoint to accept status parameter
# Update the create_content_item endpoint to use the status from form data
@app.post("/create_content_item")
async def create_content_item(
    strategy_id: int = Form(...),
    platform: str = Form(...),
    content_type: str = Form(...),
    caption: str = Form(None),
    hashtags: str = Form(None),
    best_time: str = Form(None),
    status: str = Form('approved'),  # Default to 'approved' but can be overridden
    media: UploadFile = File(None),
    user: dict = Depends(get_current_user)
):
    try:
        # Verify strategy belongs to user
        cursor.execute("""
            SELECT s.id 
            FROM strategies s
            JOIN companies c ON s.company_id = c.id
            WHERE s.id = %s AND c.user_id = %s
        """, (strategy_id, user["user_id"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        # Handle file upload if exists
        media_link = None
        if media and media.filename:
            # Save the file temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                shutil.copyfileobj(media.file, temp_file)
                temp_path = temp_file.name
            
            # Upload to Cloudinary
            resource_type = "video" if "video" in content_type.lower() else "image"
            public_id = f"content_{strategy_id}_{int(time.time())}"
            
            media_link = upload_image_to_cloudinary(
                temp_path,
                public_id=public_id,
                resource_type=resource_type
            )
            
            # Clean up temp file
            os.unlink(temp_path)
        
        # Insert into database with the provided status
        cursor.execute("""
            INSERT INTO content_items (
                strategy_id, company_id, user_id, platform, content_type,
                caption, hashtags, media_link, best_time, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            strategy_id,
            get_company_id_from_strategy(strategy_id),
            user["user_id"],
            platform,
            content_type,
            caption,
            hashtags,
            media_link,
            best_time,
            status  # Use the status from form data
        ))
        
        content_id = cursor.fetchone()[0]
        conn.commit()
        
        return {"success": True, "content_id": content_id}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating content item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if media:
            media.file.close()

@app.put("/update_content_item/{content_id}")
async def update_content_item(
    content_id: int,
    platform: str = Form(...),
    content_type: str = Form(...),
    caption: str = Form(None),
    hashtags: str = Form(None),
    best_time: str = Form(None),
    status: str = Form(None),  # Optional status parameter
    media: UploadFile = File(None),
    user: dict = Depends(get_current_user)
):
    try:
        # Verify content belongs to user and get current status
        cursor.execute("""
            SELECT ci.id, ci.media_link, ci.status
            FROM content_items ci
            JOIN strategies s ON ci.strategy_id = s.id
            JOIN companies c ON s.company_id = c.id
            WHERE ci.id = %s AND c.user_id = %s
        """, (content_id, user["user_id"]))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Content item not found")
        
        current_media_link = result[1]
        current_status = result[2]
        media_link = current_media_link
        
        # Use the provided status or keep the current one
        final_status = status if status else current_status
        
        # Handle file upload if exists
        if media and media.filename:
            # Save the file temporarily
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                shutil.copyfileobj(media.file, temp_file)
                temp_path = temp_file.name
            
            # Upload to Cloudinary
            resource_type = "video" if "video" in content_type.lower() else "image"
            public_id = f"content_{content_id}_{int(time.time())}"
            
            media_link = upload_image_to_cloudinary(
                temp_path,
                public_id=public_id,
                resource_type=resource_type
            )
            
            # Clean up temp file
            os.unlink(temp_path)
        
        # Update in database
        cursor.execute("""
            UPDATE content_items
            SET platform = %s,
                content_type = %s,
                caption = %s,
                hashtags = %s,
                media_link = %s,
                best_time = %s,
                status = %s
            WHERE id = %s
        """, (
            platform,
            content_type,
            caption,
            hashtags,
            media_link,
            best_time,
            final_status,
            content_id
        ))
        
        conn.commit()
        
        return {"success": True}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating content item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if media:
            media.file.close()

@app.get("/get_content_item/{content_id}")
def get_content_item(content_id: int, user: dict = Depends(get_current_user)):
    try:
        # Verify content belongs to user
        cursor.execute("""
            SELECT ci.id 
            FROM content_items ci
            JOIN strategies s ON ci.strategy_id = s.id
            JOIN companies c ON s.company_id = c.id
            WHERE ci.id = %s AND c.user_id = %s
        """, (content_id, user["user_id"]))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Content item not found")
        
        # Get the content item
        cursor.execute("""
            SELECT id, platform, content_type, caption, hashtags, 
                   media_link, video_placeholder, best_time, status
            FROM content_items
            WHERE id = %s
        """, (content_id,))
        
        item = cursor.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Content item not found")
        
        return {
            "id": item[0],
            "platform": item[1],
            "content_type": item[2],
            "caption": item[3],
            "hashtags": item[4],
            "media_link": item[5],
            "video_placeholder": item[6],
            "best_time": item[7],
            "status": item[8]
        }
        
    except Exception as e:
        logger.error(f"Error getting content item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_content_item/{content_id}")
def delete_content_item(content_id: int, user: dict = Depends(get_current_user)):
    try:
        # Verify content belongs to user
        cursor.execute("""
            SELECT ci.id, ci.media_link
            FROM content_items ci
            JOIN strategies s ON ci.strategy_id = s.id
            JOIN companies c ON s.company_id = c.id
            WHERE ci.id = %s AND c.user_id = %s
        """, (content_id, user["user_id"]))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Content item not found")
        
        # Delete from database
        cursor.execute("DELETE FROM content_items WHERE id = %s", (content_id,))
        conn.commit()
        
        return {"success": True}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting content item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_company_id_from_strategy(strategy_id: int) -> int:
    cursor.execute("SELECT company_id FROM strategies WHERE id = %s", (strategy_id,))
    result = cursor.fetchone()
    return result[0] if result else None            