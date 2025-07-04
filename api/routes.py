from flask import request, jsonify, current_app
from api import api_bp
# Removed direct imports of NewsScraper and AIService here

from utils.access_control import check_access_limit

# Helper function to get the initialized services
def get_news_scraper():
    """Retrieves the NewsScraper instance from app.config."""
    return current_app.config.get('NEWS_SCRAPER_INSTANCE')

def get_ai_service():
    """Retrieves the AIService instance from app.config."""
    return current_app.config.get('AI_SERVICE_INSTANCE')

@api_bp.route('/news', methods=['GET'])
def get_news_headlines():
    """
    Fetches and returns the latest news headlines from multiple sources.
    """
    news_scraper = get_news_scraper()
    if not news_scraper:
        return jsonify({"error": "News scraper not initialized."}), 500

    headlines = news_scraper.scrape_headlines()
    if not headlines:
        return jsonify({"message": "Could not fetch headlines from any source. Please try again later."}), 500
    return jsonify(headlines), 200

@api_bp.route('/article/<article_id>', methods=['GET'])
def get_article_content(article_id):
    """
    Retrieves the full content of a specific article by ID.
    If content is not yet scraped, it scrapes it on demand.
    """
    news_scraper = get_news_scraper()
    if not news_scraper:
        return jsonify({"error": "News scraper not initialized."}), 500

    articles_db = current_app.config.get('ARTICLES_DB')
    article_data = articles_db.get(article_id)

    if not article_data:
        return jsonify({"error": "Article not found."}), 404

    if not article_data.get('content'):
        # Scrape content if it hasn't been already
        current_app.logger.info(f"Scraping content for article ID: {article_id} from URL: {article_data['url']}")
        content = news_scraper.scrape_article_content(article_data['url'])
        if content:
            articles_db[article_id]['content'] = content
            current_app.config['ARTICLES_DB'] = articles_db # Update global DB
        else:
            return jsonify({"error": "Failed to retrieve article content."}), 500

    return jsonify({
        "id": article_id,
        "title": article_data['title'],
        "url": article_data['url'],
        "source": article_data['source'], # Include source in the response
        "content": articles_db[article_id]['content']
    }), 200

@api_bp.route('/summarize', methods=['POST'])
@check_access_limit('summary')
def summarize_article():
    """
    Summarizes an article. Accepts either article_id or raw text.
    Enforces free tier summary limits.
    """
    ai_service = get_ai_service()
    if not ai_service:
        return jsonify({"error": "AI service not initialized."}), 500

    news_scraper = get_news_scraper() # Needed if article_id is provided
    if not news_scraper:
        return jsonify({"error": "News scraper not initialized."}), 500

    data = request.get_json()
    article_id = data.get('article_id')
    raw_text = data.get('text')
    
    text_to_summarize = ""

    if article_id:
        articles_db = current_app.config.get('ARTICLES_DB')
        article_data = articles_db.get(article_id)
        if not article_data:
            return jsonify({"error": "Article not found for summarization."}), 404
        
        # Ensure content is scraped
        if not article_data.get('content'):
            content = news_scraper.scrape_article_content(article_data['url'])
            if content:
                articles_db[article_id]['content'] = content
                current_app.config['ARTICLES_DB'] = articles_db
            else:
                return jsonify({"error": "Failed to retrieve article content for summarization."}), 500
        
        text_to_summarize = articles_db[article_id]['content']
    elif raw_text:
        text_to_summarize = raw_text
    else:
        return jsonify({"error": "No article_id or text provided for summarization."}), 400

    if not text_to_summarize:
        return jsonify({"error": "Content to summarize is empty."}), 400

    summary = ai_service.summarize_text(text_to_summarize)
    return jsonify({"summary": summary}), 200

@api_bp.route('/chat', methods=['POST'])
@check_access_limit('chat')
def chat_with_article():
    """
    Provides a chatbot interface using article content as context.
    Enforces free tier chat limits.
    """
    ai_service = get_ai_service()
    if not ai_service:
        return jsonify({"error": "AI service not initialized."}), 500

    news_scraper = get_news_scraper() # Needed if article_id is provided
    if not news_scraper:
        return jsonify({"error": "News scraper not initialized."}), 500

    data = request.get_json()
    article_id = data.get('article_id')
    question = data.get('question')

    if not question:
        return jsonify({"error": "No question provided for chat."}), 400

    context = ""
    if article_id:
        articles_db = current_app.config.get('ARTICLES_DB')
        article_data = articles_db.get(article_id)
        if not article_data:
            return jsonify({"error": "Article not found for chat context."}), 404
        
        # Ensure content is scraped
        if not article_data.get('content'):
            content = news_scraper.scrape_article_content(article_data['url'])
            if content:
                articles_db[article_id]['content'] = content
                current_app.config['ARTICLES_DB'] = articles_db
            else:
                return jsonify({"error": "Failed to retrieve article content for chat."}), 500
        
        context = articles_db[article_id]['content']
    else:
        return jsonify({"error": "No article_id provided for chat context."}), 400

    if not context:
        return jsonify({"error": "Article content is empty, cannot provide context for chat."}), 400

    chat_response = ai_service.chat_with_context(context, question)
    return jsonify({"response": chat_response}), 200

