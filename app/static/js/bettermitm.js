/**
 * BetterMITM Web Interface JavaScript
 * Provides functionality for network security testing with Bettercap
 */

class BetterMITM {
    constructor() {
        console.log('BetterMITM constructor called');
        this.refreshInterval = 3000; // 3 seconds
        this.statusRefreshTimer = null;
        this.devicesRefreshTimer = null;
        this.packetCount = 0;
        this.currentDevices = {};
        this.isRunning = false;
        this.csrf_token = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
        console.log('BetterMITM constructed with CSRF token:', this.csrf_token);
    }

    static init() {
        console.log('BetterMITM.init() called');
        window.BetterMITM = new BetterMITM();
        console.log('BetterMITM instance created');
        window.BetterMITM.bindEvents();
        console.log('Events bound');
        window.BetterMITM.startAutoRefresh();
        window.BetterMITM.refreshStatus();
        console.log('BetterMITM initialization complete');
    }

    bindEvents() {
        console.log('bindEvents() called');
        // Bettercap control buttons
        const startBtn = document.getElementById('start-bettercap-btn');
        const stopBtn = document.getElementById('stop-bettercap-btn');
        
        console.log('Start button found:', !!startBtn);
        console.log('Stop button found:', !!stopBtn);
        
        if (startBtn) {
            console.log('Adding click listener to start button');
            startBtn.addEventListener('click', () => {
                console.log('Start button clicked!');
                this.showInterfaceModal();
            });
        } else {
            console.error('Start Bettercap button not found!');
        }

        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                console.log('Stop button clicked!');
                this.stopBettercap();
            });
        } else {
            console.error('Stop Bettercap button not found!');
        }

        // Form submissions
        document.getElementById('network-scan-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startNetworkScan();
        });

        document.getElementById('arp-spoof-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startARPSpoof();
        });

        document.getElementById('dns-spoof-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startDNSSpoof();
        });

        document.getElementById('proxy-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startProxy();
        });

        document.getElementById('sniffer-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startSniffer();
        });

        document.getElementById('device-target-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.targetDevice();
        });

        // Global functions
        window.startNetworkScan = () => this.startNetworkScan();
        window.stopNetworkScan = () => this.stopNetworkScan();
        window.startARPSpoofAll = () => this.startARPSpoofAll();
        window.stopARPSpoof = () => this.stopARPSpoof();
        window.stopDNSSpoof = () => this.stopDNSSpoof();
        window.stopProxy = () => this.stopProxy();
        window.stopSniffer = () => this.stopSniffer();
        window.clearCapture = () => this.clearCapture();
        window.emergencyStop = () => this.emergencyStop();
        window.exportDevices = () => this.exportDevices();
        window.startPacketCapture = () => this.startPacketCapture();
        window.targetCurrentDevice = () => this.targetCurrentDevice();
        window.startBettercapClick = () => {
            console.log('startBettercapClick called');
            this.showInterfaceModal();
        };
        window.stopBettercapClick = () => {
            console.log('stopBettercapClick called');
            this.stopBettercap();
        };
    }

    showInterfaceModal() {
        const modal = new bootstrap.Modal(document.getElementById('interfaceModal'));
        modal.show();
    }

    async startBettercap(interface = null, sudoPassword = null) {
        try {
            const requestData = { interface: interface };
            if (sudoPassword) {
                requestData.sudo_password = sudoPassword;
            }

            const response = await fetch('/bettermitm/api/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrf_token
                },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();

            if (result.success) {
                const message = result.sudo_used ? 
                    'Bettercap started successfully with sudo privileges' : 
                    'Bettercap started successfully';
                this.showNotification(message, 'success');
                this.isRunning = true;
                this.updateBettercapStatus(true, interface);
                this.startAutoRefresh();
                
                // Clear password field for security
                if (sudoPassword) {
                    document.getElementById('sudo-password').value = '';
                }
            } else {
                this.showNotification('Failed to start Bettercap: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error starting Bettercap: ' + error.message, 'error');
        }
    }

    async stopBettercap() {
        try {
            const response = await fetch('/bettermitm/api/stop', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                }
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Bettercap stopped successfully', 'success');
                this.isRunning = false;
                this.updateBettercapStatus(false);
                this.stopAutoRefresh();
            } else {
                this.showNotification('Failed to stop Bettercap: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error stopping Bettercap: ' + error.message, 'error');
        }
    }

    async refreshStatus() {
        try {
            const response = await fetch('/bettermitm/api/status');
            const result = await response.json();

            if (result.success) {
                this.isRunning = result.bettercap_running;
                this.updateBettercapStatus(result.bettercap_running, result.current_interface);
                this.updateStatistics(result);
                this.updateActiveAttacks(result.active_attacks);
            }
        } catch (error) {
            console.error('Error refreshing status:', error);
        }
    }

    async refreshDevices() {
        try {
            const response = await fetch('/bettermitm/api/hosts');
            const result = await response.json();

            if (result.success) {
                this.currentDevices = {};
                result.hosts.forEach(device => {
                    this.currentDevices[device.ip || device.mac] = device;
                });
                this.updateDevicesList(result.hosts);
                this.updateNetworkMap(result.hosts);
            }
        } catch (error) {
            console.error('Error refreshing devices:', error);
        }
    }

    async startNetworkScan() {
        try {
            const form = document.getElementById('network-scan-form');
            const formData = new FormData(form);
            
            const data = {
                scan_type: formData.get('scan_type'),
                target_range: formData.get('target_range')
            };

            const response = await fetch('/bettermitm/api/scan/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrf_token
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Network scan started', 'success');
                this.logToConsole('Network scan started: ' + result.scan_type);
            } else {
                this.showNotification('Failed to start scan: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error starting scan: ' + error.message, 'error');
        }
    }

    async stopNetworkScan() {
        try {
            const response = await fetch('/bettermitm/api/scan/stop', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Network scan stopped', 'success');
                this.logToConsole('Network scan stopped');
            } else {
                this.showNotification('Failed to stop scan: ' + result.message, 'error');
            }
        } catch (error) {
            this.showNotification('Error stopping scan: ' + error.message, 'error');
        }
    }

    async startARPSpoof() {
        try {
            const form = document.getElementById('arp-spoof-form');
            const response = await fetch('/bettermitm/api/arp/start', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: new FormData(form)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('ARP spoofing started', 'success');
                this.logToConsole('ARP spoofing attack started: ' + result.message);
            } else {
                this.showNotification('ARP spoofing failed: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error starting ARP spoof: ' + error.message, 'error');
        }
    }

    async stopARPSpoof() {
        try {
            const response = await fetch('/bettermitm/api/arp/stop', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showNotification('ARP spoofing stopped', 'success');
                this.logToConsole('ARP spoofing stopped');
            } else {
                this.showNotification('Failed to stop ARP spoof', 'error');
            }
        } catch (error) {
            this.showNotification('Error stopping ARP spoof: ' + error.message, 'error');
        }
    }

    async startDNSSpoof() {
        try {
            const form = document.getElementById('dns-spoof-form');
            const response = await fetch('/bettermitm/api/dns/start', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: new FormData(form)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('DNS spoofing started', 'success');
                this.logToConsole('DNS spoofing attack started: ' + result.message);
            } else {
                this.showNotification('DNS spoofing failed: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error starting DNS spoof: ' + error.message, 'error');
        }
    }

    async stopDNSSpoof() {
        try {
            const response = await fetch('/bettermitm/api/dns/stop', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showNotification('DNS spoofing stopped', 'success');
                this.logToConsole('DNS spoofing stopped');
            } else {
                this.showNotification('Failed to stop DNS spoof', 'error');
            }
        } catch (error) {
            this.showNotification('Error stopping DNS spoof: ' + error.message, 'error');
        }
    }

    async startProxy() {
        try {
            const form = document.getElementById('proxy-form');
            const response = await fetch('/bettermitm/api/proxy/start', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: new FormData(form)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('HTTP proxy started', 'success');
                this.logToConsole('HTTP proxy started: ' + result.message);
            } else {
                this.showNotification('Proxy failed: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error starting proxy: ' + error.message, 'error');
        }
    }

    async stopProxy() {
        try {
            const response = await fetch('/bettermitm/api/proxy/stop', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showNotification('HTTP proxy stopped', 'success');
                this.logToConsole('HTTP proxy stopped');
            } else {
                this.showNotification('Failed to stop proxy', 'error');
            }
        } catch (error) {
            this.showNotification('Error stopping proxy: ' + error.message, 'error');
        }
    }

    async startSniffer() {
        try {
            const form = document.getElementById('sniffer-form');
            const response = await fetch('/bettermitm/api/sniffer/start', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: new FormData(form)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Packet sniffer started', 'success');
                this.logToConsole('Packet capture started');
                this.clearCapture();
            } else {
                this.showNotification('Sniffer failed: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error starting sniffer: ' + error.message, 'error');
        }
    }

    async stopSniffer() {
        try {
            const response = await fetch('/bettermitm/api/sniffer/stop', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Packet sniffer stopped', 'success');
                this.logToConsole('Packet capture stopped');
            } else {
                this.showNotification('Failed to stop sniffer', 'error');
            }
        } catch (error) {
            this.showNotification('Error stopping sniffer: ' + error.message, 'error');
        }
    }

    async targetDevice() {
        try {
            const form = document.getElementById('device-target-form');
            const response = await fetch('/bettermitm/api/device/target', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrf_token
                },
                body: new FormData(form)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Device targeted successfully', 'success');
                this.refreshDevices();
            } else {
                this.showNotification('Device targeting failed: ' + result.error, 'error');
            }
        } catch (error) {
            this.showNotification('Error targeting device: ' + error.message, 'error');
        }
    }

    async executeCommand(command) {
        try {
            this.logToConsole('bettercap> ' + command, 'command');

            const response = await fetch('/bettermitm/api/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrf_token
                },
                body: JSON.stringify({ command: command })
            });

            const result = await response.json();

            if (result.success) {
                if (result.output) {
                    this.logToConsole(JSON.stringify(result.output, null, 2), 'output');
                }
            } else {
                this.logToConsole('Error: ' + result.error, 'error');
            }
        } catch (error) {
            this.logToConsole('Request failed: ' + error.message, 'error');
        }
    }

    updateBettercapStatus(running, interface = null) {
        const statusElement = document.getElementById('bettercap-status');
        const statusTextElement = document.getElementById('status-text');
        const interfaceElement = document.getElementById('current-interface');
        const startBtn = document.getElementById('start-bettercap-btn');
        const stopBtn = document.getElementById('stop-bettercap-btn');

        if (running) {
            statusElement.className = 'bettercap-status running';
            statusTextElement.textContent = 'Running';
            startBtn.disabled = true;
            stopBtn.disabled = false;
            interfaceElement.textContent = interface || 'Unknown';
        } else {
            statusElement.className = 'bettercap-status stopped';
            statusTextElement.textContent = 'Stopped';
            startBtn.disabled = false;
            stopBtn.disabled = true;
            interfaceElement.textContent = 'None';
        }
    }

    updateStatistics(data) {
        document.getElementById('total-devices').textContent = data.discovered_hosts.length || 0;
        document.getElementById('active-devices').textContent = 
            data.discovered_hosts.filter(d => d.status === 'online').length || 0;
        document.getElementById('targeted-devices').textContent = 
            data.discovered_hosts.filter(d => d.targeted).length || 0;
        document.getElementById('under-attack').textContent = 
            data.discovered_hosts.filter(d => Object.keys(d.attacks || {}).some(k => d.attacks[k].active)).length || 0;
    }

    updateActiveAttacks(attacks) {
        const attackCount = Object.keys(attacks).length;
        document.getElementById('active-attacks-count').textContent = attackCount;
    }

    updateDevicesList(devices) {
        const container = document.getElementById('devices-list');
        
        if (devices.length === 0) {
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
                <div class="device-card ${targetedClass} p-3 mb-2" onclick="showDeviceDetails('${device.ip}')">
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
                        <div>
                            ${attacksActive ? '<span class="attack-indicator active"></span>' : ''}
                            <button class="btn btn-outline-primary btn-sm" onclick="event.stopPropagation(); targetDeviceQuick('${device.ip}')">
                                <i class="bi bi-crosshair"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    updateNetworkMap(devices) {
        const container = document.getElementById('network-map');
        
        if (devices.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-diagram-3" style="font-size: 3rem;"></i>
                    <h4 class="mt-3">Network Map</h4>
                    <p>Start Bettercap and begin network discovery to see devices</p>
                </div>
            `;
            return;
        }

        // Simple network visualization
        let html = '<div class="row">';
        devices.forEach((device, index) => {
            if (index % 4 === 0 && index > 0) html += '</div><div class="row mt-2">';
            
            const statusClass = device.status === 'online' ? 'success' : 'secondary';
            const targetedClass = device.targeted ? 'danger' : statusClass;
            
            html += `
                <div class="col-3 text-center mb-2">
                    <div class="card border-${targetedClass}" onclick="showDeviceDetails('${device.ip}')">
                        <div class="card-body p-2">
                            <i class="bi bi-${this.getDeviceIcon(device.device_type)} text-${targetedClass}" style="font-size: 1.5rem;"></i>
                            <div class="mt-1">
                                <small class="d-block">${device.hostname || device.ip}</small>
                                <small class="text-muted">${device.vendor || 'Unknown'}</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    getDeviceIcon(deviceType) {
        const icons = {
            'router': 'router',
            'desktop': 'pc-display',
            'laptop': 'laptop',
            'mobile': 'phone',
            'server': 'server',
            'printer': 'printer',
            'camera': 'camera',
            'iot': 'thermometer'
        };
        return icons[deviceType] || 'device-ssd';
    }

    logToConsole(message, type = 'info') {
        const console = document.getElementById('console-output');
        const timestamp = new Date().toLocaleTimeString();
        
        let cssClass = 'text-light';
        if (type === 'error') cssClass = 'text-danger';
        else if (type === 'success') cssClass = 'text-success';
        else if (type === 'command') cssClass = 'text-warning';
        else if (type === 'output') cssClass = 'text-info';

        const logEntry = `<div class="${cssClass}">[${timestamp}] ${message}</div>`;
        console.innerHTML += logEntry;
        console.scrollTop = console.scrollHeight;
    }

    clearConsole() {
        document.getElementById('console-output').innerHTML = 'Console cleared.\n';
    }

    clearCapture() {
        document.getElementById('packet-output').innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-search" style="font-size: 2rem;"></i>
                <p class="mt-2">No packets captured yet. Start packet capture to see network traffic.</p>
            </div>
        `;
        this.packetCount = 0;
        document.getElementById('packet-count').textContent = '0 packets';
    }

    startAutoRefresh() {
        this.stopAutoRefresh();
        
        this.statusRefreshTimer = setInterval(() => {
            if (this.isRunning) {
                this.refreshStatus();
            }
        }, this.refreshInterval);

        this.devicesRefreshTimer = setInterval(() => {
            if (this.isRunning) {
                this.refreshDevices();
            }
        }, this.refreshInterval * 2);
    }

    stopAutoRefresh() {
        if (this.statusRefreshTimer) {
            clearInterval(this.statusRefreshTimer);
            this.statusRefreshTimer = null;
        }
        
        if (this.devicesRefreshTimer) {
            clearInterval(this.devicesRefreshTimer);
            this.devicesRefreshTimer = null;
        }
    }

    async emergencyStop() {
        try {
            // Stop all attacks and operations
            await Promise.all([
                this.stopARPSpoof(),
                this.stopDNSSpoof(), 
                this.stopProxy(),
                this.stopSniffer(),
                this.stopNetworkScan()
            ]);
            
            // Stop Bettercap
            await this.stopBettercap();
            
            this.showNotification('Emergency stop completed', 'success');
            this.logToConsole('Emergency stop - all operations terminated', 'error');
            
        } catch (error) {
            this.showNotification('Emergency stop failed: ' + error.message, 'error');
        }
    }

    showNotification(message, type = 'info') {
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

    saveConsoleLog() {
        const content = document.getElementById('console-output').textContent;
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = 'bettermitm-console-' + new Date().toISOString().slice(0, 10) + '.log';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    exportDevices() {
        const devices = Object.values(this.currentDevices);
        const content = JSON.stringify(devices, null, 2);
        const blob = new Blob([content], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = 'bettermitm-devices-' + new Date().toISOString().slice(0, 10) + '.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Global helper functions
window.showDeviceDetails = function(ip) {
    const device = window.BetterMITM.currentDevices[ip];
    if (!device) return;

    const modal = document.getElementById('deviceModal');
    const modalBody = document.getElementById('device-modal-body');

    let attacksList = '';
    if (device.attacks) {
        Object.entries(device.attacks).forEach(([type, info]) => {
            const status = info.active ? 'text-danger' : 'text-muted';
            attacksList += `<li class="${status}">${type}: ${info.active ? 'Active' : 'Inactive'}</li>`;
        });
    }

    modalBody.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <h6>Basic Information</h6>
                <table class="table table-sm">
                    <tr><td>IP Address:</td><td>${device.ip}</td></tr>
                    <tr><td>MAC Address:</td><td>${device.mac || 'Unknown'}</td></tr>
                    <tr><td>Hostname:</td><td>${device.hostname || 'Unknown'}</td></tr>
                    <tr><td>Vendor:</td><td>${device.vendor || 'Unknown'}</td></tr>
                    <tr><td>OS:</td><td>${device.os || 'Unknown'}</td></tr>
                    <tr><td>Status:</td><td><span class="badge bg-${device.status === 'online' ? 'success' : 'secondary'}">${device.status}</span></td></tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6>Network Statistics</h6>
                <table class="table table-sm">
                    <tr><td>Packets Sent:</td><td>${device.packets_sent || 0}</td></tr>
                    <tr><td>Packets Received:</td><td>${device.packets_received || 0}</td></tr>
                    <tr><td>Bytes Sent:</td><td>${device.bytes_sent || 0}</td></tr>
                    <tr><td>Bytes Received:</td><td>${device.bytes_received || 0}</td></tr>
                    <tr><td>First Seen:</td><td>${device.first_seen ? new Date(device.first_seen).toLocaleString() : 'Unknown'}</td></tr>
                    <tr><td>Last Seen:</td><td>${device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Unknown'}</td></tr>
                </table>
                
                ${attacksList ? '<h6 class="mt-3">Active Attacks</h6><ul>' + attacksList + '</ul>' : ''}
            </div>
        </div>
    `;

    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Store current device for targeting
    modal.setAttribute('data-device-ip', ip);
};

window.targetDeviceQuick = function(ip) {
    document.getElementById('device_ip').value = ip;
    document.getElementById('device-target-form').dispatchEvent(new Event('submit'));
};

window.targetCurrentDevice = function() {
    const modal = document.getElementById('deviceModal');
    const ip = modal.getAttribute('data-device-ip');
    if (ip) {
        targetDeviceQuick(ip);
        bootstrap.Modal.getInstance(modal).hide();
    }
};

window.startARPSpoofAll = function() {
    if (confirm('This will start ARP spoofing against all discovered devices. Continue?')) {
        window.BetterMITM.showNotification('ARP spoofing all devices - feature not implemented yet', 'warning');
    }
};

window.startPacketCapture = function() {
    // Quick packet capture start
    document.getElementById('sniffer-form').dispatchEvent(new Event('submit'));
};

// Interface selection functions
window.startBettercapWithInterface = async function() {
    const selectedInterface = document.getElementById('interface-select')?.value;
    
    if (!selectedInterface) {
        window.BetterMITM.showNotification('Please select an interface', 'error');
        return;
    }
    
    // Hide the interface modal
    const interfaceModal = bootstrap.Modal.getInstance(document.getElementById('interfaceModal'));
    if (interfaceModal) {
        interfaceModal.hide();
    }
    
    // Start Bettercap without sudo
    await window.BetterMITM.startBettercap(selectedInterface);
};

// Sudo authentication functions
window.showSudoModal = function() {
    const selectedInterface = document.getElementById('interface-select')?.value;
    
    if (!selectedInterface) {
        window.BetterMITM.showNotification('Please select an interface first', 'error');
        return;
    }
    
    // Update sudo modal with selected interface
    const interfaceDisplay = document.getElementById('selected-interface-name');
    if (interfaceDisplay) {
        interfaceDisplay.textContent = selectedInterface;
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
    const sudoPassword = document.getElementById('sudo-password').value;
    const selectedInterface = document.getElementById('interface-select')?.value;
    
    if (!sudoPassword.trim()) {
        window.BetterMITM.showNotification('Please enter sudo password', 'error');
        return;
    }
    
    if (!selectedInterface) {
        window.BetterMITM.showNotification('Interface not selected', 'error');
        return;
    }
    
    // Hide the sudo modal
    const sudoModal = bootstrap.Modal.getInstance(document.getElementById('sudoModal'));
    if (sudoModal) {
        sudoModal.hide();
    }
    
    // Start Bettercap with sudo
    await window.BetterMITM.startBettercap(selectedInterface, sudoPassword);
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', BetterMITM.init);