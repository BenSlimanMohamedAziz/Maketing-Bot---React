import time
from groq import Groq
from config.config import settings
from datetime import datetime
import logging
import requests
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Initialize Groq client
GROQ_API_KEY = settings.GROQ_API_KEY_1
TAVILY_API_KEY = settings.TAVILY_API_KEY_2
client = Groq(api_key=GROQ_API_KEY)

    
    
# Tool Search Web :
def search_web_for_marketing_trends(company_name: str, description: str, year: int) -> Optional[str]:
    """
    Search the web for current marketing trends and expert advice
    """
    try:
        tavily_url = "https://api.tavily.com/search"
        
        search_queries = [
            f"marketing trends for {description} in {year} expert advice",
            f"marketing best practices in {year}",
            f"social media marketing tips in {year}",
            f"content marketing trends {year}",
            f"influencer marketing strategies {year}",
            f"ROI measurement marketing metrics {year}"
        ]
        
        all_results = []
        
        for query in search_queries:
            payload = {
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "include_images": False,
                "include_raw_content": False,
                "max_results": 3
            }
            
            response = requests.post(tavily_url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('results'):
                for result in data['results']:
                    all_results.append({
                        'title': result.get('title', ''),
                        'content': result.get('content', ''),
                        'url': result.get('url', '')
                    })
            
            time.sleep(1)  # Rate limiting
        
        if all_results:
            return f"""
            Current Marketing Trends & Expert Insights ({year}):
            {str(all_results)[:2500]}
            """
        
        return None
        
    except Exception as e:
        logger.error(f"Marketing trends web search failed: {str(e)}")
        return None

# Generate the advices and tips
def generate_advices_and_tips(company_data: Dict[str, Any], current_date: datetime, logo_description: str) -> str:
    """
    Generate marketing advice and tips with real-time trend data
    """
    current_year = current_date.year
    
    # Format target audience
    target_audience = f"""
    - Age Groups: {company_data.get('target_age_groups', 'Not specified')}
    - Audience Types: {company_data.get('target_audience_types', 'Not specified')}
    - Business Types: {company_data.get('target_business_types', 'Not specified')}
    - Geographic Targets: {company_data.get('target_geographics', 'Not specified')}
    """
    
    
    # Perform web search for current marketing trends
    trend_insights = search_web_for_marketing_trends(
        company_data['name'], 
        company_data['description'],
        current_year
    )

    prompt = f"""
    IMPORTANT: You are a professional marketing strategist for {company_data['name']}.
    Logo Description: {logo_description}
    
    Generate actionable and trending marketing advice, tips and recommendations for {current_date.strftime('%B %Y')}.
    
    
    {f'REAL-TIME MARKETING TRENDS: {trend_insights}' if trend_insights else 'Using proven marketing best practices'}
    
    COMPANY PROFILE:
    Name: {company_data['name']}
    Slogan: {company_data.get('slogan', '')}
    DESCRIPTION: {company_data.get('description', '')}
    Products: {company_data.get('products', '')}
    Services: {company_data.get('services', '')}
    Target Audience: {target_audience}
    Website : {company_data.get('website', '')}
    Platforms: {company_data['preferred_platforms']}
    Brand Tone: {company_data['brand_tone']}
    LOGO: {company_data.get('logo_url', 'No logo')}"
    LOGO Description: {logo_description}
    Marketing Goals: {company_data.get('marketing_goals', '')}
    Monthly Budget: {company_data.get('monthly_budget', '')}

    REQUIREMENTS:
    - Provide EXECUTABLE, ready-to-implement advice
    - Incorporate {current_year} marketing trends
    - Focus on nowadays-specific opportunities
    - Align with company's brand tone: {company_data['brand_tone']}
    - Use bullet points for easy readability
    - Ensure all recommendations are practical and measurable

    OUTPUT FORMAT (STRICT HTML STRUCTURE):

    <!-- Marketing Advice & Recommendations -->
    <section class="marketing-advice">
        <h2>Marketing Recommendations</h2>
        
        <div class="growth">
            <h3>Growth & Trends</h3>
            <ul>
                <li><strong>2025 Trends:</strong> [3 specific opportunities with actionable steps]</li>
                <li><strong>New Audiences:</strong> [2 untapped segments with approach strategies]</li>
                <li><strong>Partnerships:</strong> [3 collaboration ideas with implementation steps]</li>
            </ul>
        </div>
        
        <div class="content">
            <h3>Content & Ads</h3>
            <ul>
                <li><strong>Content:</strong> [Specific formats, color schemes, messaging guidelines]</li>
                <li><strong>3 M's:</strong> [Market-Message-Media alignment strategies]</li>
                <li><strong>Ad Tips:</strong> [3 actionable improvements with examples]</li>
                <li><strong>Engagement:</strong> [3 interaction tactics with implementation steps]</li>
            </ul>
        </div>
        
        <div class="advantage">
            <h3>Competitive Edge</h3>
            <ul>
                <li><strong>Differentiation:</strong> [2 specific ways to stand out]</li>
                <li><strong>Authority:</strong> [2 thought leadership strategies]</li>
            </ul>
        </div>
        
        <div class="outreach">
            <h3>Influencers & Events</h3>
            <ul>
                <li><strong>Influencers:</strong> [2 collaboration benefits with execution tips]</li>
                <li><strong>Events:</strong> [2 participation strategies with timing recommendations]</li>
            </ul>
        </div>
        
        <div class="budget">
            <h3>Budget & Metrics</h3>
            <ul>
                <li><strong>Allocation:</strong> [Specific breakdown: Ads X%, Collabs Y%, Events Z%]</li>
                <li><strong>KPIs:</strong> [3 essential metrics with measurement methods]</li>
                <li><strong>Tools:</strong> [3 analytics platforms with usage recommendations]</li>
            </ul>
        </div>
    </section>

    FINAL INSTRUCTIONS:
    - Return ONLY the HTML above.
    - Fill ALL list items with specific, actionable content.
    - Use bullet points within list items for better organization.
    - Incorporate {current_year} trends and opportunities.
    - Ensure professional, polished language.
    - Maintain exact HTML structure for CSS compatibility.
    - All recommendations must be executable immediately.
    - For the Budgets make sure the are in TND with it's equivalents in Euros and Dollars. Make sure when there is money the main coin is TND.
    - Keep it brief and efficient.
    """

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_completion_tokens=4096,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            stop=None
        )
        
        content = completion.choices[0].message.content
        
        # Validate and clean the HTML output
        content = validate_html_structure(content)
        
        time.sleep(3)
        return content
        
    except Exception as e:
        logger.error(f"Failed to generate marketing advice: {str(e)}")
        return f"Failed to generate marketing advice: {str(e)}"

def validate_html_structure(html_content: str) -> str:
    """
    Ensure the HTML output maintains the exact structure for CSS compatibility
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Ensure all required sections are present
        required_sections = ['growth', 'content', 'advantage', 'outreach', 'budget']
        
        for section in required_sections:
            if not soup.find('div', class_=section):
                logger.warning(f"Missing section: {section}")
        
        return str(soup)
    
    except Exception as e:
        logger.error(f"HTML validation failed: {str(e)}")
        return html_content  # Return original if validation fails