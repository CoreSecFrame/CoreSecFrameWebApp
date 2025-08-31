/**
 * MetaSpidey Web Interface JavaScript
 * Provides functionality for web crawling, metadata analysis, and file operations
 */

class MetaSpidey {
    constructor() {
        this.activeOperations = new Map();
        this.pollInterval = 2000; // 2 seconds
        this.csrf_token = document.querySelector('meta[name=csrf-token]').getAttribute('content');
    }

    static init() {
        window.metaspidey = new MetaSpidey();
        window.metaspidey.bindEvents();
        window.metaspidey.loadOperations();
    }

    bindEvents() {
        // Form submissions
        document.getElementById('crawler-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startCrawling();
        });

        document.getElementById('metadata-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.analyzeMetadata();
        });

        document.getElementById('download-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startDownload();
        });

        document.getElementById('bruteforce-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startBruteForce();
        });

        // Removed SecLists download functionality

        // Depth description update
        const depthSelect = document.querySelector('[name="depth"]');
        if (depthSelect) {
            depthSelect.addEventListener('change', (e) => {
                this.updateDepthDescription(e.target.value);
            });
            this.updateDepthDescription(depthSelect.value);
        }

        // Tab switching
        document.querySelectorAll('[data-bs-toggle="pill"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                if (e.target.id === 'operations-tab') {
                    this.loadOperations();
                }
            });
        });
    }

    updateDepthDescription(depth) {
        const descriptions = {
            '1': 'Crawls only the links found on the initial URL',
            '2': 'Crawls the main page and one layer of internal links',
            '3': 'Includes main sections and their subsections',
            '4': 'Crawls down to more specific content and files',
            '5': 'Exhaustive crawl (can take a long time)'
        };
        
        const descElement = document.getElementById('depth-description');
        if (descElement && descriptions[depth]) {
            descElement.textContent = descriptions[depth];
        }
    }

    async startCrawling() {
        const form = document.getElementById('crawler-form');
        const formData = new FormData(form);
        
        try {
            this.showOperationStatus('crawler', 'Starting web crawler...');
            
            const response = await fetch('/metaspidey/crawl', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Crawling started successfully', 'success');
                this.monitorOperation(result.operation_id, 'crawler');
            } else {
                this.hideOperationStatus('crawler');
                this.showNotification('Failed to start crawling: ' + (result.error || 'Unknown error'), 'error');
                this.displayFormErrors(result.errors);
            }
        } catch (error) {
            this.hideOperationStatus('crawler');
            this.showNotification('Error starting crawler: ' + error.message, 'error');
        }
    }

    async analyzeMetadata() {
        const form = document.getElementById('metadata-form');
        const formData = new FormData(form);
        
        // Check if files are selected
        const fileInput = form.querySelector('[name="files"]');
        if (!fileInput.files.length) {
            this.showNotification('Please select at least one file to analyze', 'warning');
            return;
        }

        try {
            this.showOperationStatus('metadata', 'Analyzing file metadata...');
            
            const response = await fetch('/metaspidey/metadata', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification(`Analyzing ${fileInput.files.length} file(s)`, 'success');
                this.monitorOperation(result.operation_id, 'metadata');
            } else {
                this.hideOperationStatus('metadata');
                this.showNotification('Failed to start analysis: ' + (result.error || 'Unknown error'), 'error');
                this.displayFormErrors(result.errors);
            }
        } catch (error) {
            this.hideOperationStatus('metadata');
            this.showNotification('Error starting analysis: ' + error.message, 'error');
        }
    }

    async startDownload() {
        const form = document.getElementById('download-form');
        const formData = new FormData(form);
        
        // Check if URLs are provided
        const urlsTextarea = form.querySelector('[name="urls"]');
        const urls = urlsTextarea.value.trim().split('\n').filter(url => url.trim());
        
        if (!urls.length) {
            this.showNotification('Please enter at least one URL to download', 'warning');
            return;
        }

        try {
            this.showOperationStatus('download', `Starting download of ${urls.length} file(s)...`);
            
            const response = await fetch('/metaspidey/download', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification(result.message, 'success');
                this.monitorOperation(result.operation_id, 'download');
            } else {
                this.hideOperationStatus('download');
                this.showNotification('Failed to start download: ' + (result.error || 'Unknown error'), 'error');
                this.displayFormErrors(result.errors);
            }
        } catch (error) {
            this.hideOperationStatus('download');
            this.showNotification('Error starting download: ' + error.message, 'error');
        }
    }

    async startBruteForce() {
        const form = document.getElementById('bruteforce-form');
        const formData = new FormData(form);
        
        // Basic validation
        const fuzzUrl = form.querySelector('[name="fuzz_url"]').value.trim();
        if (!fuzzUrl) {
            this.showNotification('Please enter a target URL with FUZZ placeholder', 'warning');
            return;
        }
        
        if (!fuzzUrl.includes('FUZZ')) {
            this.showNotification('Target URL must contain the FUZZ keyword', 'warning');
            return;
        }
        
        // Check if wordlist is provided
        const wordlistFile = form.querySelector('[name="wordlist_file"]').files[0];
        const wordlistPath = form.querySelector('[name="wordlist_path"]').value.trim();
        
        if (!wordlistFile && !wordlistPath) {
            this.showNotification('Please provide a wordlist file or path', 'warning');
            return;
        }

        try {
            this.showOperationStatus('bruteforce', 'Starting brute force fuzzer...');
            this.showFoundUrlsSection();
            
            const response = await fetch('/metaspidey/bruteforce', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Brute force fuzzing started successfully', 'success');
                this.monitorOperation(result.operation_id, 'bruteforce');
            } else {
                this.hideOperationStatus('bruteforce');
                this.hideFoundUrlsSection();
                this.showNotification('Failed to start fuzzing: ' + (result.error || 'Unknown error'), 'error');
                this.displayFormErrors(result.errors);
            }
        } catch (error) {
            this.hideOperationStatus('bruteforce');
            this.hideFoundUrlsSection();
            this.showNotification('Error starting fuzzer: ' + error.message, 'error');
        }
    }

    // SecLists download functionality has been removed for simplicity

    showFoundUrlsSection() {
        const section = document.getElementById('found-urls-section');
        const terminal = document.getElementById('found-urls-terminal');
        const counter = document.getElementById('found-urls-count');
        
        section.style.display = 'block';
        terminal.innerHTML = ''; // Clear previous results
        counter.textContent = '0';
    }

    hideFoundUrlsSection() {
        const section = document.getElementById('found-urls-section');
        section.style.display = 'none';
    }

    addFoundUrl(url, status, length) {
        const terminal = document.getElementById('found-urls-terminal');
        const counter = document.getElementById('found-urls-count');
        
        if (terminal && counter) {
            const currentCount = parseInt(counter.textContent) || 0;
            counter.textContent = currentCount + 1;
            
            // Add URL to terminal with color coding based on status
            const statusClass = this.getStatusClass(status);
            const urlLine = document.createElement('div');
            urlLine.className = 'url-found';
            urlLine.innerHTML = `<span class="badge ${statusClass} me-2">${status}</span><span class="text-muted">[${length}]</span> ${url}`;
            
            terminal.appendChild(urlLine);
            terminal.scrollTop = terminal.scrollHeight; // Auto-scroll to bottom
        }
    }

    getStatusClass(status) {
        if (status >= 200 && status < 300) return 'status-badge-200';
        if (status >= 300 && status < 400) return 'status-badge-redirect';
        return 'status-badge-error';
    }

    async monitorOperation(operationId, type) {
        this.activeOperations.set(operationId, { type, startTime: Date.now() });

        const pollOperation = async () => {
            try {
                const response = await fetch(`/metaspidey/status/${operationId}`);
                const result = await response.json();

                if (result.status === 'running') {
                    // Update progress if available
                    this.updateOperationProgress(type, result.operation);
                    
                    // For brute force operations, get real-time results
                    if (type === 'bruteforce') {
                        await this.updateRealtimeResults(operationId);
                    }
                    
                    // Continue polling
                    setTimeout(pollOperation, this.pollInterval);
                } else if (result.status === 'completed') {
                    // Operation finished, get results
                    this.activeOperations.delete(operationId);
                    this.hideOperationStatus(type);
                    
                    // Get final real-time results for brute force
                    if (type === 'bruteforce') {
                        await this.updateRealtimeResults(operationId);
                    }
                    
                    await this.loadOperationResults(operationId, type);
                    this.loadOperations(); // Refresh operations list
                } else {
                    // Operation not found or error
                    this.activeOperations.delete(operationId);
                    this.hideOperationStatus(type);
                    this.showNotification('Operation status unknown', 'warning');
                }
            } catch (error) {
                console.error('Error polling operation:', error);
                setTimeout(pollOperation, this.pollInterval * 2); // Retry with longer interval
            }
        };

        setTimeout(pollOperation, this.pollInterval);
    }

    async updateRealtimeResults(operationId) {
        try {
            const response = await fetch(`/metaspidey/realtime/${operationId}`);
            const result = await response.json();
            
            if (result.success && result.results.length > 0) {
                // Update the found URLs terminal with new results
                const terminal = document.getElementById('found-urls-terminal');
                const counter = document.getElementById('found-urls-count');
                
                if (terminal && counter) {
                    // Clear and rebuild with all results
                    terminal.innerHTML = '';
                    
                    result.results.forEach(urlResult => {
                        const statusClass = this.getStatusClass(urlResult.status);
                        const urlLine = document.createElement('div');
                        urlLine.className = 'url-found mb-1';
                        urlLine.innerHTML = `
                            <span class="badge ${statusClass} me-2">${urlResult.status}</span>
                            <span class="text-muted me-2">[${urlResult.length}]</span>
                            <span class="text-break">${urlResult.url}</span>
                        `;
                        terminal.appendChild(urlLine);
                    });
                    
                    counter.textContent = result.count;
                    terminal.scrollTop = terminal.scrollHeight; // Auto-scroll to bottom
                }
            }
        } catch (error) {
            console.error('Error updating real-time results:', error);
        }
    }

    async loadOperationResults(operationId, type) {
        try {
            const response = await fetch(`/metaspidey/results/${operationId}`);
            const result = await response.json();

            if (result.success) {
                this.displayResults(result.results, type);
                this.showNotification('Operation completed successfully', 'success');
            } else {
                this.showNotification('Operation failed: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error loading results: ' + error.message, 'error');
        }
    }

    displayResults(results, type) {
        const container = document.getElementById(`${type}-results`);
        
        switch (type) {
            case 'crawler':
                container.innerHTML = this.renderCrawlerResults(results);
                break;
            case 'metadata':
                container.innerHTML = this.renderMetadataResults(results);
                break;
            case 'download':
                container.innerHTML = this.renderDownloadResults(results);
                break;
            case 'bruteforce':
                container.innerHTML = this.renderBruteForceResults(results);
                break;
            case 'wordlist_download':
                container.innerHTML = this.renderWordlistResults(results);
                break;
        }
    }

    renderCrawlerResults(results) {
        if (!results.urls || results.urls.length === 0) {
            return '<div class="text-center text-muted py-4"><h5>No URLs found</h5></div>';
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5><i class="bi bi-globe me-2"></i>Crawling Results</h5>
                <div class="text-muted">
                    Found ${results.total_urls} URLs (Depth: ${results.crawl_depth})
                </div>
            </div>
            <div class="table-responsive">
                    <table class="table table-sm table-hover results-table">
                        <thead class="table-light">
                            <tr>
                                <th>URL</th>
                                <th>Title</th>
                                <th>Status</th>
                                <th>Size</th>
                                <th>Type</th>
                                <th>Depth</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        results.urls.forEach(url => {
            const sizeFormatted = url.content_length ? this.formatBytes(url.content_length) : 'Unknown';
            const statusBadge = this.getStatusBadge(url.status_code);
            
            html += `
                <tr>
                    <td>
                        <a href="${url.url}" target="_blank" class="text-decoration-none">
                            ${this.truncateText(url.url, 50)}
                        </a>
                    </td>
                    <td>${this.truncateText(url.title || 'No title', 30)}</td>
                    <td>${statusBadge}</td>
                    <td>${sizeFormatted}</td>
                    <td><span class="badge bg-secondary badge-file-type">${url.content_type || 'Unknown'}</span></td>
                    <td><span class="badge bg-primary">${url.depth}</span></td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        return html;
    }

    renderMetadataResults(results) {
        console.log('Metadata results:', results); // Debug log
        
        // Handle both direct array and results object
        const fileResults = Array.isArray(results) ? results : (results.results || []);
        
        if (!fileResults || fileResults.length === 0) {
            return '<div class="text-center text-muted py-4"><h5>No metadata extracted</h5></div>';
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5><i class="bi bi-file-text me-2"></i>Metadata Analysis Results</h5>
                <div class="text-muted">
                    Analyzed ${fileResults.length} file(s)
                </div>
            </div>
            <div class="results-list">
        `;

        fileResults.forEach((file, index) => {
            const filename = file.filename || file.basic_metadata?.filename || 'Unknown file';
            html += `
                <div class="card mb-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0"><i class="bi bi-file-earmark me-2"></i>${filename}</h6>
                        <button class="btn btn-sm btn-outline-primary" type="button" 
                                onclick="
                                    const content = this.parentElement.nextElementSibling;
                                    const isHidden = content.style.display === 'none';
                                    content.style.display = isHidden ? 'block' : 'none';
                                    this.innerHTML = isHidden ? '<i class=\\'bi bi-eye-slash\\'></i> Hide' : '<i class=\\'bi bi-eye\\'></i> Show';
                                ">
                            <i class="bi bi-eye"></i> Show
                        </button>
                    </div>
                    <div class="card-body" style="display: none;">
                        ${this.renderFileMetadata(file)}
                    </div>
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    renderFileMetadata(file) {
        console.log('Rendering metadata for file:', file); // Debug log
        
        let html = '<div class="row">';
        
        // Basic metadata
        if (file.basic_metadata && !file.basic_metadata.error) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-info-circle me-2"></i>Basic Information</h6>
                    <table class="table table-sm table-borderless">
                        <tr><td><strong>File Path:</strong></td><td>${file.basic_metadata.file_path || 'Unknown'}</td></tr>
                        <tr><td><strong>Size:</strong></td><td>${file.basic_metadata.file_size_human || 'Unknown'}</td></tr>
                        <tr><td><strong>MIME Type:</strong></td><td>${file.basic_metadata.mime_type || 'Unknown'}</td></tr>
                        <tr><td><strong>Extension:</strong></td><td>${file.basic_metadata.extension || 'None'}</td></tr>
                        <tr><td><strong>Created:</strong></td><td>${file.basic_metadata.created ? new Date(file.basic_metadata.created).toLocaleString() : 'Unknown'}</td></tr>
                        <tr><td><strong>Modified:</strong></td><td>${file.basic_metadata.modified ? new Date(file.basic_metadata.modified).toLocaleString() : 'Unknown'}</td></tr>
                        <tr><td><strong>Permissions:</strong></td><td>${file.basic_metadata.permissions || 'Unknown'}</td></tr>
                    </table>
                </div>
            `;
        } else if (file.basic_metadata?.error) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-exclamation-triangle me-2"></i>Basic Information</h6>
                    <div class="alert alert-warning">${file.basic_metadata.error}</div>
                </div>
            `;
        }

        // Hashes
        if (file.hashes && !file.hashes.error) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-shield-check me-2"></i>File Hashes</h6>
                    <table class="table table-sm table-borderless">
                        ${file.hashes.MD5 ? `<tr><td><strong>MD5:</strong></td><td><code class="small">${file.hashes.MD5}</code></td></tr>` : ''}
                        ${file.hashes.SHA1 ? `<tr><td><strong>SHA1:</strong></td><td><code class="small">${file.hashes.SHA1}</code></td></tr>` : ''}
                        ${file.hashes.SHA256 ? `<tr><td><strong>SHA256:</strong></td><td><code class="small">${file.hashes.SHA256}</code></td></tr>` : ''}
                    </table>
                </div>
            `;
        } else if (file.hashes?.error) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-exclamation-triangle me-2"></i>File Hashes</h6>
                    <div class="alert alert-warning">${file.hashes.error}</div>
                </div>
            `;
        }

        html += '</div>';

        // Show errors if present
        if (file.error) {
            html += `
                <div class="mt-3">
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        <strong>Analysis Error:</strong> ${file.error}
                    </div>
                </div>
            `;
        }

        // Document metadata
        if (file.document_metadata && !file.document_metadata.error) {
            html += `
                <div class="mt-3">
                    <h6><i class="bi bi-file-text me-2"></i>Document Information</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <table class="table table-sm table-borderless">
                                <tr><td><strong>Document Type:</strong></td><td>${file.document_metadata.document_type || 'Unknown'}</td></tr>
                                <tr><td><strong>Has Text Content:</strong></td><td>${file.document_metadata.estimated_text_content ? 'Yes' : 'No'}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }

        // Deep analysis
        if (file.deep_analysis && !file.deep_analysis.error) {
            html += `
                <div class="mt-3">
                    <h6><i class="bi bi-graph-up me-2"></i>Deep Analysis</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <table class="table table-sm table-borderless">
                                <tr><td><strong>Entropy:</strong></td><td>${file.deep_analysis.entropy ? file.deep_analysis.entropy.toFixed(4) : 'N/A'}</td></tr>
                                <tr><td><strong>Unique Bytes:</strong></td><td>${file.deep_analysis.unique_bytes || 'N/A'}</td></tr>
                                <tr><td><strong>Analysis Depth:</strong></td><td>${file.deep_analysis.analysis_depth || 'N/A'}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }

        // Image metadata
        if (file.image_metadata && !file.image_metadata.error) {
            html += `
                <div class="mt-3">
                    <h6>Image Information</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr><td><strong>Dimensions:</strong></td><td>${file.image_metadata.width} × ${file.image_metadata.height}</td></tr>
                                <tr><td><strong>Format:</strong></td><td>${file.image_metadata.format}</td></tr>
                                <tr><td><strong>Mode:</strong></td><td>${file.image_metadata.mode}</td></tr>
                                <tr><td><strong>Transparency:</strong></td><td>${file.image_metadata.has_transparency ? 'Yes' : 'No'}</td></tr>
                            </table>
                        </div>
                        ${file.image_metadata.exif && Object.keys(file.image_metadata.exif).length > 0 ? `
                            <div class="col-md-6">
                                <h6>EXIF Data</h6>
                                <div class="metadata-details small">
                                    ${Object.entries(file.image_metadata.exif).map(([key, value]) => 
                                        `<div><strong>${key}:</strong> ${value}</div>`
                                    ).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }

        return html;
    }

    renderDownloadResults(results) {
        if (!results.results || results.results.length === 0) {
            return '<div class="text-center text-muted py-4"><h5>No files downloaded</h5></div>';
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5><i class="bi bi-download me-2"></i>Download Results</h5>
                <div class="text-muted">
                    ${results.successful_downloads}/${results.total_urls} successful 
                    (${results.success_rate.toFixed(1)}%)
                </div>
            </div>
            
            <div class="mb-3">
                <div class="row">
                    <div class="col-md-3">
                        <div class="card bg-success text-white">
                            <div class="card-body text-center">
                                <h5>${results.successful_downloads}</h5>
                                <small>Successful</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-danger text-white">
                            <div class="card-body text-center">
                                <h5>${results.failed_downloads}</h5>
                                <small>Failed</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-info text-white">
                            <div class="card-body text-center">
                                <h5>${results.total_size_human}</h5>
                                <small>Total Size</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-secondary text-white">
                            <div class="card-body text-center">
                                <h5>${results.duration}</h5>
                                <small>Duration</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="table-responsive">
                <table class="table table-sm table-hover results-table">
                    <thead class="table-light">
                        <tr>
                            <th>URL</th>
                            <th>Filename</th>
                            <th>Status</th>
                            <th>Size</th>
                            <th>Type</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        results.results.forEach(result => {
            const statusBadge = result.status === 'success' 
                ? '<span class="badge bg-success">Success</span>'
                : '<span class="badge bg-danger">Failed</span>';
            
            const size = result.file_size_human || 'Unknown';
            const type = result.content_type || 'Unknown';
            
            html += `
                <tr>
                    <td>
                        <a href="${result.url}" target="_blank" class="text-decoration-none">
                            ${this.truncateText(result.url, 50)}
                        </a>
                    </td>
                    <td>${result.filename || 'N/A'}</td>
                    <td>${statusBadge}</td>
                    <td>${size}</td>
                    <td><span class="badge bg-secondary badge-file-type">${type}</span></td>
                </tr>
            `;

            if (result.error) {
                html += `
                    <tr class="table-danger">
                        <td colspan="5">
                            <small><i class="bi bi-exclamation-triangle me-1"></i>${result.error}</small>
                        </td>
                    </tr>
                `;
            }
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        return html;
    }

    renderBruteForceResults(results) {
        if (!results.success) {
            return `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong>Fuzzing Failed:</strong> ${results.error}
                    ${results.simulated ? '<br><small>Note: FFUF not available on system - showing simulated results</small>' : ''}
                </div>
            `;
        }

        if (!results.results || results.results.length === 0) {
            return `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
                    <h5 class="mt-3">No URLs Found</h5>
                    <p>The fuzzer didn't discover any URLs matching the specified criteria</p>
                    ${results.note ? `<small class="text-info">${results.note}</small>` : ''}
                </div>
            `;
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5><i class="bi bi-lightning me-2"></i>Fuzzing Results</h5>
                <div class="text-muted">
                    Found ${results.total_found} URLs
                    ${results.simulated ? '<span class="badge bg-warning ms-2">Simulated</span>' : ''}
                </div>
            </div>

            ${results.note ? `<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>${results.note}</div>` : ''}
            
            <div class="table-responsive">
                    <table class="table table-sm table-hover results-table">
                    <thead class="table-light">
                        <tr>
                            <th>URL</th>
                            <th>Status</th>
                            <th>Length</th>
                            <th>Words</th>
                            <th>Lines</th>
                            <th>Content Type</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        results.results.forEach(result => {
            const statusBadge = this.getStatusBadge(result.status);
            
            html += `
                <tr>
                    <td>
                        <a href="${result.url}" target="_blank" class="text-decoration-none">
                            ${this.truncateText(result.url, 60)}
                        </a>
                    </td>
                    <td>${statusBadge}</td>
                    <td>${result.length || '-'}</td>
                    <td>${result.words || '-'}</td>
                    <td>${result.lines || '-'}</td>
                    <td>
                        <span class="badge bg-secondary badge-file-type">
                            ${result.content_type || 'Unknown'}
                        </span>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        return html;
    }

    renderWordlistResults(results) {
        if (!results.success) {
            return `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong>Download Failed:</strong> ${results.error}
                </div>
            `;
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5><i class="bi bi-download me-2"></i>Wordlist Download Results</h5>
                <div class="text-success">
                    <i class="bi bi-check-circle me-1"></i>Download Complete
                </div>
            </div>
            
            <div class="mb-3">
                <div class="row">
                    <div class="col-md-6">
                        <div class="card bg-success text-white">
                            <div class="card-body text-center">
                                <h5>${results.wordlists_found || 0}</h5>
                                <small>Wordlists Found</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card bg-info text-white">
                            <div class="card-body text-center">
                                <h5>SecLists</h5>
                                <small>Collection Downloaded</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="mb-3">
                <strong>Download Path:</strong>
                <code>${results.download_path}</code>
            </div>
        `;

        if (results.common_wordlists && results.common_wordlists.length > 0) {
            html += `
                <h6><i class="bi bi-list-ul me-2"></i>Popular Wordlists</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead class="table-light">
                            <tr>
                                <th>Name</th>
                                <th>Category</th>
                                <th>Size</th>
                                <th>Path</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            results.common_wordlists.forEach(wordlist => {
                html += `
                    <tr>
                        <td><strong>${wordlist.name}</strong></td>
                        <td><span class="badge bg-primary">${wordlist.category}</span></td>
                        <td>${this.formatBytes(wordlist.size)}</td>
                        <td><code class="small">${wordlist.path}</code></td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;
        }

        if (results.progress_log && results.progress_log.length > 0) {
            html += `
                <div class="mt-3">
                    <h6><i class="bi bi-clock-history me-2"></i>Download Log</h6>
                    <div class="terminal-output" style="max-height: 200px; overflow-y: auto;">
            `;

            results.progress_log.forEach(message => {
                html += `<div>${message}</div>`;
            });

            html += `
                    </div>
                </div>
            `;
        }

        return html;
    }

    async loadOperations() {
        try {
            const response = await fetch('/metaspidey/operations');
            const result = await response.json();

            if (result.operations) {
                this.renderOperationsList(result.operations);
                document.getElementById('operations-last-updated').textContent = 
                    `Last updated: ${new Date().toLocaleTimeString()}`;
            }
        } catch (error) {
            console.error('Error loading operations:', error);
        }
    }

    renderOperationsList(operations) {
        const container = document.getElementById('operations-list');
        
        if (operations.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-list-task" style="font-size: 3rem;"></i>
                    <h4 class="mt-3">No Operations Yet</h4>
                    <p>Your completed operations will appear here</p>
                </div>
            `;
            return;
        }

        let html = '<div class="list-group">';
        
        operations.forEach(op => {
            const statusBadge = this.getOperationStatusBadge(op.status);
            const icon = this.getOperationIcon(op.type);
            const time = op.started || op.timestamp;
            
            html += `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <div>
                        <div class="d-flex align-items-center">
                            <i class="bi ${icon} me-2"></i>
                            <strong>${this.capitalizeFirst(op.type)}</strong>
                            ${statusBadge}
                        </div>
                        <small class="text-muted">
                            ${time ? new Date(time).toLocaleString() : 'Unknown time'}
                        </small>
                    </div>
                    <div>
                        ${op.status === 'completed' || op.status === 'error' ? `
                            <button class="btn btn-sm btn-outline-primary" 
                                    onclick="viewOperationResults('${op.id}')">
                                <i class="bi bi-eye"></i> View
                            </button>
                        ` : `
                            <div class="spinner-border spinner-border-sm" role="status"></div>
                        `}
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    }

    showOperationStatus(type, message) {
        const statusEl = document.getElementById(`${type}-status`);
        const textEl = document.getElementById(`${type}-status-text`);
        
        if (statusEl && textEl) {
            textEl.textContent = message;
            statusEl.classList.add('active');
        }
    }

    hideOperationStatus(type) {
        const statusEl = document.getElementById(`${type}-status`);
        if (statusEl) {
            statusEl.classList.remove('active');
        }
    }

    updateOperationProgress(type, operation) {
        const statusEl = document.getElementById(`${type}-status`);
        const textEl = document.getElementById(`${type}-status-text`);
        
        if (textEl) {
            let message = `${this.capitalizeFirst(type)} in progress...`;
            
            if (operation.urls_count) {
                message = `Processing ${operation.urls_count} URL(s)...`;
            } else if (operation.files_count) {
                message = `Analyzing ${operation.files_count} file(s)...`;
            }
            
            textEl.textContent = message;
        }
    }

    showNotification(message, type = 'info') {
        // Use the global CoreSecFrame notification system if available
        if (window.CoreSecFrame && window.CoreSecFrame.showNotification) {
            window.CoreSecFrame.showNotification(message, type);
        } else {
            // Fallback to console
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }

    displayFormErrors(errors) {
        if (!errors) return;
        
        // Display form validation errors
        Object.entries(errors).forEach(([field, fieldErrors]) => {
            const input = document.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                
                // Create or update error message
                let errorDiv = input.parentNode.querySelector('.invalid-feedback');
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.className = 'invalid-feedback';
                    input.parentNode.appendChild(errorDiv);
                }
                errorDiv.textContent = fieldErrors.join(', ');
            }
        });
    }

    // Utility functions
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    getStatusBadge(statusCode) {
        if (statusCode >= 200 && statusCode < 300) {
            return `<span class="badge bg-success">${statusCode}</span>`;
        } else if (statusCode >= 300 && statusCode < 400) {
            return `<span class="badge bg-warning">${statusCode}</span>`;
        } else if (statusCode >= 400) {
            return `<span class="badge bg-danger">${statusCode}</span>`;
        }
        return `<span class="badge bg-secondary">${statusCode || 'Unknown'}</span>`;
    }

    getOperationStatusBadge(status) {
        const badges = {
            'running': '<span class="badge bg-primary ms-2">Running</span>',
            'completed': '<span class="badge bg-success ms-2">Completed</span>',
            'error': '<span class="badge bg-danger ms-2">Error</span>'
        };
        return badges[status] || '<span class="badge bg-secondary ms-2">Unknown</span>';
    }

    getOperationIcon(type) {
        const icons = {
            'crawl': 'bi-globe',
            'metadata': 'bi-file-text',
            'download': 'bi-download',
            'bruteforce': 'bi-lightning',
            'wordlist_download': 'bi-collection'
        };
        return icons[type] || 'bi-gear';
    }

    capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
}

// Global functions for template callbacks
window.refreshOperations = function() {
    if (window.metaspidey) {
        window.metaspidey.loadOperations();
    }
};

window.viewOperationResults = async function(operationId) {
    try {
        const response = await fetch(`/metaspidey/results/${operationId}`);
        const result = await response.json();

        if (result.success) {
            document.getElementById('modal-results-content').innerHTML = 
                '<pre class="bg-light p-3 rounded">' + JSON.stringify(result.results, null, 2) + '</pre>';
            
            const modal = new bootstrap.Modal(document.getElementById('resultsModal'));
            modal.show();
        } else {
            window.metaspidey.showNotification('Failed to load results: ' + result.error, 'error');
        }
    } catch (error) {
        window.metaspidey.showNotification('Error loading results: ' + error.message, 'error');
    }
};

window.exportResults = function() {
    const content = document.getElementById('modal-results-content').textContent;
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'metaspidey-results-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MetaSpidey;
}