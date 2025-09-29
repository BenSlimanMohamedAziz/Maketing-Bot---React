from datetime import datetime, timedelta
import time
import requests
import os
import asyncio
from typing import Dict, Any, Optional, List
import logging
import random
from auth.meta_oauth import MetaOAuth
import aiohttp
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Global thread pool for blocking operations
thread_pool = ThreadPoolExecutor(max_workers=10)

async def run_in_thread(func, *args):
    """Run blocking functions in thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(thread_pool, func, *args)

# Facebook Analytics
async def get_facebook_analytics(user_id: int, db_cursor, days: int = 30):
    """Get Facebook analytics for the user - handles token decryption internally"""
    try:
        # Run database query in thread pool
        facebook_account = await run_in_thread(
            fetch_facebook_account, db_cursor, user_id
        )
        
        if not facebook_account:
            return {"error": "No Facebook account linked"}
        
        # Decrypt the access token
        ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
        meta_oauth = MetaOAuth(ENCRYPTION_KEY)
        
        encrypted_access_token = facebook_account[3]
        access_token = meta_oauth._decrypt_token(encrypted_access_token)
        page_id = facebook_account[4]
        
        # Fetch all data concurrently
        today = datetime.now()
        since = (today - timedelta(days=days)).strftime('%Y-%m-%d')
        until = today.strftime('%Y-%m-%d')
        
        # Fetch data concurrently
        fan_count_task = fetch_facebook_fan_count(page_id, access_token)
        fans_data_task = fetch_facebook_insight(page_id, access_token, 'page_fans', since, until)
        impressions_task = fetch_facebook_insight(page_id, access_token, 'page_impressions', since, until)
        engagement_task = fetch_facebook_insight(page_id, access_token, 'page_post_engagements', since, until)
        reach_task = fetch_facebook_insight(page_id, access_token, 'page_impressions_unique', since, until)
        views_task = fetch_facebook_insight(page_id, access_token, 'page_views_total', since, until)
        
        # Wait for all tasks to complete
        fan_count, fans_data, impressions_data, engagement_data, reach_data, views_data = await asyncio.gather(
            fan_count_task, fans_data_task, impressions_task, engagement_task, reach_task, views_task
        )
        
        # Calculate growth rate
        growth_rate = 0
        if fans_data and len(fans_data['values']) > 1:
            first = fans_data['values'][0]
            last = fans_data['values'][-1]
            if first > 0:
                growth_rate = round(((last - first) / first) * 100, 1)
        
        return {
            "page_fans": fan_count,
            "page_impressions": sum(impressions_data['values']) if impressions_data else 0,
            "page_engagement": sum(engagement_data['values']) if engagement_data else 0,
            "growth_rate": growth_rate,
            "fans_data": fans_data,
            "impressions_data": impressions_data,
            "engagement_data": engagement_data,
            "reach_data": reach_data,
            "views_data": views_data
        }
        
    except Exception as e:
        logger.error(f"Facebook analytics error: {str(e)}")
        return {"error": str(e)}

def fetch_facebook_account(cursor, user_id):
    """Blocking function to fetch Facebook account"""
    cursor.execute("""
        SELECT platform, account_id, account_name, access_token, page_id, instagram_id
        FROM user_linked_accounts 
        WHERE user_id = %s AND platform = 'facebook'
        ORDER BY created_at DESC LIMIT 1
    """, (user_id,))
    return cursor.fetchone()

async def fetch_facebook_fan_count(page_id: str, access_token: str):
    """Fetch Facebook fan count asynchronously"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f'https://graph.facebook.com/v22.0/{page_id}'
            params = {
                'fields': 'fan_count',
                'access_token': access_token
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('fan_count', 0)
                return 0
    except Exception as e:
        logger.error(f"Error fetching Facebook fan count: {e}")
        return 0

async def fetch_facebook_insight(page_id: str, access_token: str, metric: str, since: str, until: str):
    """Fetch Facebook insight data asynchronously"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f'https://graph.facebook.com/v22.0/{page_id}/insights'
            params = {
                'metric': metric,
                'period': 'day',
                'since': since,
                'until': until,
                'access_token': access_token
            }
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                data = data.get('data', [])
                if not data:
                    return None
                
                values = []
                labels = []
                
                for item in data[0].get('values', []):
                    end_time = item.get('end_time', '')
                    if end_time:
                        try:
                            date = datetime.strptime(end_time.split('T')[0], '%Y-%m-%d')
                            labels.append(date.strftime('%b %d'))
                            values.append(item.get('value', 0))
                        except ValueError:
                            continue
                
                return {"labels": labels, "values": values}
                
    except Exception as e:
        logger.error(f"Error fetching Facebook {metric} data: {e}")
        return None

# Instagram Analytics
async def get_instagram_analytics(user_id: int, db_cursor, days: int = 14):
    """Get Instagram analytics for the user - handles token decryption internally"""
    try:
        # Run database query in thread pool
        instagram_account = await run_in_thread(
            fetch_instagram_account, db_cursor, user_id
        )
        
        if not instagram_account:
            return {"error": "No Instagram account linked"}
        
        # Decrypt the access token
        ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
        meta_oauth = MetaOAuth(ENCRYPTION_KEY)
        
        encrypted_access_token = instagram_account[3]
        access_token = meta_oauth._decrypt_token(encrypted_access_token)
        instagram_account_id = instagram_account[5]
        
        # Calculate date range
        today = datetime.now()
        since = (today - timedelta(days=days)).strftime('%Y-%m-%d')
        until = today.strftime('%Y-%m-%d')
        
        # Fetch data concurrently
        account_info_task = fetch_instagram_account_info(instagram_account_id, access_token)
        insights_task = fetch_instagram_insights(instagram_account_id, access_token, since, until)
        
        account_info, insights = await asyncio.gather(account_info_task, insights_task)
        
        if not account_info:
            return {"error": "Failed to fetch Instagram account info"}
        
        # Process data
        followers_count = account_info.get('followers_count', 0)
        total_views = insights.get('total_views', 0)
        accounts_reached = insights.get('accounts_reached', 0)
        profile_views = insights.get('profile_views', 0)
        
        # Calculate growth rate
        growth_rate = 0
        if insights.get('starting_followers', 0) > 0:
            growth_rate = round((insights.get('follower_change', 0) / insights.get('starting_followers', 1)) * 100, 1)
        
        # Generate chart labels
        chart_labels = await generate_chart_labels(since, until)
        
        # Generate simulated data concurrently
        sim_tasks = [
            simulate_daily_values(followers_count, len(chart_labels)),
            simulate_daily_values(total_views, len(chart_labels), variation=0.3),
            simulate_daily_values(accounts_reached, len(chart_labels), variation=0.4),
            simulate_daily_values(profile_views, len(chart_labels), variation=0.5)
        ]
        
        followers_values, views_values, reach_values, profile_views_values = await asyncio.gather(*sim_tasks)
        
        return {
            "followers_count": followers_count,
            "total_views": total_views,
            "accounts_reached": accounts_reached,
            "profile_views": profile_views,
            "growth_rate": growth_rate,
            "account_info": account_info,
            "followers_data": {"labels": chart_labels, "values": followers_values},
            "views_data": {"labels": chart_labels, "values": views_values},
            "reach_data": {"labels": chart_labels, "values": reach_values},
            "profile_activity_data": {"labels": chart_labels, "values": profile_views_values},
            "content_breakdown": {"stories_percentage": 99.4, "posts_percentage": 0.6}
        }
        
    except Exception as e:
        logger.error(f"Instagram analytics error: {str(e)}")
        return {"error": str(e)}

def fetch_instagram_account(cursor, user_id):
    """Blocking function to fetch Instagram account"""
    cursor.execute("""
        SELECT platform, account_id, account_name, access_token, page_id, instagram_id
        FROM user_linked_accounts 
        WHERE user_id = %s AND platform = 'instagram'
        ORDER BY created_at DESC LIMIT 1
    """, (user_id,))
    return cursor.fetchone()

async def fetch_instagram_account_info(account_id: str, access_token: str):
    """Fetch Instagram account basic information asynchronously"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://graph.facebook.com/v19.0/{account_id}"
            params = {
                'fields': 'id,username,name,followers_count,follows_count,media_count',
                'access_token': access_token
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                return None
                
    except Exception as e:
        logger.error(f"Error fetching Instagram account info: {e}")
        return None

async def fetch_instagram_insights(account_id: str, access_token: str, since: str, until: str):
    """Fetch Instagram insights data asynchronously"""
    insights = {}
    
    try:
        base_url = "https://graph.facebook.com/v19.0/"
        url = f"{base_url}{account_id}/insights"
        
        # Define all metrics to fetch
        metrics = [
            ('reach', {}),
            ('profile_views', {'metric_type': 'total_value'}),
            ('follower_count', {}),
            ('views', {'metric_type': 'total_value'})
        ]
        
        # Fetch all metrics concurrently
        tasks = []
        for metric, extra_params in metrics:
            params = {
                'metric': metric,
                'period': 'day',
                'since': since,
                'until': until,
                'access_token': access_token,
                **extra_params
            }
            tasks.append(make_instagram_api_call(url, params))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, (metric, _) in enumerate(metrics):
            result = results[i] if not isinstance(results[i], Exception) else None
            if result and 'data' in result:
                process_instagram_insight(insights, metric, result)
                
    except Exception as e:
        logger.error(f"Error fetching Instagram insights: {e}")
    
    return insights

def process_instagram_insight(insights: dict, metric: str, data: dict):
    """Process Instagram insight data"""
    if metric == 'reach':
        reach_values = data['data'][0]['values']
        insights['accounts_reached'] = sum(v['value'] for v in reach_values)
        insights['recent_reach'] = reach_values[-1]['value'] if reach_values else 0
        
    elif metric == 'profile_views':
        pv_data = data['data'][0]
        if 'total_value' in pv_data:
            insights['profile_views'] = pv_data['total_value']['value']
            
    elif metric == 'follower_count':
        fc_values = data['data'][0]['values']
        if fc_values:
            insights['starting_followers'] = fc_values[0]['value']
            insights['current_followers'] = fc_values[-1]['value']
            insights['follower_change'] = fc_values[-1]['value'] - fc_values[0]['value']
            
    elif metric == 'views':
        views_info = data['data'][0]
        if 'total_value' in views_info:
            insights['total_views'] = views_info['total_value']['value']

async def make_instagram_api_call(url: str, params: dict):
    """Make Instagram API call with retry logic asynchronously"""
    max_retries = 3
    
    async with aiohttp.ClientSession() as session:
        for attempt in range(max_retries):
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limited
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"API call failed: {response.status}")
                        return None
                        
            except Exception as e:
                logger.error(f"Exception in API call: {e}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)
    
    return None

async def generate_chart_labels(since: str, until: str) -> List[str]:
    """Generate chart labels for date range"""
    labels = []
    current_date = datetime.strptime(since, '%Y-%m-%d')
    end_date = datetime.strptime(until, '%Y-%m-%d')
    
    while current_date <= end_date:
        labels.append(current_date.strftime('%b %d'))
        current_date += timedelta(days=1)
    
    return labels

async def simulate_daily_values(total_value: int, num_days: int, variation: float = 0.2) -> List[int]:
    """Generate simulated daily values that sum up to the total"""
    if total_value == 0 or num_days == 0:
        return [0] * num_days
    
    # Run in thread pool
    return await run_in_thread(_simulate_daily_values_sync, total_value, num_days, variation)

def _simulate_daily_values_sync(total_value: int, num_days: int, variation: float = 0.2) -> List[int]:
    """Synchronous version of simulate_daily_values"""
    # Create base daily average
    base_daily = total_value / num_days
    
    # Generate values with variation
    values = []
    remaining_total = total_value
    
    for i in range(num_days - 1):
        # Add some random variation
        variance = base_daily * variation * (random.random() - 0.5) * 2
        daily_value = max(0, int(base_daily + variance))
        values.append(daily_value)
        remaining_total -= daily_value
    
    # Last day gets the remainder to ensure exact total
    values.append(max(0, remaining_total))
    
    return values

# LinkedIn Analytics
async def get_linkedin_analytics(user_id: int, days: int = 30):
    """Get LinkedIn analytics - static data for now (non-blocking)"""
    try:
        # Generate data asynchronously without blocking
        chart_labels = await generate_chart_labels(
            (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d')
        )
        
        # Static metrics
        connections = 2847
        profile_views = 156 * days
        post_impressions = 3200 * days
        
        # Generate data concurrently
        sim_tasks = [
            simulate_daily_values(connections, len(chart_labels), variation=0.1),
            simulate_daily_values(profile_views, len(chart_labels), variation=0.3),
            simulate_daily_values(post_impressions, len(chart_labels), variation=0.4)
        ]
        
        connections_values, views_values, impressions_values = await asyncio.gather(*sim_tasks)
        
        return {
            "connections": connections,
            "profile_views": profile_views,
            "post_impressions": post_impressions,
            "engagement_rate": 4.2,
            "growth_rate": 2.8,
            "connections_data": {"labels": chart_labels, "values": connections_values},
            "views_data": {"labels": chart_labels, "values": views_values},
            "impressions_data": {"labels": chart_labels, "values": impressions_values},
            "industry_data": {"tech": 45, "finance": 25, "marketing": 20, "other": 10}
        }
        
    except Exception as e:
        logger.error(f"LinkedIn analytics error: {str(e)}")
        return {"error": str(e)}