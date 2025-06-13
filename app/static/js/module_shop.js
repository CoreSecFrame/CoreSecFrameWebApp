document.addEventListener('DOMContentLoaded', function () {
    // Category filtering
    const categoryLinks = document.querySelectorAll('.list-group-item[data-category]');
    const moduleRows = document.querySelectorAll('#moduleList tr');
    const noResults = document.getElementById('noResults'); // Get the noResults element

    let currentCategory = 'all';
    let searchTerm = '';

    categoryLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();

            // Update active state
            categoryLinks.forEach(item => item.classList.remove('active'));
            this.classList.add('active');

            currentCategory = this.getAttribute('data-category');

            // Apply both category and search filters
            applyFilters();
        });
    });

    // Search functionality
    const searchInput = document.getElementById('moduleSearch');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    const resetSearchBtn = document.getElementById('resetSearchBtn');
    const searchInfo = document.getElementById('searchInfo');
    const searchResultCount = document.getElementById('searchResultCount');

    if (searchInput) { // Ensure searchInput exists before adding listeners
        searchInput.addEventListener('input', function () {
            searchTerm = this.value.toLowerCase();
            applyFilters();

            // Show or hide clear button based on search input
            if (searchTerm && clearSearchBtn) {
                clearSearchBtn.style.display = '';
            } else if (clearSearchBtn) {
                clearSearchBtn.style.display = 'none';
            }
            // Show or hide search info
            if (searchTerm && searchInfo) {
                 searchInfo.classList.remove('d-none');
            } else if (searchInfo) {
                 searchInfo.classList.add('d-none');
            }
        });
    }


    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            searchTerm = '';
            applyFilters();
            this.style.display = 'none';
            if (searchInfo) searchInfo.classList.add('d-none');
        });
    }

    if (resetSearchBtn) {
        resetSearchBtn.addEventListener('click', function () {
            // Reset search
            if (searchInput) searchInput.value = '';
            searchTerm = '';

            // Reset category to "All"
            currentCategory = 'all';
            categoryLinks.forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('data-category') === 'all') {
                    item.classList.add('active');
                }
            });

            applyFilters();

            // Hide search info
            if (searchInfo) searchInfo.classList.add('d-none');
            if (clearSearchBtn) clearSearchBtn.style.display = 'none';
        });
    }

    // Initialize clear button visibility
    if (clearSearchBtn) { // Check if clearSearchBtn exists
        clearSearchBtn.style.display = (searchInput && searchInput.value) ? '' : 'none';
    }
    if (searchInfo && searchInput && searchInput.value) {
        searchInfo.classList.remove('d-none');
    } else if (searchInfo) {
        searchInfo.classList.add('d-none');
    }


    // Function to apply both category and search filters
    function applyFilters() {
        let visibleCount = 0;

        moduleRows.forEach(row => {
            const name = (row.getAttribute('data-name') || '').toLowerCase();
            const description = (row.querySelector('td:nth-child(3)')?.textContent || '').toLowerCase();
            const category = (row.getAttribute('data-category') || '').toLowerCase();

            const matchesCategory = currentCategory === 'all' || category === currentCategory.toLowerCase();
            const matchesSearch = !searchTerm ||
                name.includes(searchTerm) ||
                description.includes(searchTerm) ||
                category.includes(searchTerm);

            if (matchesCategory && matchesSearch) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        if (searchResultCount) { // Check if searchResultCount exists
             searchResultCount.textContent = visibleCount;
        }

        if (noResults) { // Check if noResults exists
            if (visibleCount === 0) {
                noResults.classList.remove('d-none');
            } else {
                noResults.classList.add('d-none');
            }
        }
    }
    // Initial filter application in case of page reload with search terms or categories
    applyFilters();
});
