# Imports
import re
import asyncio
import aiohttp
from groq import AsyncGroq
from config.config import settings
from datetime import datetime
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Initialize async Groq client
GROQ_API_KEY = settings.GROQ_API_KEY_1
client = AsyncGroq(api_key=GROQ_API_KEY)

# Tavily Search tool api
TAVILY_API_KEY = settings.TAVILY_API_KEY_1

# Thread pool for CPU-bound operations
thread_pool = ThreadPoolExecutor(max_workers=4)

async def search_company_info(company_name: str, slogan: str) -> Optional[str]:
    """
    Async search for additional company information and industry insights
    """
    try:
        tavily_url = "https://api.tavily.com/search"
        
        search_queries = [
            f"{company_name} {slogan} company information",
            f"marketing trends",
            f"{company_name}{slogan} brand reputation",
            f"digital marketing strategies",
            f"competitive analysis for {company_name}{slogan}"
        ]
        
        all_results = []
        
        async with aiohttp.ClientSession() as session:
            for query in search_queries:
                payload = {
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": 2
                }
                
                try:
                    async with session.post(tavily_url, json=payload, timeout=30) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        if data.get('results'):
                            for result in data['results']:
                                all_results.append({
                                    'title': result.get('title', ''),
                                    'content': result.get('content', ''),
                                    'url': result.get('url', '')
                                })
                        
                        await asyncio.sleep(1)  # Rate limiting
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Search query failed for '{query}': {str(e)}")
                    continue
        
        if all_results:
            return f"""
            Company & Industry Research Findings:
            {str(all_results)[:2000]}
            """
        
        return None
        
    except Exception as e:
        logger.error(f"Company research failed: {str(e)}")
        return None

async def validate_executive_summary_html(html_content: str) -> str:
    """
    Async validate and ensure the HTML structure matches the required format
    """
    try:
        # Run CPU-bound operation in thread pool
        loop = asyncio.get_event_loop()
        soup = await loop.run_in_executor(
            thread_pool, 
            lambda: BeautifulSoup(html_content, 'html.parser')
        )
        
        # Check for required elements
        required_elements = [
            ('section', 'executive-summary'),
            ('h1', None),
            ('div', 'summary-card'),
            ('div', 'key-focus'),
            ('h3', None),
            ('ul', None)
        ]
        
        for tag_name, class_name in required_elements:
            if class_name:
                element = soup.find(tag_name, class_=class_name)
            else:
                element = soup.find(tag_name)
            
            if not element:
                logger.warning(f"Missing required element: {tag_name} {class_name}")
        
        return str(soup)
    
    except Exception as e:
        logger.error(f"HTML validation failed: {str(e)}")
        return html_content

async def clean_html_response(content: str) -> str:
    """
    Async clean the AI response by removing markdown code blocks and extra formatting
    """
    try:
        # Run regex operations in thread pool
        loop = asyncio.get_event_loop()
        
        def clean_content():
            # Remove ```html and ``` markers
            cleaned = re.sub(r'```html\s*', '', content, flags=re.IGNORECASE)
            cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'```', '', cleaned)
            
            # Remove any leading/trailing whitespace
            cleaned = cleaned.strip()
            
            # Ensure content starts with <section
            if not cleaned.startswith('<section'):
                # Find the first <section tag
                section_match = re.search(r'<section.*?>', cleaned, re.DOTALL)
                if section_match:
                    start_index = cleaned.find(section_match.group())
                    cleaned = cleaned[start_index:]
            
            return cleaned
        
        return await loop.run_in_executor(thread_pool, clean_content)
    
    except Exception as e:
        logger.error(f"HTML cleaning failed: {str(e)}")
        return content

async def generate_executive_summary(company_data: Dict[str, Any], current_date: datetime, logo_description: str) -> str:
    """
    Async generate executive summary with real-time company research and market insights
    """
    current_year = current_date.year
    
    # Format target audience
    target_audience = f"""
    - Age Groups: {company_data.get('target_age_groups', 'Not specified')}
    - Audience Types: {company_data.get('target_audience_types', 'Not specified')}
    - Business Types: {company_data.get('target_business_types', 'Not specified')}
    - Geographic Targets: {company_data.get('target_geographics', 'Not specified')}
    """
    
    # Perform async web search for company and industry insights
    company_research = await search_company_info(company_data['name'], company_data['slogan'])

    prompt = f"""
    IMPORTANT: You are the Chief Marketing Strategist for {company_data['name']}.
    Logo Description: {logo_description}
    
    Create a comprehensive executive summary for our {current_date.strftime('%B %Y')} marketing strategy.
    
    STRATEGIC CONTEXT:
    - Current Period: {current_year}
    - Total Budget: {company_data.get('monthly_budget', 'Not specified')}
    
    {f'ADDITIONAL RESEARCH INSIGHTS: {company_research}' if company_research else 'Using provided company data with industry best practices'}
    
    COMPANY CORE PROFILE:
    Name: {company_data['name']}
    Slogan: {company_data.get('slogan', '')}
    Description: {company_data.get('description', '')}
    Website : {company_data.get('website', '')}
    Products: {company_data.get('products', '')}
    Services: {company_data.get('services', '')}
    Target Audience: {target_audience}
    Preferred Platforms: {company_data['preferred_platforms']}
    Brand Tone: {company_data['brand_tone']}
    LOGO: {company_data.get('logo_url', 'No logo')}"
    LOGO Description: {logo_description}
    Marketing Goals: {company_data.get('marketing_goals', '')}
    Special Events: {company_data.get('special_events', '')}

    STRATEGY REQUIREMENTS:
    - Incorporate {current_year}-specific opportunities
    - Align with {current_year} marketing trends
    - Use "we" perspective as company strategist
    - Focus on measurable, executable outcomes
    - Consider budget constraints: {company_data.get('monthly_budget', 'Not specified')}
    - Leverage platform strengths: {company_data['preferred_platforms']}
    - For coins, money, and budgets always use TND and it's equivalent in Euros and Dollars

    OUTPUT FORMAT (STRICT HTML STRUCTURE):

    <!-- 1. Executive Summary -->
    <section class="executive-summary">
        <h1>Marketing Strategy for "{company_data['name']}", ({current_date.strftime('%B %Y')})</h1>
        <div class="summary-card">
            <p>[One compelling paragraph connecting company profile to strategic recommendations. Focus on growth opportunities, market positioning, and key differentiators. Use "we" language.]</p>
            <div class="key-focus">
                <h3>Key Focus Areas:</h3>
                <ul>
                    <li>Primary Objective: [Single most important goal - specific and measurable]</li>
                    <li>Secondary Objectives: [Goal 1 - audience growth], [Goal 2 - engagement improvement], [Goal 3 - conversion optimization]</li>
                </ul>
            </div>
        </div>
    </section>

    CONTENT GUIDELINES:
    - Primary Objective: Should be SMART (Specific, Measurable, Achievable, Relevant, Time-bound)
    - Secondary Objectives: Support primary goal with clear metrics
    - Overview Paragraph: Connect company strengths to market opportunities
    - Incorporate seasons advantages
    - Reference any special events: {company_data.get('special_events', 'None')}

    FINAL INSTRUCTIONS:
    - Return ONLY the HTML above
    - Maintain exact class names and structure for CSS compatibility
    - Ensure professional, boardroom-ready language
    - All objectives must be actionable and measurable
    - Incorporate research insights if available
    - Focus on {company_data['name']}'s unique value proposition
    """

    try:
        completion = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4,
            max_completion_tokens=2048,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            stop=None
        )
        
        content = completion.choices[0].message.content
        
        # Validate HTML structure asynchronously
        content = await validate_executive_summary_html(content)
        
        # Clean the response to remove markdown formatting asynchronously
        cleaned_content = await clean_html_response(content)
        
        await asyncio.sleep(2)  # Non-blocking delay
        return cleaned_content
        
    except Exception as e:
        logger.error(f"Failed to generate executive summary: {str(e)}")
        return f"Failed to generate executive summary: {str(e)}"