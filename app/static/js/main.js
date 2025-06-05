// app/static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Auto-focus on search inputs
    const searchInputs = document.querySelectorAll('input[type="search"], input[name="q"]');
    if (searchInputs.length > 0) {
        searchInputs[0].focus();
    }
    
    // Add confirm dialog for dangerous actions
    const dangerForms = document.querySelectorAll('form[data-confirm]');
    dangerForms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            const confirmMessage = this.getAttribute('data-confirm');
            if (!confirm(confirmMessage)) {
                event.preventDefault();
            }
        });
    });
    
    // Handle live updates for terminal sessions
    const terminalOutput = document.getElementById('terminal-output');
    if (terminalOutput) {
        // Auto-scroll to bottom of terminal
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }
    
    // Handle copy to clipboard buttons
    const copyButtons = document.querySelectorAll('.btn-copy');
    copyButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy');
            const tempTextarea = document.createElement('textarea');
            tempTextarea.value = textToCopy;
            document.body.appendChild(tempTextarea);
            tempTextarea.select();
            document.execCommand('copy');
            document.body.removeChild(tempTextarea);
            
            // Show copied notification
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="bi bi-check"></i> Copied!';
            setTimeout(() => {
                this.innerHTML = originalText;
            }, 2000);
        });
    });

    // Theme Switching Functionality
    /**
     * Updates the application theme (light/dark).
     * Sets 'data-theme' on documentElement, stores in localStorage, updates toggle icon, and logs.
     * @param {string} theme - The theme to apply ('light' or 'dark').
     */
    function updateTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);

        const themeIcon = document.getElementById('theme-icon');
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'bi bi-sun-fill';
            } else {
                themeIcon.className = 'bi bi-moon-fill';
            }
        }
        
        console.log(`Theme updated to: ${theme}`); // For debugging
        
        // Apply theme to dynamically created modals
        applyThemeToModals();
    }

    /**
     * Applies the selected accent color to the application.
     * Sets the '--current-accent' CSS variable on the documentElement and stores the preference in localStorage.
     * @param {string} color - The accent color value to apply (e.g., 'var(--accent-red)' or a hex code).
     */
    function applyAccentColor(color) {
        document.documentElement.style.setProperty('--current-accent', color);
        localStorage.setItem('accentColor', color);
        console.log(`Accent color applied: ${color}`); // For debugging
    }

    // On page load, apply saved theme and accent color, or defaults.
    const savedTheme = localStorage.getItem('theme') || 'light'; // Default to light theme
    const savedAccentColor = localStorage.getItem('accentColor') || 'var(--accent-default-blue)'; // Default to Fluent blue

    updateTheme(savedTheme); // Use the new function
    applyAccentColor(savedAccentColor);

    // Update UI elements on profile page if they exist
    const themeLightRadio = document.getElementById('themeLight');
    const themeDarkRadio = document.getElementById('themeDark');
    if (themeLightRadio && themeDarkRadio) {
        // Reflect current theme state from documentElement after initial updateTheme call
        const currentTheme = document.documentElement.getAttribute('data-theme');
        if (currentTheme === 'light') {
            themeLightRadio.checked = true;
        } else {
            themeDarkRadio.checked = true;
        }
        
        document.querySelectorAll('input[name="themeMode"]').forEach(radio => {
            radio.addEventListener('change', function() {
                updateTheme(this.value); // Use the new function
            });
        });
    }

    const accentSwatchesContainer = document.getElementById('accentColorSwatches');
    if (accentSwatchesContainer) {
        const swatches = accentSwatchesContainer.querySelectorAll('.accent-swatch');
        swatches.forEach(swatch => {
            if (swatch.getAttribute('data-accent-color') === savedAccentColor) {
                swatch.classList.add('active');
            }
            swatch.addEventListener('click', function() {
                const newAccentColor = this.getAttribute('data-accent-color');
                applyAccentColor(newAccentColor);
                // Update active class on swatches
                swatches.forEach(s => s.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }
    
    // Make functions globally available if needed for other dynamic UI elements later
    window.setAppTheme = updateTheme; // Expose the new function
    window.setAppAccentColor = applyAccentColor;

    // Moved Modal Theming Logic here for better scope and cohesion
    function applyThemeToModals() {
        // Read theme from documentElement
        const theme = document.documentElement.getAttribute('data-theme'); 
        const modals = document.querySelectorAll('.modal, .custom-modal');
        
        modals.forEach(modal => {
            modal.setAttribute('data-theme', theme);
        });
    }

    // Watch for new modals being added to DOM
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    if (node.matches('.modal, .custom-modal') || 
                        node.querySelector('.modal, .custom-modal')) {
                        applyThemeToModals(); // This will now correctly call the function defined above
                    }
                }
            });
        });
    });
    
    observer.observe(document.body, { // Observe body for dynamically added modals
        childList: true,
        subtree: true
    });

    // Theme toggle specific logic (if #theme-toggle exists)
    // This was previously in the second DOMContentLoaded, moving relevant parts here.
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            updateTheme(newTheme);
        });
    }
    // The initial theme application and icon update are already handled by updateTheme(savedTheme)
    // and the logic within updateTheme itself.
});

// Windows 11 Theme System - Enhanced
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.currentAccent = localStorage.getItem('accent-color') || '#0078d4';
        this.accentPickerVisible = false;
        
        this.init();
        this.createAccentPicker();
        this.setupEventListeners();
    }

    init() {
        // Apply saved theme
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        
        // Apply saved accent color
        this.setAccentColor(this.currentAccent);
        
        // Update theme toggle icon
        this.updateThemeIcon();
        
        // Initialize with system preference if no saved theme
        if (!localStorage.getItem('theme')) {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.setTheme(prefersDark ? 'dark' : 'light');
        }
    }

    setTheme(theme) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        this.updateThemeIcon();
        
        // Dispatch custom event for components that need to react to theme changes
        window.dispatchEvent(new CustomEvent('themeChanged', { 
            detail: { theme: theme } 
        }));
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }

    updateThemeIcon() {
        const icon = document.getElementById('theme-icon');
        if (icon) {
            icon.className = this.currentTheme === 'light' ? 'bi bi-moon-fill' : 'bi bi-sun-fill';
        }
    }

    setAccentColor(color) {
        const { h, s, l } = this.hexToHsl(color);
        
        // Update CSS custom properties
        document.documentElement.style.setProperty('--w11-accent-hue', h);
        document.documentElement.style.setProperty('--w11-accent-saturation', `${s}%`);
        document.documentElement.style.setProperty('--w11-accent-lightness', `${l}%`);
        
        this.currentAccent = color;
        localStorage.setItem('accent-color', color);
        
        // Update accent picker toggle button
        const toggleBtn = document.querySelector('.accent-picker-toggle');
        if (toggleBtn) {
            toggleBtn.style.background = color;
        }
        
        // Update active preset
        this.updateActivePreset(color);
        
        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('accentColorChanged', { 
            detail: { color: color } 
        }));
    }

    hexToHsl(hex) {
        // Remove # if present
        hex = hex.replace('#', '');
        
        // Parse hex values
        const r = parseInt(hex.substr(0, 2), 16) / 255;
        const g = parseInt(hex.substr(2, 2), 16) / 255;
        const b = parseInt(hex.substr(4, 2), 16) / 255;

        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0; // achromatic
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch (max) {
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }

        return {
            h: Math.round(h * 360),
            s: Math.round(s * 100),
            l: Math.round(l * 100)
        };
    }

    createAccentPicker() {
        // Predefined Windows 11 color presets
        const colorPresets = [
            '#0078d4', // Default Blue
            '#0099bc', // Teal
            '#00b7c3', // Light Teal
            '#8764b8', // Purple
            '#881798', // Dark Purple
            '#744da9', // Violet
            '#0078d4', // Blue
            '#005a9e', // Dark Blue
            '#107c10', // Green
            '#486860', // Sage
            '#498205', // Lime Green
            '#107c10', // Forest Green
            '#ca5010', // Orange
            '#ff8c00', // Dark Orange
            '#d13438', // Red
            '#a4262c', // Dark Red
            '#e74856', // Light Red
            '#ff4343', // Bright Red
            '#b146c2', // Magenta
            '#881798', // Dark Magenta
            '#0078d4', // Windows Blue
            '#005a9e', // Navy Blue
            '#8764b8', // Lavender
            '#744da9'  // Indigo
        ];

        const pickerHTML = `
            <div class="accent-color-picker" id="accentColorPicker">
                <h6><i class="bi bi-palette me-2"></i>Accent Color</h6>
                
                <div class="color-presets">
                    ${colorPresets.map(color => `
                        <div class="color-preset" 
                             style="background-color: ${color}" 
                             data-color="${color}"
                             title="${color}">
                        </div>
                    `).join('')}
                </div>
                
                <div class="custom-color-section">
                    <label>Custom Color</label>
                    <div class="color-input-group">
                        <input type="color" 
                               class="color-picker-input" 
                               id="customColorPicker" 
                               value="${this.currentAccent}">
                        <input type="text" 
                               class="color-input" 
                               id="colorHexInput" 
                               placeholder="#0078d4" 
                               value="${this.currentAccent}"
                               maxlength="7">
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', pickerHTML);
        
        // Set initial active preset
        this.updateActivePreset(this.currentAccent);
    }

    updateActivePreset(color) {
        const presets = document.querySelectorAll('.color-preset');
        presets.forEach(preset => {
            if (preset.dataset.color.toLowerCase() === color.toLowerCase()) {
                preset.classList.add('active');
            } else {
                preset.classList.remove('active');
            }
        });
    }

    setupEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Accent picker toggle - Updated to use the new ID
        const accentToggle = document.getElementById('accent-color-toggle');
        if (accentToggle) {
            accentToggle.addEventListener('click', () => this.toggleAccentPicker());
        }

        // Color presets
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('color-preset')) {
                const color = e.target.dataset.color;
                this.setAccentColor(color);
                this.updateColorInputs(color);
            }
        });

        // Custom color picker
        const customPicker = document.getElementById('customColorPicker');
        if (customPicker) {
            customPicker.addEventListener('input', (e) => {
                const color = e.target.value;
                this.setAccentColor(color);
                this.updateColorInputs(color);
            });
        }

        // Hex input
        const hexInput = document.getElementById('colorHexInput');
        if (hexInput) {
            hexInput.addEventListener('input', (e) => {
                let color = e.target.value;
                if (!color.startsWith('#')) {
                    color = '#' + color;
                }
                
                if (this.isValidHex(color)) {
                    this.setAccentColor(color);
                    document.getElementById('customColorPicker').value = color;
                }
            });

            hexInput.addEventListener('blur', (e) => {
                // Validate and fix input on blur
                let color = e.target.value;
                if (!color.startsWith('#') && color.length > 0) {
                    color = '#' + color;
                }
                
                if (!this.isValidHex(color) && color.length > 0) {
                    e.target.value = this.currentAccent;
                } else if (color.length > 0) {
                    e.target.value = color.toUpperCase();
                }
            });
        }

        // Close picker when clicking outside
        document.addEventListener('click', (e) => {
            const picker = document.getElementById('accentColorPicker');
            const toggle = document.getElementById('accent-color-toggle'); // Updated ID
            
            if (this.accentPickerVisible && 
                !picker.contains(e.target) && 
                !toggle.contains(e.target)) {
                this.hideAccentPicker();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl + Shift + T for theme toggle
            if (e.ctrlKey && e.shiftKey && e.key === 'T') {
                e.preventDefault();
                this.toggleTheme();
            }
            
            // Ctrl + Shift + C for color picker
            if (e.ctrlKey && e.shiftKey && e.key === 'C') {
                e.preventDefault();
                this.toggleAccentPicker();
            }
            
            // Escape to close color picker
            if (e.key === 'Escape' && this.accentPickerVisible) {
                this.hideAccentPicker();
            }
        });

        // System theme change detection
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    isValidHex(hex) {
        return /^#[0-9A-F]{6}$/i.test(hex);
    }

    updateColorInputs(color) {
        const hexInput = document.getElementById('colorHexInput');
        const colorPicker = document.getElementById('customColorPicker');
        
        if (hexInput) hexInput.value = color.toUpperCase();
        if (colorPicker) colorPicker.value = color;
    }

    toggleAccentPicker() {
        if (this.accentPickerVisible) {
            this.hideAccentPicker();
        } else {
            this.showAccentPicker();
        }
    }

    showAccentPicker() {
        const picker = document.getElementById('accentColorPicker');
        
        if (picker) {
            picker.classList.add('show');
            this.accentPickerVisible = true;
        }
    }

    hideAccentPicker() {
        const picker = document.getElementById('accentColorPicker');
        
        if (picker) {
            picker.classList.remove('show');
            this.accentPickerVisible = false;
        }
    }
}

// Enhanced notification system
class NotificationManager {
    constructor() {
        this.container = this.createContainer();
        this.notifications = new Map();
        this.idCounter = 0;
    }

    createContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            max-width: 400px;
            pointer-events: none;
        `;
        document.body.appendChild(container);
        return container;
    }

    show(message, type = 'info', duration = 5000) {
        const id = ++this.idCounter;
        const notification = this.createNotification(id, message, type);
        
        this.container.appendChild(notification);
        this.notifications.set(id, notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);
        
        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                this.remove(id);
            }, duration);
        }
        
        return id;
    }

    createNotification(id, message, type) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible`;
        notification.style.cssText = `
            margin-bottom: 10px;
            pointer-events: auto;
            transform: translateX(100%);
            opacity: 0;
            transition: all 0.3s ease;
            border-radius: var(--w11-radius-large);
            box-shadow: var(--w11-shadow-8);
            border: 1px solid var(--w11-card-stroke);
            backdrop-filter: blur(20px);
        `;
        
        const icons = {
            success: 'check-circle',
            danger: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        
        notification.innerHTML = `
            <i class="bi bi-${icons[type] || 'info-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-notification-id="${id}"></button>
        `;
        
        // Add close handler
        const closeBtn = notification.querySelector('.btn-close');
        closeBtn.addEventListener('click', () => this.remove(id));
        
        return notification;
    }

    remove(id) {
        const notification = this.notifications.get(id);
        if (notification) {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
                this.notifications.delete(id);
            }, 300);
        }
    }

    clear() {
        this.notifications.forEach((_, id) => this.remove(id));
    }
}

// Performance Monitor
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            loadTime: 0,
            renderTime: 0,
            memoryUsage: 0
        };
        this.init();
    }

    init() {
        // Measure initial load time
        window.addEventListener('load', () => {
            const perfData = performance.getEntriesByType('navigation')[0];
            if (perfData) {
                this.metrics.loadTime = Math.round(perfData.loadEventEnd - perfData.loadEventStart);
                this.metrics.renderTime = Math.round(perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart);
            }
        });

        // Monitor memory usage (if available)
        if ('memory' in performance) {
            setInterval(() => {
                this.metrics.memoryUsage = Math.round(performance.memory.usedJSHeapSize / 1048576); // MB
            }, 10000);
        }
    }

    getMetrics() {
        return this.metrics;
    }
}

// Accessibility Manager
class AccessibilityManager {
    constructor() {
        this.init();
    }

    init() {
        // Add focus indicators for keyboard navigation
        this.setupFocusIndicators();
        
        // Add skip to content link
        this.addSkipLink();
        
        // Improve screen reader experience
        this.enhanceScreenReaderSupport();
        
        // Handle reduced motion preferences
        this.handleReducedMotion();
    }

    setupFocusIndicators() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                document.body.classList.add('keyboard-navigation');
            }
        });

        document.addEventListener('mousedown', () => {
            document.body.classList.remove('keyboard-navigation');
        });
    }

    addSkipLink() {
        const skipLink = document.createElement('a');
        skipLink.href = '#main-content';
        skipLink.textContent = 'Skip to main content';
        skipLink.className = 'skip-link';
        skipLink.style.cssText = `
            position: absolute;
            top: -40px;
            left: 6px;
            background: var(--w11-accent);
            color: white;
            padding: 8px;
            text-decoration: none;
            border-radius: 4px;
            z-index: 10001;
            transition: top 0.3s;
        `;
        
        skipLink.addEventListener('focus', () => {
            skipLink.style.top = '6px';
        });
        
        skipLink.addEventListener('blur', () => {
            skipLink.style.top = '-40px';
        });
        
        document.body.insertAdjacentElement('afterbegin', skipLink);
    }

    enhanceScreenReaderSupport() {
        // Add aria-live region for dynamic content
        const liveRegion = document.createElement('div');
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        liveRegion.style.cssText = `
            position: absolute;
            left: -10000px;
            width: 1px;
            height: 1px;
            overflow: hidden;
        `;
        liveRegion.id = 'aria-live-region';
        document.body.appendChild(liveRegion);
    }

    handleReducedMotion() {
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        
        if (prefersReducedMotion.matches) {
            document.documentElement.style.setProperty('--w11-duration-fast', '0ms');
            document.documentElement.style.setProperty('--w11-duration-normal', '0ms');
            document.documentElement.style.setProperty('--w11-duration-slow', '0ms');
        }
    }

    announceToScreenReader(message) {
        const liveRegion = document.getElementById('aria-live-region');
        if (liveRegion) {
            liveRegion.textContent = message;
        }
    }
}

// Initialize systems when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize core systems
    window.themeManager = new ThemeManager();
    window.notificationManager = new NotificationManager();
    window.performanceMonitor = new PerformanceMonitor();
    window.accessibilityManager = new AccessibilityManager();
    
    // Add keyboard navigation styles
    const keyboardStyles = document.createElement('style');
    keyboardStyles.textContent = `
        .keyboard-navigation *:focus {
            outline: 2px solid var(--w11-accent) !important;
            outline-offset: 2px !important;
        }
        
        .keyboard-navigation .btn:focus,
        .keyboard-navigation .form-control:focus,
        .keyboard-navigation .form-select:focus {
            box-shadow: 0 0 0 2px hsla(var(--w11-accent-hue), var(--w11-accent-saturation), var(--w11-accent-lightness), 0.3) !important;
        }
    `;
    document.head.appendChild(keyboardStyles);
    
    // Add main content landmark if not present
    if (!document.getElementById('main-content')) {
        const main = document.querySelector('main') || document.querySelector('.container-fluid');
        if (main) {
            main.id = 'main-content';
            main.setAttribute('role', 'main');
        }
    }
    
    // Enhance form accessibility
    document.querySelectorAll('input, textarea, select').forEach(input => {
        if (!input.id && input.name) {
            input.id = input.name + '_' + Math.random().toString(36).substr(2, 9);
        }
        
        const label = document.querySelector(`label[for="${input.id}"]`);
        if (!label && input.placeholder) {
            input.setAttribute('aria-label', input.placeholder);
        }
    });
    
    console.log('🎨 CoreSecFrame Theme System Initialized');
    console.log('📱 Responsive Design Active');
    console.log('♿ Accessibility Features Enabled');
    
    // Global utility functions
    window.showNotification = (message, type = 'info', duration = 5000) => {
        return window.notificationManager.show(message, type, duration);
    };
    
    window.announceToScreenReader = (message) => {
        window.accessibilityManager.announceToScreenReader(message);
    };
});

// Utility Functions
const Utils = {
    // Debounce function for performance
    debounce(func, wait, immediate) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    },

    // Throttle function for scroll events
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // Format file sizes
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Format time duration
    formatDuration(seconds) {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hrs > 0) {
            return `${hrs}h ${mins}m ${secs}s`;
        } else if (mins > 0) {
            return `${mins}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    },

    // Copy text to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            window.showNotification('Copied to clipboard', 'success', 2000);
            return true;
        } catch (err) {
            console.error('Failed to copy: ', err);
            window.showNotification('Failed to copy to clipboard', 'danger', 3000);
            return false;
        }
    },

    // Generate unique ID
    generateId(prefix = 'id') {
        return prefix + '_' + Math.random().toString(36).substr(2, 9);
    },

    // Validate email
    isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    // Sanitize HTML
    sanitizeHtml(str) {
        const temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    },

    // Get contrast ratio for accessibility
    getContrastRatio(color1, color2) {
        const lum1 = this.getLuminance(color1);
        const lum2 = this.getLuminance(color2);
        const brightest = Math.max(lum1, lum2);
        const darkest = Math.min(lum1, lum2);
        return (brightest + 0.05) / (darkest + 0.05);
    },

    getLuminance(hex) {
        const rgb = this.hexToRgb(hex);
        const rsRGB = rgb.r / 255;
        const gsRGB = rgb.g / 255;
        const bsRGB = rgb.b / 255;

        const r = rsRGB <= 0.03928 ? rsRGB / 12.92 : Math.pow((rsRGB + 0.055) / 1.055, 2.4);
        const g = gsRGB <= 0.03928 ? gsRGB / 12.92 : Math.pow((gsRGB + 0.055) / 1.055, 2.4);
        const b = bsRGB <= 0.03928 ? bsRGB / 12.92 : Math.pow((bsRGB + 0.055) / 1.055, 2.4);

        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    },

    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }
};

// Enhanced Form Validation
class FormValidator {
    constructor(form) {
        this.form = form;
        this.rules = new Map();
        this.errors = new Map();
        this.init();
    }

    init() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.form.addEventListener('input', (e) => this.validateField(e.target));
        this.form.addEventListener('blur', (e) => this.validateField(e.target), true);
    }

    addRule(fieldName, validator, message) {
        if (!this.rules.has(fieldName)) {
            this.rules.set(fieldName, []);
        }
        this.rules.get(fieldName).push({ validator, message });
        return this;
    }

    validateField(field) {
        const fieldName = field.name || field.id;
        const rules = this.rules.get(fieldName);
        
        if (!rules) return true;

        this.clearFieldError(field);
        
        for (const rule of rules) {
            if (!rule.validator(field.value, field)) {
                this.showFieldError(field, rule.message);
                return false;
            }
        }
        
        this.showFieldSuccess(field);
        return true;
    }

    validateAll() {
        let isValid = true;
        const fields = this.form.querySelectorAll('[name], [id]');
        
        fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });
        
        return isValid;
    }

    handleSubmit(e) {
        if (!this.validateAll()) {
            e.preventDefault();
            const firstError = this.form.querySelector('.is-invalid');
            if (firstError) {
                firstError.focus();
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    showFieldError(field, message) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        
        let feedback = field.parentNode.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentNode.appendChild(feedback);
        }
        feedback.textContent = message;
        feedback.style.display = 'block';
    }

    showFieldSuccess(field) {
        field.classList.add('is-valid');
        field.classList.remove('is-invalid');
        
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.style.display = 'none';
        }
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid', 'is-valid');
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.style.display = 'none';
        }
    }

    // Common validators
    static validators = {
        required: (value) => value && value.trim().length > 0,
        email: (value) => !value || Utils.isValidEmail(value),
        minLength: (min) => (value) => !value || value.length >= min,
        maxLength: (max) => (value) => !value || value.length <= max,
        pattern: (regex) => (value) => !value || regex.test(value),
        confirmed: (otherFieldName) => (value, field) => {
            const otherField = field.form.querySelector(`[name="${otherFieldName}"]`);
            return !value || !otherField || value === otherField.value;
        }
    };
}

// Loading States Manager
class LoadingManager {
    constructor() {
        this.activeLoaders = new Set();
    }

    show(target, text = 'Loading...') {
        const loaderId = Utils.generateId('loader');
        const loader = this.createLoader(loaderId, text);
        
        if (typeof target === 'string') {
            target = document.querySelector(target);
        }
        
        if (target) {
            target.style.position = 'relative';
            target.appendChild(loader);
            this.activeLoaders.add(loaderId);
        }
        
        return loaderId;
    }

    hide(loaderId) {
        const loader = document.getElementById(loaderId);
        if (loader) {
            loader.remove();
            this.activeLoaders.delete(loaderId);
        }
    }

    createLoader(id, text) {
        const loader = document.createElement('div');
        loader.id = id;
        loader.className = 'loading-overlay';
        loader.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(var(--w11-bg-primary), 0.8);
            backdrop-filter: blur(4px);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            border-radius: inherit;
        `;
        
        loader.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <div class="mt-2 text-muted">${text}</div>
        `;
        
        return loader;
    }

    hideAll() {
        this.activeLoaders.forEach(id => this.hide(id));
    }
}

// Data Table Enhancements
class DataTable {
    constructor(table, options = {}) {
        this.table = table;
        this.options = {
            sortable: true,
            filterable: true,
            pagination: false,
            pageSize: 10,
            ...options
        };
        this.data = [];
        this.filteredData = [];
        this.currentPage = 1;
        this.sortColumn = null;
        this.sortDirection = 'asc';
        
        this.init();
    }

    init() {
        this.extractData();
        if (this.options.sortable) this.setupSorting();
        if (this.options.filterable) this.setupFiltering();
        if (this.options.pagination) this.setupPagination();
    }

    extractData() {
        const rows = Array.from(this.table.querySelectorAll('tbody tr'));
        this.data = rows.map(row => {
            const cells = Array.from(row.querySelectorAll('td'));
            return {
                element: row,
                data: cells.map(cell => cell.textContent.trim())
            };
        });
        this.filteredData = [...this.data];
    }

    setupSorting() {
        const headers = this.table.querySelectorAll('thead th');
        headers.forEach((header, index) => {
            if (header.dataset.sortable !== 'false') {
                header.style.cursor = 'pointer';
                header.classList.add('sortable');
                header.addEventListener('click', () => this.sort(index));
                
                const icon = document.createElement('i');
                icon.className = 'bi bi-arrow-up-down ms-2';
                header.appendChild(icon);
            }
        });
    }

    sort(columnIndex) {
        if (this.sortColumn === columnIndex) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = columnIndex;
            this.sortDirection = 'asc';
        }

        this.filteredData.sort((a, b) => {
            const aVal = a.data[columnIndex];
            const bVal = b.data[columnIndex];
            
            // Try to parse as numbers
            const aNum = parseFloat(aVal);
            const bNum = parseFloat(bVal);
            
            let result;
            if (!isNaN(aNum) && !isNaN(bNum)) {
                result = aNum - bNum;
            } else {
                result = aVal.localeCompare(bVal);
            }
            
            return this.sortDirection === 'asc' ? result : -result;
        });

        this.updateSortIcons();
        this.render();
    }

    updateSortIcons() {
        const headers = this.table.querySelectorAll('thead th');
        headers.forEach((header, index) => {
            const icon = header.querySelector('i');
            if (icon) {
                if (index === this.sortColumn) {
                    icon.className = this.sortDirection === 'asc' ? 
                        'bi bi-arrow-up ms-2' : 'bi bi-arrow-down ms-2';
                } else {
                    icon.className = 'bi bi-arrow-up-down ms-2';
                }
            }
        });
    }

    filter(searchTerm) {
        if (!searchTerm) {
            this.filteredData = [...this.data];
        } else {
            this.filteredData = this.data.filter(row => 
                row.data.some(cell => 
                    cell.toLowerCase().includes(searchTerm.toLowerCase())
                )
            );
        }
        
        this.currentPage = 1;
        this.render();
    }

    render() {
        const tbody = this.table.querySelector('tbody');
        tbody.innerHTML = '';
        
        let dataToShow = this.filteredData;
        
        if (this.options.pagination) {
            const start = (this.currentPage - 1) * this.options.pageSize;
            const end = start + this.options.pageSize;
            dataToShow = this.filteredData.slice(start, end);
        }
        
        dataToShow.forEach(row => {
            tbody.appendChild(row.element);
        });
        
        if (this.options.pagination) {
            this.updatePagination();
        }
    }

    setupPagination() {
        // Implementation for pagination controls
        // This would create pagination UI elements
    }

    updatePagination() {
        // Update pagination display
    }
}

// Modal Manager
class ModalManager {
    constructor() {
        this.modals = new Map();
        this.currentModal = null;
    }

    create(id, content, options = {}) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = id;
        modal.tabIndex = -1;
        
        const config = {
            title: 'Modal',
            size: '', // sm, lg, xl
            backdrop: true,
            keyboard: true,
            ...options
        };
        
        modal.innerHTML = `
            <div class="modal-dialog ${config.size ? 'modal-' + config.size : ''}">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${config.title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${content}
                    </div>
                    ${config.footer ? `<div class="modal-footer">${config.footer}</div>` : ''}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const bsModal = new bootstrap.Modal(modal, {
            backdrop: config.backdrop,
            keyboard: config.keyboard
        });
        
        this.modals.set(id, { element: modal, instance: bsModal });
        return bsModal;
    }

    show(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.instance.show();
            this.currentModal = id;
        }
    }

    hide(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.instance.hide();
            if (this.currentModal === id) {
                this.currentModal = null;
            }
        }
    }

    destroy(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.instance.dispose();
            modal.element.remove();
            this.modals.delete(id);
        }
    }
}

// Storage Manager with encryption
class StorageManager {
    constructor() {
        this.prefix = 'csf_';
    }

    set(key, value, encrypt = false) {
        try {
            const data = {
                value: encrypt ? this.encrypt(value) : value,
                encrypted: encrypt,
                timestamp: Date.now()
            };
            localStorage.setItem(this.prefix + key, JSON.stringify(data));
            return true;
        } catch (error) {
            console.error('Storage error:', error);
            return false;
        }
    }

    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(this.prefix + key);
            if (!item) return defaultValue;
            
            const data = JSON.parse(item);
            return data.encrypted ? this.decrypt(data.value) : data.value;
        } catch (error) {
            console.error('Storage retrieval error:', error);
            return defaultValue;
        }
    }

    remove(key) {
        localStorage.removeItem(this.prefix + key);
    }

    clear() {
        Object.keys(localStorage)
            .filter(key => key.startsWith(this.prefix))
            .forEach(key => localStorage.removeItem(key));
    }

    // Simple encryption (not for sensitive data)
    encrypt(text) {
        return btoa(text);
    }

    decrypt(encodedText) {
        return atob(encodedText);
    }
}

// Initialize global utilities
window.Utils = Utils;
window.loadingManager = new LoadingManager();
window.modalManager = new ModalManager();
window.storageManager = new StorageManager();

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ThemeManager,
        NotificationManager,
        PerformanceMonitor,
        AccessibilityManager,
        FormValidator,
        LoadingManager,
        DataTable,
        ModalManager,
        StorageManager,
        Utils
    };
}