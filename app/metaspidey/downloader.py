import os
import requests
from urllib.parse import urlparse
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime

class FileDownloader:
    """File downloader for MetaSpidey web interface"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MetaSpidey/1.0 (Security Research Tool)'
        })
        self.downloaded_files = []
        self.failed_downloads = []
        self.lock = threading.Lock()

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