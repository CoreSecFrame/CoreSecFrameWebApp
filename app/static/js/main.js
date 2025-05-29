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
     * Applies the selected theme (light/dark) to the application.
     * Sets the 'data-theme' attribute on the documentElement and stores the preference in localStorage.
     * @param {string} theme - The theme to apply ('light' or 'dark').
     */
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        console.log(`Theme applied: ${theme}`); // For debugging
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

    applyTheme(savedTheme);
    applyAccentColor(savedAccentColor);

    // Update UI elements on profile page if they exist
    const themeLightRadio = document.getElementById('themeLight');
    const themeDarkRadio = document.getElementById('themeDark');
    if (themeLightRadio && themeDarkRadio) {
        if (savedTheme === 'light') {
            themeLightRadio.checked = true;
        } else {
            themeDarkRadio.checked = true;
        }
        
        document.querySelectorAll('input[name="themeMode"]').forEach(radio => {
            radio.addEventListener('change', function() {
                applyTheme(this.value);
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
    window.setAppTheme = applyTheme;
    window.setAppAccentColor = applyAccentColor;
});