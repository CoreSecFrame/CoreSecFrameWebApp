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

// The second DOMContentLoaded listener is now significantly reduced or can be removed if empty.
// For now, I'll leave it empty. If other non-theme logic was there, it should remain.
// Based on the initial read, the second listener was purely for theme toggle and modal observer.
document.addEventListener('DOMContentLoaded', function() {
    // Intentionally left empty if all specific logic moved to the first listener.
    // If other, unrelated JavaScript was here, it should be preserved.
    // For this refactoring, assuming it was primarily for theme related elements.
});