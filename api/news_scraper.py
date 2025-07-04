import requests
from bs4 import BeautifulSoup
import uuid
import re
from flask import current_app
from urllib.parse import urljoin, urlparse
import time # Import time for delays
import random # Import random for user agent rotation

class NewsScraper:
    def __init__(self, news_sources):
        self.news_sources = news_sources
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/127.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        ]
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/', # Mimic a referrer
            'DNT': '1', # Do Not Track header
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

    def _get_domain(self, url):
        """Helper to get the domain from a URL."""
        return urlparse(url).netloc

    def scrape_headlines(self):
        """
        Scrapes the latest news headlines from all configured news sources.
        Returns a list of dictionaries, each containing 'id', 'title', 'url', and 'source'.
        Attempts to get around 30-40 articles in total.
        """
        all_headlines = []
        seen_urls = set() # To avoid duplicate articles across sources

        for source in self.news_sources:
            source_name = source['name']
            source_url = source['url']
            current_app.logger.info(f"Attempting to scrape headlines from: {source_name} ({source_url})")

            # Rotate User-Agent for each request
            self.headers['User-Agent'] = random.choice(self.user_agents)

            try:
                response = requests.get(source_url, headers=self.headers, timeout=10)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                soup = BeautifulSoup(response.text, 'html.parser')

                potential_links = []
                # Times of India specific headline selectors (based on common patterns)
                # Look for links within common news listing containers
                for selector in [
                    '.listing5 li a', # Common for latest news lists
                    '.top-story a', # Top story links
                    '.section_item a', # General section items
                    '.articles a', # Generic article links
                    'div[class*="card"] a', # Links within elements with "card" in their class
                    'div[data-tb-region="news"] a', # Data attributes
                    'h2 a', 'h3 a', 'h4 a', 'h5 a', # Links within common heading tags
                ]:
                    potential_links.extend(soup.select(selector))
                
                # Also consider all general links as a fallback, then filter
                potential_links.extend(soup.find_all('a', href=True))
                
                # Use a set to store unique links to process
                unique_links_to_process = {} # {full_url: (title, original_link_tag)}

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

                    # Enhanced filtering for valid news article links based on common patterns
                    # and avoiding navigation/image/video/social links.
                    if (
                        re.search(r'/\d{4}/\d{2}/\d{2}/', full_url) or # Date pattern
                        re.search(r'/(news|articleshow|story|india|world|business|sports|entertainment|tech|auto|education)/', full_url) # Category pattern
                    ) and not re.search(r'(photogallery|videos|elections|liveblog|tags|contact|about|privacy|terms|login|signup|#|javascript:|mailto:|/amp/|/web-stories/|/photos/|/videos/|/live-updates/|/topic/|/authors/|/rss/|/sitemap/|/subscribe/|/apps/|/partner/|/advertise/|/feedback/|/careers/|/terms-of-use/|/privacy-policy/|/cookie-policy/|/disclaimer/|/sitemap/|/archive/|/newsletter/|/faq/|/press-release/|/events/|/jobs/|/deals/|/shop/|/gallery/|/embed/|/widget/|/apps/|/premium/|/plus/|/epaper/|/feedback/|/contactus/)', full_url, re.IGNORECASE):
                        
                        # Ensure the link is within the same domain or a subdomain
                        parsed_source_domain = self._get_domain(source_url)
                        parsed_full_url_domain = self._get_domain(full_url)
                        if not (parsed_full_url_domain == parsed_source_domain or \
                                parsed_full_url_domain.endswith('.' + parsed_source_domain)):
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
                            'content': None, # Content will be scraped on demand
                            'description': None, # Description will be scraped on demand
                            'image_url': None # Image will be scraped on demand
                        }
                        
                        if len(all_headlines) >= 40: # Limit total articles
                            return all_headlines

            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"Network or HTTP error during headline scraping from {source_name}: {e}")
            except Exception as e:
                current_app.logger.error(f"Error scraping headlines from {source_name}: {e}")
            
            # Add a small delay between requests to different sources
            time.sleep(1) # 1 second delay

        return all_headlines

    def scrape_article_content(self, article_url):
        """
        Scrapes the full content, description, and image of a single news article.
        Returns a dictionary with 'content', 'description', and 'image_url'.
        """
        article_data = {
            'content': "Failed to scrape article content.",
            'description': None,
            'image_url': None
        }
        try:
            response = requests.get(article_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # --- Extract Description ---
            description_tag = soup.find('meta', attrs={'name': 'description'}) or \
                              soup.find('meta', attrs={'property': 'og:description'})
            if description_tag and description_tag.get('content'):
                article_data['description'] = description_tag['content'].strip()

            # --- Extract Image URL ---
            # 1. Try Open Graph image (most reliable for social sharing images)
            image_tag = soup.find('meta', attrs={'property': 'og:image'})
            if image_tag and image_tag.get('content'):
                article_data['image_url'] = image_tag['content'].strip()
            else:
                # 2. Try specific Times of India image selectors
                # These are common patterns for main images on TOI articles
                toi_image_selectors = [
                    'img.img-fluid', # Common class for responsive images
                    'img.media-img', # Another common class
                    'div.image-container img', # Image within a container
                    'figure img', # Image within a figure tag
                    'div[itemprop="articleBody"] img', # Image within the article body schema
                    'div[data-tb-region="article-img"] img', # Data attribute for article image
                ]
                for selector in toi_image_selectors:
                    img_tag = soup.select_one(selector)
                    if img_tag and img_tag.get('src'):
                        # Ensure it's a full URL and not a tiny icon/spacer
                        img_src = urljoin(article_url, img_tag['src'])
                        if not re.search(r'(logo|icon|spacer|thumb|small|ads)\.(png|jpg|jpeg|gif|svg)', img_src, re.IGNORECASE):
                            article_data['image_url'] = img_src
                            break # Found a good candidate, stop searching

            # 3. Fallback: Look for any prominent image within the main content area
            if not article_data['image_url']:
                content_div = soup.find(
                    lambda tag: tag.name == 'div' and any(
                        cls in tag.get('class', []) for cls in [
                            'article-content', 'story-content', 'body-content', 'news-body',
                            'td-post-content', 'content-area', 'entry-content', 'single-post-content',
                            'article-body', 'inner-article', 'main-content', 'post-content'
                        ]
                    )
                ) or soup.find('article') or soup.find('main')

                if content_div:
                    # Look for the first significant image (avoiding very small ones)
                    img_tag = content_div.find('img', src=True, class_=lambda x: x not in ['icon', 'logo', 'small-thumbnail'] if x else True)
                    if img_tag and img_tag.get('src'):
                        img_src = urljoin(article_url, img_tag['src'])
                        if not re.search(r'(logo|icon|spacer|thumb|small|ads)\.(png|jpg|jpeg|gif|svg)', img_src, re.IGNORECASE):
                            article_data['image_url'] = img_src
            
            # Provide a placeholder if no image is found after all attempts
            if not article_data['image_url']:
                article_data['image_url'] = "https://placehold.co/600x400/cccccc/333333?text=No+Image"


            # --- Extract Full Article Content ---
            # More robust generic selectors for article content
            # Try common article containers first
            content_div = soup.find(
                lambda tag: tag.name == 'div' and any(
                    cls in tag.get('class', []) for cls in [
                        'article-content', 'story-content', 'body-content', 'news-body',
                        'td-post-content', 'content-area', 'entry-content', 'single-post-content',
                        'article-body', 'inner-article', 'main-content', 'post-content'
                    ]
                )
            ) or soup.find('article') or soup.find('main') or soup.find('body') # Fallback to body

            if content_div:
                # Remove unwanted elements that are typically not part of the main article text
                for script_or_style in content_div(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form', 'iframe', 'button', 'figcaption', 'figure', 'img', 'video', 'audio', 'svg', 'canvas', 'amp-img', 'blockquote']):
                    script_or_style.decompose() # Remove unwanted elements

                # Get all text from direct children paragraphs or text nodes
                article_text_parts = []
                for element in content_div.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'span', 'div']):
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        article_text_parts.append(text)
                
                # If still no content, try getting all text from the main content div
                if not article_text_parts:
                    article_text_parts = [content_div.get_text(separator=' ', strip=True)]

                article_text = '\n'.join(article_text_parts) # Use '\n' for paragraph breaks
                
                # Clean up multiple spaces, newlines, and common artifacts
                article_text = re.sub(r'\s+', ' ', article_text).strip()
                article_text = re.sub(r'(\n\s*){2,}', '\n\n', article_text) # Reduce multiple newlines
                
                # Remove common "read more" or "related articles" phrases that might be scraped
                article_text = re.sub(r'read more.*|related articles.*|also read.*|further reading.*|topics.*|tags.*|comments.*|share this article.*|follow us.*', '', article_text, flags=re.IGNORECASE | re.DOTALL).strip()
                
                article_data['content'] = article_text
            else:
                current_app.logger.warning(f"Could not find main article content for URL: {article_url}")
                article_data['content'] = "Could not scrape main article content."

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Network or HTTP error during article scraping for {article_url}: {e}")
            article_data['content'] = "Failed to scrape article content due to network error."
        except Exception as e:
            current_app.logger.error(f"Error scraping article content for {article_url}: {e}")
            article_data['content'] = "Failed to scrape article content due to an unexpected error."
        
        return article_data

