from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime

def check_access_limit(feature_type):
    """
    Decorator to check and enforce free tier limits for summary and chat features.
    `feature_type` can be 'summary' or 'chat'.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = current_app.config.get('CURRENT_USER_ID')
            users_db = current_app.config.get('USERS_DB') # Access the global users_db

            if not user_id or user_id not in users_db:
                return jsonify({"error": "User not found or session expired. Please refresh."}), 401

            user_data = users_db[user_id]
            tier = user_data.get('tier', 'free')

            if tier == 'pro':
                # Pro users have unlimited access
                return f(*args, **kwargs)

            # Free tier logic
            limit_key = f'{feature_type}_count'
            config_limit_key = f'FREE_TIER_{feature_type.upper()}_LIMIT'
            current_count = user_data.get(limit_key, 0)
            daily_limit = current_app.config.get(config_limit_key)

            if current_count >= daily_limit:
                return jsonify({
                    "error": f"Free tier limit reached for {feature_type}. Please upgrade to Pro for unlimited access.",
                    "limit_reached": True,
                    "feature": feature_type
                }), 403
            
            # Increment count for free tier users
            user_data[limit_key] += 1
            users_db[user_id] = user_data # Update in-memory DB
            current_app.config['CURRENT_USER_DATA'] = user_data # Update current user data in app config

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def grant_pro_access(user_id):
    """
    Grants 'pro' access to a user.
    """
    users_db = current_app.config.get('USERS_DB')
    if user_id in users_db:
        users_db[user_id]['tier'] = 'pro'
        users_db[user_id]['summary_count'] = 0 # Reset counts upon upgrade
        users_db[user_id]['chat_count'] = 0
        users_db[user_id]['last_reset_date'] = datetime.now().date()
        current_app.config['CURRENT_USER_DATA'] = users_db[user_id] # Update if current user
        return True
    return False

