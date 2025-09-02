/**
 * BetterMITM Final Implementation - Working Version
 */

console.log('BetterMITM Final script loading...');

// Global state
const BetterMITM = {
    isRunning: false,
    currentInterface: null,
    csrfToken: '',
    refreshInterval: null
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    // Get CSRF token
    BetterMITM.csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    console.log('CSRF token loaded:', BetterMITM.csrfToken ? 'Yes' : 'No');
    
    // Start status checking
    checkStatus();
    startStatusRefresh();
    
    // Bind console input
    const consoleInput = document.getElementById('console-input');
    if (consoleInput) {
        consoleInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                executeCommand();
            }
        });
    }
    
    console.log('BetterMITM Final initialized');
});

// API helper
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'X-CSRFToken': BetterMITM.csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        };
        
        if (data) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(`/bettermitm/api${endpoint}`, options);
        const result = await response.json();
        
        console.log(`API ${method} ${endpoint}:`, result);
        return result;
        
    } catch (error) {
        console.error(`API call failed: ${method} ${endpoint}`, error);
        showNotification('API call failed: ' + error.message, 'error');
        return { success: false, error: error.message };
    }
}

// Notification system
function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Create toast
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${getBgClass(type)} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove after shown
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

function getBgClass(type) {
    switch(type) {
        case 'error': return 'danger';
        case 'success': return 'success';
        case 'warning': return 'warning';
        default: return 'primary';
    }
}

// Main Bettercap functions
window.startBettercapClick = function() {
    console.log('Start Bettercap clicked');
    const modal = new bootstrap.Modal(document.getElementById('interfaceModal'));
    modal.show();
};

window.stopBettercapClick = async function() {
    console.log('Stop Bettercap clicked');
    showNotification('Stopping Bettercap...', 'info');
    
    const result = await apiCall('/stop', 'POST');
    
    if (result.success) {
        showNotification('Bettercap stopped successfully', 'success');
        BetterMITM.isRunning = false;
        updateBettercapStatus(false);
        stopStatusRefresh();
    } else {
        showNotification('Failed to stop Bettercap: ' + result.error, 'error');
    }
};

window.startBettercapWithInterface = async function() {
    const interfaceSelect = document.getElementById('interface-select');
    if (!interfaceSelect || !interfaceSelect.value) {
        showNotification('Please select a network interface', 'error');
        return;
    }
    
    const selectedInterface = interfaceSelect.value;
    showNotification(`Starting Bettercap on ${selectedInterface}...`, 'info');
    
    // Hide modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('interfaceModal'));
    if (modal) modal.hide();
    
    // Start Bettercap
    const result = await apiCall('/start', 'POST', {
        interface: selectedInterface
    });
    
    if (result.success) {
        showNotification(`Bettercap started on ${selectedInterface}`, 'success');
        BetterMITM.isRunning = true;
        BetterMITM.currentInterface = selectedInterface;
        updateBettercapStatus(true, selectedInterface);
        startStatusRefresh();
    } else {
        showNotification('Failed to start Bettercap: ' + result.error, 'error');
    }
};

window.showSudoModal = function() {
    const interfaceSelect = document.getElementById('interface-select');
    if (!interfaceSelect || !interfaceSelect.value) {
        showNotification('Please select an interface first', 'error');
        return;
    }
    
    // Update sudo modal with selected interface
    const interfaceDisplay = document.getElementById('selected-interface-name');
    if (interfaceDisplay) {
        interfaceDisplay.textContent = interfaceSelect.value;
    }
    
    // Show sudo modal
    const interfaceModal = bootstrap.Modal.getInstance(document.getElementById('interfaceModal'));
    if (interfaceModal) interfaceModal.hide();
    
    const sudoModal = new bootstrap.Modal(document.getElementById('sudoModal'));
    sudoModal.show();
};

window.startBettercapWithSudo = async function() {
    const sudoPassword = document.getElementById('sudo-password').value;
    const interfaceSelect = document.getElementById('interface-select');
    
    if (!sudoPassword.trim()) {
        showNotification('Please enter sudo password', 'error');
        return;
    }
    
    if (!interfaceSelect || !interfaceSelect.value) {
        showNotification('Interface not selected', 'error');
        return;
    }
    
    const selectedInterface = interfaceSelect.value;
    showNotification(`Starting Bettercap with sudo on ${selectedInterface}...`, 'info');
    
    // Hide modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('sudoModal'));
    if (modal) modal.hide();
    
    // Start with sudo
    const result = await apiCall('/start', 'POST', {
        interface: selectedInterface,
        sudo_password: sudoPassword
    });
    
    // Clear password
    document.getElementById('sudo-password').value = '';
    
    if (result.success) {
        showNotification(`Bettercap started with sudo on ${selectedInterface}`, 'success');
        BetterMITM.isRunning = true;
        BetterMITM.currentInterface = selectedInterface;
        updateBettercapStatus(true, selectedInterface);
        startStatusRefresh();
    } else {
        showNotification('Failed to start Bettercap with sudo: ' + result.error, 'error');
    }
};

// Network functions
window.startNetworkScan = async function() {
    console.log('Start network scan clicked');
    
    if (!BetterMITM.isRunning) {
        showNotification('Please start Bettercap first', 'error');
        return;
    }
    
    showNotification('Starting network scan...', 'info');
    
    const result = await apiCall('/scan/start', 'POST', {
        scan_type: 'arp',
        target_range: null
    });
    
    if (result.success) {
        showNotification('Network scan started', 'success');
    } else {
        showNotification('Failed to start scan: ' + result.error, 'error');
    }
};

window.stopNetworkScan = async function() {
    console.log('Stop network scan clicked');
    
    const result = await apiCall('/scan/stop', 'POST');
    
    if (result.success) {
        showNotification('Network scan stopped', 'success');
    } else {
        showNotification('Failed to stop scan: ' + result.error, 'error');
    }
};

window.startARPSpoofAll = function() {
    if (confirm('This will start ARP spoofing against all discovered devices. Continue?')) {
        showNotification('ARP spoofing all - feature under development', 'warning');
    }
};

window.stopARPSpoof = async function() {
    const result = await apiCall('/arp/stop', 'POST');
    if (result.success) {
        showNotification('ARP spoofing stopped', 'success');
    } else {
        showNotification('Failed to stop ARP spoofing: ' + result.error, 'error');
    }
};

window.stopDNSSpoof = async function() {
    const result = await apiCall('/dns/stop', 'POST');
    if (result.success) {
        showNotification('DNS spoofing stopped', 'success');
    } else {
        showNotification('Failed to stop DNS spoofing: ' + result.error, 'error');
    }
};

window.stopProxy = async function() {
    const result = await apiCall('/proxy/stop', 'POST');
    if (result.success) {
        showNotification('HTTP proxy stopped', 'success');
    } else {
        showNotification('Failed to stop proxy: ' + result.error, 'error');
    }
};

window.stopSniffer = async function() {
    const result = await apiCall('/sniffer/stop', 'POST');
    if (result.success) {
        showNotification('Packet sniffer stopped', 'success');
    } else {
        showNotification('Failed to stop sniffer: ' + result.error, 'error');
    }
};

window.startPacketCapture = async function() {
    console.log('Start packet capture clicked');
    
    if (!BetterMITM.isRunning) {
        showNotification('Please start Bettercap first', 'error');
        return;
    }
    
    showNotification('Starting packet capture...', 'info');
    
    const result = await apiCall('/sniffer/start', 'POST', {
        protocols: ['tcp', 'udp'],
        bpf_filter: '',
        max_packets: 100
    });
    
    if (result.success) {
        showNotification('Packet capture started', 'success');
        clearCapture();
    } else {
        showNotification('Failed to start packet capture: ' + result.error, 'error');
    }
};

window.clearCapture = function() {
    const packetOutput = document.getElementById('packet-output');
    if (packetOutput) {
        packetOutput.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-search" style="font-size: 2rem;"></i>
                <p class="mt-2">No packets captured yet. Start packet capture to see network traffic.</p>
            </div>
        `;
    }
};

window.emergencyStop = async function() {
    if (!confirm('This will stop all active attacks and operations. Continue?')) {
        return;
    }
    
    showNotification('Emergency stop initiated...', 'warning');
    
    try {
        // Stop all attacks
        await Promise.all([
            apiCall('/arp/stop', 'POST'),
            apiCall('/dns/stop', 'POST'),
            apiCall('/proxy/stop', 'POST'),
            apiCall('/sniffer/stop', 'POST'),
            apiCall('/scan/stop', 'POST')
        ]);
        
        // Stop Bettercap
        await apiCall('/stop', 'POST');
        
        showNotification('Emergency stop completed', 'success');
        BetterMITM.isRunning = false;
        updateBettercapStatus(false);
        stopStatusRefresh();
        
    } catch (error) {
        showNotification('Emergency stop failed: ' + error.message, 'error');
    }
};

window.exportDevices = function() {
    showNotification('Export devices - feature under development', 'info');
};

window.targetCurrentDevice = function() {
    showNotification('Target device - feature under development', 'info');
};

// Console functions
window.executeCommand = async function() {
    const input = document.getElementById('console-input');
    if (!input) return;
    
    const command = input.value.trim();
    if (!command) return;
    
    console.log('Executing command:', command);
    
    const result = await apiCall('/command', 'POST', { command: command });
    
    // Add to console output
    const consoleOutput = document.getElementById('console-output');
    if (consoleOutput) {
        const timestamp = new Date().toLocaleTimeString();
        consoleOutput.innerHTML += `<div class="text-warning">[${timestamp}] bettercap> ${command}</div>`;
        
        if (result.success) {
            if (result.data) {
                consoleOutput.innerHTML += `<div class="text-info">[${timestamp}] ${JSON.stringify(result.data, null, 2)}</div>`;
            }
        } else {
            consoleOutput.innerHTML += `<div class="text-danger">[${timestamp}] Error: ${result.error}</div>`;
        }
        
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
    
    // Clear input
    input.value = '';
};

window.clearConsole = function() {
    const consoleOutput = document.getElementById('console-output');
    if (consoleOutput) {
        consoleOutput.innerHTML = 'Console cleared.\n';
    }
};

window.saveConsoleLog = function() {
    const consoleOutput = document.getElementById('console-output');
    if (!consoleOutput) return;
    
    const content = consoleOutput.textContent;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'bettermitm-console-' + new Date().toISOString().slice(0, 10) + '.log';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('Console log saved', 'success');
};

window.refreshAll = function() {
    console.log('Refresh all clicked');
    checkStatus();
    showNotification('Status refreshed', 'info');
};

window.cleanupAll = function() {
    emergencyStop();
};

window.diagnoseSystem = async function() {
    console.log('Running system diagnosis...');
    showNotification('Running system diagnosis...', 'info');
    
    try {
        const result = await apiCall('/diagnose');
        
        if (result.success) {
            const diagnosis = result.diagnosis;
            
            console.log('Diagnosis results:', diagnosis);
            
            let message = 'System Diagnosis:\n\n';
            message += `Bettercap Installed: ${diagnosis.bettercap_installed ? 'Yes' : 'No'}\n`;
            message += `Install Message: ${diagnosis.install_message}\n`;
            message += `Currently Running: ${diagnosis.is_running ? 'Yes' : 'No'}\n`;
            message += `Current Interface: ${diagnosis.current_interface || 'None'}\n`;
            message += `Available Interfaces: ${diagnosis.available_interfaces.length}\n`;
            
            if (diagnosis.api_accessible) {
                message += `API Status: Accessible (${diagnosis.api_status})\n`;
            } else if (diagnosis.api_error) {
                message += `API Status: Error - ${diagnosis.api_error}\n`;
            }
            
            alert(message);
            
            if (!diagnosis.bettercap_installed) {
                showNotification('Bettercap is not installed! Please install it first.', 'error');
            } else {
                showNotification('Diagnosis completed - check console for details', 'success');
            }
        } else {
            showNotification('Diagnosis failed: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Diagnosis error: ' + error.message, 'error');
    }
};

window.testAPIConnection = async function() {
    console.log('Testing API connection...');
    showNotification('Testing Bettercap API connection...', 'info');
    
    try {
        const result = await apiCall('/test');
        
        if (result.success) {
            const testResults = result.test_results;
            
            console.log('API test results:', testResults);
            
            let message = 'API Connection Test Results:\n\n';
            message += `Overall Success: ${testResults.success ? 'Yes' : 'No'}\n`;
            message += `Summary: ${testResults.summary || 'N/A'}\n\n`;
            
            if (testResults.results) {
                message += 'Individual Tests:\n';
                Object.entries(testResults.results).forEach(([test, success]) => {
                    message += `- ${test}: ${success ? 'PASS' : 'FAIL'}\n`;
                });
            }
            
            if (testResults.error) {
                message += `\nError: ${testResults.error}\n`;
            }
            
            alert(message);
            
            if (testResults.success) {
                showNotification('API connection test passed', 'success');
            } else {
                showNotification('API connection test failed', 'error');
            }
        } else {
            showNotification('API test failed: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('API test error: ' + error.message, 'error');
    }
};

// UI update functions
function updateBettercapStatus(running, interface = null) {
    const statusElement = document.getElementById('bettercap-status');
    const statusTextElement = document.getElementById('status-text');
    const interfaceElement = document.getElementById('current-interface');
    const startBtn = document.getElementById('start-bettercap-btn');
    const stopBtn = document.getElementById('stop-bettercap-btn');

    if (running) {
        if (statusElement) statusElement.className = 'bettercap-status running';
        if (statusTextElement) statusTextElement.textContent = 'Running';
        if (startBtn) startBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
        if (interfaceElement) interfaceElement.textContent = interface || 'Unknown';
    } else {
        if (statusElement) statusElement.className = 'bettercap-status stopped';
        if (statusTextElement) statusTextElement.textContent = 'Stopped';
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        if (interfaceElement) interfaceElement.textContent = 'None';
    }
}

// Status checking
async function checkStatus() {
    try {
        const result = await apiCall('/status');
        
        if (result.success) {
            BetterMITM.isRunning = result.bettercap_running;
            updateBettercapStatus(result.bettercap_running, result.current_interface);
            updateStatistics(result);
        }
    } catch (error) {
        console.error('Status check failed:', error);
    }
}

function updateStatistics(data) {
    const totalDevicesEl = document.getElementById('total-devices');
    const activeDevicesEl = document.getElementById('active-devices');
    const targetedDevicesEl = document.getElementById('targeted-devices');
    const underAttackEl = document.getElementById('under-attack');
    
    if (totalDevicesEl) totalDevicesEl.textContent = data.discovered_hosts?.length || 0;
    if (activeDevicesEl) activeDevicesEl.textContent = data.discovered_hosts?.filter(d => d.status === 'online').length || 0;
    if (targetedDevicesEl) targetedDevicesEl.textContent = data.discovered_hosts?.filter(d => d.targeted).length || 0;
    if (underAttackEl) underAttackEl.textContent = Object.keys(data.active_attacks || {}).length;
}

function startStatusRefresh() {
    stopStatusRefresh();
    BetterMITM.refreshInterval = setInterval(() => {
        if (BetterMITM.isRunning) {
            checkStatus();
        }
    }, 3000);
}

function stopStatusRefresh() {
    if (BetterMITM.refreshInterval) {
        clearInterval(BetterMITM.refreshInterval);
        BetterMITM.refreshInterval = null;
    }
}

console.log('BetterMITM Final script loaded successfully');