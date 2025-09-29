import time
import random
import requests
from groq import Groq
from bs4 import BeautifulSoup
from config.config import settings
import logging
from config.config import get_db_connection, get_db_cursor, release_db_connection
from typing import List, Dict, Any, Optional
import json
import re
import os

logger = logging.getLogger(__name__)

# Initialize Groq client
GROQ_API_KEY = settings.GROQ_API_KEY_2
client = Groq(api_key=GROQ_API_KEY)

# Firecrawl API configuration
FIRECRAWL_API_KEY = settings.FIRECRAWL_API_KEY_2
FIRECRAWL_API_URL = settings.FIRECRAWL_API_URL

# Tavily API for search
TAVILY_API_KEY = settings.TAVILY_API_KEY_2
TAVILY_API_URL = settings.TAVILY_API_URL

# JSON file path
INFLUENCERS_JSON_PATH = os.path.join(os.path.dirname(__file__), "influencers_collab.json")


def generate_email_from_handle(handle):
    """
    Generate Gmail address from handle if email is not available
    """
    if not handle:
        return None
    
    # Remove @ symbol if present
    clean_handle = handle.strip().replace('@', '')
    
    # Return the handle with @gmail.com
    return f"{clean_handle}@gmail.com"


def format_followers(follower_count):
    """Format follower count to K/M format (e.g., 180K, 1.2M)"""
    try:
        # Handle string inputs like "180,000" or "1,200,000" or "180K" or "1.2M"
        if isinstance(follower_count, str):
            # Remove commas from numbers like "180,000"
            follower_count = follower_count.replace(',', '')
            
            # If already in K/M format, return as is
            if 'K' in follower_count.upper() or 'M' in follower_count.upper():
                return follower_count.upper()
            
            # Convert to number
            num = float(follower_count)
        else:
            # Handle numeric inputs
            num = float(follower_count)
        
        # Format based on size
        if num >= 1000000:
            formatted = f"{num/1000000:.1f}M"
            # Remove .0 if whole number
            return formatted.replace('.0', '') if '.0' in formatted else formatted
        elif num >= 1000:
            formatted = f"{num/1000:.0f}K"
            return formatted
        else:
            return str(int(num))
            
    except:
        # Fallback to random realistic value in proper format
        return random.choice(['50K', '100K', '250K', '500K', '1M', '1.5M', '2M'])

def load_json_influencers():
    """Load influencers from the JSON file"""
    try:
        if os.path.exists(INFLUENCERS_JSON_PATH):
            with open(INFLUENCERS_JSON_PATH, 'r', encoding='utf-8') as f:
                influencers = json.load(f)
                logger.info(f"Loaded {len(influencers)} influencers from JSON file")
                return influencers
        else:
            logger.warning("JSON influencers file not found")
            return []
    except Exception as e:
        logger.error(f"Failed to load JSON influencers: {str(e)}")
        return []

def scrape_tunisian_influencers() -> Optional[List[Dict[str, Any]]]:
    """
    Scrape Tunisian influencers from Modash website using Firecrawl API
    """
    try:
        logger.info("Scraping Tunisian influencers from Modash using Firecrawl API...")

        schema = {
            "type": "object",
            "properties": {
                "influencers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "followers": {"type": "string"},
                            "platforms": {"type": "string"},
                            "handle": {"type": "string"},
                            "niche": {"type": "string"},
                            "engagement_rate": {"type": "string"},
                            "collaboration_types": {"type": "string"},
                            "price_range": {"type": "string"}
                        }
                    }
                }
            }
        }

        payload = {
            "url": "https://www.modash.io/find-influencers/tunisia",
            "formats": [{
                "type": "json",
                "schema": schema,
                "prompt": "Extract a list of Tunisian influencers with their details including name, email, followers count, platforms, social media handle, niche, engagement rate, collaboration types, and price range. Make sure to extract the exact handle as shown on the platform."
            }],
            "onlyMainContent": True
        }

        headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(FIRECRAWL_API_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        result = response.json()

        if result.get('success') and result.get('data', {}).get('json', {}).get('influencers'):
            influencers = result['data']['json']['influencers']
            logger.info(f"Successfully scraped {len(influencers)} influencers from website")
            return enhance_influencer_data(influencers)
        else:
            logger.warning("No influencers found in scraped data")
            return []

    except Exception as e:
        logger.error(f"Failed to scrape influencers: {str(e)}")
        return []

def enhance_influencer_data(influencers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhance influencer data with proper formatting
    """
    enhanced_influencers = []
    
    for influencer in influencers:
        try:
            # Format followers count properly
            if 'followers' in influencer and influencer['followers']:
                influencer['followers'] = format_followers(influencer['followers'])
            
            # Ensure we have all required fields
            if 'handle' not in influencer or not influencer['handle']:
                name_part = influencer.get('name', '').split()[0].lower()
                influencer['handle'] = f"@{name_part}"
            
            # Generate email from handle if email is missing or invalid
            email = influencer.get('email', '')
            if not email or email.lower() in ['n/a', 'null', 'none', '', 'dms']:
                influencer['email'] = generate_email_from_handle(influencer['handle'])
            
            if 'followers' not in influencer or not influencer['followers']:
                influencer['followers'] = format_followers(random.randint(50000, 2000000))
            
            if 'niche' not in influencer or not influencer['niche']:
                influencer['niche'] = "Lifestyle"
            
            if 'platforms' not in influencer or not influencer['platforms']:
                influencer['platforms'] = "Instagram"
            
            if 'engagement_rate' not in influencer or not influencer['engagement_rate']:
                influencer['engagement_rate'] = f"{random.randint(3, 8)}%"
            
            if 'collaboration_types' not in influencer or not influencer['collaboration_types']:
                influencer['collaboration_types'] = "Sponsored Posts, Brand Collaborations"
            
            if 'price_range' not in influencer or not influencer['price_range']:
                followers = influencer['followers']
                if 'K' in followers:
                    num = float(followers.replace('K', '')) * 1000
                elif 'M' in followers:
                    num = float(followers.replace('M', '')) * 1000000
                else:
                    num = float(followers)
                
                if num < 10000:
                    price = "100-300 TND"
                elif num < 50000:
                    price = "300-700 TND"
                elif num < 100000:
                    price = "700-1200 TND"
                elif num < 500000:
                    price = "1200-2500 TND"
                else:
                    price = "2500-5000 TND"
                
                influencer['price_range'] = price
            
            enhanced_influencers.append(influencer)
            
        except Exception as e:
            logger.warning(f"Failed to enhance data for {influencer.get('name')}: {str(e)}")
            continue
    
    return enhanced_influencers

def merge_influencers(web_influencers, json_influencers):
    """
    Merge web scraped influencers with JSON influencers, prioritizing JSON data for emails/handles
    """
    merged_influencers = []
    
    # First add all JSON influencers
    for json_inf in json_influencers:
        # Generate email from handle if email is missing or invalid
        email = json_inf.get('email', '')
        if not email or email.lower() in ['n/a', 'null', 'none', '', 'dms']:
            email = generate_email_from_handle(json_inf.get('handle', ''))
        
        merged_influencers.append({
            "name": json_inf.get("name", ""),
            "handle": json_inf.get("handle", ""),
            "email": email,
            "followers": format_followers(json_inf.get("followers", "0")),
            "niche": json_inf.get("niche", "Lifestyle"),
            "platforms": "Instagram",  # Default platform
            "engagement_rate": f"{random.randint(3, 8)}%",
            "collaboration_types": "Sponsored Posts, Brand Collaborations",
            "price_range": "500-2000 TND",
            "source": "json"
        })
    
    # Add web influencers that don't exist in JSON
    for web_inf in web_influencers:
        web_name = web_inf.get("name", "").lower().strip()
        web_handle = web_inf.get("handle", "").lower().strip()
        
        # Check if this influencer already exists in JSON
        exists_in_json = False
        for json_inf in json_influencers:
            json_name = json_inf.get("name", "").lower().strip()
            json_handle = json_inf.get("handle", "").lower().strip()
            
            if (web_name == json_name or web_handle == json_handle or 
                web_name in json_name or json_name in web_name):
                exists_in_json = True
                break
        
        if not exists_in_json:
            # Generate email from handle if email is missing or invalid
            email = web_inf.get('email', '')
            if not email or email.lower() in ['n/a', 'null', 'none', '', 'dms']:
                email = generate_email_from_handle(web_inf.get('handle', ''))
                web_inf['email'] = email
            
            merged_influencers.append({
                **web_inf,
                "source": "web"
            })
    
    return merged_influencers

def extract_company_niche(products, services, brand_tone):
    """
    Extract the company's niche from products, services, and brand tone
    """
    text = f"{products} {services} {brand_tone}".lower()
    
    niches = {
        'fashion': ['fashion', 'clothing', 'apparel', 'outfit', 'style', 'mode', 'أزياء'],
        'beauty': ['beauty', 'cosmetic', 'makeup', 'skincare', 'hair', 'grooming', 'جمال'],
        'lifestyle': ['lifestyle', 'life', 'daily', 'home', 'living', 'حياة'],
        'food': ['food', 'restaurant', 'recipe', 'cooking', 'culinary', 'طعام', 'مطبخ'],
        'fitness': ['fitness', 'gym', 'workout', 'exercise', 'health', 'رياضة', 'صحة'],
        'tech': ['tech', 'technology', 'gadget', 'electronic', 'digital', 'تكنولوجيا'],
        'travel': ['travel', 'tour', 'vacation', 'destination', 'adventure', 'سفر'],
        'nutrition': ['nutrition', 'diet', 'food', 'health', 'wellness', 'تغذية', 'صحة'],
        'music': ['music', 'rapper', 'singer', 'artist', 'موسيقى', 'غناء'],
        'entertainment': ['entertainment', 'cinema', 'tv', 'streamer', 'تسلية', 'ترفيه'],
        'gaming': ['gaming', 'games', 'gamer', 'ألعاب', 'تسلية'],
        'tech_ai': ['tech', 'ai', 'data', 'coding', 'development', 'science', 'maths', 'تكنولوجيا']
    }
    
    for niche, keywords in niches.items():
        for keyword in keywords:
            if keyword in text:
                return niche.capitalize()
    
    return "Lifestyle"

def match_influencers_to_theme(influencers: List[Dict[str, Any]], company_niche: str, products: str, services: str) -> List[Dict[str, Any]]:
    """
    Match influencers to company theme with preference for JSON influencers
    """
    # Score influencers based on relevance
    scored_influencers = []
    
    for influencer in influencers:
        score = 0
        
        # Check niche match
        influencer_niche = influencer.get('niche', '').lower()
        if company_niche.lower() in influencer_niche:
            score += 10
        elif any(word in influencer_niche for word in company_niche.lower().split()):
            score += 5
        
        # Check products/services keywords in niche
        keywords = f"{products} {services}".lower()
        if any(keyword in influencer_niche for keyword in keywords.split()):
            score += 3
        
        # Prefer JSON influencers
        if influencer.get('source') == 'json':
            score += 2
        
        scored_influencers.append((score, influencer))
    
    # Sort by score and select top 6 for random selection
    scored_influencers.sort(key=lambda x: x[0], reverse=True)
    top_influencers = [inf for score, inf in scored_influencers[:6]]
    
    # Randomly select 3 from top matches, ensuring platform diversity
    selected = []
    platforms_used = set()
    
    random.shuffle(top_influencers)
    for influencer in top_influencers:
        if len(selected) >= 3:
            break
        
        platform = influencer.get('platforms', '').lower()
        if platform not in platforms_used or len(platforms_used) < 2:
            selected.append(influencer)
            platforms_used.add(platform)
    
    # If we don't have enough, add any from top
    if len(selected) < 3:
        for influencer in top_influencers:
            if influencer not in selected:
                selected.append(influencer)
            if len(selected) >= 3:
                break
    
    return selected[:3]

def search_additional_influencer_data(influencers: List[Dict[str, Any]]):
    """
    Search for additional data about influencers (engagement, growth rate, etc.)
    """
    enhanced_influencers = []
    
    for influencer in influencers:
        enhanced_inf = influencer.copy()
        
        # Generate email from handle if missing or invalid
        email = enhanced_inf.get('email', '')
        if not email or email.lower() in ['n/a', 'null', 'none', '', 'dms']:
            enhanced_inf['email'] = generate_email_from_handle(enhanced_inf.get('handle', ''))
        
        # Only search for additional data for JSON influencers
        if influencer.get('source') == 'json':
            try:
                name = influencer.get('name', '')
                handle = influencer.get('handle', '')
                
                # Search for engagement data
                search_query = f"{name} {handle} engagement rate growth Tunisia"
                
                payload = {
                    "api_key": TAVILY_API_KEY,
                    "query": search_query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 2
                }
                
                response = requests.post(TAVILY_API_URL, json=payload, timeout=30)
                if response.ok:
                    data = response.json()
                    
                    # Try to extract engagement rate from results
                    if data.get('results'):
                        for result in data['results']:
                            content = result.get('content', '').lower()
                            if 'engagement' in content and '%' in content:
                                # Look for engagement rate pattern
                                engagement_match = re.search(r'(\d+\.?\d*)%', content)
                                if engagement_match:
                                    enhanced_inf['engagement_rate'] = f"{engagement_match.group(1)}%"
                                    break
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Failed to search additional data for {name}: {str(e)}")
        
        enhanced_influencers.append(enhanced_inf)
    
    return enhanced_influencers

def clean_html_response(content: str) -> str:
    """
    Clean the AI response by removing markdown code blocks and extra formatting
    """
    # Remove ```html and ``` markers
    content = re.sub(r'```html\s*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'```', '', content)
    
    # Remove any leading/trailing whitespace
    content = content.strip()
    
    # Ensure content starts with <section
    if not content.startswith('<section'):
        # Find the first <section tag
        section_match = re.search(r'<section.*?>', content, re.DOTALL)
        if section_match:
            start_index = content.find(section_match.group())
            content = content[start_index:]
    
    return content

def generate_influencer_recommendations(company_data, target_audience, products, services):
    """
    Generate influencer recommendations using both web scraped and JSON data
    """
    # Load influencers from both sources
    json_influencers = load_json_influencers()
    web_influencers = scrape_tunisian_influencers()
    
    # Merge influencers, prioritizing JSON data
    all_influencers = merge_influencers(web_influencers, json_influencers)
    
    if not all_influencers:
        logger.error("No influencers available from any source")
        return "<section class='influencer-recommendations'><h2>Error: Could not retrieve influencer data</h2></section>"
    
    # Extract company niche
    company_niche = extract_company_niche(products, services, company_data.get('brand_tone', ''))
    
    # Match influencers to theme
    selected_influencers = match_influencers_to_theme(all_influencers, company_niche, products, services)
    
    # Search for additional data for JSON influencers
    selected_influencers = search_additional_influencer_data(selected_influencers)
    
    # Prepare influencer data for the prompt
    influencer_data_str = "\n".join([
        f"Influencer {i+1}: {inf.get('name', 'Unknown')} - {inf.get('platforms', 'Unknown')} - "
        f"{inf.get('niche', 'Unknown')} - {inf.get('followers', 'Unknown')} followers - "
        f"Handle: {inf.get('handle', 'Unknown')} - Email: {inf.get('email', 'Unknown')}"
        for i, inf in enumerate(selected_influencers)
    ])
    
    prompt = f"""
    Recommend exactly 3 Tunisian influencers for {company_data['name']} to promote:
    - Products: {products}
    - Services: {services}
    - Target Audience: {target_audience}
    - Brand Tone: {company_data['brand_tone']}
    
    For each influencer include:
    - Full name
    - Professional contact email
    - Number of followers and platform
    - Social media handle
    - Niche/expertise
    - Engagement rate
    - Collaboration types and price range (in TND)
    
    CRITICAL INSTRUCTION: YOU MUST USE THE EXACT DATA PROVIDED BELOW WITHOUT MODIFICATION:
    - Use the exact follower numbers as provided (e.g., 180K, 2.3M) - DO NOT convert them
    - Use the exact email addresses as provided
    - Use the exact handles as provided
    - Use the exact niches as provided
    
    Also generate:
    1. Complete outreach strategy
    2. Customized professional email for each influencer (3 total)
    
    INFLUENCER DATA:
    {influencer_data_str}
    
    OUTPUT FORMAT:
    <section class="influencer-recommendations">
        <h2>Recommended Tunisian Influencers for {company_data['name']}</h2>
        <div class="influencer-grid">
            <!-- Generate exactly 3 influencers -->
            <div class="influencer-card">
                <h3>INFLUENCER_NAME: [Full Name]</h3>
                <p>EMAIL: [professional@email.com]</p>
                <p>FOLLOWERS: [Number] (Platform: [Platform])</p>
                <p>HANDLE: [@username]</p>
                <p>NICHE: [Fashion/Tech/Lifestyle etc.]</p>
                <p>ENGAGEMENT_RATE: [X%]</p>
                <p>COLLABORATION_TYPE: [Type]</p>
                <p>Price Range: [Price Range in TND Only put the price range without any other text Exp: 800 – 2,000 TND] </p>
            </div>
            <!-- 2 more influencers -->
        </div>
        
        <div class="outreach-strategy">
            <h3>Influencer Outreach Strategy</h3>
            <ul>
                <li>Timing: [Best days/times to contact]</li>
                <li>Approach: [Collaboration proposal style]</li>
                <li>Budget Allocation: [Amount per influencer]</li>
                <li>Campaign Duration: [Timeline]</li>
            </ul>
            
            <!-- Custom emails for each influencer -->
            <div class="email-content">
                <h4>Message - E-mail for: [Influencer Name 1]</h4>
                <textarea class="editable-email" data-influencer-id="0" rows="8" style="width: 100%;">
                Subject: Partnership Opportunity with {company_data['name']}

                Dear [Influencer Name],
                
                We've been following your work in [Niche/Field] and are impressed by your creativity and community engagement.
                We'd love to collaborate with you to promote our products/services to your audience.
                Let us know if you're interested — we'd be happy to discuss further.
                
                Best regards,  
                Marketing Team – {company_data['name']}  
                {company_data.get('website', '')}
                {company_data.get('phone_number', '')}
                </textarea>
            </div>
            <!-- 2 more emails, for the other 2 you should add/Increment +1 to the data-influencer-id  -->
        </div>
    </section>
    
    Important :
        - Use the exact influencer data provided
        - When you generate the e-mails make sure it's always in we dont use names or person its alwasy we as in safia marketing team
        - Keep the HTML structure exactly as shown
        - Ensure platform diversity in the selection
        - Tailor recommendations to match the company niche: {company_niche}
    """

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=8192,
            top_p=1,
            stream=False
        )
    
        content = completion.choices[0].message.content
        
        # Clean the response to remove markdown formatting
        cleaned_content = clean_html_response(content)
        
        time.sleep(4)
        return cleaned_content

    except Exception as e:
        logger.error(f"Failed to generate influencer recommendations: {str(e)}")
        return "<section class='influencer-recommendations'><h2>Error: Could not generate recommendations</h2></section>"

# The rest of your existing functions remain unchanged
def extract_and_save_influencers(strategy_id: int, company_id: int, user_id: int, strategy_content: str):
    """Extract influencer data from strategy content and save to database"""
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)

        soup = BeautifulSoup(strategy_content, 'html.parser')
        influencer_section = soup.find('section', class_='influencer-recommendations')

        if not influencer_section:
            logger.warning("No influencer section found in strategy content")
            return

        influencer_cards = influencer_section.find_all('div', class_='influencer-card')
        email_textareas = influencer_section.find_all('textarea', class_='editable-email')

        logger.info(f"Found {len(influencer_cards)} influencer cards and {len(email_textareas)} email textareas")

        for idx, card in enumerate(influencer_cards):
            logger.info(f"Processing influencer {idx}")

            # Extract data from each card
            data = {
                'name': extract_field(card, 'INFLUENCER_NAME:'),
                'email': extract_field(card, 'EMAIL:'),
                'followers': extract_field(card, 'FOLLOWERS:'),
                'platform': extract_field(card, 'Platform:', after_key=True),
                'handle': extract_field(card, 'HANDLE:'),
                'niche': extract_field(card, 'NICHE:'),
                'engagement_rate': extract_field(card, 'ENGAGEMENT_RATE:'),
                'collaboration_type': extract_field(card, 'COLLABORATION_TYPE:'),
                'price_range': extract_price_range(card),
                'email_text': None,
            }
            
            # Generate email from handle if email is missing or invalid
            email = data.get('email', '')
            if not email or email.lower() in ['n/a', 'null', 'none', '', 'dms']:
                data['email'] = generate_email_from_handle(data.get('handle', ''))

            # Get the corresponding email textarea content
            if idx < len(email_textareas):
                textarea = email_textareas[idx]
                email_content = textarea.get_text() if textarea else None
                if email_content:
                    data['email_text'] = email_content.strip()
                    logger.info(f"Extracted email for influencer {idx}: {len(email_content)} characters")
                else:
                    logger.warning(f"No email content found for influencer {idx}")
            else:
                logger.warning(f"No textarea found for influencer {idx}")

            try:
                # Save to database
                cursor.execute("""
                    INSERT INTO influencers (
                        strategy_id, company_id, user_id, name, email, followers, 
                        platform, handle, niche, engagement_rate, collaboration_type,
                        price_range, email_text
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    strategy_id, company_id, user_id,
                    data['name'], data['email'], data['followers'],
                    data['platform'], data['handle'], data['niche'],
                    data['engagement_rate'], data['collaboration_type'],
                    data['price_range'], data['email_text']
                ))

                logger.info(f"Successfully saved influencer {idx}: {data['name']} with email length: {len(data['email_text']) if data['email_text'] else 0}")

            except Exception as insert_error:
                logger.error(f"Failed to insert influencer {idx}: {str(insert_error)}")
                continue   

        conn.commit()
        logger.info(f"Successfully committed all influencers for strategy {strategy_id}")

    except Exception as e:
        logger.error(f"Failed to extract influencers: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_db_connection(conn)

def extract_field(card, key, after_key=False):
    """Helper to extract field values from influencer card"""
    try:
        text = card.get_text()
        if key in text:
            if after_key:
                parts = text.split(key)
                if len(parts) > 1:
                    return parts[1].split(')')[0].strip()
            else:
                parts = text.split(key)
                if len(parts) > 1:
                    return parts[1].split('\n')[0].strip()
        return None
    except:
        return None

def extract_price_range(card):
    """Extract price range from collaboration type"""
    try:
        # Get the entire text content of the card
        text = card.get_text()
        
        # Look for the COLLABORATION_TYPE: pattern
        if 'COLLABORATION_TYPE:' in text:
            # Extract the part after COLLABORATION_TYPE:
            collab_part = text.split('COLLABORATION_TYPE:')[1].split('\n')[0].strip()
            
            # Look for price patterns with various separators (dash, en dash, em dash, etc.)
            price_patterns = [
                r'(\d+[, ]?\d*\s*[–\-—]\s*\d+[, ]?\d*\s*TND)',  # Matches "1,200 – 1,800 TND"
                r'(\d+[, ]?\d*\s*to\s*\d+[, ]?\d*\s*TND)',      # Matches "1,200 to 1,800 TND"
                r'(\d+[, ]?\d*\s*TND)',                         # Matches "1,200 TND"
                r'(\d+[, ]?\d*\s*[–\-—]\s*\d+[, ]?\d*)',        # Matches "1,200 – 1,800"
                r'(\d+[, ]?\d*\s*to\s*\d+[, ]?\d*)',            # Matches "1,200 to 1,800"
                r'(\d+[, ]?\d*)'                                # Matches "1200"
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, collab_part, re.IGNORECASE)
                if price_match:
                    price_range = price_match.group(1).strip()
                    # Clean up the price range (remove special spaces, ensure TND)
                    price_range = price_range.replace(' ', '').replace(',', '')  # Remove special spaces and commas
                    if 'TND' not in price_range.upper():
                        price_range += ' TND'
                    return price_range
            
            # If no pattern matched but there's a dash/en dash/em dash, use the price part
            dash_patterns = [r'[–\-—]']
            for dash_pattern in dash_patterns:
                if re.search(dash_pattern, collab_part):
                    # Split by dash and take the last part that contains numbers
                    parts = re.split(dash_pattern, collab_part)
                    for part in reversed(parts):
                        if re.search(r'\d', part):
                            price_part = part.strip()
                            # Extract just the numbers and TND
                            numbers_match = re.search(r'(\d+[, ]?\d*)\s*(TND)?', price_part, re.IGNORECASE)
                            if numbers_match:
                                price_range = numbers_match.group(1).replace(' ', '').replace(',', '')
                                if numbers_match.group(2):
                                    price_range += ' TND'
                                else:
                                    price_range += ' TND'
                                return price_range
        
        # Fallback: look for any price pattern in the entire card text
        fallback_patterns = [
            r'(\d+[, ]?\d*\s*[–\-—]\s*\d+[, ]?\d*\s*TND)',
            r'(\d+[, ]?\d*\s*to\s*\d+[, ]?\d*\s*TND)',
            r'(\d+[, ]?\d*\s*TND)',
            r'(\d+[, ]?\d*\s*[–\-—]\s*\d+[, ]?\d*)',
            r'(\d+[, ]?\d*\s*to\s*\d+[, ]?\d*)'
        ]
        
        for pattern in fallback_patterns:
            price_match = re.search(pattern, text, re.IGNORECASE)
            if price_match:
                price_range = price_match.group(1).strip()
                price_range = price_range.replace(' ', '').replace(',', '')  # Remove special spaces and commas
                if 'TND' not in price_range.upper():
                    price_range += ' TND'
                return price_range
        
        return "500-2000 TND"  # Default fallback
        
    except Exception as e:
        logger.warning(f"Failed to extract price range: {str(e)}")
        return "500-2000 TND"  # Default fallback