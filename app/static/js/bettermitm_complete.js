/**
 * BetterMITM Complete JavaScript Implementation
 * Provides full functionality for network security testing with Bettercap
 */

console.log('BetterMITM Complete script loading...');

// Global state management
const BetterMITMState = {
    isRunning: false,
    currentInterface: null,
    refreshInterval: 3000,
    statusTimer: null,
    devicesTimer: null,
    csrf_token: ''
};

// Initialize CSRF token
document.addEventListener('DOMContentLoaded', function() {
    BetterMITMState.csrf_token = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    console.log('CSRF token initialized:', BetterMITMState.csrf_token);
    
    // Start auto-refresh if Bettercap is running
    startAutoRefresh();
    checkStatus();
});

// API Helper Functions
async function makeAPICall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'X-CSRFToken': BetterMITMState.csrf_token,
                'X-Requested-With': 'XMLHttpRequest'
            }
        };
        
        if (data) {
            if (data instanceof FormData) {
                options.body = data;
            } else {
                options.headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(data);
            }
        }
        
        const response = await fetch(`/bettermitm/api${endpoint}`, options);
        const result = await response.json();
        
        return result;
    } catch (error) {
        console.error('API call failed:', error);
        showNotification('API call failed: ' + error.message, 'error');
        return { success: false, error: error.message };
    }
}

function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Create toast notification
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'primary'} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    // Add to toast container (create if needed)
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.innerHTML = toastHtml;
    const toast = new bootstrap.Toast(toastContainer.querySelector('.toast'));
    toast.show();
}

// Main Bettercap Control Functions
window.startBettercapClick = function() {
    console.log('startBettercapClick called');
    showInterfaceModal();
};

window.stopBettercapClick = async function() {
    console.log('stopBettercapClick called');
    
    const result = await makeAPICall('/stop', 'POST');
    
    if (result.success) {
        showNotification('Bettercap stopped successfully', 'success');
        BetterMITMState.isRunning = false;
        updateBettercapStatus(false);
        stopAutoRefresh();
    } else {
        showNotification('Failed to stop Bettercap: ' + result.error, 'error');
    }
};

function showInterfaceModal() {
    const modal = new bootstrap.Modal(document.getElementById('interfaceModal'));
    modal.show();
}

window.startBettercapWithInterface = async function() {
    console.log('startBettercapWithInterface called');
    
    const interfaceSelect = document.getElementById('interface-select');
    if (!interfaceSelect || !interfaceSelect.value) {
        showNotification('Please select a network interface', 'error');
        return;
    }
    
    const selectedInterface = interfaceSelect.value;
    console.log('Selected interface:', selectedInterface);
    
    // Hide modal
    const interfaceModal = bootstrap.Modal.getInstance(document.getElementById('interfaceModal'));
    if (interfaceModal) {
        interfaceModal.hide();
    }
    
    // Start Bettercap
    const result = await makeAPICall('/start', 'POST', {
        interface: selectedInterface
    });
    
    if (result.success) {
        showNotification('Bettercap started successfully on ' + selectedInterface, 'success');
        BetterMITMState.isRunning = true;
        BetterMITMState.currentInterface = selectedInterface;
        updateBettercapStatus(true, selectedInterface);
        startAutoRefresh();
    } else {
        showNotification('Failed to start Bettercap: ' + result.error, 'error');
    }
};

window.showSudoModal = function() {
    console.log('showSudoModal called');
    
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
    
    // Hide interface modal and show sudo modal
    const interfaceModal = bootstrap.Modal.getInstance(document.getElementById('interfaceModal'));
    if (interfaceModal) {
        interfaceModal.hide();
    }
    
    const sudoModal = new bootstrap.Modal(document.getElementById('sudoModal'));
    sudoModal.show();
};

window.startBettercapWithSudo = async function() {
    console.log('startBettercapWithSudo called');
    
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
    
    // Hide sudo modal
    const sudoModal = bootstrap.Modal.getInstance(document.getElementById('sudoModal'));
    if (sudoModal) {
        sudoModal.hide();
    }
    
    // Start Bettercap with sudo
    const result = await makeAPICall('/start', 'POST', {
        interface: selectedInterface,
        sudo_password: sudoPassword
    });
    
    // Clear password field
    document.getElementById('sudo-password').value = '';
    
    if (result.success) {
        showNotification('Bettercap started successfully with sudo privileges on ' + selectedInterface, 'success');
        BetterMITMState.isRunning = true;
        BetterMITMState.currentInterface = selectedInterface;
        updateBettercapStatus(true, selectedInterface);
        startAutoRefresh();
    } else {
        showNotification('Failed to start Bettercap with sudo: ' + result.error, 'error');
    }
};

// Network Scanning Functions
window.startNetworkScan = async function() {
    console.log('startNetworkScan called');
    
    // Check if Bettercap is running
    if (!BetterMITMState.isRunning) {
        showNotification('Please start Bettercap first before scanning', 'error');
        return;
    }
    
    const result = await makeAPICall('/scan/start', 'POST', {
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
    console.log('stopNetworkScan called');
    
    const result = await makeAPICall('/scan/stop', 'POST');
    
    if (result.success) {
        showNotification('Network scan stopped', 'success');
    } else {
        showNotification('Failed to stop scan', 'error');
    }
};

// Attack Functions
window.startARPSpoofAll = function() {
    console.log('startARPSpoofAll called');
    if (confirm('This will start ARP spoofing against all discovered devices. Continue?')) {
        showNotification('ARP spoofing all devices - feature under development', 'warning');
    }
};

window.stopARPSpoof = async function() {
    console.log('stopARPSpoof called');
    
    const result = await makeAPICall('/arp/stop', 'POST');
    
    if (result.success) {
        showNotification('ARP spoofing stopped', 'success');
    } else {
        showNotification('Failed to stop ARP spoofing', 'error');
    }
};

window.stopDNSSpoof = async function() {
    console.log('stopDNSSpoof called');
    
    const result = await makeAPICall('/dns/stop', 'POST');
    
    if (result.success) {
        showNotification('DNS spoofing stopped', 'success');
    } else {
        showNotification('Failed to stop DNS spoofing', 'error');
    }
};

window.stopProxy = async function() {
    console.log('stopProxy called');
    
    const result = await makeAPICall('/proxy/stop', 'POST');
    
    if (result.success) {
        showNotification('HTTP proxy stopped', 'success');
    } else {
        showNotification('Failed to stop proxy', 'error');
    }
};

window.stopSniffer = async function() {
    console.log('stopSniffer called');
    
    const result = await makeAPICall('/sniffer/stop', 'POST');
    
    if (result.success) {
        showNotification('Packet sniffer stopped', 'success');
    } else {
        showNotification('Failed to stop sniffer', 'error');
    }
};

window.startPacketCapture = function() {
    console.log('startPacketCapture called');
    showNotification('Starting packet capture...', 'info');
    
    // Submit the sniffer form
    const form = document.getElementById('sniffer-form');
    if (form) {
        form.dispatchEvent(new Event('submit'));
    }
};

window.clearCapture = function() {
    console.log('clearCapture called');
    document.getElementById('packet-output').innerHTML = `
        <div class="text-center text-muted py-5">
            <i class="bi bi-search" style="font-size: 2rem;"></i>
            <p class="mt-2">No packets captured yet. Start packet capture to see network traffic.</p>
        </div>
    `;
};

window.emergencyStop = async function() {
    console.log('emergencyStop called');
    
    if (!confirm('This will stop all active attacks and operations. Continue?')) {
        return;
    }
    
    showNotification('Emergency stop initiated...', 'warning');
    
    try {
        // Stop all attacks in parallel
        await Promise.all([
            makeAPICall('/arp/stop', 'POST'),
            makeAPICall('/dns/stop', 'POST'),
            makeAPICall('/proxy/stop', 'POST'),
            makeAPICall('/sniffer/stop', 'POST'),
            makeAPICall('/scan/stop', 'POST')
        ]);
        
        // Stop Bettercap
        await makeAPICall('/stop', 'POST');
        
        showNotification('Emergency stop completed', 'success');
        BetterMITMState.isRunning = false;
        updateBettercapStatus(false);
        stopAutoRefresh();
        
    } catch (error) {
        showNotification('Emergency stop failed: ' + error.message, 'error');
    }
};

// Device Management Functions
window.exportDevices = function() {
    console.log('exportDevices called');
    showNotification('Exporting devices - feature under development', 'info');
};

window.targetCurrentDevice = function() {
    console.log('targetCurrentDevice called');
    showNotification('Device targeting - feature under development', 'info');
};

// Status and UI Update Functions
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

async function checkStatus() {
    try {
        const result = await makeAPICall('/status');
        
        if (result.success) {
            BetterMITMState.isRunning = result.bettercap_running;
            updateBettercapStatus(result.bettercap_running, result.current_interface);
            updateStatistics(result);
            updateActiveAttacks(result.active_attacks);
        }
    } catch (error) {
        console.error('Error checking status:', error);
    }
}

async function refreshDevices() {
    try {
        const result = await makeAPICall('/hosts');
        
        if (result.success) {
            updateDevicesList(result.hosts);
        }
    } catch (error) {
        console.error('Error refreshing devices:', error);
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
    if (underAttackEl) underAttackEl.textContent = data.discovered_hosts?.filter(d => Object.keys(d.attacks || {}).some(k => d.attacks[k].active)).length || 0;
}

function updateActiveAttacks(attacks) {
    const attackCountEl = document.getElementById('active-attacks-count');
    if (attackCountEl) {
        attackCountEl.textContent = Object.keys(attacks || {}).length;
    }
}

function updateDevicesList(devices) {
    const container = document.getElementById('devices-list');
    if (!container) return;
    
    if (!devices || devices.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-devices" style="font-size: 3rem;"></i>
                <h4 class="mt-3">No Devices Found</h4>
                <p>Start a network scan to discover devices</p>
            </div>
        `;
        return;
    }

    let html = '';
    devices.forEach(device => {
        const statusClass = device.status === 'online' ? 'online' : 'offline';
        const targetedClass = device.targeted ? 'targeted' : '';
        const attacksActive = Object.values(device.attacks || {}).some(a => a.active);
        
        html += `
            <div class="device-card ${targetedClass} p-3 mb-2">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="d-flex align-items-center">
                            <span class="status-indicator ${statusClass}"></span>
                            <strong>${device.hostname || device.ip}</strong>
                            ${device.targeted ? '<span class="badge bg-danger ms-2">TARGETED</span>' : ''}
                        </div>
                        <small class="text-muted">
                            ${device.ip} • ${device.mac || 'Unknown MAC'} • ${device.vendor || 'Unknown Vendor'}
                        </small>
                        ${attacksActive ? '<div class="mt-1"><small class="text-danger">Under Attack</small></div>' : ''}
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Auto-refresh functions
function startAutoRefresh() {
    stopAutoRefresh();
    
    BetterMITMState.statusTimer = setInterval(() => {
        if (BetterMITMState.isRunning) {
            checkStatus();
        }
    }, BetterMITMState.refreshInterval);

    BetterMITMState.devicesTimer = setInterval(() => {
        if (BetterMITMState.isRunning) {
            refreshDevices();
        }
    }, BetterMITMState.refreshInterval * 2);
    
    console.log('Auto-refresh started');
}

function stopAutoRefresh() {
    if (BetterMITMState.statusTimer) {
        clearInterval(BetterMITMState.statusTimer);
        BetterMITMState.statusTimer = null;
    }
    
    if (BetterMITMState.devicesTimer) {
        clearInterval(BetterMITMState.devicesTimer);
        BetterMITMState.devicesTimer = null;
    }
    
    console.log('Auto-refresh stopped');
}

// Console and utility functions
window.refreshAll = function() {
    console.log('refreshAll called');
    checkStatus();
    refreshDevices();
    showNotification('Refreshed status and devices', 'info');
};

window.cleanupAll = function() {
    console.log('cleanupAll called');
    emergencyStop();
};

window.executeCommand = async function() {
    const input = document.getElementById('console-input');
    if (!input) return;
    
    const command = input.value.trim();
    if (!command) return;
    
    console.log('Executing command:', command);
    
    try {
        const result = await makeAPICall('/command', 'POST', {
            command: command
        });
        
        // Add command to console output
        const consoleOutput = document.getElementById('console-output');
        if (consoleOutput) {
            const timestamp = new Date().toLocaleTimeString();
            consoleOutput.innerHTML += `<div class="text-warning">[${timestamp}] bettercap> ${command}</div>`;
            
            if (result.success) {
                if (result.output) {
                    consoleOutput.innerHTML += `<div class="text-info">[${timestamp}] ${JSON.stringify(result.output, null, 2)}</div>`;
                }
            } else {
                consoleOutput.innerHTML += `<div class="text-danger">[${timestamp}] Error: ${result.error}</div>`;
            }
            
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        
        // Clear input
        input.value = '';
        
    } catch (error) {
        console.error('Error executing command:', error);
        showNotification('Command execution failed: ' + error.message, 'error');
    }
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

// Form submission handlers
document.addEventListener('DOMContentLoaded', function() {
    // Network scan form
    const networkScanForm = document.getElementById('network-scan-form');
    if (networkScanForm) {
        networkScanForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await startNetworkScan();
        });
    }
    
    // Sniffer form
    const snifferForm = document.getElementById('sniffer-form');
    if (snifferForm) {
        snifferForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            showNotification('Starting packet sniffer...', 'info');
            
            const result = await makeAPICall('/sniffer/start', 'POST', {
                protocols: ['tcp', 'udp'],
                bpf_filter: '',
                max_packets: 100
            });
            
            if (result.success) {
                showNotification('Packet sniffer started', 'success');
                clearCapture();
            } else {
                showNotification('Failed to start sniffer: ' + result.error, 'error');
            }
        });
    }
    
    // Console input handler
    const consoleInput = document.getElementById('console-input');
    if (consoleInput) {
        consoleInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                executeCommand();
            }
        });
    }
});

console.log('BetterMITM Complete script loaded successfully');
console.log('All functions defined and ready');