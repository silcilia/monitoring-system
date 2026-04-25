function loadPage(page, el = null) {
    const content = document.getElementById('content');

    if (!content) return;

    // Loading state
    content.innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"></div>
            <p>Memuat ${page}...</p>
        </div>
    `;

    // Fetch content
    fetch(`/load-${page}/`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Gagal load halaman ${page}`);
            }
            return response.text();
        })
        .then(html => {
            content.innerHTML = html;

            // Jalankan script yang ada di dalam HTML yang di-load
            const scripts = content.querySelectorAll("script");
            scripts.forEach(oldScript => {
                const newScript = document.createElement("script");
                newScript.textContent = oldScript.textContent;
                document.body.appendChild(newScript);
                oldScript.remove();
            });

            // Set active menu
            document.querySelectorAll('.sidebar li').forEach(li => {
                li.classList.remove('active');
            });
            
            if (el) {
                el.classList.add('active');
            }

            // Update URL
            history.pushState({ page: page }, "", `/${page}/`);
        })
        .catch(error => {
            console.error("ERROR:", error);
            content.innerHTML = `
                <div class="error-container">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Gagal Memuat Halaman</h3>
                    <p>${error.message}</p>
                    <button onclick="loadPage('${page}')" class="retry-btn">
                        <i class="fas fa-redo"></i> Coba Lagi
                    </button>
                </div>
            `;
        });
}

// Handle back button
window.onpopstate = function (event) {
    if (event.state && event.state.page) {
        loadPage(event.state.page);
    } else {
        const firstMenu = document.querySelector('.sidebar li');
        loadPage('dashboard', firstMenu);
    }
};

// Auto load dashboard
window.addEventListener("DOMContentLoaded", function () {
    const content = document.getElementById("content");
    if (content && (!content.innerHTML.trim() || content.innerHTML.trim() === "")) {
        const firstMenu = document.querySelector('.sidebar li');
        if (firstMenu && typeof loadPage === 'function') {
            loadPage('dashboard', firstMenu);
        }
    }
});