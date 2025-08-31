import time
import requests
import os
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class WebCrawler:
    """Web crawler adapted for the Flask application"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MetaSpidey/1.0 (Security Research Tool)'
        })
        self.robots_parser = RobotFileParser()
        self.should_stop = False
        self.visited_urls = set()
        self.lock = threading.Lock()
        self.results = []

    def is_allowed(self, url):
        """Check if URL is allowed by robots.txt"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
            return self.robots_parser.can_fetch("*", url)
        except:
            return True

    def is_valid_file(self, url, allowed_extensions):
        """Check if URL points to allowed file type"""
        if not allowed_extensions:
            return True
        return any(url.lower().endswith(ext.lower()) for ext in allowed_extensions)

    def get_links(self, url, allowed_extensions=None):
        """Get all valid links from a page"""
        try:
            if self.should_stop:
                return []
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            links = []

            # Get all links from various tags
            for link in soup.find_all(['a', 'link', 'script', 'img']):
                href = link.get('href') or link.get('src')
                if href:
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)
                    
                    # Only process links from same domain
                    if (parsed.netloc == urlparse(url).netloc and
                        self.is_allowed(full_url) and
                        self.is_valid_file(full_url, allowed_extensions)):
                        
                        with self.lock:
                            if full_url not in self.visited_urls:
                                self.visited_urls.add(full_url)
                                links.append(full_url)

            return links

        except Exception as e:
            print(f"Error crawling {url}: {e}")
            return []

    def crawl(self, url, max_depth=2, delay=0.1, extensions=None, threads=5):
        """
        Main crawl function - Simplified and more robust version
        """
        try:
            # Reset state
            self.results = []
            self.visited_urls = set()
            self.should_stop = False
            
            # Validate input URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url.strip()
            
            print(f"Starting crawl of {url} with depth {max_depth}")
            
            # Initialize with starting URL
            urls_queue = [(url, 0)]
            processed_count = 0
            
            while urls_queue and not self.should_stop and processed_count < 100:  # Limit for safety
                current_url, current_depth = urls_queue.pop(0)
                
                # Skip if already visited
                if current_url in self.visited_urls:
                    continue
                    
                self.visited_urls.add(current_url)
                processed_count += 1
                
                try:
                    # Crawl single page
                    page_data = self._crawl_single_page(current_url, current_depth)
                    if page_data:
                        self.results.append(page_data)
                        print(f"Crawled: {current_url} - Found {page_data.get('links_count', 0)} links")
                    
                    # If within depth limit, find new links
                    if current_depth < max_depth - 1:
                        new_links = self._extract_links(current_url, extensions)
                        for link in new_links[:10]:  # Limit links per page
                            if link not in self.visited_urls:
                                urls_queue.append((link, current_depth + 1))
                    
                    # Respect delay
                    if delay > 0:
                        time.sleep(delay)
                        
                except Exception as e:
                    print(f"Error crawling {current_url}: {str(e)}")
                    continue
            
            print(f"Crawl completed. Found {len(self.results)} pages.")
            
            return {
                'total_urls': len(self.results),
                'urls': self.results,
                'crawl_depth': max_depth,
                'extensions_filter': extensions or []
            }
            
        except Exception as e:
            print(f"Crawl failed: {str(e)}")
            return {
                'total_urls': 0,
                'urls': [],
                'crawl_depth': max_depth,
                'extensions_filter': extensions or [],
                'error': str(e)
            }

    def _crawl_single_page(self, url, depth):
        """Crawl a single page and return page metadata"""
        try:
            response = self.session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            # Parse content type
            content_type = response.headers.get('content-type', '').lower()
            
            page_data = {
                'url': url,
                'depth': depth,
                'status_code': response.status_code,
                'content_length': len(response.content),
                'content_type': content_type,
                'title': '',
                'last_modified': response.headers.get('last-modified', ''),
                'server': response.headers.get('server', ''),
                'meta_description': '',
                'meta_keywords': '',
                'links_count': 0,
                'images_count': 0,
                'scripts_count': 0,
                'forms_count': 0
            }
            
            # Only parse HTML content
            if 'text/html' in content_type:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract page title
                    if soup.title:
                        page_data['title'] = soup.title.string.strip() if soup.title.string else ''
                    
                    # Extract meta information
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc:
                        page_data['meta_description'] = meta_desc.get('content', '')
                    
                    meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                    if meta_keywords:
                        page_data['meta_keywords'] = meta_keywords.get('content', '')
                    
                    # Count page elements
                    page_data['links_count'] = len(soup.find_all('a', href=True))
                    page_data['images_count'] = len(soup.find_all('img'))
                    page_data['scripts_count'] = len(soup.find_all('script'))
                    page_data['forms_count'] = len(soup.find_all('form'))
                    
                except Exception as parse_error:
                    print(f"Error parsing HTML for {url}: {parse_error}")
            
            return page_data
            
        except requests.exceptions.RequestException as e:
            return {
                'url': url,
                'depth': depth,
                'error': f'Request error: {str(e)}',
                'status_code': 0
            }
        except Exception as e:
            return {
                'url': url,
                'depth': depth,
                'error': f'Unexpected error: {str(e)}',
                'status_code': 0
            }
    
    def _extract_links(self, url, allowed_extensions=None):
        """Extract links from a page for further crawling"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Only parse HTML content
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = set()
            base_domain = urlparse(url).netloc
            
            # Get all links from various tags
            for link in soup.find_all(['a'], href=True):
                href = link.get('href')
                if href:
                    try:
                        full_url = urljoin(url, href)
                        parsed = urlparse(full_url)
                        
                        # Only process links from same domain
                        if (parsed.netloc == base_domain and 
                            parsed.scheme in ['http', 'https'] and
                            self.is_valid_file(full_url, allowed_extensions) and
                            full_url not in self.visited_urls):
                            
                            links.add(full_url)
                            
                    except Exception as link_error:
                        continue
            
            return list(links)
            
        except Exception as e:
            print(f"Error extracting links from {url}: {e}")
            return []

    def stop(self):
        """Stop the crawler"""
        self.should_stop = True