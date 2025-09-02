import subprocess
import threading
import json
import os
import time
from urllib.parse import urlparse

class FFUFRunner:
    """FFUF (Fuzz Faster U Fool) runner for web directory/file discovery"""
    
    def __init__(self):
        self.process = None
        self.should_stop = False
        self.results = []
        self.lock = threading.Lock()
    
    def run_ffuf(self, options, progress_callback=None):
        """
        Run FFUF with the specified options
        
        Args:
            options: Dictionary containing:
                - fuzz_template: URL template with FUZZ keyword
                - wordlist: Path to wordlist file
                - threads: Number of threads
                - status_codes: List of status codes to match
                - recursion: Enable recursion
                - recursion_depth: Recursion depth
                - timeout: Request timeout
            progress_callback: Function to call for real-time updates
        
        Returns:
            Dictionary with results
        """
        try:
            # Check if ffuf is available
            if not self.check_ffuf_available():
                return self.simulate_ffuf(options, progress_callback)
            
            # Build FFUF command
            cmd = self.build_ffuf_command(options)
            
            # Create temporary output file
            temp_output = f"/tmp/ffuf_output_{int(time.time())}.json"
            cmd.extend(["-o", temp_output, "-of", "json"])
            
            # Run FFUF process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Wait for completion or stop signal
            stdout, stderr = self.process.communicate()
            
            # Parse results
            results = self.parse_ffuf_output(temp_output)
            
            # Cleanup
            if os.path.exists(temp_output):
                os.unlink(temp_output)
            
            return {
                'success': True,
                'results': results,
                'total_found': len(results),
                'stdout': stdout,
                'stderr': stderr
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def build_ffuf_command(self, options):
        """Build the FFUF command line"""
        cmd = ["ffuf"]
        
        # Basic options
        cmd.extend(["-u", options['fuzz_template']])
        cmd.extend(["-w", options['wordlist']])
        cmd.extend(["-t", str(options['threads'])])
        
        # Status codes
        if options.get('status_codes'):
            status_codes_str = ','.join(map(str, options['status_codes']))
            cmd.extend(["-mc", status_codes_str])
        
        # Recursion
        if options.get('recursion'):
            cmd.append("-recursion")
            if options.get('recursion_depth'):
                cmd.extend(["-recursion-depth", str(options['recursion_depth'])])
        
        # Timeout
        if options.get('timeout'):
            cmd.extend(["-timeout", str(options['timeout'])])
        
        # Additional options for better results
        cmd.extend(["-c"])  # Colorize output
        cmd.extend(["-v"])  # Verbose output
        
        return cmd
    
    def parse_ffuf_output(self, output_file):
        """Parse FFUF JSON output"""
        try:
            if not os.path.exists(output_file):
                return []
            
            with open(output_file, 'r') as f:
                data = json.load(f)
            
            results = []
            if 'results' in data:
                for result in data['results']:
                    results.append({
                        'url': result.get('url', ''),
                        'status': result.get('status', 0),
                        'length': result.get('length', 0),
                        'words': result.get('words', 0),
                        'lines': result.get('lines', 0),
                        'content_type': result.get('content-type', ''),
                        'redirectlocation': result.get('redirectlocation', ''),
                        'input': result.get('input', {})
                    })
            
            return results
            
        except Exception as e:
            print(f"Error parsing FFUF output: {e}")
            return []
    
    def check_ffuf_available(self):
        """Check if FFUF is available in the system"""
        try:
            subprocess.run(["ffuf", "-h"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def simulate_ffuf(self, options, progress_callback=None):
        """Simulate FFUF results when the tool is not available"""
        # This is a fallback simulation for demonstration
        import random
        
        try:
            # Read some words from the wordlist for simulation
            with open(options['wordlist'], 'r') as f:
                words = [line.strip() for line in f.readlines()[:100]]  # First 100 words
            
            results = []
            base_url = options['fuzz_template'].replace('FUZZ', '')
            total_words = len(words)
            
            print(f"Starting fuzzing simulation with {total_words} words")
            
            # Simulate findings with various status codes
            for i, word in enumerate(words):
                if self.should_stop:
                    break
                
                url = options['fuzz_template'].replace('FUZZ', word)
                
                # Simulate different status codes with realistic probabilities
                rand = random.random()
                if rand < 0.05:  # 5% chance of 200
                    status = 200
                elif rand < 0.08:  # 3% chance of 301/302
                    status = random.choice([301, 302])
                elif rand < 0.12:  # 4% chance of 403
                    status = 403
                elif rand < 0.15:  # 3% chance of 401
                    status = 401
                else:
                    status = 404  # Most will be 404
                
                # Only include results that match the status code filter
                if status in options.get('status_codes', [200, 301, 302, 403]):
                    result = {
                        'url': url,
                        'status': status,
                        'length': random.randint(100, 5000),
                        'words': random.randint(10, 500),
                        'lines': random.randint(5, 100),
                        'content_type': 'text/html',
                        'redirectlocation': '',
                        'input': {'FUZZ': word}
                    }
                    results.append(result)
                    
                    # Call progress callback for real-time updates
                    if progress_callback:
                        progress_callback(result)
                    
                    print(f"Found: [{status}] {url}")
                
                # Update progress
                progress = (i + 1) / total_words * 100
                if i % 10 == 0:  # Update every 10 items
                    print(f"Progress: {progress:.1f}% ({i+1}/{total_words})")
                
                # Small delay to simulate real fuzzing
                time.sleep(0.05)
            
            print(f"Fuzzing simulation completed. Found {len(results)} results")
            
            return {
                'success': True,
                'results': results,
                'total_found': len(results),
                'total_tested': len(words),
                'simulated': True,
                'note': 'FFUF not available - showing simulated results'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Simulation failed: {str(e)}",
                'results': []
            }
    
    def stop(self):
        """Stop the FFUF process"""
        self.should_stop = True
        
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                # Give it a moment to terminate gracefully
                time.sleep(1)
                
                if self.process.poll() is None:
                    self.process.kill()
                    
            except Exception as e:
                print(f"Error stopping FFUF process: {e}")

class WordlistDownloader:
    """Download and manage wordlists for fuzzing"""
    
    def __init__(self):
        self.should_stop = False
        self.progress_callback = None
    
    def download_seclists(self, download_path=None):
        """
        Download SecLists wordlist collection
        
        Args:
            download_path: Directory to download to (default: ~/wordlists)
        
        Returns:
            Dictionary with download results
        """
        if download_path is None:
            download_path = os.path.expanduser("~/wordlists")
        
        os.makedirs(download_path, exist_ok=True)
        
        seclists_url = "https://github.com/danielmiessler/SecLists/archive/refs/heads/master.zip"
        output_file = os.path.join(download_path, "SecLists-master.zip")
        
        try:
            return self.download_and_extract(seclists_url, output_file, download_path)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_and_extract(self, url, output_file, extract_path):
        """Download and extract a wordlist archive"""
        import requests
        import zipfile
        
        try:
            # Download with progress tracking
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.should_stop:
                        return {'success': False, 'error': 'Download cancelled'}
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Report progress
                        if self.progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            self.progress_callback(f"Downloading: {progress:.1f}%")
            
            # Extract the archive
            if self.progress_callback:
                self.progress_callback("Extracting archive...")
            
            with zipfile.ZipFile(output_file, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # Clean up zip file
            os.unlink(output_file)
            
            # Find common wordlists
            wordlists = self.find_common_wordlists(extract_path)
            
            return {
                'success': True,
                'download_path': extract_path,
                'wordlists_found': len(wordlists),
                'common_wordlists': wordlists
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def find_common_wordlists(self, base_path):
        """Find common wordlists in the downloaded collection"""
        common_lists = []
        
        # Common wordlist paths in SecLists
        common_paths = [
            "SecLists-master/Discovery/Web-Content/common.txt",
            "SecLists-master/Discovery/Web-Content/directory-list-2.3-small.txt",
            "SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt",
            "SecLists-master/Discovery/Web-Content/raft-small-words.txt",
            "SecLists-master/Discovery/Web-Content/raft-medium-words.txt",
            "SecLists-master/Usernames/top-usernames-shortlist.txt",
            "SecLists-master/Passwords/Common-Credentials/10-million-password-list-top-1000.txt"
        ]
        
        for path in common_paths:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path):
                common_lists.append({
                    'name': os.path.basename(path),
                    'path': full_path,
                    'category': path.split('/')[1] if '/' in path else 'Other',
                    'size': os.path.getsize(full_path)
                })
        
        return common_lists
    
    def stop(self):
        """Stop the download process"""
        self.should_stop = True