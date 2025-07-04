import requests
from flask import current_app

class AIService:
    def __init__(self):
        # Determine which AI service to use based on configuration
        # Prioritize OpenRouter if its specific API key is provided
        self.openrouter_api_key = current_app.config.get('OPENROUTER_API_KEY')
        self.openrouter_api_url = current_app.config.get('OPENROUTER_API_URL')
        self.openrouter_model_name = current_app.config.get('OPENROUTER_MODEL_NAME')

        if self.openrouter_api_key and self.openrouter_api_url and self.openrouter_model_name:
            self.use_openrouter = True
            current_app.logger.info("Using OpenRouter AI service.")
        else:
            self.use_openrouter = False
            self.gemini_api_key = current_app.config.get('AI_API_KEY')
            self.gemini_model_name = current_app.config.get('AI_MODEL_NAME')
            
            if not self.gemini_api_key:
                current_app.logger.error("AI_API_KEY (for Gemini) or OPENROUTER_API_KEY (for OpenRouter) is not set in config. Please set it in .env file.")
                raise ValueError("AI API key is not configured.")
            
            # Initialize Gemini if OpenRouter is not used
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
            current_app.logger.info("Using Gemini AI service.")

    def _call_openrouter_api(self, messages):
        """Helper to make calls to the OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.openrouter_model_name,
            "messages": messages
        }
        try:
            response = requests.post(self.openrouter_api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error calling OpenRouter API: {e}")
            raise ConnectionError(f"Failed to connect to OpenRouter API: {e}")
        except Exception as e:
            current_app.logger.error(f"Unexpected error with OpenRouter API response: {e}")
            raise Exception(f"Unexpected error from OpenRouter API: {e}")

    def summarize_text(self, text):
        """
        Summarizes the given text using the configured AI model (OpenRouter or Gemini). Do not give any punctuations to indicate bold text or anything like that.
        """
        if not text:
            return "No text provided for summarization."

        try:
            if self.use_openrouter:
                messages = [
                    {"role": "user", "content": f"Please provide a concise summary of the following news article:\n\n{text}\n\nSummary:"}
                ]
                response_json = self._call_openrouter_api(messages)
                if response_json and response_json.get('choices') and response_json['choices'][0].get('message'):
                    return response_json['choices'][0]['message']['content'].strip()
                else:
                    current_app.logger.error(f"Unexpected OpenRouter response structure for summarization: {response_json}")
                    return "Failed to get summary from OpenRouter due to unexpected response."
            else:
                # Use Gemini
                prompt = f"Please provide a concise summary of the following news article:\n\n{text}\n\nSummary:"
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
        except Exception as e:
            current_app.logger.error(f"Error summarizing text with AI: {e}")
            return f"Failed to summarize text: {e}"

    def chat_with_context(self, context, question):
        """
        Answers a question using the provided context with the AI model (OpenRouter or Gemini).
        """
        if not context or not question:
            return "Please provide both context and a question for the chatbot."

        try:
            if self.use_openrouter:
                messages = [
                    {"role": "user", "content": f"Based on the following article content, answer the question:\n\nArticle: {context}\n\nQuestion: {question}\n\nAnswer:"}
                ]
                response_json = self._call_openrouter_api(messages)
                if response_json and response_json.get('choices') and response_json['choices'][0].get('message'):
                    return response_json['choices'][0]['message']['content'].strip()
                else:
                    current_app.logger.error(f"Unexpected OpenRouter response structure for chat: {response_json}")
                    return "Failed to get chat response from OpenRouter due to unexpected response."
            else:
                # Use Gemini
                chat_session = self.gemini_model.start_chat(history=[])
                prompt = f"Based on the following article content, answer the question:\n\nArticle: {context}\n\nQuestion: {question}\n\nAnswer:"
                response = chat_session.send_message(prompt)
                return response.text.strip()
        except Exception as e:
            current_app.logger.error(f"Error chatting with AI: {e}")
            return f"Failed to get a response from the chatbot: {e}"

