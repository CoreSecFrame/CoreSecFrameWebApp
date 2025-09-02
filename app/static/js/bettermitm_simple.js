/**
 * Simplified BetterMITM JavaScript for testing
 */

console.log('Simple BetterMITM script loading...');

// Simple global functions for testing
window.startBettercapClick = function() {
    console.log('startBettercapClick called - Simple version');
    alert('Start Bettercap clicked! (Simple version)');
    
    // Try to show interface modal
    try {
        const modal = new bootstrap.Modal(document.getElementById('interfaceModal'));
        modal.show();
    } catch (error) {
        console.error('Error showing modal:', error);
    }
};

window.stopBettercapClick = function() {
    console.log('stopBettercapClick called - Simple version');
    alert('Stop Bettercap clicked! (Simple version)');
};

window.startBettercapWithInterface = async function() {
    console.log('startBettercapWithInterface called');
    
    const interfaceSelect = document.getElementById('interface-select');
    if (!interfaceSelect) {
        console.error('Interface select not found!');
        alert('Interface selection not found');
        return;
    }
    
    const selectedInterface = interfaceSelect.value;
    if (!selectedInterface) {
        alert('Please select a network interface');
        return;
    }
    
    console.log('Selected interface:', selectedInterface);
    
    // Hide modal
    const interfaceModal = bootstrap.Modal.getInstance(document.getElementById('interfaceModal'));
    if (interfaceModal) {
        interfaceModal.hide();
    }
    
    // Make API call to start Bettercap
    try {
        const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
        
        const response = await fetch('/bettermitm/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                interface: selectedInterface
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Bettercap started successfully on ' + selectedInterface);
            console.log('Bettercap started:', result);
        } else {
            alert('Failed to start Bettercap: ' + result.error);
            console.error('Bettercap start failed:', result);
        }
    } catch (error) {
        console.error('Error starting Bettercap:', error);
        alert('Error starting Bettercap: ' + error.message);
    }
};

window.showSudoModal = function() {
    console.log('showSudoModal called');
    
    const interfaceSelect = document.getElementById('interface-select');
    if (!interfaceSelect || !interfaceSelect.value) {
        alert('Please select an interface first');
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
        alert('Please enter sudo password');
        return;
    }
    
    if (!interfaceSelect || !interfaceSelect.value) {
        alert('Interface not selected');
        return;
    }
    
    const selectedInterface = interfaceSelect.value;
    
    // Hide sudo modal
    const sudoModal = bootstrap.Modal.getInstance(document.getElementById('sudoModal'));
    if (sudoModal) {
        sudoModal.hide();
    }
    
    // Make API call with sudo
    try {
        const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
        
        const response = await fetch('/bettermitm/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                interface: selectedInterface,
                sudo_password: sudoPassword
            })
        });
        
        const result = await response.json();
        
        // Clear password field
        document.getElementById('sudo-password').value = '';
        
        if (result.success) {
            alert('Bettercap started successfully with sudo privileges on ' + selectedInterface);
            console.log('Bettercap started with sudo:', result);
        } else {
            alert('Failed to start Bettercap with sudo: ' + result.error);
            console.error('Bettercap sudo start failed:', result);
        }
    } catch (error) {
        console.error('Error starting Bettercap with sudo:', error);
        alert('Error starting Bettercap with sudo: ' + error.message);
    }
};

console.log('Simple BetterMITM script loaded successfully');
console.log('Functions defined:', {
    startBettercapClick: typeof window.startBettercapClick,
    stopBettercapClick: typeof window.stopBettercapClick
});