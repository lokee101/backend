import os
from flask import Flask, jsonify, session
from datetime import datetime, timedelta
from config import get_config
import uuid
from flask_cors import CORS # Import CORS

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all origins and all routes
# For production, consider restricting origins: CORS(app, origins=["https://your-netlify-app.netlify.app"])
CORS(app)

# Load configuration based on environment
app.config.from_object(get_config())

# --- In-memory data stores (for demonstration purposes) ---
# In a real application, these would be replaced by a database (e.g., Firestore, PostgreSQL)
users_db = {} # Stores user_id -> {'tier': 'free'/'pro', 'summary_count': int, 'chat_count': int, 'last_reset_date': date}
articles_db = {} # Stores article_id -> {'title': str, 'content': str, 'url': str}

# --- Blueprints Registration ---
# Import and register blueprints from payment and api modules
from payment import payment_bp
from api import api_bp

app.register_blueprint(payment_bp, url_prefix='/payment')
app.register_blueprint(api_bp, url_prefix='/api')

# --- Initialize NewsScraper and AIService within an application context ---
# This block runs when the 'app' object is created, which happens when Gunicorn imports app.py.
# Using app.app_context() ensures current_app.config is available during instantiation.
from api.news_scraper import NewsScraper
from api.summarizer import AIService
with app.app_context():
    try:
        app.config['NEWS_SCRAPER_INSTANCE'] = NewsScraper(app.config['NEWS_SOURCES'])
        app.config['AI_SERVICE_INSTANCE'] = AIService()
        app.logger.info("NewsScraper and AIService initialized successfully.")
    except Exception as e:
        app.logger.error(f"Failed to initialize NewsScraper or AIService: {e}")
        # Depending on severity, you might want to exit or handle gracefully
        # For now, we'll let the app start but log the error.


# --- Before Request / User Management (Simplified for Demo) ---
@app.before_request
def manage_user_session():
    """
    Manages a simple user session for access control.
    In a real app, this would involve proper authentication (e.g., Flask-Login).
    """
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        # Initialize new user in our in-memory DB
        users_db[session['user_id']] = {
            'tier': 'free',
            'summary_count': 0,
            'chat_count': 0,
            'last_reset_date': datetime.now().date()
        }
    else:
        user_id = session['user_id']
        if user_id not in users_db:
            # Handle case where session exists but user_id is not in our in-memory DB
            # This could happen if server restarts and in-memory DB is cleared
            users_db[user_id] = {
                'tier': 'free',
                'summary_count': 0,
                'chat_count': 0,
                'last_reset_date': datetime.now().date()
            }
        # Reset daily limits if a new day has started
        current_date = datetime.now().date()
        if users_db[user_id]['last_reset_date'] < current_date:
            users_db[user_id]['summary_count'] = 0
            users_db[user_id]['chat_count'] = 0
            users_db[user_id]['last_reset_date'] = current_date

    # Make user_id and user_data available globally for requests
    app.config['CURRENT_USER_ID'] = session['user_id']
    app.config['CURRENT_USER_DATA'] = users_db[session['user_id']]
    app.config['USERS_DB'] = users_db # Pass the entire DB for modifications in other modules
    app.config['ARTICLES_DB'] = articles_db # Pass articles DB


# --- Home Route (for API health check) ---
@app.route('/')
def home():
    """
    A simple home route to confirm the API server is running.
    Returns a JSON message as this is an API-only backend.
    """
    return jsonify({"message": "AI News Backend API is running!"}), 200

# --- Error Handling ---
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # This block is only for local development, Gunicorn will not execute it.
    # Create a .env file if it doesn't exist to guide the user
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("SECRET_KEY=your_flask_secret_key_here\n")
            f.write("RAZORPAY_KEY_ID=rzp_test_YOUR_KEY_ID\n")
            f.write("RAZORPAY_KEY_SECRET=YOUR_RAZORPAY_SECRET\n")
            f.write("AI_API_KEY=YOUR_GEMINI_OR_OPENAI_API_KEY\n")
            f.write("AI_MODEL_NAME=gemini-pro\n")
            f.write("OPENROUTER_API_URL=\"https://openrouter.ai/api/v1/chat/completions\"\n")
            f.write("OPENROUTER_API_KEY=\"sk-or-v1-YOUR_OPENROUTER_API_KEY\"\n")
            f.write("OPENROUTER_MODEL_NAME=\"deepseek/deepseek-r1-0528:free\"\n")
            f.write("FLASK_ENV=development\n")
        print("Created a .env file. Please fill in your API keys and secrets.")

    # Create necessary directories if they don't exist (for local setup)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('utils', exist_ok=True)
    os.makedirs('payment', exist_ok=True)
    os.makedirs('api', exist_ok=True)
    os.makedirs('frontend', exist_ok=True) # Placeholder

    app.run(debug=True) # debug=True for local development
