import os
import json
import tempfile
import threading
import traceback
from datetime import datetime
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.metaspidey import metaspidey_bp
from app.metaspidey.forms import CrawlerForm, BruteForceForm, MetadataForm, DownloadForm, WordlistDownloadForm
from app.metaspidey.crawler import WebCrawler
from app.metaspidey.metadata_analyzer import MetadataAnalyzer
from app.metaspidey.downloader import FileDownloader
from app.metaspidey.ffuf_runner import FFUFRunner
from werkzeug.utils import secure_filename

# Global variables to store active operations
active_operations = {}
operation_results = {}
realtime_results = {}

@metaspidey_bp.route('/')
@login_required
def index():
    """Main MetaSpidey dashboard"""
    crawler_form = CrawlerForm()
    bruteforce_form = BruteForceForm()
    metadata_form = MetadataForm()
    download_form = DownloadForm()
    wordlist_form = WordlistDownloadForm()
    
    return render_template('metaspidey/index.html',
                         crawler_form=crawler_form,
                         bruteforce_form=bruteforce_form,
                         metadata_form=metadata_form,
                         download_form=download_form,
                         wordlist_form=wordlist_form)

@metaspidey_bp.route('/crawl', methods=['POST'])
@login_required
def start_crawl():
    """Start web crawling operation"""
    form = CrawlerForm()
    
    if form.validate_on_submit():
        try:
            operation_id = f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Parse extensions
            extensions = []
            if form.extensions.data:
                extensions = [ext.strip() for ext in form.extensions.data.split(',')]
            
            # Create crawler instance
            crawler = WebCrawler()
            
            # Start crawling in background thread
            def crawl_worker():
                try:
                    print(f"Starting crawl operation {operation_id}")
                    results = crawler.crawl(
                        url=form.url.data,
                        max_depth=int(form.depth.data),
                        delay=form.delay.data / 1000,  # Convert ms to seconds
                        extensions=extensions,
                        threads=form.threads.data
                    )
                    
                    print(f"Crawl operation {operation_id} completed successfully")
                    operation_results[operation_id] = {
                        'status': 'completed',
                        'results': results,
                        'timestamp': datetime.now().isoformat()
                    }
                except Exception as e:
                    print(f"Crawl operation {operation_id} failed: {str(e)}")
                    print(f"Traceback: {traceback.format_exc()}")
                    operation_results[operation_id] = {
                        'status': 'error',
                        'error': str(e),
                        'traceback': traceback.format_exc(),
                        'timestamp': datetime.now().isoformat()
                    }
                finally:
                    if operation_id in active_operations:
                        del active_operations[operation_id]
            
            # Store operation info
            active_operations[operation_id] = {
                'type': 'crawl',
                'status': 'running',
                'url': form.url.data,
                'started': datetime.now().isoformat()
            }
            
            # Start background thread
            thread = threading.Thread(target=crawl_worker)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'operation_id': operation_id,
                'message': 'Crawling started successfully'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return jsonify({
        'success': False,
        'errors': form.errors
    }), 400

@metaspidey_bp.route('/bruteforce', methods=['POST'])
@login_required
def start_bruteforce():
    """Start brute force fuzzing operation"""
    form = BruteForceForm()
    
    if form.validate_on_submit():
        try:
            # Determine wordlist source
            wordlist_path = None
            if form.wordlist_file.data and form.wordlist_file.data.filename:
                # Save uploaded wordlist
                filename = secure_filename(form.wordlist_file.data.filename)
                wordlist_path = os.path.join(tempfile.gettempdir(), filename)
                form.wordlist_file.data.save(wordlist_path)
            elif form.wordlist_path.data:
                wordlist_path = form.wordlist_path.data
            else:
                return jsonify({
                    'success': False,
                    'error': 'No wordlist provided. Upload a file or specify a path.'
                }), 400
            
            if not os.path.exists(wordlist_path):
                return jsonify({
                    'success': False,
                    'error': f'Wordlist file not found: {wordlist_path}'
                }), 400
                
            operation_id = f"bruteforce_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            def bruteforce_worker():
                try:
                    ffuf_runner = FFUFRunner()
                    
                    # Store real-time results for this operation
                    realtime_results[operation_id] = []
                    
                    def progress_callback(result):
                        """Store real-time results for live updates"""
                        realtime_results[operation_id].append(result)
                    
                    options = {
                        'fuzz_template': form.fuzz_url.data,
                        'wordlist': wordlist_path,
                        'threads': form.threads.data,
                        'status_codes': [int(code) for code in form.status_codes.data],
                        'recursion': form.recursion.data,
                        'recursion_depth': form.recursion_depth.data if form.recursion.data else None,
                        'timeout': form.timeout.data
                    }
                    
                    print(f"Starting brute force operation {operation_id}")
                    results = ffuf_runner.run_ffuf(options, progress_callback)
                    
                    operation_results[operation_id] = {
                        'status': 'completed',
                        'results': results,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    operation_results[operation_id] = {
                        'status': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                finally:
                    # Clean up temporary wordlist file
                    if form.wordlist_file.data and os.path.exists(wordlist_path):
                        os.unlink(wordlist_path)
                    
                    if operation_id in active_operations:
                        del active_operations[operation_id]
            
            # Store operation info
            active_operations[operation_id] = {
                'type': 'bruteforce',
                'status': 'running',
                'fuzz_url': form.fuzz_url.data,
                'wordlist': os.path.basename(wordlist_path),
                'started': datetime.now().isoformat()
            }
            
            # Start background thread
            thread = threading.Thread(target=bruteforce_worker)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'operation_id': operation_id,
                'message': 'Brute force fuzzing started successfully'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return jsonify({
        'success': False,
        'errors': form.errors
    }), 400

# SecLists download functionality removed for simplicity

@metaspidey_bp.route('/metadata', methods=['POST'])
@login_required
def analyze_metadata():
    """Analyze file metadata"""
    form = MetadataForm()
    
    if form.validate_on_submit():
        try:
            uploaded_files = request.files.getlist('files')
            input_directory = form.input_directory.data.strip() if form.input_directory.data else None
            output_file = form.output_file.data.strip() if form.output_file.data else None
            
            # Check if we have input (files or directory)
            if not uploaded_files and not input_directory:
                return jsonify({
                    'success': False,
                    'error': 'Please provide files to upload or specify an input directory'
                }), 400
            
            # Filter out empty files
            uploaded_files = [f for f in uploaded_files if f and f.filename]
            
            if not uploaded_files and not input_directory:
                return jsonify({
                    'success': False,
                    'error': 'No valid files or directory provided'
                }), 400
            
            operation_id = f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            def analyze_worker():
                try:
                    analyzer = MetadataAnalyzer()
                    results = []
                    
                    analysis_options = {
                        'extract_exif': form.extract_exif.data,
                        'calculate_hashes': form.calculate_hashes.data,
                        'deep_analysis': form.deep_analysis.data
                    }
                    
                    # Process uploaded files
                    if uploaded_files:
                        for uploaded_file in uploaded_files:
                            temp_path = None
                            try:
                                # Save uploaded file temporarily with unique name
                                filename = secure_filename(uploaded_file.filename)
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                                temp_path = os.path.join(tempfile.gettempdir(), f"metaspidey_{timestamp}_{filename}")
                                
                                print(f"Saving uploaded file: {filename} -> {temp_path}")
                                
                                # Read file content in memory first
                                uploaded_file.seek(0)
                                file_content = uploaded_file.read()
                                
                                if not file_content:
                                    raise Exception(f"Uploaded file {filename} is empty or unreadable")
                                
                                # Write to temporary file
                                with open(temp_path, 'wb') as temp_file:
                                    temp_file.write(file_content)
                                
                                # Verify file was written correctly
                                if not os.path.exists(temp_path):
                                    raise Exception(f"Failed to create temporary file: {temp_path}")
                                
                                file_size = os.path.getsize(temp_path)
                                if file_size == 0:
                                    raise Exception(f"Temporary file is empty: {temp_path}")
                                
                                print(f"Temporary file created successfully: {temp_path} ({file_size} bytes)")
                                
                                # Analyze file
                                print(f"Starting analysis of: {temp_path}")
                                metadata = analyzer.analyze_file(temp_path, **analysis_options)
                                
                                # Add source information
                                metadata['source'] = 'uploaded'
                                metadata['original_filename'] = filename
                                metadata['temp_file_size'] = file_size
                                
                                results.append(metadata)
                                print(f"Successfully analyzed: {filename}")
                                
                            except Exception as e:
                                error_msg = f'Failed to process {uploaded_file.filename}: {str(e)}'
                                print(f"Error: {error_msg}")
                                print(f"Traceback: {traceback.format_exc()}")
                                results.append({
                                    'error': error_msg,
                                    'filename': uploaded_file.filename,
                                    'source': 'uploaded'
                                })
                            finally:
                                # Clean up temp file
                                if temp_path and os.path.exists(temp_path):
                                    try:
                                        os.unlink(temp_path)
                                        print(f"Cleaned up temp file: {temp_path}")
                                    except Exception as cleanup_error:
                                        print(f"Failed to cleanup {temp_path}: {cleanup_error}")
                    
                    # Process directory
                    if input_directory:
                        print(f"Processing directory: {input_directory}")
                        directory_result = analyzer.analyze_directory(input_directory, **analysis_options)
                        
                        if 'error' in directory_result:
                            results.append(directory_result)
                        else:
                            # Add directory results
                            for result in directory_result.get('results', []):
                                result['source'] = 'directory'
                                results.append(result)
                    
                    # Save to output file if specified
                    if output_file and results:
                        try:
                            output_data = {
                                'analysis_timestamp': datetime.now().isoformat(),
                                'total_files': len(results),
                                'results': results
                            }
                            
                            # Create directory if it doesn't exist
                            os.makedirs(os.path.dirname(output_file), exist_ok=True)
                            
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(output_data, f, indent=2, ensure_ascii=False)
                            
                            print(f"Results saved to: {output_file}")
                            
                        except Exception as e:
                            results.append({
                                'error': f'Failed to save to output file: {str(e)}',
                                'output_file': output_file
                            })
                    
                    operation_results[operation_id] = {
                        'status': 'completed',
                        'results': results,
                        'total_analyzed': len(results),
                        'output_file': output_file,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    print(f"Metadata analysis error: {str(e)}")
                    operation_results[operation_id] = {
                        'status': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                finally:
                    if operation_id in active_operations:
                        del active_operations[operation_id]
            
            # Store operation info
            files_count = len(uploaded_files) if uploaded_files else 0
            active_operations[operation_id] = {
                'type': 'metadata',
                'status': 'running',
                'files_count': files_count,
                'input_directory': input_directory,
                'started': datetime.now().isoformat()
            }
            
            # Start background thread
            thread = threading.Thread(target=analyze_worker)
            thread.daemon = True
            thread.start()
            
            source_desc = []
            if uploaded_files:
                source_desc.append(f"{len(uploaded_files)} uploaded file(s)")
            if input_directory:
                source_desc.append(f"directory: {input_directory}")
            
            return jsonify({
                'success': True,
                'operation_id': operation_id,
                'message': f'Analyzing {" and ".join(source_desc)}'
            })
            
        except Exception as e:
            print(f"Metadata route error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return jsonify({
        'success': False,
        'errors': form.errors
    }), 400

@metaspidey_bp.route('/download', methods=['POST'])
@login_required
def start_download():
    """Start file download operation"""
    form = DownloadForm()
    
    if form.validate_on_submit():
        try:
            urls = []
            
            # Get URLs from text input
            if form.urls.data:
                urls.extend([url.strip() for url in form.urls.data.split('\n') if url.strip()])
            
            # Get URLs from uploaded file
            if form.url_file.data:
                try:
                    file_content = form.url_file.data.read().decode('utf-8', errors='ignore')
                    file_urls = [url.strip() for url in file_content.split('\n') if url.strip()]
                    urls.extend(file_urls)
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Error reading uploaded file: {str(e)}'
                    }), 400
            
            if not urls:
                return jsonify({
                    'success': False,
                    'error': 'No URLs provided in text input or uploaded file'
                }), 400
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            urls = unique_urls
            
            print(f"Processing {len(urls)} URLs for download")
            
            operation_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Determine download path
            download_path = form.download_path.data or os.path.expanduser('~/Downloads/MetaSpidey')
            
            def download_worker():
                try:
                    downloader = FileDownloader()
                    results = downloader.download_files(
                        urls=urls,
                        download_path=download_path,
                        max_size_mb=form.max_size.data,
                        threads=form.threads.data
                    )
                    
                    operation_results[operation_id] = {
                        'status': 'completed',
                        'results': results,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    operation_results[operation_id] = {
                        'status': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                finally:
                    if operation_id in active_operations:
                        del active_operations[operation_id]
            
            # Store operation info
            active_operations[operation_id] = {
                'type': 'download',
                'status': 'running',
                'urls_count': len(urls),
                'download_path': download_path,
                'started': datetime.now().isoformat()
            }
            
            # Start background thread
            thread = threading.Thread(target=download_worker)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'operation_id': operation_id,
                'message': f'Starting download of {len(urls)} file(s)'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return jsonify({
        'success': False,
        'errors': form.errors
    }), 400

@metaspidey_bp.route('/status/<operation_id>')
@login_required
def operation_status(operation_id):
    """Get status of an operation"""
    
    # Check active operations
    if operation_id in active_operations:
        return jsonify({
            'status': 'running',
            'operation': active_operations[operation_id]
        })
    
    # Check completed operations
    if operation_id in operation_results:
        return jsonify({
            'status': 'completed',
            'operation': operation_results[operation_id]
        })
    
    return jsonify({
        'status': 'not_found',
        'error': 'Operation not found'
    }), 404

@metaspidey_bp.route('/realtime/<operation_id>')
@login_required
def get_realtime_results(operation_id):
    """Get real-time results for fuzzing operations"""
    
    if operation_id in realtime_results:
        results = realtime_results[operation_id]
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
    
    return jsonify({
        'success': False,
        'results': [],
        'count': 0
    })

@metaspidey_bp.route('/results/<operation_id>')
@login_required
def get_results(operation_id):
    """Get results of a completed operation"""
    
    if operation_id in operation_results:
        result = operation_results[operation_id]
        if result['status'] == 'completed':
            return jsonify({
                'success': True,
                'results': result['results'],
                'timestamp': result['timestamp']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Operation failed'),
                'timestamp': result['timestamp']
            })
    
    return jsonify({
        'success': False,
        'error': 'Results not found'
    }), 404

@metaspidey_bp.route('/operations')
@login_required
def list_operations():
    """List all active and recent operations"""
    
    operations = []
    
    # Add active operations
    for op_id, op_data in active_operations.items():
        operations.append({
            'id': op_id,
            'status': 'running',
            **op_data
        })
    
    # Add completed operations (last 50)
    completed_ops = list(operation_results.items())[-50:]
    for op_id, op_data in completed_ops:
        operations.append({
            'id': op_id,
            'status': op_data['status'],
            'timestamp': op_data['timestamp'],
            'type': op_id.split('_')[0]  # Extract type from operation_id
        })
    
    return jsonify({
        'operations': sorted(operations, key=lambda x: x.get('started', x.get('timestamp', '')), reverse=True)
    })