document.addEventListener('DOMContentLoaded', function() {
    const fileManagerDataEl = document.getElementById('fileManagerData');
    if (!fileManagerDataEl) {
        console.error('File manager data element not found. URLs and current path will not be available.');
        return;
    }

    const urls = {
        list_files: fileManagerDataEl.dataset.urlList_files,
        quick_navigate: fileManagerDataEl.dataset.urlQuick_navigate,
        create_file: fileManagerDataEl.dataset.urlCreate_file,
        create_folder: fileManagerDataEl.dataset.urlCreate_folder,
        delete_item: fileManagerDataEl.dataset.urlDelete_item,
        view_file: fileManagerDataEl.dataset.urlView_file,
        download_file: fileManagerDataEl.dataset.urlDownload_file,
        get_disk_usage: fileManagerDataEl.dataset.urlGet_disk_usage,
        rename_item: fileManagerDataEl.dataset.urlRename_item,
        upload_file: fileManagerDataEl.dataset.urlUpload_file
    };
    const currentPath = fileManagerDataEl.dataset.currentPath;

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Load quick navigation shortcuts
    loadQuickNavigation();

    // CSRF setup is assumed to be global, so setupCSRFProtection() is removed.
    // The postData function will rely on the global fetch wrapper if it exists,
    // or use the CSRF token from meta tag if not.

    // Upload functionality
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    if (uploadArea && fileInput) {
        uploadArea.addEventListener('click', function() {
            fileInput.click();
        });

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
                uploadFilesInternal(files); // Renamed to avoid conflict if global uploadFiles exists
            }
        });

        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                uploadFilesInternal(e.target.files); // Renamed
            }
        });
    }

    // Handle Enter key in forms
    const fileNameInput = document.getElementById('file_name');
    const folderNameInput = document.getElementById('folder_name');
    const newItemNameInput = document.getElementById('new_item_name');

    if (fileNameInput) {
        fileNameInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                createFileInternal(); // Renamed
            }
        });
    }

    if (folderNameInput) {
        folderNameInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                createFolderInternal(); // Renamed
            }
        });
    }

    if (newItemNameInput) {
        newItemNameInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                renameItemInternal(); // Renamed
            }
        });
    }

    // Expose functions to global scope if they are called by inline onclick handlers
    // It's better to attach event listeners directly, but for now, this maintains compatibility.
    window.navigateToPath = navigateToPathInternal;
    window.toggleHiddenFiles = toggleHiddenFilesInternal;
    window.createFile = createFileInternal;
    window.createFolder = createFolderInternal;
    window.deleteItem = deleteItemInternal;
    window.viewFile = viewFileInternal;
    window.downloadFile = downloadFileInternal;
    window.showDiskUsage = showDiskUsageInternal;
    window.showRenameModal = showRenameModalInternal;
    window.renameItem = renameItemInternal;
    window.selectFiles = selectFilesInternal;
    // uploadFiles is handled by event listeners now primarily

    async function loadQuickNavigation() {
        try {
            const response = await fetch(urls.quick_navigate); // Use urls object
            const data = await response.json();

            const menu = document.getElementById('quickNavMenu');
            const existingItems = menu.querySelectorAll('.quick-nav-item');
            existingItems.forEach(item => item.remove());

            data.shortcuts.forEach(shortcut => {
                const li = document.createElement('li');
                li.className = 'quick-nav-item';
                li.innerHTML = `
                    <a class="dropdown-item" href="#" onclick="navigateToPath('${shortcut.path}')">
                        <i class="bi bi-${shortcut.icon} me-2"></i>${shortcut.name}
                    </a>
                `; // navigateToPath is now window.navigateToPath
                menu.appendChild(li);
            });

        } catch (error) {
            console.error('Error loading quick navigation:', error);
        }
    }

    function navigateToPathInternal(path) { // Renamed
        const currentShowHidden = document.getElementById('showHidden').checked;
        const url = `${urls.list_files}?path=${encodeURIComponent(path)}&show_hidden=${currentShowHidden}`; // Use urls object
        window.location.href = url;
    }

    function toggleHiddenFilesInternal() { // Renamed
        const showHidden = document.getElementById('showHidden').checked;
        const url = `${urls.list_files}?path=${encodeURIComponent(currentPath)}&show_hidden=${showHidden}`; // Use urls object and currentPath
        window.location.href = url;
    }

    async function postData(url = '', data = {}) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

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

    async function createFileInternal() { // Renamed
        try {
            const fileName = document.getElementById('file_name').value.trim();
            if (!fileName) {
                window.CoreSecFrame.showNotification('Please enter a file name.', 'warning');
                return;
            }

            const data = await postData(urls.create_file, { // Use urls object
                file_name: fileName,
                path: currentPath // Use currentPath
            });

            if (data.status === 'success') { // Assuming new json_success format
                window.CoreSecFrame.showNotification(data.message || 'File created successfully!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                window.CoreSecFrame.showNotification('Error: ' + (data.message || 'Unknown error'), 'danger');
            }

            bootstrap.Modal.getInstance(document.getElementById('createFileModal'))?.hide();
            document.getElementById('file_name').value = '';

        } catch (error) {
            console.error('Error creating file:', error);
            window.CoreSecFrame.showNotification('An error occurred while creating the file.', 'danger');
        }
    }

    async function createFolderInternal() { // Renamed
        try {
            const folderName = document.getElementById('folder_name').value.trim();
            if (!folderName) {
                window.CoreSecFrame.showNotification('Please enter a folder name.', 'warning');
                return;
            }

            const data = await postData(urls.create_folder, { // Use urls object
                folder_name: folderName,
                path: currentPath // Use currentPath
            });

            if (data.status === 'success') {
                window.CoreSecFrame.showNotification(data.message || 'Folder created successfully!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                window.CoreSecFrame.showNotification('Error: ' + (data.message || 'Unknown error'), 'danger');
            }

            bootstrap.Modal.getInstance(document.getElementById('createFolderModal'))?.hide();
            document.getElementById('folder_name').value = '';

        } catch (error) {
            console.error('Error creating folder:', error);
            window.CoreSecFrame.showNotification('An error occurred while creating the folder.', 'danger');
        }
    }

    async function deleteItemInternal(itemName, isDir, fullPath) { // Renamed
        const itemType = isDir ? 'folder' : 'file';

        if (!confirm(`Are you sure you want to delete this ${itemType}: "${itemName}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            const data = await postData(urls.delete_item, {  // Use urls object
                item_path: fullPath
            });

            if (data.status === 'success') {
                window.CoreSecFrame.showNotification(data.message || `${itemType.charAt(0).toUpperCase() + itemType.slice(1)} deleted successfully!`, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                window.CoreSecFrame.showNotification('Error: ' + (data.message || 'Unknown error'), 'danger');
            }

        } catch (error) {
            console.error('Error deleting item:', error);
            window.CoreSecFrame.showNotification(`An error occurred while deleting the ${itemType}.`, 'danger');
        }
    }

    async function viewFileInternal(fileName, filePath) { // Renamed
        document.getElementById('viewerFileName').textContent = fileName;
        document.getElementById('fileContent').textContent = 'Loading file content...';

        const modalElement = document.getElementById('fileViewerModal');
        if (!modalElement) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        modal.show();

        try {
            const response = await fetch(`${urls.view_file}?path=${encodeURIComponent(filePath)}`); // Use urls object
            const data = await response.json();

            if (data.status === 'success') {
                document.getElementById('fileContent').textContent = data.data.content;
            } else {
                document.getElementById('fileContent').textContent = `Error loading file: ${data.message}`;
            }
        } catch (error) {
            console.error('Error viewing file:', error);
            document.getElementById('fileContent').textContent = 'Error loading file content.';
        }
    }

    function downloadFileInternal(filePath) { // Renamed
        const link = document.createElement('a');
        link.href = `${urls.download_file}?path=${encodeURIComponent(filePath)}`; // Use urls object
        link.download = ''; // Browser will infer filename
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    async function showDiskUsageInternal() { // Renamed
        const modalElement = document.getElementById('diskUsageModal');
        if (!modalElement) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        document.getElementById('diskUsageContent').innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Calculating disk usage...</p>
            </div>`;
        modal.show();

        try {
            const response = await fetch(`${urls.get_disk_usage}?path=${encodeURIComponent(currentPath)}`); // Use urls object and currentPath
            const data = await response.json();

            if (data.status === 'success') {
                const usage = data.data;
                document.getElementById('diskUsageContent').innerHTML = `
                    <div class="mb-3">
                        <h6>Directory: <code>${usage.path}</code></h6>
                    </div>
                    <div class="row text-center">
                        <div class="col-md-4">
                            <h3 class="text-primary">${usage.total_size}</h3>
                            <p class="text-muted">Total Size</p>
                        </div>
                        <div class="col-md-4">
                            <h3 class="text-success">${usage.file_count}</h3>
                            <p class="text-muted">Files</p>
                        </div>
                        <div class="col-md-4">
                            <h3 class="text-warning">${usage.folder_count}</h3>
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
                document.getElementById('diskUsageContent').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-circle me-2"></i>
                        Error: ${data.message}
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error getting disk usage:', error);
            document.getElementById('diskUsageContent').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-circle me-2"></i>
                    Error loading disk usage information.
                </div>
            `;
        }
    }

    function showRenameModalInternal(itemName, itemPath) { // Renamed
        document.getElementById('new_item_name').value = itemName;
        document.getElementById('old_item_path').value = itemPath;

        const modalElement = document.getElementById('renameItemModal');
        if (!modalElement) return;
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        modal.show();
    }

    async function renameItemInternal() { // Renamed
        try {
            const oldPath = document.getElementById('old_item_path').value;
            const newName = document.getElementById('new_item_name').value.trim();

            if (!newName) {
                window.CoreSecFrame.showNotification('Please enter a new name.', 'warning');
                return;
            }

            const data = await postData(urls.rename_item, { // Use urls object
                old_path: oldPath,
                new_name: newName
            });

            if (data.status === 'success') {
                window.CoreSecFrame.showNotification(data.message ||'Item renamed successfully!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                window.CoreSecFrame.showNotification('Error: ' + (data.message || 'Unknown error'), 'danger');
            }

            bootstrap.Modal.getInstance(document.getElementById('renameItemModal'))?.hide();

        } catch (error) {
            console.error('Error renaming item:', error);
            window.CoreSecFrame.showNotification('An error occurred while renaming the item.', 'danger');
        }
    }

    function selectFilesInternal() { // Renamed
        document.getElementById('fileInput').click();
    }

    async function uploadFilesInternal(files) { // Renamed
        const progressDiv = document.getElementById('uploadProgress');
        const progressBar = progressDiv.querySelector('.progress-bar');
        const fileInput = document.getElementById('fileInput'); // To reset it later

        progressDiv.style.display = 'block';

        let completed = 0;
        const total = files.length;

        for (let file of files) {
            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('path', currentPath); // Use currentPath

                const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

                const response = await fetch(urls.upload_file, { // Use urls object
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken
                    },
                    body: formData
                });

                const data = await response.json();

                if (data.status !== 'success') { // Check new response format
                    window.CoreSecFrame.showNotification(`Error uploading ${file.name}: ${data.message || 'Unknown error'}`, 'danger');
                }

            } catch (error) {
                console.error(`Error uploading ${file.name}:`, error);
                window.CoreSecFrame.showNotification(`Error uploading ${file.name}`, 'danger');
            }

            completed++;
            const percent = (completed / total) * 100;
            progressBar.style.width = percent + '%';
        }

        setTimeout(() => {
            bootstrap.Modal.getInstance(document.getElementById('uploadFileModal'))?.hide();
            window.CoreSecFrame.showNotification(`${completed} file(s) processed. Refreshing...`, 'success');
            setTimeout(() => location.reload(), 1000); // Refresh after uploads
        }, 500);

        progressDiv.style.display = 'none';
        progressBar.style.width = '0%';
        if(fileInput) fileInput.value = ''; // Reset file input
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'u') { // Ctrl+U for upload
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('uploadFileModal'))?.show();
        }
        if (e.ctrlKey && e.shiftKey && e.key === 'N') { // Ctrl+Shift+N for new folder
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('createFolderModal'))?.show();
        }
        if (e.ctrlKey && e.key === 'n' && !e.shiftKey) { // Ctrl+N for new file (ensure not conflicting with browser new window)
            e.preventDefault();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('createFileModal'))?.show();
        }
        if (e.key === 'F5') { // F5 for refresh
            e.preventDefault();
            location.reload();
        }
        if (e.key === 'Escape') { // Escape to close modals
            const openModals = document.querySelectorAll('.modal.show');
            openModals.forEach(modalEl => {
                bootstrap.Modal.getInstance(modalEl)?.hide();
            });
        }
    });
});
