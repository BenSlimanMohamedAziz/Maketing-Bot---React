import os
import cloudinary
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from pathlib import Path

# 1. Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 2. Verify .env file exists
if not env_path.exists():
    raise FileNotFoundError(
        f"❌ .env file not found at: {env_path}\n"
        "Please create a .env file in the config folder with all required variables"
    )

# 3. Environment variable loader with debug info
def get_env(var_name, default=None):
    value = os.getenv(var_name)
    if value is None and default is None:
        raise ValueError(
            f"Missing required environment variable: {var_name}\n"
            f"Checked file: {env_path}\n"
            f"Current variables: {list(os.environ.keys())}"
        )
    return value if value is not None else default

# 4. Settings class with initialization verification
class Settings:
    def __init__(self):
        print("🔄 Loading configuration...")
        
        # LLAMA API Configuration
        self.LLAMA_API_KEY = get_env("LLAMA_API_KEY")
        self.LLAMA_API_URL = get_env("LLAMA_API_URL", "https://api.together.xyz/v1/chat/completions")
        
        # Groq Models Api Config
        self.GROQ_API_KEY_1 = get_env("GROQ_API_KEY_1")
        self.GROQ_API_KEY_2 = get_env("GROQ_API_KEY_2")
        self.GROQ_API_KEY_3 = get_env("GROQ_API_KEY_3")
        self.GROQ_API_KEY_4 = get_env("GROQ_API_KEY_4")
        self.GROQ_API_KEY_5 = get_env("GROQ_API_KEY_5")
        self.GROQ_API_URL = get_env("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        
        # TAVILY AI web search Tool Api Config
        self.TAVILY_API_KEY_1 = get_env("TAVILY_API_KEY_1")
        self.TAVILY_API_KEY_2 = get_env("TAVILY_API_KEY_2")
        self.TAVILY_API_KEY_3 = get_env("TAVILY_API_KEY_3")
        self.TAVILY_API_URL = get_env("TAVILY_API_URL", "https://api.tavily.com/search")
        
        # FIRECRAWL AI scraping Tool Api Config
        self.FIRECRAWL_API_KEY_1 = get_env("FIRECRAWL_API_KEY_1")
        self.FIRECRAWL_API_KEY_2 = get_env("FIRECRAWL_API_KEY_2")
        self.FIRECRAWL_API_KEY_3 = get_env("FIRECRAWL_API_KEY_3")
        self.FIRECRAWL_API_URL = get_env("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v2/scrape")
        
        # Cloudinary Configuration
        self.CLOUDINARY_CLOUD_NAME = get_env("CLOUDINARY_CLOUD_NAME")
        self.CLOUDINARY_API_KEY = get_env("CLOUDINARY_API_KEY")
        self.CLOUDINARY_API_SECRET = get_env("CLOUDINARY_API_SECRET")
        
        # Database Configuration
        self.DB_NAME = get_env("DB_NAME")
        self.DB_USER = get_env("DB_USER")
        self.DB_PASSWORD = get_env("DB_PASSWORD")
        self.DB_HOST = get_env("DB_HOST", "localhost")
        self.DB_MIN_CONNECTIONS = int(get_env("DB_MIN_CONNECTIONS", "1"))
        self.DB_MAX_CONNECTIONS = int(get_env("DB_MAX_CONNECTIONS", "10"))
        
        
        print("✅ Configuration loaded successfully")

# 5. Initialize settings with verification
try:
    settings = Settings()
except Exception as e:
    print(f"\n❌ Configuration Error:")
    print(str(e))
    print(f"\nPlease verify your .env file at: {env_path}")
    print("Required variables: LLAMA_API_KEY, CLOUDINARY_CLOUD_NAME, DB_NAME, etc.")
    raise

# 6. Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

# 7. Database Connection Pool
db_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=settings.DB_MIN_CONNECTIONS,
    maxconn=settings.DB_MAX_CONNECTIONS,
    dbname=settings.DB_NAME,
    user=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST
)

def get_db_connection():
    """Get a database connection from the pool"""
    return db_pool.getconn()

def release_db_connection(conn):
    """Release a connection back to the pool"""
    db_pool.putconn(conn)

def get_db_cursor(conn):
    """Get a cursor from a connection"""
    return conn.cursor()

# Test config when run directly
if __name__ == "__main__":
    print("\n🔍 Configuration Test:")
    print(f"LLAMA_API_KEY: {settings.LLAMA_API_KEY[:4]}... (truncated)")
    print(f"DB_NAME: {settings.DB_NAME}")
    print(f"CLOUDINARY_CLOUD_NAME: {settings.CLOUDINARY_CLOUD_NAME}")
    print("Database connection test...")
    conn = get_db_connection()
    try:
        cursor = get_db_cursor(conn)
        cursor.execute("SELECT version()")
        print(f"Database version: {cursor.fetchone()[0]}")
    finally:
        release_db_connection(conn)
    print("✅ All tests passed!")
    
    