document.addEventListener('DOMContentLoaded', function() {
    const sessionTypeSelect = document.getElementById('session_type');
    const moduleSelection = document.getElementById('module_selection');
    const moduleNameSelect = document.getElementById('module_name');

    if (sessionTypeSelect && moduleSelection && moduleNameSelect) {
        sessionTypeSelect.addEventListener('change', function() {
            if (this.value === 'terminal') {
                moduleSelection.classList.add('d-none');
                moduleNameSelect.removeAttribute('required');
                moduleNameSelect.value = ''; // Clear selection when hiding
            } else {
                moduleSelection.classList.remove('d-none');
                moduleNameSelect.setAttribute('required', 'required');
            }
        });

        // Ensure initial state is correct on page load (e.g., if form is re-rendered with errors)
        if (sessionTypeSelect.value === 'terminal') {
            moduleSelection.classList.add('d-none');
            moduleNameSelect.removeAttribute('required');
        } else {
            moduleSelection.classList.remove('d-none');
            moduleNameSelect.setAttribute('required', 'required');
        }
    }
});
