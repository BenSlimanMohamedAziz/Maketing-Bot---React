import logging
import re
import time
from fastapi import logger
from groq import AsyncGroq,Groq
import requests
from config.config import settings
from datetime import datetime

# Initialize Groq client
GROQ_API_KEY = settings.GROQ_API_KEY_1
client = Groq(api_key=GROQ_API_KEY)

logger = logging.getLogger(__name__)
   

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
    
def generate_event_strategy(company_data, events_text, current_date):
    """
    Generate an event participation strategy focusing on the most relevant 2 events
    """
    
 
    prompt = f"""
    IMPORTANT: You are my personal marketing strategist working directly for my company {company_data['name']}, Here's the logo {company_data.get('logo_url', '')}
    (this will be used for making a COMPLETE marketing events for our company). 
    Also as Event Strategy Director for {company_data['name']}, create a HIGHLY TARGETED 
    event participation plan focusing on ONLY 4 events that will deliver maximum value.

    === COMPANY CONTEXT ===
    🏢 Company: {company_data['name']}
    🏢 Slogan: {company_data['slogan']}
    🏢 DESCRIPTION: {company_data['description']}
    🎯 Audience: {company_data.get('target_audience_types', 'Not specified')}
    🏆 Goals: {company_data.get('marketing_goals', '')}
    💰 Budget: ${company_data.get('monthly_budget', 'N/A')}
    🗓 Current Date: {current_date}
    === AVAILABLE EVENTS ===
    {events_text}

    === STRATEGY REQUIREMENTS ===
    1. SELECTION: Choose ONLY 4 events with strongest alignment to:
       - Our target audience
       - Marketing goals
       - Budget considerations
    2. For EACH selected event provide:
       a. DATE & LOCATION: Exact details (From the {events_text} )
       b. STRATEGIC VALUE: 2 specific benefits for us
       c. PARTICIPATION PLAN: Concrete action steps
       d. UNIQUE ANGLES: Different approaches for each event
    3. FORMATTING: Use bullet points for clarity
    4. For coins, money, prices and budget make sure it's always in TND

    === OUTPUT FORMAT ===
        <section class="event-strategy">
                      <h2>Event Participation Strategy</h2>
                        <div>
                          {events_text}
                            [For each relevant event:
                            - Extract Event Title
                            - Extract the Date and Place
                            - Why this event matters for my company and benefits
                            - How to participate effectively + activities
                            ]
                        </div>
                    </section>


    === FINAL INSTRUCTIONS ===
    1. BE SELECTIVE: Only include 4 events
    2. BE SPECIFIC: Exact dates, locations, and actions
    3. BE STRATEGIC: Clear business rationale for each
    4. FORMAT: ONLY return the HTML block above
    5. NO DISCLAIMERS: Just the event strategy
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
            temperature=0.3,
            max_completion_tokens=2500,
            top_p=1,
            stream=False,
            stop=None
        )
        
        content = completion.choices[0].message.content
        
        # Clean the response to remove markdown formatting
        cleaned_content = clean_html_response(content)
        time.sleep(2)  # Shorter wait for this smaller generation
        print(events_text)
        return cleaned_content
    
    except Exception as e:
        logger.error(f"Failed to generate event strategy: {str(e)}")
        raise Exception(f"Event strategy generation failed: {str(e)}")