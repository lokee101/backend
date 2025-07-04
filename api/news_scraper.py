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
        Returns a list of dictionaries, each containing 'id', 'title', 'url', 'source', 'snippet', and 'image_url'.
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

                # --- REVISED STRATEGY FOR REUTERS HEADLINES ---
                # Focus on elements that represent a complete news article card on the homepage.
                # These selectors are based on common patterns for how Reuters structures its main news feed.
                # We prioritize elements that are likely to contain a title, link, and image together.
                article_card_selectors = [
                    'div.media-story-card', # The most common card for news stories
                    'div[data-testid="MediaStoryCard"]', # Alternative data-testid for story cards
                    'div.story-card', # A more generic story card class
                    'div[class*="FeedItem"]', # Common pattern for feed items
                    'div[class*="ArticleCard"]', # Common pattern for article cards
                    'div[data-testid="article-card"]', # Another potential data-testid
                    'li.story-item', # Sometimes list items are used for news feeds
                    'div.cluster-item', # For news clusters, might contain multiple stories
                    'div.basic-card', # Another generic card class
                ]

                # Select all potential article card elements
                for card_element in soup.select(', '.join(article_card_selectors)):
                    # Try to find the primary link within this card element
                    # Prioritize links that are likely headlines (e.g., within h2/h3 or with specific data-testids)
                    link_tag = card_element.select_one('a[data-testid="Link"], h2 a, h3 a, a.media-story-card__heading__2g1Xp')
                    
                    # If no suitable link is found within this card, skip it
                    if not link_tag:
                        continue

                    href = link_tag.get('href')
                    title = link_tag.get_text(strip=True)

                    if not href or not title:
                        continue

                    # Construct full URL if it's relative
                    if href.startswith('/'):
                        full_url = urljoin(source_url, href)
                    else:
                        full_url = href

                    # Enhanced filtering for valid news article links based on common patterns
                    # This regex helps filter out non-article links like categories, special sections, or author pages.
                    if (
                        re.search(r'/(article|news|business|markets|world|technology|sports|lifestyle|science|health|legal|politics|economy|companies|commodities|deals|funds|currencies|wealth|arts|media|entertainment|environment|climate|innovation|space|gaming|oddly-enough)/', full_url) and
                        not re.search(r'(photogallery|videos|elections|liveblog|tags|contact|about|privacy|terms|login|signup|#|javascript:|mailto:|/amp/|/web-stories/|/photos/|/videos|/live-updates|/topic|/authors|/rss|/sitemap|/subscribe|/apps|/partner|/advertise|/feedback|/careers|/terms-of-use|/privacy-policy|/cookie-policy|/disclaimer|/archive|/newsletter|/faq|/press-release|/events|/jobs|/deals|/shop|/gallery|/embed|/widget|/premium|/plus|/epaper|/contactus|/breakingnews|/authors/|/topics/|/search\?)', full_url, re.IGNORECASE)
                    ):
                        
                        # Ensure the link is within the same domain or a subdomain
                        parsed_source_domain = self._get_domain(source_url)
                        parsed_full_url_domain = self._get_domain(full_url)
                        if not (parsed_full_url_domain == parsed_source_domain or \
                                parsed_full_url_domain.endswith('.' + parsed_source_domain)):
                            continue

                        if full_url in seen_urls:
                            continue
                        
                        seen_urls.add(full_url)

                        # --- Attempt to find a snippet/description within the current card element ---
                        snippet = None
                        snippet_selectors = [
                            'p.media-story-card__description__2g1Xp', # Specific class for description
                            'p[data-testid="Body"]', # Common data-testid for body text/snippet
                            'div.story-content p', # Paragraph within story content divs
                            'p.text__text__1FZLe', # Common text class
                            'div.article-excerpt p', # Paragraph within article excerpts
                            'div[class*="Description"] p', # Generic description div
                            'div[class*="Snippet"] p', # Generic snippet div
                        ]
                        for s_selector in snippet_selectors:
                            snippet_tag = card_element.select_one(s_selector)
                            if snippet_tag:
                                snippet_text = snippet_tag.get_text(strip=True)
                                if snippet_text and len(snippet_text) > 20 and len(snippet_text) < 300 and snippet_text != title:
                                    snippet = snippet_text
                                    break
                        
                        # Fallback for snippet if not found by specific selectors
                        if not snippet:
                            # Try to get text from a general paragraph within the card, excluding the title
                            for p_tag in card_element.find_all('p'):
                                p_text = p_tag.get_text(strip=True)
                                if p_text and p_text != title and len(p_text) > 50 and len(p_text) < 300:
                                    snippet = p_text
                                    break
                        
                        # Final fallback: Use a truncated version of the title if no snippet is found
                        if not snippet:
                            snippet = title[:100] + '...' if len(title) > 100 else title

                        # --- Attempt to find an image URL for the headline card within the current element ---
                        image_url = None
                        # Specific Reuters thumbnail selectors within the card element
                        thumbnail_selectors = [
                            'img[data-testid="media-image"]',
                            'img.media-story-card__image__2g1Xp',
                            'img.media-object__image__3tY4J',
                            'img.image__image__1g1Xp', # Generic image class
                            'img[src*="thumb"]', # Images with 'thumb' in src
                            'img[src*="small"]', # Images with 'small' in src
                            'div.media-object__media__1g1Xp img', # Image within a common media object container
                            'div.Image_container img', # Another common image container
                            'div.MediaItem_image img', # Another common image container
                            'figure img', # General figure image
                            'img.reuters-asset-image', # A common class for Reuters images
                            'img[data-src]', # Sometimes images use data-src attribute (lazy loading)
                            'div.media-object__image-wrapper img', # Specific wrapper for images
                            'div.media-story-card__image-wrapper img', # Another specific wrapper
                            'img.w-full.h-full.object-cover', # Common Tailwind-like classes for images
                            'img[class*="Image"]', # Generic image class pattern
                        ]
                        for img_selector in thumbnail_selectors:
                            img_tag = card_element.select_one(img_selector) # Search within the current card element
                            if img_tag and (img_tag.get('src') or img_tag.get('data-src')): # Check both src and data-src
                                img_src = urljoin(source_url, img_tag.get('src') or img_tag.get('data-src'))
                                # Filter out tiny icons/placeholders, ensure it's a valid image URL
                                # Also check for minimum dimensions if possible (though not always in HTML attributes)
                                if not re.search(r'(logo|icon|spacer|thumb-small|ads|gif|svg)\.(png|jpg|jpeg)', img_src, re.IGNORECASE) and \
                                   not re.search(r'data:image', img_src, re.IGNORECASE) and \
                                   (img_tag.get('width') and int(img_tag['width']) > 50 or img_tag.get('height') and int(img_tag['height']) > 50): # Check for actual width/height attributes
                                    image_url = img_src
                                    break
                        
                        # Fallback to a generic placeholder if no image is found for the headline
                        if not image_url:
                            image_url = "https://placehold.co/400x160/4B0082/FFFFFF?text=Image+Missing"


                        article_id = str(uuid.uuid4())
                        all_headlines.append({
                            'id': article_id,
                            'title': title,
                            'url': full_url,
                            'source': source_name,
                            'snippet': snippet, # Add the scraped snippet here
                            'image_url': image_url # Add the scraped image URL here
                        })
                        # Store in global articles_db for later retrieval
                        current_app.config['ARTICLES_DB'][article_id] = {
                            'title': title,
                            'url': full_url,
                            'source': source_name,
                            'content': None, # Content will be scraped on demand
                            'description': None, # Description will be scraped on demand (from meta tags of actual article)
                            'image_url': image_url, # Store image_url here too
                            'snippet': snippet # Store snippet here too
                        }
                        
                        if len(all_headlines) >= 40: # Limit total articles
                            break # Break from the inner loop over card_elements

            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"Network or HTTP error during headline scraping from {source_name}: {e}")
            except Exception as e:
                current_app.logger.error(f"Error scraping headlines from {source_name}: {e}")
            
            # Add a small delay between requests to different sources
            time.sleep(1) # 1 second delay

        return all_headlines

    def scrape_article_content(self, article_url):
        """
        Scrapes the full content, description, author, in-article summary, and image of a single news article.
        Returns a dictionary with 'content', 'description', 'author', 'in_article_summary', and 'image_url'.
        """
        article_data = {
            'content': "Failed to scrape article content.",
            'description': None,
            'author': None,             # New field for author
            'in_article_summary': None, # New field for in-article summary
            'image_url': None
        }
        try:
            response = requests.get(article_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # --- Extract Title ---
            # Reuters titles are often in h1 with specific data-testid or classes
            title_tag = soup.select_one('h1[data-testid="ArticleHeader_headline"]') or \
                        soup.select_one('h1.article-header__title') or \
                        soup.select_one('h1.Headline-headline-2FX_p') or \
                        soup.find('h1')
            if title_tag:
                # Update the title in article_data (though it's usually already in the main dict)
                # This is more for completeness if this function were called standalone
                article_data['title'] = title_tag.get_text(strip=True)

            # --- Extract Author (By who) ---
            # Reuters author information is often in a span or div with specific classes/data-testids
            author_tag = soup.select_one('p[data-testid="BylineBar_byline"]') or \
                         soup.select_one('div.byline__name') or \
                         soup.select_one('span.byline-name') or \
                         soup.find('div', class_=re.compile(r'byline|author|writer', re.IGNORECASE))
            if author_tag:
                author_text = author_tag.get_text(strip=True)
                # Clean up "By " prefix if present
                article_data['author'] = re.sub(r'^By\s+', '', author_text, flags=re.IGNORECASE)


            # --- Extract Description (Meta Tags) ---
            # Prioritize og:description, then name="description"
            description_tag = soup.find('meta', attrs={'property': 'og:description'}) or \
                              soup.find('meta', attrs={'name': 'description'})
            if description_tag and description_tag.get('content'):
                article_data['description'] = description_tag['content'].strip()

            # --- Extract In-Article Summary Area ---
            # Reuters often has a lead paragraph or a specific summary div at the start
            in_article_summary_selectors = [
                'p[data-testid="ArticleBody_lead_paragraph"]', # Common lead paragraph
                'div.article-body > p:first-of-type', # First paragraph in the article body
                'div.ArticleBody_lede__2g1Xp', # Specific lede class
                'div.ArticleBody_summary__2g1Xp', # Specific summary class
                'div[itemprop="articleBody"] p:first-of-type', # First paragraph in schema body
                'div.article-body_content__17lYj > p:first-of-type', # First paragraph within the specific content div
            ]
            for selector in in_article_summary_selectors:
                summary_tag = soup.select_one(selector)
                if summary_tag:
                    summary_text = summary_tag.get_text(strip=True)
                    if summary_text and len(summary_text) > 50: # Ensure it's substantial
                        article_data['in_article_summary'] = summary_text
                        break # Found a good summary, stop searching


            # --- Extract Image URL ---
            # 1. Try Open Graph image (most reliable for social sharing images)
            image_tag = soup.find('meta', attrs={'property': 'og:image'})
            if image_tag and image_tag.get('content'):
                article_data['image_url'] = image_tag['content'].strip()
            else:
                # 2. Try specific Reuters image selectors
                article_image_selectors = [
                    'img[data-testid="media-image"]', # Common data-testid for main image
                    'div.article-image-container img', # Image within a specific container
                    'figure.article-picture img', # Image within a figure with article-picture class
                    'img.media-object__image__3tY4J', # Specific class for media objects
                    'img[itemprop="image"]', # Schema.org image
                    'meta[itemprop="image"]', # Schema.org image meta tag
                    'div.Image_container img', # Another common image container
                    'div.MediaItem_image img', # Another common image container
                ]
                for selector in article_image_selectors:
                    # If it's a meta tag, get content attribute
                    if selector.startswith('meta'):
                        meta_tag = soup.select_one(selector)
                        if meta_tag and meta_tag.get('content'):
                            img_src = urljoin(article_url, meta_tag['content'])
                            # Basic check to avoid very small or irrelevant images
                            if not re.search(r'(logo|icon|spacer|thumb|small|ads)\.(png|jpg|jpeg|gif|svg)', img_src, re.IGNORECASE):
                                article_data['image_url'] = img_src
                                break
                    else: # It's an img tag
                        img_tag = soup.select_one(selector)
                        if img_tag and img_tag.get('src'):
                            # Ensure it's a full URL and not a tiny icon/spacer
                            img_src = urljoin(article_url, img_tag['src'])
                            # Basic check to avoid very small or irrelevant images
                            if not re.search(r'(logo|icon|spacer|thumb|small|ads)\.(png|jpg|jpeg|gif|svg)', img_src, re.IGNORECASE):
                                article_data['image_url'] = img_src
                                break # Found a good candidate, stop searching

            # 3. Fallback: Look for any prominent image within the main content area
            if not article_data['image_url']:
                content_div = soup.find(
                    lambda tag: tag.name == 'div' and any(
                        cls in tag.get('class', []) for cls in [
                            'article-body', 'text__text__1FZLe', 'body-content', 'main-content', 'article-body_content__17lYj' # Added this
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
            # Reuters specific content selectors
            content_div = soup.find(
                lambda tag: tag.name == 'div' and any(
                    cls in tag.get('class', []) for cls in [
                        'article-body', # Main article content div
                        'text__text__1FZLe', # Common text class for paragraphs
                        'body-content', # Generic body content
                        'main-content', # Generic main content
                        'StandardArticleBody_body', # Older Reuters class
                        'ArticleBody_body__2g1Xp', # Another common Reuters body class
                        'article-body_content__17lYj', # Added this specific class from screenshot
                    ]
                )
            ) or soup.find('article') or soup.find('main') or soup.find('body') # Fallback to body

            if content_div:
                # Remove unwanted elements that are typically not part of the main article text
                for script_or_style in content_div(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form', 'iframe', 'button', 'figcaption', 'figure', 'img', 'video', 'audio', 'svg', 'canvas', 'amp-img', 'blockquote', '.ads', '.ad-container', '.social-share', '.read-more', '.related-articles', '.comments-section', '.paywall', '#paywall', '.signin', '#signin', '.legals', '.disclaimer', '.byline', '.timestamp', '.ArticleHeader_container', '.ArticleHeader_byline', '.ArticleHeader_date', '.ArticleHeader_share']):
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
                article_text = re.sub(r'read more.*|related articles.*|also read.*|further reading.*|topics.*|tags.*|comments.*|share this article.*|follow us.*|sign in.*|subscribe now.*|create an account.*|login to read.*|our standards: the reuters trust principles.*|thomson reuters.*|reporting by.*|editing by.*|our standards.*', '', article_text, flags=re.IGNORECASE | re.DOTALL).strip()
                
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
