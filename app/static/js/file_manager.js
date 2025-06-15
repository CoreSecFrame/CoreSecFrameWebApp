// app/static/js/file_manager.js - File Manager JavaScript Functions (Fixed)

// Global variables for search and sudo functionality
let currentSearchQuery = '';
let currentItemPathForSudo = null;
let currentItemNameForSudo = null;
let currentItemIsDirForSudo = null;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Load quick navigation shortcuts
    loadQuickNavigation();
    
    // Set up CSRF protection
    setupCSRFProtection();

    // Initialize sudo modal
    initializeSudoModal();
    
    // Initialize search functionality
    initializeSearch();
    
    // Initialize path navigation
    initializePathNavigation();
    
    // Initialize upload functionality
    initializeUpload();
    
    // Add fade-in animations to table rows
    addTableAnimations();
    
    // Initialize keyboard shortcuts
    initializeKeyboardShortcuts();
});

function addTableAnimations() {
    const rows = document.querySelectorAll('.file-table tbody tr');
    rows.forEach((row, index) => {
        row.style.animationDelay = `${index * 50}ms`;
        row.classList.add('fade-in');
    });
}

function initializeSudoModal() {
    const sudoPasswordModalElement = document.getElementById('sudoPasswordModal');
    if (!sudoPasswordModalElement) {
        console.error("Sudo password modal element not found!");
        return;
    }
    
    const sudoPasswordModal = new bootstrap.Modal(sudoPasswordModalElement);
    const sudoPasswordInput = document.getElementById('sudo_password_input');
    const sudoItemNameElement = document.getElementById('sudo_item_name_modal');
    const sudoModalErrorElement = document.getElementById('sudo_modal_error');
    const submitSudoPasswordButton = document.getElementById('submit_sudo_password');

    if (submitSudoPasswordButton) {
        submitSudoPasswordButton.addEventListener('click', async function() {
            const password = sudoPasswordInput.value;
            if (!password) {
                showSudoError('Password cannot be empty.');
                return;
            }
            
            // Disable button and show loading
            submitSudoPasswordButton.disabled = true;
            submitSudoPasswordButton.innerHTML = '<span class="loading-spinner me-2"></span>Processing...';
            hideSudoError();

            try {
                const data = await postData('/file_manager/sudo_delete_item', {
                    item_path: currentItemPathForSudo,
                    password: password
                });

                if (data.success) {
                    sudoPasswordModal.hide();
                    showAlert(`${currentItemIsDirForSudo ? 'Folder' : 'File'} '${currentItemNameForSudo}' deleted successfully!`, 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showSudoError(data.error || 'Unknown error occurred');
                    sudoPasswordInput.value = '';
                }
            } catch (sudoError) {
                console.error('Error during sudo delete item:', sudoError);
                showSudoError('An error occurred during the operation. Please try again.');
                sudoPasswordInput.value = '';
            } finally {
                // Re-enable button
                submitSudoPasswordButton.disabled = false;
                submitSudoPasswordButton.innerHTML = '<i class="bi bi-shield-check me-1"></i>Authenticate & Delete';
            }
        });
    }
    
    // Clear modal on hide
    sudoPasswordModalElement.addEventListener('hidden.bs.modal', function () {
        sudoPasswordInput.value = '';
        hideSudoError();
        submitSudoPasswordButton.disabled = false;
        submitSudoPasswordButton.innerHTML = '<i class="bi bi-shield-check me-1"></i>Authenticate & Delete';
    });

    // Store modal instances globally
    window.sudoPasswordModalInstance = sudoPasswordModal;
    window.sudoItemNameElementInstance = sudoItemNameElement;
}

function showSudoError(message) {
    const errorElement = document.getElementById('sudo_modal_error');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

function hideSudoError() {
    const errorElement = document.getElementById('sudo_modal_error');
    if (errorElement) {
        errorElement.style.display = 'none';
    }
}

function initializeSearch() {
    const searchQueryInput = document.getElementById('search_query');

    if (searchQueryInput) {
        let searchTimeout;
        
        searchQueryInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            if (query.length >= 2) {
                searchTimeout = setTimeout(() => performSearch(query), 500);
            } else if (query.length === 0) {
                clearSearch();
            }
        });
        
        searchQueryInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const query = this.value.trim();
                if (query) {
                    performSearch(query);
                }
            }
        });
    }
}

function initializePathNavigation() {
    const pathInput = document.getElementById('path_input');
    const goButton = document.getElementById('go_button');

    if (pathInput && goButton) {
        function handlePathNavigation() {
            const targetPath = pathInput.value.trim();
            if (targetPath) {
                navigateToPath(targetPath);
            }
        }

        goButton.addEventListener('click', handlePathNavigation);
        pathInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                handlePathNavigation();
            }
        });
    }
}

function initializeUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    
    if (uploadArea && fileInput) {
        // Click to select files
        uploadArea.addEventListener('click', function() {
            fileInput.click();
        });
        
        // Drag and drop functionality
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });
        
        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                uploadFiles(files);
            }
        });
        
        // File input change
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                uploadFiles(e.target.files);
            }
        });
    }
}

function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+U for upload
        if (e.ctrlKey && e.key === 'u') {
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('uploadFileModal')).show();
        }
        
        // Ctrl+Shift+N for new folder
        if (e.ctrlKey && e.shiftKey && e.key === 'N') {
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('createFolderModal')).show();
        }
        
        // Ctrl+N for new file
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('createFileModal')).show();
        }
        
        // F5 for refresh
        if (e.key === 'F5') {
            e.preventDefault();
            location.reload();
        }

        // Escape to close modals
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal.show');
            openModals.forEach(modal => {
                bootstrap.Modal.getInstance(modal)?.hide();
            });
        }
        
        // Ctrl+F for search
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('search_query');
            if (searchInput) {
                searchInput.focus();
            }
        }
    });

    // Handle Enter key in forms
    const forms = [
        { input: 'file_name', action: createFile },
        { input: 'folder_name', action: createFolder },
        { input: 'new_item_name', action: renameItem },
        { input: 'sudo_password_input', action: () => {
            const btn = document.getElementById('submit_sudo_password');
            if (btn) btn.click();
        }}
    ];

    forms.forEach(form => {
        const input = document.getElementById(form.input);
        if (input) {
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    form.action();
                }
            });
        }
    });
}

function getCurrentPath() {
    // Try to get path from URL parameters or from a data attribute
    const urlParams = new URLSearchParams(window.location.search);
    const pathFromUrl = urlParams.get('path');
    
    if (pathFromUrl) {
        return pathFromUrl;
    }
    
    // Fallback: try to get from path input
    const pathInput = document.getElementById('path_input');
    if (pathInput && pathInput.value) {
        return pathInput.value;
    }
    
    // Default fallback
    return '/';
}

async function performSearch(query) {
    const searchInput = document.getElementById('search_query');
    const originalPlaceholder = searchInput ? searchInput.placeholder : '';
    
    if (!query) {
        showAlert('Please enter a search query.', 'warning');
        return;
    }
    
    // Show loading state
    if (searchInput) {
        searchInput.placeholder = 'Searching...';
        searchInput.disabled = true;
    }
    
    try {
        const currentPath = getCurrentPath();
        const showHidden = document.getElementById('showHidden') ? document.getElementById('showHidden').checked : false;
        
        const response = await fetch(`/file_manager/search?query=${encodeURIComponent(query)}&path=${encodeURIComponent(currentPath)}&show_hidden=${showHidden}`);
        const data = await response.json();
        
        if (data.success) {
            displaySearchResults(data.items, query);
            currentSearchQuery = query;
        } else {
            showAlert(`Search error: ${data.error}`, 'danger');
        }
    } catch (error) {
        console.error('Search error:', error);
        showAlert('An error occurred during search.', 'danger');
    } finally {
        // Restore input state
        if (searchInput) {
            searchInput.disabled = false;
            searchInput.placeholder = originalPlaceholder;
        }
    }
}

function displaySearchResults(items, query) {
    const searchResultsContainer = document.getElementById('searchResults');
    const searchResultsBody = document.getElementById('searchResultsBody');
    const searchQuerySpan = document.getElementById('searchQuery');
    
    if (!searchResultsContainer || !searchResultsBody || !searchQuerySpan) {
        console.error('Search results elements not found');
        return;
    }
    
    const fileListContainer = searchResultsContainer.nextElementSibling;
    
    // Update query display
    searchQuerySpan.textContent = `"${query}"`;
    
    // Clear previous results
    searchResultsBody.innerHTML = '';
    
    if (items.length === 0) {
        searchResultsBody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <div class="empty-state-icon">
                        <i class="bi bi-search"></i>
                    </div>
                    <div class="empty-state-title">No results found</div>
                    <div class="empty-state-description">
                        No files or folders found matching "${query}"
                    </div>
                </td>
            </tr>
        `;
    } else {
        // Populate results
        items.forEach((item, index) => {
            const row = createFileRow(item, true);
            row.style.animationDelay = `${index * 50}ms`;
            row.classList.add('fade-in');
            searchResultsBody.appendChild(row);
        });
    }
    
    // Show search results and hide file list
    searchResultsContainer.style.display = 'block';
    if (fileListContainer) {
        fileListContainer.style.display = 'none';
    }
    
    showAlert(`Found ${items.length} item(s) matching "${query}"`, 'info');
}

function createFileRow(item, isSearchResult = false) {
    const row = document.createElement('tr');
    if (!item.is_readable) {
        row.className = 'table-warning';
    }
    
    // File type icon
    let iconClass = 'bi bi-file text-secondary file-icon';
    if (item.is_dir) {
        iconClass = 'bi bi-folder-fill text-warning file-icon';
    } else {
        const nameParts = item.name.split('.');
        const ext = nameParts.length > 1 ? nameParts.pop().toLowerCase() : '';
        const iconMap = {
            'txt': 'bi bi-file-text text-info file-icon',
            'md': 'bi bi-file-text text-info file-icon',
            'py': 'bi bi-file-code text-success file-icon',
            'js': 'bi bi-file-code text-success file-icon',
            'html': 'bi bi-file-code text-success file-icon',
            'css': 'bi bi-file-code text-success file-icon',
            'json': 'bi bi-file-code text-success file-icon',
            'jpg': 'bi bi-file-image text-danger file-icon',
            'jpeg': 'bi bi-file-image text-danger file-icon',
            'png': 'bi bi-file-image text-danger file-icon',
            'pdf': 'bi bi-file-pdf text-danger file-icon',
            'zip': 'bi bi-file-zip text-warning file-icon',
            'mp3': 'bi bi-file-music text-purple file-icon',
            'mp4': 'bi bi-file-play text-danger file-icon'
        };
        iconClass = iconMap[ext] || iconClass;
        if (item.is_executable) {
            iconClass = 'bi bi-file-binary text-danger file-icon';
        }
    }
    
    // Escape HTML to prevent XSS
    const escapedName = escapeHtml(item.name);
    const escapedPath = escapeHtml(item.full_path);
    
    row.innerHTML = `
        <td class="file-icon-cell"><i class="${iconClass}"></i></td>
        <td class="file-name-cell">
            ${isSearchResult ? 
                `<div class="text-primary mb-1"><small><i class="bi bi-folder me-1"></i>${escapedPath}</small></div>
                 <strong>${escapedName}</strong>` : 
                (item.is_dir && item.is_readable ? 
                    `<a href="${generateNavigationUrl(item.full_path)}" class="folder-name-link">${escapedName}</a>` : 
                    `<span class="file-name-link">${escapedName}</span>`
                )
            }
            ${item.is_hidden ? '<i class="bi bi-eye-slash ms-1 text-muted"></i>' : ''}
        </td>
        <td>
            <span class="file-type-badge ${item.is_dir ? 'badge-folder' : 'badge-file'}">${item.is_dir ? 'Folder' : 'File'}</span>
            ${item.is_executable && !item.is_dir ? '<span class="file-type-badge badge-executable">Exec</span>' : ''}
        </td>
        <td class="file-size-cell">${item.size || '<span class="text-muted">-</span>'}</td>
        <td class="file-date-cell"><small>${item.modified || '<span class="text-muted">-</span>'}</small></td>
        <td><code class="file-permissions-cell">${item.permissions || ''}</code></td>
        <td class="file-owner-cell"><small>${item.owner || ''}</small></td>
        <td class="file-actions-cell">
            <div class="file-actions-group">
                ${item.is_readable && !item.is_dir ? 
                    `<button type="button" class="file-action-btn btn-outline-primary" onclick="viewFile('${escapedName}', '${escapedPath}')" title="View">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button type="button" class="file-action-btn btn-outline-secondary" onclick="downloadFile('${escapedPath}')" title="Download">
                        <i class="bi bi-download"></i>
                    </button>` : ''
                }
                <button type="button" class="file-action-btn btn-outline-warning" onclick="showRenameModal('${escapedName}', '${escapedPath}')" title="Rename">
                    <i class="bi bi-pencil"></i>
                </button>
                <button type="button" class="file-action-btn btn-outline-danger" onclick="deleteItem('${escapedName}', ${item.is_dir}, '${escapedPath}')" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </td>
    `;
    
    return row;
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

function generateNavigationUrl(path) {
    const showHidden = document.getElementById('showHidden') ? document.getElementById('showHidden').checked : false;
    return `/file_manager/list?path=${encodeURIComponent(path)}&show_hidden=${showHidden}`;
}

function clearSearch() {
    const searchResultsContainer = document.getElementById('searchResults');
    const searchQueryInput = document.getElementById('search_query');
    
    if (!searchResultsContainer) return;
    
    const fileListContainer = searchResultsContainer.nextElementSibling;
    
    // Hide search results and show file list
    searchResultsContainer.style.display = 'none';
    if (fileListContainer) {
        fileListContainer.style.display = 'block';
    }
    
    // Clear search input and query
    if (searchQueryInput) {
        searchQueryInput.value = '';
    }
    currentSearchQuery = '';
    
    showAlert('Search cleared', 'info');
}

async function loadQuickNavigation() {
    try {
        const response = await fetch('/file_manager/quick_navigate');
        const data = await response.json();
        
        const menu = document.getElementById('quickNavMenu');
        if (!menu) return;
        
        const existingItems = menu.querySelectorAll('.quick-nav-item');
        existingItems.forEach(item => item.remove());
        
        if (data.shortcuts && Array.isArray(data.shortcuts)) {
            data.shortcuts.forEach(shortcut => {
                const li = document.createElement('li');
                li.className = 'quick-nav-item';
                li.innerHTML = `
                    <a class="dropdown-item" href="#" onclick="navigateToPath('${escapeHtml(shortcut.path)}'); return false;">
                        <i class="bi bi-${shortcut.icon} me-2"></i>${escapeHtml(shortcut.name)}
                    </a>
                `;
                menu.appendChild(li);
            });
        }
        
    } catch (error) {
        console.error('Error loading quick navigation:', error);
    }
}

function navigateToPath(path) {
    const currentShowHidden = document.getElementById('showHidden') ? document.getElementById('showHidden').checked : false;
    const url = `/file_manager/list?path=${encodeURIComponent(path)}&show_hidden=${currentShowHidden}`;
    window.location.href = url;
}

function toggleHiddenFiles() {
    const showHidden = document.getElementById('showHidden') ? document.getElementById('showHidden').checked : false;
    const currentPath = getCurrentPath();
    const url = `/file_manager/list?path=${encodeURIComponent(currentPath)}&show_hidden=${showHidden}`;
    window.location.href = url;
}

function setupCSRFProtection() {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (!csrfMeta) {
        console.warn('CSRF token not found');
        return;
    }
    
    const csrfToken = csrfMeta.getAttribute('content');
    
    const originalFetch = window.fetch;
    window.fetch = function() {
        let [resource, config] = arguments;
        
        config = config || {};
        config.headers = config.headers || {};
        
        if (config.method === 'POST' || config.method === 'PUT' || config.method === 'DELETE') {
            config.headers['X-CSRFToken'] = csrfToken;
        }
        
        return originalFetch.apply(this, arguments);
    };
}

async function postData(url = '', data = {}) {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken
        },
        body: new URLSearchParams(data)
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    if (!alertContainer) {
        console.warn('Alert container not found, falling back to default behavior');
        // Fallback to old behavior
        const container = document.querySelector('.container-fluid') || document.body;
        container.insertAdjacentHTML('afterbegin', createAlertHTML(message, type));
        return;
    }
    
    // Create alert element
    const alertElement = document.createElement('div');
    alertElement.innerHTML = createAlertHTML(message, type);
    const alert = alertElement.firstElementChild;
    
    // Add to container
    alertContainer.appendChild(alert);
    
    // Auto-remove after 5 seconds with animation
    setTimeout(() => {
        if (alert && alert.parentNode) {
            alert.classList.add('fade-out');
            setTimeout(() => {
                if (alert && alert.parentNode) {
                    alert.remove();
                }
            }, 300); // Wait for animation to complete
        }
    }, 5000);
}

function createAlertHTML(message, type) {
    const iconMap = {
        'success': 'check-circle',
        'danger': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    
    const icon = iconMap[type] || 'info-circle';
    
    return `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="bi bi-${icon} me-2"></i>
            ${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
}

async function createFile() {
    try {
        const fileNameInput = document.getElementById('file_name');
        if (!fileNameInput) {
            showAlert('File name input not found.', 'danger');
            return;
        }
        
        const fileName = fileNameInput.value.trim();
        const currentPath = getCurrentPath();
        
        if (!fileName) {
            showAlert('Please enter a file name.', 'warning');
            return;
        }
        
        const data = await postData('/file_manager/create_file', { 
            file_name: fileName, 
            path: currentPath 
        });
        
        if (data.success) {
            showAlert('File created successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.error, 'danger');
        }
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('createFileModal'));
        if (modal) modal.hide();
        fileNameInput.value = '';
        
    } catch (error) {
        console.error('Error creating file:', error);
        showAlert('An error occurred while creating the file.', 'danger');
    }
}

async function createFolder() {
    try {
        const folderNameInput = document.getElementById('folder_name');
        if (!folderNameInput) {
            showAlert('Folder name input not found.', 'danger');
            return;
        }
        
        const folderName = folderNameInput.value.trim();
        const currentPath = getCurrentPath();
        
        if (!folderName) {
            showAlert('Please enter a folder name.', 'warning');
            return;
        }
        
        const data = await postData('/file_manager/create_folder', { 
            folder_name: folderName, 
            path: currentPath 
        });
        
        if (data.success) {
            showAlert('Folder created successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.error, 'danger');
        }
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('createFolderModal'));
        if (modal) modal.hide();
        folderNameInput.value = '';
        
    } catch (error) {
        console.error('Error creating folder:', error);
        showAlert('An error occurred while creating the folder.', 'danger');
    }
}

async function deleteItem(itemName, isDir, fullPath) {
    const itemType = isDir ? 'folder' : 'file';
    
    if (!confirm(`Are you sure you want to delete this ${itemType}: "${itemName}"?\n\nThis action cannot be undone.`)) {
        return;
    }
    
    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
        
        const response = await fetch('/file_manager/delete_item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken
            },
            body: new URLSearchParams({ item_path: fullPath })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showAlert(`${itemType.charAt(0).toUpperCase() + itemType.slice(1)} deleted successfully!`, 'success');
            setTimeout(() => location.reload(), 1000);
        } else if (response.status === 403 && data.requires_sudo) {
            // Show sudo modal
            currentItemPathForSudo = fullPath;
            currentItemNameForSudo = itemName;
            currentItemIsDirForSudo = isDir;

            if (window.sudoItemNameElementInstance) {
                window.sudoItemNameElementInstance.textContent = itemName;
            }
            
            if (window.sudoPasswordModalInstance) {
                window.sudoPasswordModalInstance.show();
            } else {
                showAlert('Sudo modal not available. Please refresh the page.', 'danger');
            }
        } else {
            showAlert(`Error: ${data.error || 'Unknown error'}`, 'danger');
        }
    } catch (error) {
        console.error('Error deleting item:', error);
        showAlert(`An error occurred while deleting the ${itemType}.`, 'danger');
    }
}

async function viewFile(fileName, filePath) {
    const viewerFileNameElement = document.getElementById('viewerFileName');
    const fileContentElement = document.getElementById('fileContent');
    
    if (viewerFileNameElement) {
        viewerFileNameElement.textContent = fileName;
    }
    if (fileContentElement) {
        fileContentElement.textContent = 'Loading file content...';
    }
    
    const modal = new bootstrap.Modal(document.getElementById('fileViewerModal'));
    modal.show();
    
    try {
        const response = await fetch(`/file_manager/view_file?path=${encodeURIComponent(filePath)}`);
        const data = await response.json();
        
        if (data.success && fileContentElement) {
            fileContentElement.textContent = data.content;
        } else if (fileContentElement) {
            fileContentElement.textContent = `Error loading file: ${data.error}`;
        }
    } catch (error) {
        console.error('Error viewing file:', error);
        if (fileContentElement) {
            fileContentElement.textContent = 'Error loading file content.';
        }
    }
}

function downloadFile(filePath) {
    const link = document.createElement('a');
    link.href = `/file_manager/download_file?path=${encodeURIComponent(filePath)}`;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function showDiskUsage() {
    const modal = new bootstrap.Modal(document.getElementById('diskUsageModal'));
    modal.show();
    
    try {
        const currentPath = getCurrentPath();
        const response = await fetch(`/file_manager/get_disk_usage?path=${encodeURIComponent(currentPath)}`);
        const data = await response.json();
        
        const diskUsageContentElement = document.getElementById('diskUsageContent');
        if (!diskUsageContentElement) return;
        
        if (data.success) {
            diskUsageContentElement.innerHTML = `
                <div class="mb-3">
                    <h6>Directory: <code>${escapeHtml(data.path)}</code></h6>
                </div>
                <div class="row text-center">
                    <div class="col-md-4">
                        <h3 class="text-primary">${escapeHtml(data.total_size)}</h3>
                        <p class="text-muted">Total Size</p>
                    </div>
                    <div class="col-md-4">
                        <h3 class="text-success">${data.file_count}</h3>
                        <p class="text-muted">Files</p>
                    </div>
                    <div class="col-md-4">
                        <h3 class="text-warning">${data.folder_count}</h3>
                        <p class="text-muted">Folders</p>
                    </div>
                </div>
                <hr>
                <div class="text-center">
                    <small class="text-muted">
                        <i class="bi bi-info-circle me-1"></i>
                        Calculation includes all accessible subdirectories
                    </small>
                </div>
            `;
        } else {
            diskUsageContentElement.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-circle me-2"></i>
                    Error: ${escapeHtml(data.error)}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error getting disk usage:', error);
        const diskUsageContentElement = document.getElementById('diskUsageContent');
        if (diskUsageContentElement) {
            diskUsageContentElement.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-circle me-2"></i>
                    Error loading disk usage information.
                </div>
            `;
        }
    }
}

function showRenameModal(itemName, itemPath) {
    const newItemNameInput = document.getElementById('new_item_name');
    const oldItemPathInput = document.getElementById('old_item_path');
    
    if (newItemNameInput) {
        newItemNameInput.value = itemName;
    }
    if (oldItemPathInput) {
        oldItemPathInput.value = itemPath;
    }
    
    const modal = new bootstrap.Modal(document.getElementById('renameItemModal'));
    modal.show();
}

async function renameItem() {
    try {
        const oldPathInput = document.getElementById('old_item_path');
        const newNameInput = document.getElementById('new_item_name');
        
        if (!oldPathInput || !newNameInput) {
            showAlert('Rename form elements not found.', 'danger');
            return;
        }
        
        const oldPath = oldPathInput.value;
        const newName = newNameInput.value.trim();
        
        if (!newName) {
            showAlert('Please enter a new name.', 'warning');
            return;
        }
        
        const data = await postData('/file_manager/rename_item', {
            old_path: oldPath,
            new_name: newName
        });
        
        if (data.success) {
            showAlert('Item renamed successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.error, 'danger');
        }
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('renameItemModal'));
        if (modal) modal.hide();
        
    } catch (error) {
        console.error('Error renaming item:', error);
        showAlert('An error occurred while renaming the item.', 'danger');
    }
}

function selectFiles() {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.click();
    }
}

async function uploadFiles(files) {
    const currentPath = getCurrentPath();
    const progressDiv = document.getElementById('uploadProgress');
    const fileInput = document.getElementById('fileInput');
    
    if (!progressDiv || !fileInput) {
        showAlert('Upload elements not found.', 'danger');
        return;
    }
    
    const progressBar = progressDiv.querySelector('.progress-bar');
    if (!progressBar) {
        showAlert('Progress bar not found.', 'danger');
        return;
    }
    
    progressDiv.style.display = 'block';
    
    let completed = 0;
    const total = files.length;
    
    for (let file of files) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('path', currentPath);
            
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            
            const response = await fetch('/file_manager/upload_file', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });
            
            const data = await response.json();
            
            if (!data.success) {
                showAlert(`Error uploading ${file.name}: ${data.error}`, 'danger');
            }
            
        } catch (error) {
            console.error(`Error uploading ${file.name}:`, error);
            showAlert(`Error uploading ${file.name}`, 'danger');
        }
        
        completed++;
        const percent = (completed / total) * 100;
        progressBar.style.width = percent + '%';
    }
    
    // Hide modal and refresh page
    setTimeout(() => {
        const uploadModal = bootstrap.Modal.getInstance(document.getElementById('uploadFileModal'));
        if (uploadModal) uploadModal.hide();
        showAlert(`${completed} file(s) uploaded successfully!`, 'success');
        setTimeout(() => location.reload(), 1000);
    }, 500);
    
    // Reset
    progressDiv.style.display = 'none';
    progressBar.style.width = '0%';
    fileInput.value = '';
}
