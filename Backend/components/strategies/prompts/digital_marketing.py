import time
from groq import Groq
import requests
from config.config import settings
from datetime import datetime
import logging
from config.config import get_db_connection, get_db_cursor, release_db_connection

# Initialize Groq client
GROQ_API_KEY = settings.GROQ_API_KEY_4
client = Groq(api_key=GROQ_API_KEY)

logger = logging.getLogger(__name__)


def generate_platform_strategies(company_data, current_date, logo_description):
    
    
    # Format target audience
    target_audience = f"""
    - Age Groups: {company_data.get('target_age_groups', 'Not specified')}
    - Audience Types: {company_data.get('target_audience_types', 'Not specified')}
    - Business Types: {company_data.get('target_business_types', 'Not specified')}
    - Geographic Targets: {company_data.get('target_geographics', 'Not specified')}
    """
    
    prompt = f"""
    IMPORTANT: You are my personal marketing strategist working directly for my company {company_data['name']}. Here's the logo {company_data.get('logo_url', '')} and logo description too:
        {logo_description}.
        Generate a COMPLETE, EXECUTABLE marketing strategy with ALL practical implementation details.

        -- IMPORTANT CONTEXT RULES --
        • DO NOT reference the current season in any way.
        • DO NOT reference or use special events in any way.
        • You may use today's date ONLY for scheduling (day-of-week/time), not for seasonal hooks.

        - Follow the COMPANY PROFILE, the REQUIREMENTS and INSTRUCTIONS to generate the platforms contents :
                =>   COMPANY PROFILE - INFO:
                    {{
                        "NAME": "{company_data['name']}",
                        "SLOGAN": "{company_data.get('slogan', '')}",
                        "DESCRIPTION": "{company_data.get('description', '')}",
                        "PRODUCTS": "{company_data.get('products', '')}",
                        "SERVICES": "{company_data.get('services', '')}",
                        "TARGET AUDIENCE": {target_audience},
                        "PLATFORMS": "{company_data['preferred_platforms']}",
                        "PHONE": "{company_data.get('phone', '')}",
                        "WEBSITE": "{company_data.get('website', '')}",
                        "BRAND TONE": "{company_data['brand_tone']}",
                        "BUDGET": "{company_data.get('monthly_budget', '')}",
                        "MARKETING GOALS": "{company_data.get('marketing_goals', '')}",
                        "LOGO": "{company_data.get('logo_url', 'No logo')}",
                        "LOGO Description":"{logo_description}"
                    }}

    REQUIREMENTS:
        1. EXECUTABLE STRATEGY: Provide ready-to-implement actions.
        2. VISUAL GUIDANCE: Include specific design directions using brand colors.
        3. PLATFORM-SPECIFIC: => INSTRUCTIONS:
                                    1. For EACH platform in {company_data['preferred_platforms']}, generate detailed content plans.
                                    2. For each content type, provide EXACT specifications including:
                                    - Posting : - Frequency (X times/week) and Time
                                    - Image prompts that match the description (for visual content and to use for the image generation model)
                                    - Video ideas (for video content)
                                    - Captions with hashtags
                                    - Make sure all the platform and all the content types have different captions, hashtags and descriptions
                                    3. All content must align with brand tone and target audience (IGNORE season and special events entirely).

                                    CAPTION STYLE GUIDE (apply to every CAPTION for images/videos):
                                    - Structure: Hook (1-2 lines) → Value (3-5 detailed bullet points) → CTA (1-2 lines with website/phone).
                                    - Professional, engaging tone; avoid fluff; keep it platform-appropriate.
                                    - Up to 6 relevant hashtags max; vary per item; no repetition across items in the same content type.
                                    - Examples of tone/structure to emulate (adapt to the company profile/theme):
                                    ---
                                    🚀 Scaling your software development shouldn't be complicated.

                                    At NSR, we bridge the gap between ambition and execution by offering flexible nearshoring solutions:

                                    🔹 Staff Augmentation and skilled developers seamlessly integrated into your team.
                                    🔹 Dedicated Teams, our experts working as an extension of your organization.
                                    🔹 Full Outsourcing, we build, you scale.
                                    🔹 AI Agents Development : from automation to intelligent decision-making, we craft AI-driven agents that optimize workflows, enhance customer experiences, and deliver real-time insights.

                                    With expertise across modern technologies (React, Angular, Node.js, Python, Java, .NET, and more) and specialized fields like AI, Data Science, Cloud, Cybersecurity, and Intelligent Agents, we deliver future-ready solutions tailored to your business.

                                    💡 Why partner with us?
                                    ✔ Time zone & cultural alignment
                                    ✔ Cost-effective, high-quality delivery
                                    ✔ Agile teams that grow with your vision

                                    Let's build something remarkable together 🚀.

                                    🌐 Learn more: nearshorepublic.com 
                                    ---
                                    🇹🇳 Tunisia: Africa's Rising Tech Capital?

                                    We're proud to be featured in this inspiring documentary exploring Tunisia's vibrant startup ecosystem — with a spotlight on Coworky and a special message from our co-founder. 💡

                                    Huge thanks to Martin Cregut for capturing the energy and potential of our ecosystem, and to Expertise France and Innov'i - EU4Innovation for making it possible.

                                    🎥 Watch the full video: https://lnkd.in/dYKHUiN7
                                    ---
                                    🔥Innovation. Connection. Growth. 🚀✨

                                    🤩Coworky was proud to host the Netherlands Embassy visit , bringing together visionary entrepreneurs, industry leaders, and the Ambassade des Pays-Bas en Tunisie Dutch Ambassador for a day of collaboration and opportunity. As an innovation hub, we believe in creating spaces where bold ideas thrive and global partnerships take shape.

                                    👉The room was alive with energy as visionary entrepreneurs, industry leaders, and even the Dutch Ambassador himself gathered under one roof. It was a day of collaboration, opportunity, and the kind of magic that happens when brilliant minds unite. Conversations flowed, ideas were exchanged, and the seeds of global partnerships were planted.

                                    📲Watch the recap and witness the energy, insights, and game-changing connections that define the future of business.

                                    The end? No—this was only the start. 🚀✨

                                    IMAGE & VIDEO PROMPT GUIDELINES:
                                    - MUST be simple, realistic scenes - NO graphics, shapes, illustrations, or abstract concepts
                                    - ABSOLUTELY NO text or logos of any kind in the visuals
                                    - Focus on real people, objects, environments related to the company's industry
                                    - Examples for tech company: "A development team working in a modern office", "Senior developer coding on laptop", "Team meeting with whiteboard in background"
                                    - Examples for water company: "Person drinking water outdoors", "Bottles of water on a table", "Water pouring into a glass"
                                    - Keep prompts simple, natural, and realistic

                                    OUTPUT FORMAT:

                                            <!-- Platform Strategies -->
                                            <section class="social-media-strategy">
                                                <h2>Platform-Specific Content Plans</h2>

                                                <!-- For each platform -->
                                                <div>
                                                    <h3 data-platform="[Platform Name]">PLATFORM: [Platform Name]</h3>

                                                    <!-- For each content type -->
                                                    <div>
                                                        <h4>TYPE: [Content Type Name]</h4>
                                                        <p>DESCRIPTION: [Content type purpose]</p>
                                                        <p>FREQUENCY: [X times/week]</p>
                                                        <p>BEST TIME: [Specific day/time in format: Day HourAM/PM, e.g., Thursday 9AM]</p>

                                                        <!-- For each item (based on frequency X) -->
                                                        <div>
                                                            <h5>ITEM 1</h5>
                                                            <!-- For Image Posts -->
                                                            <p>POST_IDEA: [Content idea description]</p>
                                                            <p style="display: none;">IMAGE_PROMPT: [SIMPLE, REALISTIC prompt for image generation with NO text and NO logo; realistic scenes related to company industry]</p>
                                                            <p style="display: none;">CAPTION: [Hook → Value → CTA. Follow the detailed format above]</p>
                                                            <p style="display: none;">HASHTAGS: [Up to 6 relevant hashtags separated by spaces]</p>
                                                            <p>Schedule: [From BEST TIME take the specific day/time in format: Day HourAM/PM, e.g., Thursday 9AM (each post must be a unique day/hour)]</p>

                                                            <!-- For Video Posts -->
                                                            <p>VIDEO_IDEA: [Video concept description]</p>
                                                            <p style="display: none;">VIDEO_PLACEHOLDER: [SIMPLE, REALISTIC VIDEO GENERATION PROMPT with NO text and NO logo; realistic scenes related to company industry]</p>
                                                            <p style="display: none;">CAPTION: [Hook → Value → CTA. Follow the detailed format above]</p>
                                                            <p style="display: none;">HASHTAGS: [Up to 6 relevant hashtags separated by spaces]</p>
                                                            <p>Schedule: [From BEST TIME take the specific day/time in format: Day HourAM/PM, e.g., Thursday 9AM (each post must be a unique day/hour)]</p>

                                                            <!-- For Stories -->
                                                            <p>STORY_IDEA: [Story concept]</p>
                                                            <p style="display: none;">IMAGE_PROMPT: [SIMPLE, REALISTIC prompt for story image with NO text and NO logo; realistic scenes related to company industry]</p>
                                                            <p style="display: none;">CAPTION: [Hook → Value → CTA. Follow the detailed format above]</p>
                                                            <p style="display: none;">HASHTAGS: [Up to 6 relevant hashtags separated by spaces]</p>
                                                            <p>Schedule: [From BEST TIME take the specific day/time in format: Day HourAM/PM, e.g., Thursday 9AM (each post must be a unique day/hour)]</p>

                                                                <!-- Or If video -->
                                                                <p>STORY_IDEA: [Story concept]</p>
                                                                <p style="display: none;">VIDEO_PLACEHOLDER: [SIMPLE, REALISTIC VIDEO GENERATION PROMPT with NO text and NO logo; realistic scenes related to company industry]</p>
                                                                <p style="display: none;">CAPTION: [Hook → Value → CTA. Follow the detailed format above]</p>
                                                                <p style="display: none;">HASHTAGS: [Up to 6 relevant hashtags separated by spaces]</p>
                                                                <p>Schedule: [From BEST TIME take the specific day/time in format: Day HourAM/PM, e.g., Thursday 9AM (each post must be a unique day/hour)]</p>
                                                        </div>

                                                        <!-- Next items would follow same structure -->
                                                    </div>

                                                    <!-- Next content type would follow -->
                                                </div>

                                                <!-- Next platform would follow -->
                                            </section>
                                        </div>

                                        EXAMPLE FOR TECH COMPANY:
                                        <div>
                                            <h3 data-platform="LinkedIn">PLATFORM: LinkedIn</h3>

                                            <div>
                                                <h4>TYPE: Image Posts</h4>
                                                <p>DESCRIPTION: Professional images showcasing our team and work environment</p>
                                                <p>FREQUENCY: 2 times/week</p>
                                                <p>BEST TIME: Tuesday 10AM / Thursday 3PM</p>

                                                <div>
                                                    <h5>ITEM 1</h5>
                                                    <p>POST_IDEA: Our development team in action</p>
                                                    <p style="display: none;">IMAGE_PROMPT: A diverse team of software developers collaborating in a modern office environment, working on laptops and discussing code, natural lighting, realistic scene with no text or logos</p>
                                                    <p style="display: none;">CAPTION: Behind the scenes at {company_data['name']} - where innovation meets execution.

    Our dedicated team of developers works tirelessly to deliver cutting-edge solutions:

    • Expertise in modern technologies including React, Node.js, Python, and AI frameworks
    • Agile methodology ensuring rapid iteration and quality delivery
    • Collaborative environment fostering creativity and problem-solving
    • Continuous learning culture keeping us at the forefront of tech trends

    We don't just write code - we build solutions that transform businesses and create real impact.

    Ready to elevate your digital transformation journey?

    🚀 Let's discuss how we can help you achieve your technology goals.

    🌐 Schedule a consultation: {company_data.get('website', '')}
    📞 Call us: {company_data.get('phone', '')}</p>
                                                    <p style="display: none;">HASHTAGS: #SoftwareDevelopment #TechTeam #DigitalTransformation #AgileDevelopment #TechInnovation #Programming</p>
                                                    <p>Schedule: Tuesday 10AM</p>
                                                </div>
                                                <!-- 1 more item would follow -->
                                            </div>
                                        </div>

                                        EXAMPLE FOR WATER COMPANY:
                                        <div>
                                            <h3 data-platform="Instagram">PLATFORM: Instagram</h3>

                                            <div>
                                                <h4>TYPE: Feed Image Posts</h4>
                                                <p>DESCRIPTION: Lifestyle images showing our products in use</p>
                                                <p>FREQUENCY: 2 times/week</p>
                                                <p>BEST TIME: Wednesday 11AM / Friday 4PM</p>

                                                <div>
                                                    <h5>ITEM 1</h5>
                                                    <p>POST_IDEA: Hydration during workout</p>
                                                    <p style="display: none;">IMAGE_PROMPT: An athlete drinking water after workout in a gym setting, natural light, realistic scene with no text or logos, water bottle visible</p>
                                                    <p style="display: none;">CAPTION: Fuel your fitness journey with optimal hydration.

    {company_data['name']} natural mineral water supports your active lifestyle:

    • Essential electrolytes for better hydration and recovery
    • Perfect balance of minerals for sustained energy
    • No additives or preservatives - just pure, natural water
    • Eco-friendly packaging that's easy to carry anywhere

    Whether you're hitting the gym, going for a run, or pushing through your daily routine, proper hydration makes all the difference.

    💧 Stay hydrated, stay strong with {company_data['name']}.

    🌐 Discover our range: {company_data.get('website', '')}
    📞 Contact us: {company_data.get('phone', '')}</p>
                                                    <p style="display: none;">HASHTAGS: #Hydration #Fitness #HealthyLifestyle #MineralWater #Workout #Wellness</p>
                                                    <p>Schedule: Wednesday 11AM</p>
                                                </div>
                                                <!-- 1 more item would follow -->
                                            </div>
                                        </div>

                                        SPECIAL & IMPORTANT NOTES! :
                                        1. Generate EXACTLY the number of items matching the frequency.
                                        2. All content must reflect the brand tone: {company_data['brand_tone']}.
                                        3. IGNORE the current season entirely; do not mention seasons.
                                        4. IGNORE special events entirely; do not mention holidays, events, or observances.
                                        5. For video content, fill VIDEO_PLACEHOLDER with a clear **VIDEO GENERATION PROMPT** (no text/logo), not a URL.
                                        6. For images, IMAGE_PROMPT must be a **simple, realistic prompt** (no text/logo); keep it realistic and related to company industry.
                                        7. Note the content type for Facebook is (1 Video, 2 Text posts (status updates / announcements), and 3 Images Posts) [no stories]); For LinkedIn: ([2 videos a week, 1 Text Post, 2 Image Posts]); and for Instagram: include Reels (minimum 2 reels).
                                        8. When generating the HTML don't forget to add inside the h3 tag: (data-platform="Platform_name") like the Instagram example.
                                        9. Add Hidden style to the IMAGE_PROMPT, CAPTION, HASHTAGS and VIDEO_PLACEHOLDER.
                                        10. For each Platform, make BEST TIME & all Schedules non-identical across items; if days match, use different hours.
                                        11. For each Platform the description must be different from platform to platform.
                                        12. You may include website/phone in CTAs where natural (e.g., "📞 {company_data.get('phone','')}" or "🌐 {company_data.get('website','')}").
                                        13. Create CAPTIONS in the detailed professional format: Hook → Value (3-5 detailed bullet points) → CTA.
                                        14. Keep HASHTAGS separate from CAPTION in their own field.
                                        15. ALL schedule times must be in exact format: Day HourAM/PM (e.g., Thursday 9AM, Friday 3PM, Monday 12PM).
                                        16. CAPTIONS must be detailed, professional, and engaging - NOT short or truncated.
                                        17. IMAGE & VIDEO PROMPTS MUST be simple, realistic scenes - NO graphics, shapes, illustrations, or abstract concepts.
                                        18. ABSOLUTELY NO text or logos of any kind in image/video prompts.
                                        19. Focus on real people, objects, environments related to the company's industry.

        4. TREND-INTEGRATED: Use 2025 marketing trends practically **without** referencing seasons or events (e.g., short-form video, community-led content, AI-assisted workflows, UGC collaboration, educational carousels, value-first copy, social proof).
        5. IMAGE PROMPTS: Must be simple, realistic scenes (NO text/logo/graphics/shapes), aligned with the brand/theme and content idea.
        6. VIDEO PROMPTS: VIDEO_PLACEHOLDER content must be simple, realistic video prompts (NO text/logo/graphics/shapes), simple scenes aligned with platform and idea.

    "FINAL STRICT INSTRUCTIONS:"
        - Return ONLY the HTML above. No extra explanations.
        - Fill all content blocks with strategic, actionable insights.
        - Use 2025 marketing trends as real strategy tools — not just buzzwords.
        - Ensure content is polished, professional, logically flows and executable.
        - Failure to follow the structure exactly is not allowed. Ensure all output follows this precise template and requests.
        - CAPTIONS MUST be detailed and professional like the examples provided, NOT short or truncated.
        - ALL schedule times MUST be in format: Day HourAM/PM (e.g., Thursday 9AM, Friday 3PM).
        - IMAGE & VIDEO PROMPTS MUST be simple, realistic scenes - NO graphics, shapes, illustrations, or abstract concepts.
        - ABSOLUTELY NO text or logos of any kind in image/video prompts.
        - Focus on real people, objects, environments related to the company's industry.
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
            temperature=0.2,
            max_completion_tokens=8192,
            top_p=1,
            stream=False,
            stop=None
        )
        
        content = completion.choices[0].message.content
        
        time.sleep(3)  # Shorter wait for this smaller generation
        return content
    
    except Exception as e:
        logger.error(f"Failed to generate event strategy: {str(e)}")
        raise Exception(f"Event strategy generation failed: {str(e)}")

def save_content_items_to_db(strategy_id, company_id, user_id, content):
    """
    Parse the strategy content and save individual content items to database
    """
    from bs4 import BeautifulSoup

    conn = get_db_connection()
    cursor = get_db_cursor(conn)
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find all platform divs
    platform_divs = soup.find_all('div')
    
    for platform_div in platform_divs:
        # Look for h3 with platform name
        platform_h3 = platform_div.find('h3')
        if not platform_h3 or 'PLATFORM:' not in platform_h3.get_text():
            continue
            
        platform_name = platform_h3.get_text().replace('PLATFORM:', '').strip()
        
        # Find all content type divs within this platform
        content_type_divs = platform_div.find_all('div', recursive=False)
        
        for content_type_div in content_type_divs:
            # Look for h4 with content type
            type_h4 = content_type_div.find('h4')
            if not type_h4 or 'TYPE:' not in type_h4.get_text():
                continue
                
            type_name = type_h4.get_text().replace('TYPE:', '').strip()
            
            # Extract description, frequency, and best_time
            description_p = content_type_div.find('p', string=lambda t: t and t.startswith('DESCRIPTION:'))
            frequency_p = content_type_div.find('p', string=lambda t: t and t.startswith('FREQUENCY:'))
            best_time_p = content_type_div.find('p', string=lambda t: t and t.startswith('BEST TIME:'))
            
            description = description_p.get_text().replace('DESCRIPTION:', '').strip() if description_p else None
            frequency = frequency_p.get_text().replace('FREQUENCY:', '').strip() if frequency_p else None
            best_time = best_time_p.get_text().replace('BEST TIME:', '').strip() if best_time_p else None
            
            # Find all item divs (look for h5 with ITEM)
            item_divs = []
            for item_h5 in content_type_div.find_all('h5', string=lambda t: t and 'ITEM' in t):
                item_div = item_h5.find_parent('div')
                if item_div and item_div not in item_divs:
                    item_divs.append(item_div)
            
            for item_div in item_divs:
                # Initialize all fields
                image_prompt = None
                video_idea = None
                video_placeholder = None
                story_idea = None
                post_idea = None
                caption = None
                hashtags = None
                schedule_time = None
                
                # Extract all paragraphs in this item
                all_ps = item_div.find_all('p')
                
                for p in all_ps:
                    text = p.get_text().strip()
                    
                    if text.startswith('IMAGE_PROMPT:'):
                        image_prompt = text.replace('IMAGE_PROMPT:', '').strip()
                    elif text.startswith('VIDEO_IDEA:'):
                        video_idea = text.replace('VIDEO_IDEA:', '').strip()
                    elif text.startswith('VIDEO_PLACEHOLDER:'):
                        video_placeholder = text.replace('VIDEO_PLACEHOLDER:', '').strip()
                    elif text.startswith('STORY_IDEA:'):
                        story_idea = text.replace('STORY_IDEA:', '').strip()
                    elif text.startswith('POST_IDEA:'):
                        post_idea = text.replace('POST_IDEA:', '').strip()
                    elif text.startswith('Schedule:'):
                        schedule_time = text.replace('Schedule:', '').strip()
                        # Ensure the format is correct (Day HourAM/PM)
                        if schedule_time:
                            # Clean up any extra spaces or formatting issues
                            schedule_time = ' '.join(schedule_time.split())
                    elif text.startswith('CAPTION:'):
                        caption = text.replace('CAPTION:', '').strip()
                    elif text.startswith('HASHTAGS:'):
                        hashtags = text.replace('HASHTAGS:', '').strip()
                
                # Use schedule time if available, otherwise use best_time
                final_time = schedule_time if schedule_time else best_time
                
                # Save to database
                try:
                    cursor.execute("""
                        INSERT INTO content_items (
                            strategy_id, company_id, user_id,
                            platform, content_type, description,
                            frequency, best_time, image_prompt,
                            video_idea, video_placeholder, story_idea,
                            post_idea, caption, hashtags
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        strategy_id, company_id, user_id,
                        platform_name, type_name, description,
                        frequency, final_time, image_prompt,
                        video_idea, video_placeholder, story_idea,
                        post_idea, caption, hashtags
                    ))
                    print(f"Saved item for {platform_name} - {type_name}")
                    print(f"Schedule time: {final_time}")
                    print(f"Caption length: {len(caption) if caption else 0}")
                except Exception as e:
                    print(f"Error saving item: {e}")
                    logger.error(f"Error saving content item: {e}")
    
    try:
        conn.commit()
        print("Successfully committed all content items to database")
    except Exception as e:
        print(f"Error committing to database: {e}")
        logger.error(f"Error committing content items: {e}")
    finally:
        release_db_connection(conn)
        