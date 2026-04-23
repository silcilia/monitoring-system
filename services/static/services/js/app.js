/**
 * Enhanced app.js with better loading states and error handling
 * Without changing core logic
 */

function loadPage(page, el = null) {
    const content = document.getElementById('content');

    // Enhanced loading state dengan spinner
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
            // Fade in effect
            content.style.opacity = '0';
            content.innerHTML = html;
            
            // Trigger fade in
            setTimeout(() => {
                content.style.transition = 'opacity 0.3s ease';
                content.style.opacity = '1';
            }, 50);
            
            // Set active menu
            document.querySelectorAll('.sidebar li').forEach(li => {
                li.classList.remove('active');
            });

            if (el) {
                el.classList.add('active');
            } else {
                // Find matching menu based on page
                const menuItems = document.querySelectorAll('.sidebar li span');
                menuItems.forEach(item => {
                    if (item.innerText.toLowerCase() === page.toLowerCase()) {
                        item.parentElement.classList.add('active');
                    }
                });
            }

            // Update URL (SPA feel)
            history.pushState({ page: page }, "", `/${page}/`);
            
            // Trigger any page-specific initialization
            if (typeof pageLoaded === 'function') {
                pageLoaded(page);
            }
            
            // Scroll to top on page change
            window.scrollTo({ top: 0, behavior: 'smooth' });
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
            content.style.opacity = '1';
        });
}

/**
 * Handle back button
 */
window.onpopstate = function (event) {
    if (event.state && event.state.page) {
        loadPage(event.state.page);
    } else {
        // Default to dashboard
        loadPage('dashboard');
    }
};

/**
 * Auto load dashboard first
 */
window.addEventListener("DOMContentLoaded", function () {
    const content = document.getElementById("content");
    
    // Check if content is empty or has only default Django block
    if (!content.innerHTML.trim() || content.innerHTML.trim() === "{% block content %}{% endblock %}") {
        const firstMenu = document.querySelector('.sidebar li');
        if (firstMenu) {
            loadPage('dashboard', firstMenu);
        }
    }
});

/**
 * Optional: Add page-specific initialization functions
 */
function pageLoaded(page) {
    console.log(`Page loaded: ${page}`);
    
    // Add animation to elements
    const cards = document.querySelectorAll('.card, .stat-card, table');
    cards.forEach((card, index) => {
        card.style.animation = `fadeInUp 0.5s ease ${index * 0.05}s forwards`;
        card.style.opacity = '0';
    });
}

// Add CSS animation keyframes dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);