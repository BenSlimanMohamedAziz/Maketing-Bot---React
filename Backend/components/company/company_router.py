# company_router.py
import re
import logging
from fastapi import APIRouter, FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from auth.auth import get_current_user
from config.config import get_db_connection, get_db_cursor, release_db_connection
from pydantic import BaseModel
from typing import List, Optional
import cloudinary.uploader
from fastapi.middleware.cors import CORSMiddleware

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models
class CompanyResponse(BaseModel):
    id: int
    name: str
    slogan: str
    description: str
    website: str
    phone_number: str
    products: str
    services: str
    marketing_goals: str
    target_age_groups: str
    target_audience_types: str
    target_business_types: str
    target_geographics: str
    preferred_platforms: str
    special_events: str
    marketing_challenges: str
    brand_tone: str
    monthly_budget: str
    logo_url: Optional[str] = None
    created_at: str

class CompanyCreateRequest(BaseModel):
    name: str
    slogan: str = ""
    description: str = ""
    website: str = ""
    phone_number: str = ""
    products: str = ""
    services: str = ""
    marketing_goals: List[str] = []
    target_age_groups: List[str] = []
    target_audience_types: List[str] = []
    target_business_types: List[str] = []
    target_geographics: List[str] = []
    preferred_platforms: List[str] = []
    special_events: List[str] = []
    marketing_challenges: List[str] = []
    brand_tone: str = ""
    monthly_budget: str = ""

class CompanyUpdateRequest(BaseModel):
    name: str
    slogan: str = ""
    description: str = ""
    website: str = ""
    phone_number: str = ""
    products: str = ""
    services: str = ""
    marketing_goals: List[str] = []
    target_age_groups: List[str] = []
    target_audience_types: List[str] = []
    target_business_types: List[str] = []
    target_geographics: List[str] = []
    preferred_platforms: List[str] = []
    special_events: List[str] = []
    marketing_challenges: List[str] = []
    brand_tone: str = ""
    monthly_budget: str = ""

class StrategyResponse(BaseModel):
    id: int
    content: str
    created_at: str

class CompanyDetailsResponse(BaseModel):
    company: CompanyResponse
    approved_strategy: Optional[StrategyResponse] = None
    strategy_counts: dict
    
app = FastAPI()

#CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def format_target_audience(age_groups: Optional[str], audience_types: Optional[str], 
                         business_types: Optional[str], geographics: Optional[str]) -> str:
    parts = []
    if age_groups:
        parts.append(f"Age Groups: {age_groups}")
    if audience_types:
        parts.append(f"Types: {audience_types}")
    if business_types:
        parts.append(f"Businesses: {business_types}")
    if geographics:
        parts.append(f"Geographics: {geographics}")
    return " | ".join(parts) if parts else "Not specified"

def validate_website(url):
    if not url:
        return True
    url_pattern = re.compile(
        r'^(https?://)?'
        r'(([A-Z0-9][A-Z0-9_-]*)(\.[A-Z0-9][A-Z0-9_-]*)+)'
        r'(:[0-9]{1,5})?'
        r'(/.*)?$',
        re.IGNORECASE
    )
    linkedin_pattern = re.compile(
        r'^(https?://)?(www\.)?linkedin\.com/.*',
        re.IGNORECASE
    )
    return bool(url_pattern.match(url)) or bool(linkedin_pattern.match(url))

def validate_phone(phone_number):
    if not phone_number:
        return True
    phone_pattern = re.compile(
        r'^\+?[0-9]{1,4}?[-.\s()]*[0-9]{1,4}?[-.\s()]*[0-9]{1,4}[-.\s()]*[0-9]{1,4}[-.\s()]*[0-9]{1,9}$'
    )
    return bool(phone_pattern.match(phone_number))

# API Routes
@router.get("/api/company/{company_id}", response_model=CompanyDetailsResponse)
async def get_company_details(
    company_id: int, 
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        # Fetch company details
        cursor.execute(
            """
            SELECT id, user_id, name, slogan, description, website, phone_number,
                   products, services, marketing_goals,
                   target_age_groups, target_audience_types, target_business_types,
                   target_geographics, preferred_platforms, special_events, 
                   marketing_challenges, brand_tone, monthly_budget, logo_url, created_at
            FROM companies 
            WHERE id = %s AND user_id = %s
            """,
            (company_id, user["user_id"])
        )
        company = cursor.fetchone()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Fetch approved strategy
        cursor.execute(
            """
            SELECT id, content, created_at FROM strategies 
            WHERE company_id = %s AND status = 'approved'
            LIMIT 1
            """,
            (company_id,)
        )
        approved_strategy = cursor.fetchone()
        
        # Count strategies
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_count,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_count
            FROM strategies 
            WHERE company_id = %s
            """,
            (company_id,)
        )
        counts = cursor.fetchone()
        
        total_count = counts[0] or 0
        approved_count = counts[1] or 0
        archived_count = total_count - approved_count
        
        # Format company data
        company_dict = {
            "id": company[0],
            "name": company[2],
            "slogan": company[3] or "Not specified",
            "description": company[4] or "Not provided",
            "website": company[5] or "Not provided",
            "phone_number": company[6] or "Not provided",
            "products": company[7] or "None listed",
            "services": company[8] or "None listed",
            "marketing_goals": company[9] or "Not specified",
            "target_age_groups": company[10] or "",
            "target_audience_types": company[11] or "",
            "target_business_types": company[12] or "",
            "target_geographics": company[13] or "",
            "preferred_platforms": company[14] or "Not specified",
            "special_events": company[15] or "None planned",
            "marketing_challenges": company[16] or "None specified",
            "brand_tone": company[17] or "Not defined",
            "monthly_budget": company[18] or "Not specified",
            "logo_url": company[19],
            "created_at": company[20].strftime("%Y-%m-%d")
        }
        
        # Format approved strategy if exists
        approved_strategy_dict = None
        if approved_strategy:
            approved_strategy_dict = {
                "id": approved_strategy[0],
                "content": approved_strategy[1],
                "created_at": approved_strategy[2].strftime("%Y-%m-%d %H:%M")
            }
        
        return CompanyDetailsResponse(
            company=company_dict,
            approved_strategy=approved_strategy_dict,
            strategy_counts={
                "total": total_count,
                "approved": approved_count,
                "archived": archived_count
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching company details: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        release_db_connection(conn)

@router.delete("/api/company/{company_id}")
async def delete_company(
    company_id: int, 
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    try:
        cursor.execute(
            "SELECT id FROM companies WHERE id = %s AND user_id = %s",
            (company_id, user["user_id"])
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Company not found")
        
        cursor.execute("DELETE FROM companies WHERE id = %s", (company_id,))
        cursor.connection.commit()
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Company deleted successfully"}
        )
        
    except Exception as e:
        logger.error(f"Error deleting company: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        release_db_connection(conn)