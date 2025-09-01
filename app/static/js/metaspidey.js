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
        
        // Get the selected mode
        const mode = form.querySelector('[name="mode"]').value;
        
        // Mode-specific validation
        let urls = [];
        if (mode === 'manual') {
            // Manual mode - check if URLs are provided
            const urlsTextarea = form.querySelector('[name="urls"]');
            const urlFile = form.querySelector('[name="url_file"]');
            urls = urlsTextarea.value.trim().split('\n').filter(url => url.trim());
            
            if (!urls.length && !urlFile.files.length) {
                this.showNotification('Please enter URLs or upload a file containing URLs', 'warning');
                return;
            }
        } else if (mode === 'crawler') {
            // Crawler mode - check if start URL is provided
            const startUrl = form.querySelector('[name="start_url"]').value.trim();
            
            if (!startUrl) {
                this.showNotification('Please enter a website URL to crawl', 'warning');
                return;
            }
        }

        try {
            const statusMessage = mode === 'crawler' 
                ? 'Starting file discovery and download...' 
                : `Starting download of ${urls.length} file(s)...`;
            this.showOperationStatus('download', statusMessage);
            
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
                    
                    // For brute force and crawler download operations, get real-time results
                    if (type === 'bruteforce' || (type === 'download' && result.operation.mode === 'crawler')) {
                        await this.updateRealtimeResults(operationId);
                    }
                    
                    // Continue polling
                    setTimeout(pollOperation, this.pollInterval);
                } else if (result.status === 'completed') {
                    // Operation finished, get results
                    this.activeOperations.delete(operationId);
                    this.hideOperationStatus(type);
                    
                    // Get final real-time results for brute force and crawler download
                    if (type === 'bruteforce' || (type === 'download' && result.operation?.mode === 'crawler')) {
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
                // Determine if this is bruteforce or crawler download results
                const isCrawlerDownload = result.results.some(r => r.type === 'file_discovered' || r.type === 'page_crawled');
                
                if (isCrawlerDownload) {
                    // Handle crawler download real-time updates
                    this.updateCrawlerDownloadProgress(result.results);
                } else {
                    // Handle brute force results (existing functionality)
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
            }
        } catch (error) {
            console.error('Error updating real-time results:', error);
        }
    }

    updateCrawlerDownloadProgress(results) {
        // Update download status text with crawling progress
        const statusText = document.getElementById('download-status-text');
        
        // Get latest progress info
        const latestUpdate = results[results.length - 1];
        const filesDiscovered = results.filter(r => r.type === 'file_discovered').length;
        const pagesProcessed = latestUpdate.pages_crawled || 0;
        
        if (statusText) {
            let message = '';
            if (latestUpdate.type === 'crawl_completed') {
                message = `Crawling completed. Found ${latestUpdate.total_files} files. Starting downloads...`;
            } else if (latestUpdate.type === 'file_discovered') {
                message = `Discovering files... Found ${filesDiscovered} files from ${pagesProcessed} pages`;
            } else if (latestUpdate.type === 'page_crawled') {
                message = `Crawling pages... ${pagesProcessed} processed, ${filesDiscovered} files found`;
            } else {
                message = `Processing... ${filesDiscovered} files discovered`;
            }
            
            statusText.textContent = message;
        }
        
        // Show discovered files in a simple list (reuse bruteforce terminal area)
        const terminal = document.getElementById('found-urls-terminal');
        const counter = document.getElementById('found-urls-count');
        
        if (terminal && counter) {
            // Show the terminal section for crawler downloads
            const section = document.getElementById('found-urls-section');
            if (section) section.style.display = 'block';
            
            // Update counter
            counter.textContent = filesDiscovered;
            
            // Show discovered files
            const discoveredFiles = results.filter(r => r.type === 'file_discovered');
            
            // Clear and rebuild
            terminal.innerHTML = '';
            
            discoveredFiles.forEach((update, index) => {
                const file = update.file;
                const fileRow = document.createElement('div');
                fileRow.className = 'url-found mb-1';
                fileRow.innerHTML = `
                    <span class="badge bg-info me-2">${file.estimated_type || 'File'}</span>
                    <span class="text-muted me-2">[${file.extension || 'unknown'}]</span>
                    <span class="text-break" title="${file.url}">${file.filename}</span>
                `;
                terminal.appendChild(fileRow);
            });
            
            terminal.scrollTop = terminal.scrollHeight; // Auto-scroll to bottom
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
                this.initializeMetadataToggles();
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
        console.log('Enhanced metadata results:', results); // Debug log
        
        // Handle both direct array and results object
        const fileResults = Array.isArray(results) ? results : (results.results || []);
        const isDirectoryAnalysis = results.analysis_type === 'directory';
        const isBatchAnalysis = results.analysis_type === 'batch';
        
        if (!fileResults || fileResults.length === 0) {
            return '<div class="text-center text-muted py-4"><h5>No metadata extracted</h5></div>';
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5><i class="bi bi-file-text me-2"></i>Advanced Metadata Analysis Results</h5>
                <div class="text-muted">
                    ${fileResults.length} file(s) analyzed
                    ${isDirectoryAnalysis ? ` • Directory: ${results.directory_path}` : ''}
                    ${results.analysis_version ? ` • v${results.analysis_version}` : ''}
                </div>
            </div>
        `;
        
        // Summary statistics for batch/directory analysis
        if (results.summary) {
            html += this.renderAnalysisSummary(results.summary);
        }
        
        html += '<div class="results-list">';

        fileResults.forEach((file, index) => {
            const filename = file.filename || file.basic_info?.filename || 'Unknown file';
            const category = file.categorization?.primary_category || 'Unknown';
            const riskLevel = file.categorization?.risk_level || 'low';
            const isSuspicious = file.categorization?.is_suspicious || false;
            
            // Risk level badge
            const riskBadge = this.getRiskBadge(riskLevel, isSuspicious);
            const categoryIcon = this.getCategoryIcon(category);
            
            html += `
                <div class="card mb-3 ${isSuspicious ? 'border-warning' : ''}">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-${categoryIcon} me-2"></i>
                            <h6 class="mb-0">${filename}</h6>
                            <span class="ms-2 badge bg-secondary">${category}</span>
                            ${riskBadge}
                        </div>
                        <button class="btn btn-sm btn-outline-primary metadata-toggle" type="button" 
                                data-target="metadata-${index}">
                            <i class="bi bi-eye"></i> Show Details
                        </button>
                    </div>
                    <div class="card-body collapse" id="metadata-${index}">
                        ${this.renderFileMetadata(file)}
                    </div>
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    renderFileMetadata(file) {
        console.log('Rendering enhanced metadata for file:', file); // Debug log
        
        // Handle errors first
        if (file.error) {
            return `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong>Analysis Error:</strong> ${file.error}
                </div>
            `;
        }
        
        let html = '<div class="metadata-container">';
        
        // Navigation tabs
        html += this.renderMetadataTabs(file);
        
        // Tab content
        html += '<div class="tab-content mt-3">';
        
        // Overview Tab
        html += '<div class="tab-pane fade show active" id="overview">';
        html += this.renderOverviewTab(file);
        html += '</div>';
        
        // Security Tab
        html += '<div class="tab-pane fade" id="security">';
        html += this.renderSecurityTab(file);
        html += '</div>';
        
        // Technical Tab
        html += '<div class="tab-pane fade" id="technical">';
        html += this.renderTechnicalTab(file);
        html += '</div>';
        
        // Type-specific Tab
        const category = file.categorization?.primary_category || 'Unknown';
        if (category !== 'Unknown' && category !== 'Other') {
            html += '<div class="tab-pane fade" id="type-specific">';
            html += this.renderTypeSpecificTab(file, category);
            html += '</div>';
        }
        
        html += '</div>'; // Close tab-content
        html += '</div>'; // Close metadata-container
        
        return html;
    }

    // Enhanced metadata rendering methods
    renderMetadataTabs(file) {
        const category = file.categorization?.primary_category || 'Unknown';
        const hasTypeSpecific = category !== 'Unknown' && category !== 'Other';
        
        return `
            <ul class="nav nav-tabs" id="metadata-tabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button" role="tab">
                        <i class="bi bi-house"></i> Overview
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="security-tab" data-bs-toggle="tab" data-bs-target="#security" type="button" role="tab">
                        <i class="bi bi-shield-check"></i> Security
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="technical-tab" data-bs-toggle="tab" data-bs-target="#technical" type="button" role="tab">
                        <i class="bi bi-gear"></i> Technical
                    </button>
                </li>
                ${hasTypeSpecific ? `
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="type-specific-tab" data-bs-toggle="tab" data-bs-target="#type-specific" type="button" role="tab">
                            <i class="bi bi-${this.getCategoryIcon(category)}"></i> ${category}
                        </button>
                    </li>
                ` : ''}
            </ul>
        `;
    }

    renderOverviewTab(file) {
        const basic = file.basic_info || {};
        const category = file.categorization || {};
        
        return `
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="bi bi-info-circle me-2"></i>File Information</h6>
                    <table class="table table-sm table-borderless">
                        <tr><td><strong>Filename:</strong></td><td>${basic.filename || 'Unknown'}</td></tr>
                        <tr><td><strong>Size:</strong></td><td>${basic.file_size_human || 'Unknown'}</td></tr>
                        <tr><td><strong>Type:</strong></td><td>${basic.mime_type || 'Unknown'}</td></tr>
                        <tr><td><strong>Extension:</strong></td><td>${basic.extension || 'None'}</td></tr>
                        <tr><td><strong>Category:</strong></td><td>
                            <span class="badge bg-secondary">${category.primary_category || 'Unknown'}</span>
                        </td></tr>
                        <tr><td><strong>Classification:</strong></td><td>${category.file_class || 'Unknown'}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6><i class="bi bi-clock me-2"></i>Timestamps</h6>
                    <table class="table table-sm table-borderless">
                        <tr><td><strong>Created:</strong></td><td>${basic.created ? new Date(basic.created).toLocaleString() : 'Unknown'}</td></tr>
                        <tr><td><strong>Modified:</strong></td><td>${basic.modified ? new Date(basic.modified).toLocaleString() : 'Unknown'}</td></tr>
                        <tr><td><strong>Accessed:</strong></td><td>${basic.accessed ? new Date(basic.accessed).toLocaleString() : 'Unknown'}</td></tr>
                        <tr><td><strong>Permissions:</strong></td><td>${basic.permissions || 'Unknown'}</td></tr>
                        <tr><td><strong>Hidden:</strong></td><td>${basic.is_hidden ? 'Yes' : 'No'}</td></tr>
                        <tr><td><strong>Executable:</strong></td><td>${basic.is_executable ? 'Yes' : 'No'}</td></tr>
                    </table>
                </div>
            </div>
        `;
    }

    renderSecurityTab(file) {
        const security = file.security_analysis || {};
        const signature = file.signature_analysis || {};
        const hashes = file.hashes || {};
        
        let html = '<div class="row">';
        
        // Risk Assessment
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-shield-exclamation me-2"></i>Risk Assessment</h6>
                <div class="mb-3">
                    ${this.getRiskBadge(security.risk_level, file.categorization?.is_suspicious)}
                </div>
                ${security.threat_indicators_found?.length > 0 ? `
                    <div class="alert alert-warning">
                        <strong>Threat Indicators Found:</strong>
                        <ul class="mb-0 mt-2">
                            ${security.threat_indicators_found.map(indicator => `<li><code>${indicator}</code></li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${security.suspicious_patterns?.length > 0 ? `
                    <div class="alert alert-info">
                        <strong>Suspicious Patterns:</strong>
                        <ul class="mb-0 mt-2">
                            ${security.suspicious_patterns.map(pattern => `<li>${pattern}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${security.security_notes?.length > 0 ? `
                    <div class="small text-muted">
                        <strong>Notes:</strong>
                        <ul class="mb-0">
                            ${security.security_notes.map(note => `<li>${note}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
        
        // File Signature Analysis
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-file-binary me-2"></i>File Signature</h6>
                <table class="table table-sm table-borderless">
                    <tr><td><strong>Header (hex):</strong></td><td><code class="small">${signature.file_header ? signature.file_header.substring(0, 32) + '...' : 'N/A'}</code></td></tr>
                    <tr><td><strong>Detected Type:</strong></td><td>${signature.detected_types?.join(', ') || 'Unknown'}</td></tr>
                    <tr><td><strong>Extension Suggests:</strong></td><td>${signature.extension_suggests || 'Unknown'}</td></tr>
                    <tr><td><strong>Signature Match:</strong></td><td>
                        ${signature.signature_mismatch ? 
                            '<span class="badge bg-warning">Mismatch</span>' : 
                            '<span class="badge bg-success">Match</span>'
                        }
                    </td></tr>
                </table>
            </div>
        `;
        
        html += '</div>';
        
        // File Hashes
        if (hashes && !hashes.error) {
            html += `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="bi bi-fingerprint me-2"></i>Cryptographic Hashes</h6>
                        <div class="table-responsive">
                            <table class="table table-sm">
                                ${hashes.MD5 ? `<tr><td><strong>MD5:</strong></td><td><code class="user-select-all">${hashes.MD5}</code></td></tr>` : ''}
                                ${hashes.SHA1 ? `<tr><td><strong>SHA1:</strong></td><td><code class="user-select-all">${hashes.SHA1}</code></td></tr>` : ''}
                                ${hashes.SHA256 ? `<tr><td><strong>SHA256:</strong></td><td><code class="user-select-all">${hashes.SHA256}</code></td></tr>` : ''}
                                ${hashes.SHA512 ? `<tr><td><strong>SHA512:</strong></td><td><code class="user-select-all">${hashes.SHA512}</code></td></tr>` : ''}
                            </table>
                        </div>
                        ${hashes.hash_generated_at ? `<small class="text-muted">Generated: ${new Date(hashes.hash_generated_at).toLocaleString()}</small>` : ''}
                    </div>
                </div>
            `;
        }
        
        return html;
    }

    renderTechnicalTab(file) {
        const deep = file.deep_analysis || {};
        const signature = file.signature_analysis || {};
        const basic = file.basic_info || {};
        
        let html = '<div class="row">';
        
        // Entropy Analysis
        if (deep.entropy !== undefined) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-graph-up me-2"></i>Entropy Analysis</h6>
                    <table class="table table-sm table-borderless">
                        <tr><td><strong>Shannon Entropy:</strong></td><td>${deep.entropy}</td></tr>
                        <tr><td><strong>Interpretation:</strong></td><td>${deep.entropy_analysis || 'N/A'}</td></tr>
                    </table>
                    ${deep.byte_distribution ? `
                        <h6 class="mt-3">Byte Distribution</h6>
                        <table class="table table-sm table-borderless">
                            <tr><td><strong>Unique Bytes:</strong></td><td>${deep.byte_distribution.unique_bytes}/256</td></tr>
                            <tr><td><strong>Null Bytes:</strong></td><td>${deep.byte_distribution.null_byte_percentage}%</td></tr>
                            <tr><td><strong>Printable:</strong></td><td>${deep.byte_distribution.printable_percentage}%</td></tr>
                        </table>
                    ` : ''}
                </div>
            `;
        }
        
        // File Structure
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-diagram-3 me-2"></i>File Structure</h6>
                <table class="table table-sm table-borderless">
                    <tr><td><strong>File Size:</strong></td><td>${basic.file_size_human || 'Unknown'} (${basic.file_size || 0} bytes)</td></tr>
                    <tr><td><strong>Inode:</strong></td><td>${basic.inode || 'N/A'}</td></tr>
                    <tr><td><strong>Owner UID:</strong></td><td>${basic.owner_uid || 'N/A'}</td></tr>
                    <tr><td><strong>Group GID:</strong></td><td>${basic.group_gid || 'N/A'}</td></tr>
                </table>
                ${signature.header_analysis ? `
                    <h6 class="mt-3">Header Analysis</h6>
                    <table class="table table-sm table-borderless">
                        <tr><td><strong>Printable Chars:</strong></td><td>${signature.header_analysis.printable_chars || 0}</td></tr>
                        <tr><td><strong>Null Bytes:</strong></td><td>${signature.header_analysis.null_bytes || 0}</td></tr>
                        <tr><td><strong>High Entropy:</strong></td><td>${signature.header_analysis.high_entropy_bytes || 0}</td></tr>
                        <tr><td><strong>Header Entropy:</strong></td><td>${signature.header_analysis.header_entropy || 0}</td></tr>
                    </table>
                ` : ''}
            </div>
        `;
        
        html += '</div>';
        
        // Pattern Analysis
        if (deep.pattern_analysis) {
            const patterns = deep.pattern_analysis;
            html += `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="bi bi-pattern me-2"></i>Pattern Analysis</h6>
                        <div class="row">
                            ${patterns.repeated_sequences?.length > 0 ? `
                                <div class="col-md-4">
                                    <strong>Repeated Sequences:</strong>
                                    <ul class="small">
                                        ${patterns.repeated_sequences.slice(0, 3).map(seq => 
                                            `<li>${seq.sequence.substring(0, 16)}... (${seq.count}x, ${seq.length} bytes)</li>`
                                        ).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                            ${patterns.url_patterns?.length > 0 ? `
                                <div class="col-md-4">
                                    <strong>URLs Found:</strong>
                                    <ul class="small">
                                        ${patterns.url_patterns.slice(0, 3).map(url => 
                                            `<li>${this.truncateText(url, 30)}</li>`
                                        ).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                            ${patterns.interesting_strings?.length > 0 ? `
                                <div class="col-md-4">
                                    <strong>Interesting Strings:</strong>
                                    <ul class="small">
                                        ${patterns.interesting_strings.slice(0, 3).map(str => 
                                            `<li>${this.truncateText(str, 30)}</li>`
                                        ).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }
        
        return html;
    }

    renderTypeSpecificTab(file, category) {
        switch (category) {
            case 'Image':
                return this.renderImageMetadata(file);
            case 'Document':
                return this.renderDocumentMetadata(file);
            case 'Media':
                return this.renderMediaMetadata(file);
            case 'Archive':
                return this.renderArchiveMetadata(file);
            default:
                return '<div class="text-muted">No specific metadata available for this file type.</div>';
        }
    }

    renderImageMetadata(file) {
        const image = file.image_metadata || {};
        
        if (image.error) {
            return `<div class="alert alert-warning">${image.error}</div>`;
        }
        
        let html = '<div class="row">';
        
        // Basic Image Info
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-image me-2"></i>Image Properties</h6>
                <table class="table table-sm table-borderless">
                    <tr><td><strong>Format:</strong></td><td>${image.format || 'Unknown'}</td></tr>
                    <tr><td><strong>Dimensions:</strong></td><td>${image.width || 0} × ${image.height || 0} pixels</td></tr>
                    <tr><td><strong>Color Mode:</strong></td><td>${image.mode || 'Unknown'}</td></tr>
                    <tr><td><strong>Color Description:</strong></td><td class="small">${image.color_mode || 'N/A'}</td></tr>
                    <tr><td><strong>Transparency:</strong></td><td>${image.has_transparency ? 'Yes' : 'No'}</td></tr>
                    ${image.estimated_colors ? `<tr><td><strong>Est. Colors:</strong></td><td>${image.estimated_colors}</td></tr>` : ''}
                    ${image.estimated_quality ? `<tr><td><strong>Quality Est.:</strong></td><td>${image.estimated_quality}</td></tr>` : ''}
                </table>
            </div>
        `;
        
        // Camera/EXIF Info
        if (image.camera_info) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-camera me-2"></i>Camera Information</h6>
                    <table class="table table-sm table-borderless">
                        ${image.camera_info.camera_make ? `<tr><td><strong>Make:</strong></td><td>${image.camera_info.camera_make}</td></tr>` : ''}
                        ${image.camera_info.camera_model ? `<tr><td><strong>Model:</strong></td><td>${image.camera_info.camera_model}</td></tr>` : ''}
                        ${image.camera_info.software ? `<tr><td><strong>Software:</strong></td><td>${image.camera_info.software}</td></tr>` : ''}
                        ${image.camera_info.date_taken ? `<tr><td><strong>Date Taken:</strong></td><td>${image.camera_info.date_taken}</td></tr>` : ''}
                        ${image.camera_info.exposure_time ? `<tr><td><strong>Exposure:</strong></td><td>${image.camera_info.exposure_time}</td></tr>` : ''}
                        ${image.camera_info.aperture ? `<tr><td><strong>Aperture:</strong></td><td>f/${image.camera_info.aperture}</td></tr>` : ''}
                        ${image.camera_info.iso ? `<tr><td><strong>ISO:</strong></td><td>${image.camera_info.iso}</td></tr>` : ''}
                    </table>
                </div>
            `;
        }
        
        html += '</div>';
        
        // Location Info
        if (image.location_info) {
            html += `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="bi bi-geo-alt me-2"></i>Location Information</h6>
                        <table class="table table-sm table-borderless">
                            ${image.location_info.latitude ? `<tr><td><strong>Latitude:</strong></td><td>${image.location_info.latitude}</td></tr>` : ''}
                            ${image.location_info.longitude ? `<tr><td><strong>Longitude:</strong></td><td>${image.location_info.longitude}</td></tr>` : ''}
                            ${image.location_info.altitude ? `<tr><td><strong>Altitude:</strong></td><td>${image.location_info.altitude}</td></tr>` : ''}
                        </table>
                    </div>
                </div>
            `;
        }
        
        return html;
    }

    renderDocumentMetadata(file) {
        const doc = file.document_metadata || {};
        
        if (doc.error) {
            return `<div class="alert alert-warning">${doc.error}</div>`;
        }
        
        let html = '<div class="row">';
        
        // Document Properties
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-file-text me-2"></i>Document Properties</h6>
                <table class="table table-sm table-borderless">
                    <tr><td><strong>Document Type:</strong></td><td>${doc.document_type || 'Unknown'}</td></tr>
                    ${doc.num_pages ? `<tr><td><strong>Pages:</strong></td><td>${doc.num_pages}</td></tr>` : ''}
                    ${doc.num_paragraphs ? `<tr><td><strong>Paragraphs:</strong></td><td>${doc.num_paragraphs}</td></tr>` : ''}
                    ${doc.num_worksheets ? `<tr><td><strong>Worksheets:</strong></td><td>${doc.num_worksheets}</td></tr>` : ''}
                    ${doc.word_count ? `<tr><td><strong>Word Count:</strong></td><td>${doc.word_count}</td></tr>` : ''}
                    ${doc.estimated_text_length ? `<tr><td><strong>Text Length:</strong></td><td>${doc.estimated_text_length} chars</td></tr>` : ''}
                    <tr><td><strong>Has Content:</strong></td><td>${doc.has_content || doc.has_text_content ? 'Yes' : 'No'}</td></tr>
                    ${doc.is_encrypted ? `<tr><td><strong>Encrypted:</strong></td><td>Yes</td></tr>` : ''}
                </table>
            </div>
        `;
        
        // Document Metadata/Properties
        const props = doc.core_properties || doc.properties || doc.document_info;
        if (props) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-person me-2"></i>Document Metadata</h6>
                    <table class="table table-sm table-borderless">
                        ${props.author || props.creator ? `<tr><td><strong>Author:</strong></td><td>${props.author || props.creator}</td></tr>` : ''}
                        ${props.title ? `<tr><td><strong>Title:</strong></td><td>${props.title}</td></tr>` : ''}
                        ${props.subject ? `<tr><td><strong>Subject:</strong></td><td>${props.subject}</td></tr>` : ''}
                        ${props.created ? `<tr><td><strong>Created:</strong></td><td>${new Date(props.created).toLocaleString()}</td></tr>` : ''}
                        ${props.modified ? `<tr><td><strong>Modified:</strong></td><td>${new Date(props.modified).toLocaleString()}</td></tr>` : ''}
                        ${props.last_modified_by || props.lastModifiedBy ? `<tr><td><strong>Last Modified By:</strong></td><td>${props.last_modified_by || props.lastModifiedBy}</td></tr>` : ''}
                        ${props.keywords ? `<tr><td><strong>Keywords:</strong></td><td>${props.keywords}</td></tr>` : ''}
                    </table>
                </div>
            `;
        }
        
        html += '</div>';
        
        // Preview or worksheet info
        if (doc.first_page_preview) {
            html += `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="bi bi-eye me-2"></i>Content Preview</h6>
                        <div class="border p-2 bg-light small" style="max-height: 150px; overflow-y: auto;">
                            ${doc.first_page_preview}
                        </div>
                    </div>
                </div>
            `;
        }
        
        if (doc.worksheets_info) {
            html += `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="bi bi-table me-2"></i>Worksheets</h6>
                        <div class="table-responsive">
                            <table class="table table-sm">
                                <thead><tr><th>Name</th><th>Rows</th><th>Columns</th><th>Has Data</th></tr></thead>
                                <tbody>
                                    ${doc.worksheets_info.map(sheet => `
                                        <tr>
                                            <td>${sheet.name}</td>
                                            <td>${sheet.max_row}</td>
                                            <td>${sheet.max_column}</td>
                                            <td>${sheet.has_data ? 'Yes' : 'No'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }
        
        return html;
    }

    renderMediaMetadata(file) {
        const media = file.media_metadata || {};
        
        if (media.error) {
            return `<div class="alert alert-warning">${media.error}</div>`;
        }
        
        let html = '<div class="row">';
        
        // Media Properties
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-play-circle me-2"></i>Media Properties</h6>
                <table class="table table-sm table-borderless">
                    <tr><td><strong>Media Type:</strong></td><td>${media.media_type || 'Unknown'}</td></tr>
                    <tr><td><strong>Format:</strong></td><td>${media.format || 'Unknown'}</td></tr>
                    ${media.duration_formatted ? `<tr><td><strong>Duration:</strong></td><td>${media.duration_formatted}</td></tr>` : ''}
                    ${media.bitrate ? `<tr><td><strong>Bitrate:</strong></td><td>${media.bitrate} bps</td></tr>` : ''}
                    ${media.sample_rate ? `<tr><td><strong>Sample Rate:</strong></td><td>${media.sample_rate} Hz</td></tr>` : ''}
                    ${media.channels ? `<tr><td><strong>Channels:</strong></td><td>${media.channels}</td></tr>` : ''}
                </table>
            </div>
        `;
        
        // Media Tags
        const tags = media.common_tags || {};
        if (Object.keys(tags).length > 0) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-tags me-2"></i>Media Tags</h6>
                    <table class="table table-sm table-borderless">
                        ${tags.title ? `<tr><td><strong>Title:</strong></td><td>${tags.title}</td></tr>` : ''}
                        ${tags.artist ? `<tr><td><strong>Artist:</strong></td><td>${tags.artist}</td></tr>` : ''}
                        ${tags.album ? `<tr><td><strong>Album:</strong></td><td>${tags.album}</td></tr>` : ''}
                        ${tags.date ? `<tr><td><strong>Date:</strong></td><td>${tags.date}</td></tr>` : ''}
                        ${tags.genre ? `<tr><td><strong>Genre:</strong></td><td>${tags.genre}</td></tr>` : ''}
                    </table>
                </div>
            `;
        }
        
        html += '</div>';
        
        return html;
    }

    renderArchiveMetadata(file) {
        const archive = file.archive_metadata || {};
        
        if (archive.error) {
            return `<div class="alert alert-warning">${archive.error}</div>`;
        }
        
        let html = '<div class="row">';
        
        // Archive Properties
        html += `
            <div class="col-md-6">
                <h6><i class="bi bi-archive me-2"></i>Archive Properties</h6>
                <table class="table table-sm table-borderless">
                    <tr><td><strong>Archive Type:</strong></td><td>${archive.archive_type || 'Unknown'}</td></tr>
                    ${archive.num_files ? `<tr><td><strong>Files:</strong></td><td>${archive.num_files}</td></tr>` : ''}
                    ${archive.compressed_size ? `<tr><td><strong>Compressed:</strong></td><td>${this.formatBytes(archive.compressed_size)}</td></tr>` : ''}
                    ${archive.uncompressed_size ? `<tr><td><strong>Uncompressed:</strong></td><td>${this.formatBytes(archive.uncompressed_size)}</td></tr>` : ''}
                    ${archive.compression_percentage ? `<tr><td><strong>Compression:</strong></td><td>${archive.compression_percentage}%</td></tr>` : ''}
                </table>
            </div>
        `;
        
        // File Types Distribution
        if (archive.file_types_distribution) {
            html += `
                <div class="col-md-6">
                    <h6><i class="bi bi-pie-chart me-2"></i>File Types</h6>
                    <table class="table table-sm table-borderless">
                        ${Object.entries(archive.file_types_distribution).map(([ext, count]) => 
                            `<tr><td><strong>${ext || 'no extension'}:</strong></td><td>${count} files</td></tr>`
                        ).join('')}
                    </table>
                </div>
            `;
        }
        
        html += '</div>';
        
        // File List Preview
        if (archive.file_list && archive.file_list.length > 0) {
            html += `
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="bi bi-list me-2"></i>Archive Contents (first 20 files)</h6>
                        <div class="table-responsive" style="max-height: 300px; overflow-y: auto;">
                            <table class="table table-sm">
                                <thead><tr><th>Filename</th><th>Size</th><th>Compressed</th><th>Modified</th></tr></thead>
                                <tbody>
                                    ${archive.file_list.slice(0, 20).map(file => `
                                        <tr>
                                            <td class="small">${file.filename}</td>
                                            <td>${this.formatBytes(file.size)}</td>
                                            <td>${this.formatBytes(file.compressed_size)}</td>
                                            <td class="small">${new Date(file.modified).toLocaleDateString()}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }
        
        return html;
    }

    renderAnalysisSummary(summary) {
        if (!summary) return '';
        
        return `
            <div class="card mb-3">
                <div class="card-header">
                    <h6 class="mb-0"><i class="bi bi-graph-up me-2"></i>Analysis Summary</h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-3">
                            <h6>File Categories</h6>
                            <ul class="list-unstyled">
                                ${Object.entries(summary.file_categories || {}).map(([cat, count]) => 
                                    `<li><i class="bi bi-${this.getCategoryIcon(cat)} me-1"></i>${cat}: <strong>${count}</strong></li>`
                                ).join('')}
                            </ul>
                        </div>
                        <div class="col-md-3">
                            <h6>Risk Levels</h6>
                            <ul class="list-unstyled">
                                ${Object.entries(summary.risk_levels || {}).map(([risk, count]) => 
                                    `<li>${this.getRiskBadge(risk, risk !== 'low')} <strong>${count}</strong></li>`
                                ).join('')}
                            </ul>
                        </div>
                        <div class="col-md-3">
                            <h6>Top File Types</h6>
                            <ul class="list-unstyled">
                                ${Object.entries(summary.file_types || {}).slice(0, 5).map(([ext, count]) => 
                                    `<li><code>${ext}</code>: <strong>${count}</strong></li>`
                                ).join('')}
                            </ul>
                        </div>
                        <div class="col-md-3">
                            <h6>Statistics</h6>
                            <ul class="list-unstyled">
                                <li>Total Size: <strong>${summary.total_size_human || '0 B'}</strong></li>
                                <li>Errors: <strong>${summary.error_count || 0}</strong></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Utility methods for enhanced metadata display
    getRiskBadge(riskLevel, isSuspicious) {
        const badges = {
            'low': '<span class="badge bg-success">Low Risk</span>',
            'medium': '<span class="badge bg-warning">Medium Risk</span>',
            'high': '<span class="badge bg-danger">High Risk</span>'
        };
        return badges[riskLevel] || '<span class="badge bg-secondary">Unknown</span>';
    }

    getCategoryIcon(category) {
        const icons = {
            'Image': 'image',
            'Document': 'file-text',
            'Media': 'play-circle',
            'Archive': 'archive',
            'Text': 'file-text',
            'Executable': 'cpu',
            'Other': 'file'
        };
        return icons[category] || 'file';
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    renderDownloadResults(results) {
        // Handle crawler mode results which have nested structure
        const downloadResults = results.download_results || results;
        const discoveryResults = results.discovered_files || [];
        const isCrawlerMode = Boolean(results.discovered_files || results.pages_crawled);
        
        if (!downloadResults.results || downloadResults.results.length === 0) {
            if (isCrawlerMode && discoveryResults.length > 0) {
                return `
                    <div class="text-center text-warning py-4">
                        <i class="bi bi-exclamation-triangle" style="font-size: 2rem;"></i>
                        <h5 class="mt-3">Files Found But Not Downloaded</h5>
                        <p>Discovered ${discoveryResults.length} files during crawling, but none were successfully downloaded.</p>
                        <small class="text-muted">Check download settings and try again.</small>
                    </div>
                `;
            }
            return '<div class="text-center text-muted py-4"><h5>No files downloaded</h5></div>';
        }

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5>
                    <i class="bi bi-download me-2"></i>
                    ${isCrawlerMode ? 'Crawler Download Results' : 'Download Results'}
                </h5>
                <div class="text-muted">
                    ${downloadResults.successful_downloads}/${downloadResults.total_urls} downloaded
                    (${downloadResults.success_rate ? downloadResults.success_rate.toFixed(1) : 0}%)
                    ${isCrawlerMode ? ` • ${results.pages_crawled || 0} pages crawled` : ''}
                </div>
            </div>
            
            ${isCrawlerMode ? `
                <div class="alert alert-info mb-3">
                    <i class="bi bi-info-circle me-2"></i>
                    <strong>Crawling Summary:</strong> 
                    Found ${discoveryResults.length} files from ${results.pages_crawled || 0} pages
                    ${results.start_url ? ` starting from ${results.start_url}` : ''}
                    ${results.crawl_depth ? ` (depth: ${results.crawl_depth})` : ''}
                </div>
            ` : ''}
            
            <div class="mb-3">
                <div class="row">
                    <div class="col-md-3">
                        <div class="card bg-success text-white">
                            <div class="card-body text-center">
                                <h5>${downloadResults.successful_downloads || 0}</h5>
                                <small>Downloaded</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card ${isCrawlerMode ? 'bg-info' : 'bg-danger'} text-white">
                            <div class="card-body text-center">
                                <h5>${isCrawlerMode ? discoveryResults.length : (downloadResults.failed_downloads || 0)}</h5>
                                <small>${isCrawlerMode ? 'Discovered' : 'Failed'}</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-primary text-white">
                            <div class="card-body text-center">
                                <h5>${downloadResults.total_size_human || '0 B'}</h5>
                                <small>Total Size</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-secondary text-white">
                            <div class="card-body text-center">
                                <h5>${downloadResults.duration || 'Unknown'}</h5>
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

        downloadResults.results.forEach(result => {
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

    initializeMetadataToggles() {
        // Initialize metadata toggle buttons
        document.querySelectorAll('.metadata-toggle').forEach(button => {
            button.addEventListener('click', function() {
                const targetId = this.getAttribute('data-target');
                const target = document.getElementById(targetId);
                const icon = this.querySelector('i');
                
                if (target) {
                    target.classList.toggle('show');
                    
                    if (target.classList.contains('show')) {
                        this.innerHTML = '<i class="bi bi-eye-slash"></i> Hide Details';
                        this.classList.replace('btn-outline-primary', 'btn-primary');
                    } else {
                        this.innerHTML = '<i class="bi bi-eye"></i> Show Details';
                        this.classList.replace('btn-primary', 'btn-outline-primary');
                    }
                }
            });
        });
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
            // Use appropriate rendering based on operation type
            let content = '';
            if (result.type === 'metadata') {
                content = window.metaspidey.renderMetadataResults(result.results);
            } else if (result.type === 'crawler') {
                content = window.metaspidey.renderCrawlerResults(result.results);
            } else if (result.type === 'download') {
                content = window.metaspidey.renderDownloadResults(result.results);
            } else if (result.type === 'bruteforce') {
                content = window.metaspidey.renderBruteForceResults(result.results);
            } else {
                // Fallback to JSON with proper styling
                content = '<pre class="bg-dark text-light p-3 rounded" style="max-height: 60vh; overflow-y: auto;">' + 
                         JSON.stringify(result.results, null, 2) + '</pre>';
            }
            
            document.getElementById('modal-results-content').innerHTML = content;
            
            // Add event listeners for metadata toggles if it's metadata
            if (result.type === 'metadata') {
                window.metaspidey.initializeMetadataToggles();
            }
            
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