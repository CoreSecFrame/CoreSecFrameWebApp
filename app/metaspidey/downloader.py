import os
import requests
from urllib.parse import urlparse, urljoin
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from bs4 import BeautifulSoup
import mimetypes
from urllib.robotparser import RobotFileParser
import re

class FileDownloader:
    """Enhanced File downloader with crawling capabilities for MetaSpidey"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MetaSpidey/1.0 (Security Research Tool)'
        })
        self.downloaded_files = []
        self.failed_downloads = []
        self.discovered_files = []
        self.visited_urls = set()
        self.lock = threading.Lock()
        self.robots_parser = RobotFileParser()
        self.should_stop = False

    def download_file(self, url, download_path, max_size_mb=100):
        """
        Download a single file
        
        Args:
            url: URL to download
            download_path: Directory to save the file
            max_size_mb: Maximum file size in MB
        
        Returns:
            Dictionary with download result
        """
        try:
            # Parse URL to get filename
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename or '.' not in filename:
                # Generate filename from URL
                filename = f"download_{int(time.time())}"
            
            # Ensure download directory exists
            Path(download_path).mkdir(parents=True, exist_ok=True)
            
            file_path = os.path.join(download_path, filename)
            
            # Handle duplicate filenames
            counter = 1
            original_path = file_path
            while os.path.exists(file_path):
                name, ext = os.path.splitext(original_path)
                file_path = f"{name}_{counter}{ext}"
                counter += 1
            
            # Start download with streaming
            with self.session.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                
                # Check content length
                content_length = response.headers.get('content-length')
                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    if size_mb > max_size_mb:
                        return {
                            'url': url,
                            'status': 'failed',
                            'error': f'File too large ({size_mb:.1f}MB > {max_size_mb}MB)',
                            'timestamp': datetime.now().isoformat()
                        }
                
                # Download file
                downloaded_size = 0
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Check size limit during download
                            if downloaded_size > max_size_mb * 1024 * 1024:
                                os.unlink(file_path)  # Delete partial file
                                return {
                                    'url': url,
                                    'status': 'failed',
                                    'error': f'File exceeded size limit during download',
                                    'timestamp': datetime.now().isoformat()
                                }
                
                # Get file info
                file_size = os.path.getsize(file_path)
                
                result = {
                    'url': url,
                    'status': 'success',
                    'filename': os.path.basename(file_path),
                    'file_path': file_path,
                    'file_size': file_size,
                    'file_size_human': self._format_file_size(file_size),
                    'content_type': response.headers.get('content-type', 'unknown'),
                    'download_time': datetime.now().isoformat(),
                    'server': response.headers.get('server', 'unknown')
                }
                
                with self.lock:
                    self.downloaded_files.append(result)
                
                return result
                
        except requests.exceptions.RequestException as e:
            result = {
                'url': url,
                'status': 'failed',
                'error': f'Request error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
            
            with self.lock:
                self.failed_downloads.append(result)
            
            return result
            
        except Exception as e:
            result = {
                'url': url,
                'status': 'failed',
                'error': f'Unexpected error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
            
            with self.lock:
                self.failed_downloads.append(result)
            
            return result

    def download_files(self, urls, download_path, max_size_mb=100, threads=3):
        """
        Download multiple files - simplified for better reliability
        
        Args:
            urls: List of URLs to download
            download_path: Directory to save files
            max_size_mb: Maximum file size in MB
            threads: Number of concurrent downloads (unused in simplified version)
        
        Returns:
            Dictionary with download results
        """
        try:
            self.downloaded_files = []
            self.failed_downloads = []
            
            print(f"Starting download of {len(urls)} files to {download_path}")
            
            start_time = datetime.now()
            results = []
            
            # Process downloads sequentially for better reliability
            for i, url in enumerate(urls):
                try:
                    print(f"Downloading {i+1}/{len(urls)}: {url}")
                    result = self.download_file(url, download_path, max_size_mb)
                    results.append(result)
                    
                    if result['status'] == 'success':
                        print(f"✓ Downloaded: {result['filename']}")
                    else:
                        print(f"✗ Failed: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    error_result = {
                        'url': url,
                        'status': 'failed',
                        'error': f'Download error: {str(e)}',
                        'timestamp': datetime.now().isoformat()
                    }
                    results.append(error_result)
                    self.failed_downloads.append(error_result)
                    print(f"✗ Error downloading {url}: {str(e)}")
                
                # Small delay between downloads
                time.sleep(0.1)
            
            end_time = datetime.now()
            
            # Compile summary
            successful = len(self.downloaded_files)
            failed = len(self.failed_downloads)
            total_size = sum(f.get('file_size', 0) for f in self.downloaded_files)
            
            summary = {
                'total_urls': len(urls),
                'successful_downloads': successful,
                'failed_downloads': failed,
                'success_rate': (successful / len(urls) * 100) if urls else 0,
                'total_size_bytes': total_size,
                'total_size_human': self._format_file_size(total_size),
                'download_path': download_path,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration': str(end_time - start_time),
                'results': results
            }
            
            print(f"Download completed: {successful} successful, {failed} failed")
            return summary
            
        except Exception as e:
            print(f"Download batch failed: {str(e)}")
            return {
                'total_urls': len(urls),
                'successful_downloads': 0,
                'failed_downloads': len(urls),
                'success_rate': 0,
                'total_size_bytes': 0,
                'total_size_human': '0 B',
                'download_path': download_path,
                'error': str(e),
                'results': []
            }

    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def get_url_info(self, url):
        """Get information about a URL without downloading"""
        try:
            response = self.session.head(url, timeout=10)
            
            return {
                'url': url,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', 'unknown'),
                'content_length': response.headers.get('content-length'),
                'server': response.headers.get('server', 'unknown'),
                'last_modified': response.headers.get('last-modified'),
                'accessible': response.status_code == 200
            }
            
        except Exception as e:
            return {
                'url': url,
                'error': str(e),
                'accessible': False
            }

    def validate_urls(self, urls):
        """Validate a list of URLs before downloading"""
        validation_results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {
                executor.submit(self.get_url_info, url): url 
                for url in urls
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    validation_results.append(result)
                except Exception as e:
                    validation_results.append({
                        'url': url,
                        'error': str(e),
                        'accessible': False
                    })
        
        return {
            'total_urls': len(urls),
            'accessible_urls': sum(1 for r in validation_results if r.get('accessible', False)),
            'validation_results': validation_results
        }

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

    def is_valid_file_extension(self, url, allowed_extensions):
        """Check if URL has allowed file extension"""
        if not allowed_extensions:
            return True
        
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        return any(path.endswith(ext.lower()) for ext in allowed_extensions)

    def extract_files_from_page(self, url, allowed_extensions=None, fuzzing_patterns=None):
        """Extract downloadable files from a web page"""
        try:
            if self.should_stop:
                return []
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return []
            
            soup = BeautifulSoup(response.content, 'html5lib')
            files = set()
            base_domain = urlparse(url).netloc
            
            # Find files in various HTML elements
            selectors = [
                'a[href]',      # Links
                'img[src]',     # Images
                'script[src]',  # Scripts
                'link[href]',   # Stylesheets, icons
                'embed[src]',   # Embedded content
                'object[data]', # Objects
                'source[src]',  # Media sources
                'track[src]'    # Video tracks
            ]
            
            for selector in selectors:
                for element in soup.select(selector):
                    file_url = element.get('href') or element.get('src') or element.get('data')
                    if file_url:
                        full_url = urljoin(url, file_url)
                        parsed = urlparse(full_url)
                        
                        # Check if it's a valid file from same domain
                        if (parsed.netloc == base_domain and 
                            parsed.scheme in ['http', 'https'] and
                            self.is_valid_file_extension(full_url, allowed_extensions) and
                            self.is_allowed(full_url)):
                            files.add(full_url)
            
            # Fuzzing patterns for common file locations
            if fuzzing_patterns:
                for pattern in fuzzing_patterns:
                    fuzzed_url = urljoin(url, pattern)
                    if self.is_valid_file_extension(fuzzed_url, allowed_extensions):
                        # Test if file exists
                        try:
                            head_response = self.session.head(fuzzed_url, timeout=5)
                            if head_response.status_code == 200:
                                files.add(fuzzed_url)
                        except:
                            continue
            
            return list(files)
            
        except Exception as e:
            print(f"Error extracting files from {url}: {e}")
            return []

    def crawl_and_discover_files(self, start_url, max_depth=2, delay=0.1, 
                               allowed_extensions=None, fuzzing_patterns=None, 
                               threads=3, max_files=100, progress_callback=None):
        """
        Crawl website and discover downloadable files - Improved version
        
        Args:
            start_url: Starting URL for crawling
            max_depth: Maximum crawl depth (1-5 supported)
            delay: Delay between requests in seconds
            allowed_extensions: List of allowed file extensions (e.g., ['.pdf', '.doc'])
            fuzzing_patterns: List of patterns to fuzz for files
            threads: Number of concurrent threads
            max_files: Maximum number of files to discover
            progress_callback: Function to call with discovered files for real-time updates
            
        Returns:
            Dictionary with discovered files and crawl results
        """
        try:
            # Reset state
            self.discovered_files = []
            self.visited_urls = set()
            self.should_stop = False
            
            # Validate input URL
            if not start_url.startswith(('http://', 'https://')):
                start_url = 'https://' + start_url.strip()
            
            print(f"Starting enhanced file discovery crawl of {start_url} with depth {max_depth}")
            
            # Adjust limits based on depth (similar to main crawler)
            max_pages = min(200, max_depth * 50)  # Scale with depth
            links_per_page = min(20, max_depth * 4)  # More links for deeper crawls
            
            # Initialize with starting URL
            urls_queue = [(start_url, 0)]
            processed_count = 0
            files_found = 0
            
            while (urls_queue and not self.should_stop and 
                   processed_count < max_pages and files_found < max_files):
                
                current_url, current_depth = urls_queue.pop(0)
                
                # Skip if already visited
                if current_url in self.visited_urls:
                    continue
                    
                self.visited_urls.add(current_url)
                processed_count += 1
                
                try:
                    print(f"[{processed_count}/{max_pages}] Crawling: {current_url} (depth: {current_depth})")
                    
                    # Get page info first (similar to main crawler)
                    page_info = self._analyze_page_for_files(current_url, current_depth, 
                                                           allowed_extensions, fuzzing_patterns)
                    
                    # Extract files from current page
                    page_files = page_info.get('files', [])
                    
                    # Add discovered files
                    for file_info in page_files:
                        if file_info['url'] not in [f['url'] for f in self.discovered_files]:
                            file_info.update({
                                'discovered_from': current_url,
                                'depth': current_depth,
                                'discovery_time': datetime.now().isoformat()
                            })
                            self.discovered_files.append(file_info)
                            files_found += 1
                            
                            print(f"✓ Discovered file [{files_found}]: {file_info['filename']} ({file_info['extension']})")
                            
                            # Real-time callback for UI updates
                            if progress_callback:
                                progress_callback({
                                    'type': 'file_discovered',
                                    'file': file_info,
                                    'total_discovered': len(self.discovered_files),
                                    'pages_crawled': processed_count
                                })
                    
                    # If within depth limit, find new pages to crawl
                    if current_depth < max_depth:
                        new_links = self._extract_page_links_improved(current_url, current_depth)
                        added_links = 0
                        for link in new_links:
                            if (link not in self.visited_urls and 
                                added_links < links_per_page and
                                len(urls_queue) < max_pages * 2):  # Queue size limit
                                urls_queue.append((link, current_depth + 1))
                                added_links += 1
                        
                        if added_links > 0:
                            print(f"  → Added {added_links} new URLs to crawl (queue: {len(urls_queue)})")
                    
                    # Progress callback for page completion
                    if progress_callback:
                        progress_callback({
                            'type': 'page_crawled',
                            'url': current_url,
                            'files_on_page': len(page_files),
                            'total_discovered': len(self.discovered_files),
                            'pages_crawled': processed_count,
                            'queue_remaining': len(urls_queue)
                        })
                    
                    # Respect delay
                    if delay > 0:
                        time.sleep(delay)
                        
                except Exception as e:
                    print(f"✗ Error processing {current_url}: {str(e)}")
                    continue
            
            print(f"File discovery completed. Found {len(self.discovered_files)} files from {processed_count} pages.")
            
            # Final callback
            if progress_callback:
                progress_callback({
                    'type': 'crawl_completed',
                    'total_files': len(self.discovered_files),
                    'pages_crawled': processed_count
                })
            
            return {
                'discovered_files': self.discovered_files,
                'total_files_found': len(self.discovered_files),
                'pages_crawled': processed_count,
                'crawl_depth': max_depth,
                'extensions_filter': allowed_extensions or [],
                'start_url': start_url,
                'max_pages_limit': max_pages,
                'fuzzing_enabled': bool(fuzzing_patterns)
            }
            
        except Exception as e:
            print(f"File discovery crawl failed: {str(e)}")
            return {
                'discovered_files': [],
                'total_files_found': 0,
                'pages_crawled': 0,
                'crawl_depth': max_depth,
                'extensions_filter': allowed_extensions or [],
                'start_url': start_url,
                'error': str(e)
            }

    def _analyze_page_for_files(self, url, depth, allowed_extensions=None, fuzzing_patterns=None):
        """Analyze a page for downloadable files - Enhanced version"""
        try:
            response = self.session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            page_info = {
                'url': url,
                'depth': depth,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', ''),
                'content_length': len(response.content),
                'files': []
            }
            
            # Extract files from HTML content
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                files = self.extract_files_from_page(url, allowed_extensions, fuzzing_patterns)
                
                # Convert to detailed file info
                for file_url in files:
                    parsed_url = urlparse(file_url)
                    filename = os.path.basename(parsed_url.path) or 'unknown'
                    extension = os.path.splitext(parsed_url.path)[1] or ''
                    
                    file_info = {
                        'url': file_url,
                        'filename': filename,
                        'extension': extension,
                        'estimated_type': self._guess_file_type(extension)
                    }
                    page_info['files'].append(file_info)
            
            return page_info
            
        except Exception as e:
            print(f"Error analyzing page {url}: {e}")
            return {
                'url': url,
                'depth': depth,
                'error': str(e),
                'files': []
            }

    def _guess_file_type(self, extension):
        """Guess file type from extension"""
        type_map = {
            '.pdf': 'Document',
            '.doc': 'Document', '.docx': 'Document',
            '.xls': 'Spreadsheet', '.xlsx': 'Spreadsheet',
            '.ppt': 'Presentation', '.pptx': 'Presentation',
            '.zip': 'Archive', '.rar': 'Archive', '.tar': 'Archive', '.gz': 'Archive',
            '.jpg': 'Image', '.jpeg': 'Image', '.png': 'Image', '.gif': 'Image',
            '.mp3': 'Audio', '.wav': 'Audio', '.mp4': 'Video', '.avi': 'Video',
            '.txt': 'Text', '.csv': 'Data', '.json': 'Data', '.xml': 'Data'
        }
        return type_map.get(extension.lower(), 'Unknown')

    def _extract_page_links_improved(self, url, current_depth):
        """Extract page links for further crawling - Improved version"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return []
            
            soup = BeautifulSoup(response.content, 'html5lib')
            links = set()
            base_domain = urlparse(url).netloc
            
            # Get all page links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href:
                    try:
                        full_url = urljoin(url, href)
                        parsed = urlparse(full_url)
                        
                        # Only process HTML pages from same domain
                        if (parsed.netloc == base_domain and 
                            parsed.scheme in ['http', 'https'] and
                            self._is_crawlable_page(full_url) and
                            full_url not in self.visited_urls):
                            
                            links.add(full_url)
                            
                    except Exception:
                        continue
            
            return list(links)
            
        except Exception as e:
            print(f"Error extracting links from {url}: {e}")
            return []

    def _is_crawlable_page(self, url):
        """Check if URL is a crawlable page (not a direct file)"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Skip direct file downloads
        file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                          '.zip', '.rar', '.tar', '.gz', '.jpg', '.jpeg', '.png', 
                          '.gif', '.mp3', '.mp4', '.avi', '.mov', '.txt', '.csv']
        
        if any(path.endswith(ext) for ext in file_extensions):
            return False
        
        # Skip common non-page paths
        skip_paths = ['/api/', '/ajax/', '/json/', '/xml/', '/rss/', '/feed/']
        if any(skip_path in path for skip_path in skip_paths):
            return False
        
        return True

    def _extract_page_links(self, url):
        """Extract page links for further crawling"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return []
            
            soup = BeautifulSoup(response.content, 'html5lib')
            links = set()
            base_domain = urlparse(url).netloc
            
            # Get all page links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href:
                    try:
                        full_url = urljoin(url, href)
                        parsed = urlparse(full_url)
                        
                        # Only process HTML pages from same domain
                        if (parsed.netloc == base_domain and 
                            parsed.scheme in ['http', 'https'] and
                            not any(parsed.path.lower().endswith(ext) for ext in 
                                  ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                                   '.zip', '.rar', '.tar', '.gz', '.jpg', '.jpeg', '.png', 
                                   '.gif', '.mp3', '.mp4', '.avi', '.mov']) and
                            full_url not in self.visited_urls):
                            
                            links.add(full_url)
                            
                    except Exception:
                        continue
            
            return list(links)
            
        except Exception as e:
            print(f"Error extracting links from {url}: {e}")
            return []

    def crawl_and_download_files(self, start_url, download_path, max_depth=2, 
                               delay=0.1, allowed_extensions=None, fuzzing_patterns=None,
                               threads=3, max_size_mb=100, max_files=100, progress_callback=None):
        """
        Crawl website, discover files, and download them - Enhanced with real-time feedback
        
        Args:
            start_url: Starting URL for crawling
            download_path: Directory to save downloaded files
            max_depth: Maximum crawl depth
            delay: Delay between requests
            allowed_extensions: List of allowed file extensions
            fuzzing_patterns: Patterns for file fuzzing
            threads: Number of concurrent operations
            max_size_mb: Maximum file size in MB
            max_files: Maximum number of files to download
            progress_callback: Function to call for real-time updates
            
        Returns:
            Dictionary with crawl and download results
        """
        try:
            print(f"Starting enhanced crawl-and-download operation for {start_url}")
            
            # Phase 1: Discover files with real-time feedback
            discovery_results = self.crawl_and_discover_files(
                start_url, max_depth, delay, allowed_extensions, 
                fuzzing_patterns, threads, max_files, progress_callback
            )
            
            if discovery_results.get('error'):
                return discovery_results
            
            discovered_files = discovery_results['discovered_files']
            if not discovered_files:
                return {
                    **discovery_results,
                    'download_results': {
                        'total_urls': 0,
                        'successful_downloads': 0,
                        'failed_downloads': 0,
                        'success_rate': 0,
                        'total_size_bytes': 0,
                        'total_size_human': '0 B',
                        'download_path': download_path,
                        'results': []
                    }
                }
            
            # Phase 2: Download discovered files
            file_urls = [f['url'] for f in discovered_files]
            print(f"Downloading {len(file_urls)} discovered files...")
            
            download_results = self.download_files(
                file_urls, download_path, max_size_mb, threads
            )
            
            # Combine results
            return {
                **discovery_results,
                'download_results': download_results
            }
            
        except Exception as e:
            print(f"Crawl-and-download operation failed: {str(e)}")
            return {
                'discovered_files': [],
                'total_files_found': 0,
                'pages_crawled': 0,
                'error': str(e),
                'download_results': {
                    'total_urls': 0,
                    'successful_downloads': 0,
                    'failed_downloads': 0,
                    'success_rate': 0,
                    'total_size_bytes': 0,
                    'total_size_human': '0 B',
                    'download_path': download_path,
                    'results': []
                }
            }

    def generate_fuzzing_patterns(self, common_files=True, backup_files=True, 
                                config_files=True, custom_patterns=None):
        """
        Generate common file fuzzing patterns
        
        Args:
            common_files: Include common file patterns
            backup_files: Include backup file patterns
            config_files: Include configuration file patterns
            custom_patterns: List of custom patterns to include
            
        Returns:
            List of fuzzing patterns
        """
        patterns = []
        
        if common_files:
            patterns.extend([
                'robots.txt', 'sitemap.xml', 'favicon.ico',
                'index.html', 'index.htm', 'default.html',
                'readme.txt', 'README.md', 'changelog.txt',
                'license.txt', 'terms.pdf', 'privacy.pdf'
            ])
        
        if backup_files:
            patterns.extend([
                'backup.zip', 'backup.tar.gz', 'backup.sql',
                'database.sql', 'dump.sql', 'export.csv',
                'archive.zip', 'old_site.zip', 'website_backup.tar'
            ])
        
        if config_files:
            patterns.extend([
                '.env', 'config.json', 'settings.xml',
                'web.config', '.htaccess', 'wp-config.php',
                'database.ini', 'app.conf', 'server.cfg'
            ])
        
        if custom_patterns:
            patterns.extend(custom_patterns)
        
        return patterns

    def stop(self):
        """Stop the crawler"""
        self.should_stop = True