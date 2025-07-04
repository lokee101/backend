import requests
from bs4 import BeautifulSoup
import uuid
import re
from flask import current_app
from urllib.parse import urljoin, urlparse

class NewsScraper:
    def __init__(self, news_sources):
        # news_sources is now a list of dictionaries, e.g., [{'name': 'TOI', 'url': '...'}]
        self.news_sources = news_sources
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def _get_domain(self, url):
        """Helper to get the domain from a URL."""
        return urlparse(url).netloc

    def scrape_headlines(self):
        """
        Scrapes the latest news headlines from all configured news sources.
        Returns a list of dictionaries, each containing 'id', 'title', and 'url'.
        Attempts to get around 30-40 articles in total.
        """
        all_headlines = []
        seen_urls = set() # To avoid duplicate articles across sources

        for source in self.news_sources:
            source_name = source['name']
            source_url = source['url']
            current_app.logger.info(f"Attempting to scrape headlines from: {source_name} ({source_url})")

            try:
                response = requests.get(source_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Generic selectors for common news article links
                # This is a heuristic and might need specific tuning for each site.
                # Common patterns: <a> tags within specific divs, or with certain classes.
                # We'll try to find links that look like news articles.
                potential_links = soup.find_all('a', href=True)
                
                for link in potential_links:
                    href = link.get('href')
                    title = link.get_text(strip=True)

                    if not href or not title:
                        continue

                    # Construct full URL if it's relative
                    if href.startswith('/'):
                        full_url = urljoin(source_url, href)
                    else:
                        full_url = href

                    # Basic filtering for valid news article links based on common patterns
                    # and avoiding navigation/image/video links.
                    if (
                        re.search(r'/\d{4}/\d{2}/\d{2}/', full_url) or # Date pattern
                        re.search(r'/(news|articleshow|india|world|business|sports|entertainment)/', full_url) # Category pattern
                    ) and not re.search(r'(photogallery|videos|elections|liveblog|tags|contact|about|privacy|terms|login|signup|#)', full_url):
                        
                        # Ensure the link is within the same domain or a subdomain
                        if self._get_domain(full_url) not in (self._get_domain(source_url), f"www.{self._get_domain(source_url)}", f"{source_name.lower()}.{self._get_domain(source_url)}"):
                            continue

                        if full_url in seen_urls:
                            continue
                        
                        seen_urls.add(full_url)

                        article_id = str(uuid.uuid4())
                        all_headlines.append({
                            'id': article_id,
                            'title': title,
                            'url': full_url,
                            'source': source_name
                        })
                        # Store in global articles_db for later retrieval
                        current_app.config['ARTICLES_DB'][article_id] = {
                            'title': title,
                            'url': full_url,
                            'source': source_name,
                            'content': None # Content will be scraped on demand
                        }
                        
                        if len(all_headlines) >= 40: # Limit total articles
                            return all_headlines

            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"Network or HTTP error during headline scraping from {source_name}: {e}")
            except Exception as e:
                current_app.logger.error(f"Error scraping headlines from {source_name}: {e}")
        
        return all_headlines

    def scrape_article_content(self, article_url):
        """
        Scrapes the full content of a single news article.
        Returns the article text as a string.
        """
        try:
            response = requests.get(article_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # More robust generic selectors for article content
            # Try common article containers first
            content_div = soup.find(
                lambda tag: tag.name == 'div' and any(
                    cls in tag.get('class', []) for cls in [
                        'article-content', 'story-content', 'body-content', 'news-body',
                        'td-post-content', 'content-area', 'entry-content', 'single-post-content'
                    ]
                )
            )
            
            if not content_div:
                # Fallback: look for common article tags within the main body
                content_div = soup.find('article') or soup.find('main') or soup.find('body')

            if content_div:
                # Extract text from paragraphs, removing script/style tags
                for script_or_style in content_div(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form', 'img', 'figure']):
                    script_or_style.decompose() # Remove unwanted elements

                paragraphs = content_div.find_all('p')
                article_text_parts = [p.get_text(separator=' ', strip=True) for p in paragraphs if p.get_text(strip=True)]
                
                # If no paragraphs found, try to get text from the whole div
                if not article_text_parts:
                    article_text_parts = [content_div.get_text(separator=' ', strip=True)]

                article_text = '\n'.join(article_text_parts)
                
                # Clean up multiple spaces, newlines, and common artifacts
                article_text = re.sub(r'\s+', ' ', article_text).strip()
                article_text = re.sub(r'(\n\s*){2,}', '\n\n', article_text) # Reduce multiple newlines
                
                # Remove common "read more" or "related articles" phrases that might be scraped
                article_text = re.sub(r'read more.*|related articles.*|also read.*', '', article_text, flags=re.IGNORECASE).strip()

                return article_text
            else:
                current_app.logger.warning(f"Could not find article content for URL: {article_url}")
                return "Could not scrape article content."

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Network or HTTP error during article scraping for {article_url}: {e}")
            return "Failed to scrape article content due to network error."
        except Exception as e:
            current_app.logger.error(f"Error scraping article content for {article_url}: {e}")
            return "Failed to scrape article content due to an unexpected error."

