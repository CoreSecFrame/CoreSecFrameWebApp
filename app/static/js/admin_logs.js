let autoRefreshInterval = null;
let autoRefreshEnabled = false;

document.addEventListener('DOMContentLoaded', function() {
    const logsTable = document.getElementById('logsTable');
    let logsStatsUrl = '';
    if (logsTable && logsTable.dataset.logsStatsUrl) {
        logsStatsUrl = logsTable.dataset.logsStatsUrl;
    } else {
        console.error('Logs stats URL data attribute not found on logsTable.');
    }

    // Load statistics when modal is opened
    const statsModal = document.getElementById('statsModal');
    if (statsModal) {
        statsModal.addEventListener('show.bs.modal', function() {
            loadStatistics(logsStatsUrl);
        });
    }

    // Auto-refresh functionality for active page
    setupAutoRefresh();

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        // Check if a tooltip isn't already initialized by main.js for data-bs-toggle="tooltip"
        if (!tooltipTriggerEl.hasAttribute('data-bs-toggle') ||
            (tooltipTriggerEl.getAttribute('data-bs-toggle') !== 'tooltip' && tooltipTriggerEl.getAttribute('data-bs-toggle') !== 'popover')) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        }
    });

    // Highlight recent entries (last 5 minutes) - This part was duplicated, removing one.
    const logEntries = document.querySelectorAll('.log-entry');
    const now = new Date();

    logEntries.forEach(function(entry) {
        const timestampCell = entry.querySelector('td:first-child small');
        if (timestampCell) {
            const timestampText = timestampCell.textContent.trim();
            // Attempt to parse the date, assuming format YYYY-MM-DD HH:MM:SS
            // More robust parsing might be needed if format varies or includes timezone.
            const logTime = new Date(timestampText.replace(' ', 'T') + 'Z'); // Assume UTC if no TZ info
            if (isNaN(logTime.getTime())) { // Check if date parsing failed
                // Try another common format if applicable, or log error
                // console.warn("Could not parse date:", timestampText);
                return;
            }
            const diffMinutes = (now - logTime) / (1000 * 60);

            if (diffMinutes < 5 && diffMinutes >= 0) { // Ensure it's not in the future
                entry.classList.add('table-success');
                entry.style.borderLeft = '3px solid var(--w11-color-success-default)'; // Use theme variable
            }
        }
    });

    // Make functions available on window object if they are called by inline HTML onclick
    window.refreshLogs = refreshLogs;
    window.toggleAutoRefresh = toggleAutoRefresh;
    window.toggleFullMessage = toggleFullMessage;
    window.toggleException = toggleException;
    window.copyLogEntry = copyLogEntry;

});

function loadStatistics(logsStatsUrl) {
    const statsContent = document.getElementById('statsContent');
    if (!statsContent || !logsStatsUrl) {
        if(statsContent) statsContent.innerHTML = '<div class="alert alert-danger">Configuration error: Logs stats URL not found.</div>';
        return;
    }

    statsContent.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p>Loading statistics...</p>
        </div>`;

    fetch(logsStatsUrl + '?hours=24') // Example: always fetch for 24h for this modal
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(responseData => {
            const data = responseData.data; // Assuming json_success wraps data
            if (!data) {
                statsContent.innerHTML = '<div class="alert alert-danger">Error: Invalid data format from server.</div>';
                console.error('Invalid data format for stats:', responseData);
                return;
            }
            const html = `
                <div class="row">
                    <div class="col-md-6">
                        <h6>Overall Statistics</h6>
                        <table class="table table-sm">
                            <tr><td>Total Logs:</td><td><strong>${(data.total_logs || 0).toLocaleString()}</strong></td></tr>
                            <tr><td>Last 24 Hours:</td><td><strong>${(data.recent_logs || 0).toLocaleString()}</strong></td></tr>
                            <tr><td>Errors (24h):</td><td><strong class="text-danger">${data.error_count_24h || 0}</strong></td></tr>
                            <tr><td>Security Events (24h):</td><td><strong class="text-warning">${data.security_events_24h || 0}</strong></td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h6>Log Level Distribution (24h)</h6>
                        <div class="row">
                            ${Object.entries(data.level_stats || {}).map(([level, count]) => `
                                <div class="col-6 mb-2">
                                    <div class="text-center">
                                        <div class="badge bg-${getLevelClass(level)} w-100">${level}</div>
                                        <div><strong>${count}</strong></div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
                <hr>
                <h6>Top Modules (24h)</h6>
                <div class="row">
                    ${(data.module_stats || []).slice(0, 6).map(mod => `
                        <div class="col-md-4 mb-2">
                            <div class="d-flex justify-content-between">
                                <span class="text-truncate" title="${mod.module}">${mod.module}</span>
                                <strong>${mod.count}</strong>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            statsContent.innerHTML = html;
        })
        .catch(error => {
            statsContent.innerHTML = '<div class="alert alert-danger">Error loading statistics. Please try again later.</div>';
            console.error('Error loading statistics:', error);
        });
}

function getLevelClass(level) {
    const classes = {
        'DEBUG': 'secondary',
        'INFO': 'info',
        'WARNING': 'warning',
        'ERROR': 'danger',
        'CRITICAL': 'danger',
        // Add other levels if they exist
    };
    return classes[level.toUpperCase()] || 'secondary';
}

function refreshLogs() {
    window.location.reload();
}

function toggleAutoRefresh() {
    const btn = document.getElementById('autoRefreshBtn');
    if (!btn) return;

    if (autoRefreshEnabled) {
        clearInterval(autoRefreshInterval);
        autoRefreshEnabled = false;
        btn.innerHTML = '<i class="bi bi-play-circle"></i>';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-outline-light');
        if (window.CoreSecFrame && window.CoreSecFrame.showNotification) {
            window.CoreSecFrame.showNotification('Auto-refresh disabled.', 'info', 2000);
        }
    } else {
        autoRefreshInterval = setInterval(refreshLogs, 30000); // 30 seconds
        autoRefreshEnabled = true;
        btn.innerHTML = '<i class="bi bi-pause-circle"></i>';
        btn.classList.remove('btn-outline-light');
        btn.classList.add('btn-success');
         if (window.CoreSecFrame && window.CoreSecFrame.showNotification) {
            window.CoreSecFrame.showNotification('Auto-refresh enabled (30s).', 'info', 2000);
        }
    }
}

function setupAutoRefresh() {
    const urlParams = new URLSearchParams(window.location.search);
    const page = urlParams.get('page') || '1';
    const hasFilters = urlParams.get('search') || urlParams.get('level') || urlParams.get('module') || urlParams.get('hours');

    if (page === '1' && !hasFilters) {
        setTimeout(() => {
            if (!autoRefreshEnabled) { // Check if not already enabled by user click
                toggleAutoRefresh();
            }
        }, 5000);
    }
}

function toggleFullMessage(logId) {
    const element = document.getElementById(`fullMessage${logId}`);
    if (element) {
        const collapse = bootstrap.Collapse.getOrCreateInstance(element);
        collapse.toggle();
    }
}

function toggleException(logId) {
    const element = document.getElementById(`exception${logId}`);
    if (element) {
        const collapse = bootstrap.Collapse.getOrCreateInstance(element);
        collapse.toggle();
    }
}

function copyLogEntry(logId) {
    const row = document.querySelector(`tr[data-log-id="${logId}"]`);
    if (!row) return;

    const cells = row.querySelectorAll('td');
    let logText = "";

    if (cells.length >= 5) { // Ensure all expected cells are there
         logText = [
            cells[0].textContent.trim(), // timestamp
            cells[1].textContent.trim().replace(/\s+/g, ' '), // level (remove extra spaces from badge)
            cells[2].textContent.trim().replace(/\s+/g, ' '), // module
            cells[3].textContent.trim(), // function
            // For message, try to get full message if available, otherwise short
            (document.getElementById(`fullMessage${logId}`)?.textContent.trim() || cells[4].querySelector('.log-message').textContent.trim().replace(/\s*Show more...$/, ''))
        ].join(' | ');
    } else {
        logText = row.textContent.trim().replace(/\s+/g, ' '); // Fallback to all row text
    }

    navigator.clipboard.writeText(logText).then(() => {
        const btn = event.target.closest('button');
        if(btn){
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-check-lg"></i>'; // Use bi-check-lg for better visibility
            btn.classList.add('btn-success');
            btn.classList.remove('btn-outline-secondary');

            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-secondary');
            }, 2000);
        }
         if (window.CoreSecFrame && window.CoreSecFrame.showNotification) {
            window.CoreSecFrame.showNotification('Log entry copied to clipboard.', 'success', 2000);
        }
    }).catch(err => {
        console.error('Failed to copy log entry:', err);
        if (window.CoreSecFrame && window.CoreSecFrame.showNotification) {
            window.CoreSecFrame.showNotification('Failed to copy log entry.', 'danger', 3000);
        }
    });
}
