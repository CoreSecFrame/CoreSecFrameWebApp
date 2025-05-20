// app/static/js/csrf_protection.js
document.addEventListener('DOMContentLoaded', function() {
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    // Add CSRF token to AJAX requests
    const oldXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        oldXHROpen.apply(this, arguments);
        if (method.toLowerCase() !== 'get') {
            this.setRequestHeader('X-CSRFToken', csrfToken);
        }
    };
});