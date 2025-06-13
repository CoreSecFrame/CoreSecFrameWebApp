document.addEventListener('DOMContentLoaded', function () {
    // Add subtle entrance animation
    const loginCard = document.querySelector('.w11-login-card');
    if (loginCard) { // Check if element exists
        loginCard.style.opacity = '0';
        loginCard.style.transform = 'translateY(20px) scale(0.95)';

        setTimeout(() => {
            loginCard.style.transition = 'all 0.6s cubic-bezier(0.4, 0.0, 0.2, 1)';
            loginCard.style.opacity = '1';
            loginCard.style.transform = 'translateY(0) scale(1)';
        }, 100);
    }

    // Focus on username field
    const usernameField = document.querySelector('input[name="username"]');
    if (usernameField) {
        setTimeout(() => {
            usernameField.focus();
        }, 700); // Delay focus slightly after animation
    }

    // Enhanced form interactions
    const formInputs = document.querySelectorAll('.w11-form-input');
    formInputs.forEach(input => {
        input.addEventListener('focus', function () {
            if (this.parentElement.classList.contains('w11-input-group')) { // Ensure parent is the group
                this.parentElement.style.transform = 'scale(1.02)';
                this.parentElement.style.transition = 'transform 0.2s ease';
            }
        });

        input.addEventListener('blur', function () {
            if (this.parentElement.classList.contains('w11-input-group')) {
                 this.parentElement.style.transform = 'scale(1)';
            }
        });

        input.addEventListener('input', function () {
            if (this.value.length > 0) {
                this.style.borderColor = 'var(--w11-accent)';
                // Ensure this doesn't override themes that might want different input bg on type
                // this.style.backgroundColor = 'rgba(var(--w11-accent-rgb), 0.05)'; // Use RGB version for opacity
            } else {
                this.style.borderColor = 'var(--w11-surface-stroke)';
                // this.style.backgroundColor = 'var(--w11-bg-primary)';
            }
        });
    });

    // Enhanced button interactions
    const loginBtn = document.querySelector('.w11-login-btn');
    let isSubmitting = false;

    if (loginBtn) { // Check if loginBtn exists
        // If the form is part of a larger form, ensure we target the correct one
        const loginForm = loginBtn.closest('form');
        if (loginForm) {
            loginForm.addEventListener('submit', function(e) {
                 // The button click handler will manage the text and style
                 // This is mostly to prevent double submission if user hits Enter rapidly
                if (isSubmitting) {
                    e.preventDefault();
                    return;
                }
                isSubmitting = true;
                loginBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Signing in...';
                loginBtn.style.background = 'var(--w11-accent-light1)'; // Or use a class
                loginBtn.disabled = true;

                // No need for setTimeout to reset here, server response or page change will handle it.
                // If validation fails client-side and form isn't submitted, it might need reset.
                // But Flask's server-side validation will re-render the page.
            });
        }
        // The original click listener on loginBtn is removed as form submission handles it.
        // If client-side validation was intended before actual submission, it would go here or in the submit listener.
    }


    // Checkbox animation
    const checkbox = document.querySelector('.w11-checkbox input');
    if (checkbox) {
        checkbox.addEventListener('change', function () {
            const indicator = this.nextElementSibling;
            if (indicator && this.checked) { // Ensure indicator exists
                indicator.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    indicator.style.transform = 'scale(1)';
                }, 100);
            }
        });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.ctrlKey && !e.altKey) {
            const activeElement = document.activeElement;
            if (activeElement && activeElement.tagName === 'INPUT' && activeElement.closest('form')) {
                const form = activeElement.closest('form');
                const submitButton = form.querySelector('button[type="submit"], input[type="submit"], .w11-login-btn');
                if (submitButton && !isSubmitting) { // Check isSubmitting here too
                    submitButton.click();
                }
            }
        }

        if (e.key === 'Escape') {
            formInputs.forEach(input => {
                input.value = '';
                input.style.borderColor = 'var(--w11-surface-stroke)';
                // input.style.backgroundColor = 'var(--w11-bg-primary)';
            });
            if (checkbox) {
                checkbox.checked = false;
                const indicator = checkbox.nextElementSibling;
                if (indicator) { // Ensure indicator exists
                    // Reset indicator style if needed, though typically handled by CSS
                    // indicator.style.background = 'var(--w11-bg-primary)';
                }
            }
        }
    });

    // Add particle effect on successful login (if no errors)
    // This condition needs to be re-evaluated as 'login=success' might not be how success is indicated.
    // It might be better to trigger this based on a specific element or data attribute present on successful redirect.
    // For now, keeping the logic as it was, assuming 'login=success' is a valid query parameter.
    const hasErrors = document.querySelector('.w11-error-message');
    if (!hasErrors && window.location.search.includes('login=success')) { // This condition might need adjustment
        createSuccessParticles();
    }
});

function createSuccessParticles() {
    const container = document.querySelector('.w11-login-container');
    if (!container) return; // Ensure container exists

    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.style.cssText = `
            position: absolute;
            width: 4px;
            height: 4px;
            background: var(--w11-accent);
            border-radius: 50%;
            pointer-events: none;
            top: 50%; /* Start from center */
            left: 50%; /* Start from center */
            animation: particle-float 2s ease-out forwards;
            animation-delay: ${Math.random() * 0.5}s; /* Stagger start times */
            opacity: 0;
        `;
        // Randomize end positions more effectively within the keyframes or by setting custom properties
        // The current keyframes are global, so this only randomizes delay.
        // For truly random end positions per particle, you'd need to generate keyframes dynamically
        // or use JS animations entirely. For simplicity, we use the CSS keyframes.
        container.appendChild(particle);

        setTimeout(() => {
            particle.remove();
        }, 2500); // Remove after animation + delay
    }
}
// Note: The @keyframes particle-float CSS will be moved to auth.css
// So, the particleStyle element creation is removed from here.
