import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_very_secret_key_for_dev')
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
    
    # AI API Configuration - Now supporting OpenRouter
    AI_API_KEY = os.environ.get('AI_API_KEY') # Generic key, can be used for Gemini or OpenRouter
    AI_MODEL_NAME = os.environ.get('AI_MODEL_NAME', 'gemini-pro') # Default to gemini-pro
    
    # OpenRouter Specific Configuration
    OPENROUTER_API_URL = os.environ.get('OPENROUTER_API_URL', "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY') # Dedicated OpenRouter API key
    OPENROUTER_MODEL_NAME = os.environ.get('OPENROUTER_MODEL_NAME', "deepseek/deepseek-r1-0528:free")


    # Tier limits
    FREE_TIER_SUMMARY_LIMIT = 1
    FREE_TIER_CHAT_LIMIT = 1

    # News scraping configuration
    # Define multiple news sources as a list of dictionaries
    NEWS_SOURCES = [
        {'name': 'NDTV', 'url': 'https://www.ndtv.com/latest'},
        {'name': 'Hindustan Times', 'url': 'https://www.hindustantimes.com/latest-news'},
        {'name': 'Times of India', 'url': 'https://timesofindia.indiatimes.com/'},
        # Add more Indian news sources here as needed
    ]

class DevelopmentConfig(Config):
    """Development specific configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production specific configuration."""
    DEBUG = False
    # Add more production-specific settings here

def get_config():
    """Returns the appropriate configuration based on FLASK_ENV."""
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig
    return DevelopmentConfig

