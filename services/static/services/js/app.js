// ===============================
// 🔐 CSRF HELPER
// ===============================
function getCSRFToken() {
    let cookieValue = null;

    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith('csrftoken=')) {
                cookieValue = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }

    return cookieValue;
}

// ===============================
// 🌐 GLOBAL FETCH (API WRAPPER)
// ===============================
async function apiFetch(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    };

    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {})
        }
    };

    try {
        const response = await fetch(url, finalOptions);

        if (response.status === 401) {
            window.location.href = '/login/';
            return;
        }

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || `HTTP ${response.status}`);
        }

        if (response.status === 204) {
            return { success: true };
        }

        return await response.json();

    } catch (error) {
        console.error('API ERROR:', error);
        showNotification(error.message, 'error');
        throw error;
    }
}

// ===============================
// 🔔 NOTIFICATION
// ===============================
function showNotification(message, type = 'success') {
    // Hapus notifikasi lama
    const oldNotif = document.querySelector('.notification-toast');
    if (oldNotif) oldNotif.remove();

    const el = document.createElement('div');
    el.className = 'notification-toast';
    
    const bgColor = type === 'success' ? '#10b981' : (type === 'error' ? '#ef4444' : '#3b82f6');
    const icon = type === 'success' ? 'fa-check-circle' : (type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle');
    
    el.innerHTML = `
        <div style="
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${bgColor};
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            z-index: 9999;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideInRight 0.3s ease;
        ">
            <i class="fas ${icon}"></i>
            <span>${message}</span>
        </div>
    `;

    // Tambahkan style animasi jika belum ada
    if (!document.querySelector('#notification-style')) {
        const style = document.createElement('style');
        style.id = 'notification-style';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(el);

    setTimeout(() => {
        const notif = document.querySelector('.notification-toast');
        if (notif) {
            notif.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notif.remove(), 300);
        }
    }, 3000);
}

// ===============================
// 📦 SERVICES STATE
// ===============================
let currentEditId = null;
let currentDeleteId = null;
let currentDeleteType = null;

// Pagination variables
let currentPage = 1;
let itemsPerPage = 10;
let totalItems = 0;
let currentServicesData = [];
let currentContactsData = [];

// ===============================
// 📥 LOAD SERVICES (GET)
// ===============================
async function loadServices(page = 1, search = '') {
    const tableBody = document.getElementById('serviceTableBody');
    if (!tableBody) return;

    currentPage = page;
    
    tableBody.innerHTML = `
        <tr>
            <td colspan="5" class="loading-state">
                <i class="fas fa-spinner fa-spin"></i> Loading...
            </td>
        </tr>
    `;

    try {
        const data = await apiFetch('/api/services/');
        currentServicesData = data;
        totalItems = data.length;
        
        renderServicesTable(data, page, search);
        renderPagination('service');

    } catch (error) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    Gagal memuat data
                </td>
            </tr>
        `;
    }
}

function renderServicesTable(data, page, search) {
    const tableBody = document.getElementById('serviceTableBody');
    if (!tableBody) return;

    // Filter data
    let filteredData = data;
    if (search) {
        filteredData = data.filter(item => 
            item.name.toLowerCase().includes(search.toLowerCase()) ||
            item.url.toLowerCase().includes(search.toLowerCase())
        );
        totalItems = filteredData.length;
    }

    // Pagination
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageData = filteredData.slice(start, end);

    if (!pageData.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>Belum ada data service</p>
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = pageData.map(s => `
        <tr data-id="${s.id}">
            <td data-label="Nama">
                <strong>${escapeHtml(s.name)}</strong>
            </td>
            <td data-label="URL">
                <code style="font-family: monospace; font-size: 0.8rem;">${escapeHtml(s.url)}</code>
            </td>
            <td data-label="Tipe">
                <span class="type-badge ${s.service_type === 'HTTP' ? 'type-http' : 'type-ping'}">
                    ${s.service_type === 'HTTP' ? '🌐' : '📡'} ${s.service_type}
                </span>
            </td>
            <td data-label="Status">
                <span class="status-badge ${s.status === 'UP' ? 'status-up' : 'status-down'}">
                    <i class="fas fa-circle"></i> ${s.status || '?'}
                </span>
            </td>
            <td data-label="Aksi">
                <button class="btn-edit" onclick="openEdit(${s.id}, '${escapeHtml(s.name)}', '${escapeHtml(s.url)}', '${s.service_type}')">
                    <i class="fas fa-edit"></i> Edit
                </button>
                <button class="btn-delete" onclick="confirmDeleteService(${s.id}, '${escapeHtml(s.name)}')">
                    <i class="fas fa-trash"></i> Hapus
                </button>
            </td>
        </tr>
    `).join('');
}

// ===============================
// 📥 LOAD CONTACTS (GET)
// ===============================
async function loadContacts(page = 1, search = '') {
    const tableBody = document.getElementById('contactTableBody');
    if (!tableBody) return;

    currentPage = page;
    
    tableBody.innerHTML = `
        <tr>
            <td colspan="3" class="loading-state">
                <i class="fas fa-spinner fa-spin"></i> Loading...
            </td>
        </tr>
    `;

    try {
        const data = await apiFetch('/api/contacts/');
        currentContactsData = data;
        totalItems = data.length;
        
        renderContactsTable(data, page, search);
        renderPagination('contact');

    } catch (error) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    Gagal memuat data
                </td>
            </tr>
        `;
    }
}

function renderContactsTable(data, page, search) {
    const tableBody = document.getElementById('contactTableBody');
    if (!tableBody) return;

    // Filter data
    let filteredData = data;
    if (search) {
        filteredData = data.filter(item => 
            item.name.toLowerCase().includes(search.toLowerCase())
        );
        totalItems = filteredData.length;
    }

    // Pagination
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageData = filteredData.slice(start, end);

    if (!pageData.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>Belum ada data contact</p>
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = pageData.map(c => `
        <tr data-id="${c.id}">
            <td data-label="Nama">
                <div class="contact-name">
                    <div class="avatar">
                        <i class="fas fa-user-circle"></i>
                    </div>
                    <strong>${escapeHtml(c.name)}</strong>
                </div>
            </td>
            <td data-label="WhatsApp">
                <span class="phone-number">
                    <i class="fab fa-whatsapp"></i> ${escapeHtml(c.phone)}
                </span>
            </td>
            <td data-label="Aksi">
                <div class="action-buttons">
                    <button class="btn-edit" onclick="openEditContact(${c.id}, '${escapeHtml(c.name)}', '${escapeHtml(c.phone)}')">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <button class="btn-delete" onclick="confirmDeleteContact(${c.id}, '${escapeHtml(c.name)}')">
                        <i class="fas fa-trash"></i> Hapus
                    </button>
                    <button class="btn-icon" onclick="copyToClipboard('${escapeHtml(c.phone)}')">
                        <i class="fas fa-copy"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

// ===============================
// 📄 PAGINATION RENDER
// ===============================
function renderPagination(type) {
    const paginationContainer = document.getElementById('pagination');
    if (!paginationContainer) return;

    const totalPages = Math.ceil(totalItems / itemsPerPage);

    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }

    let html = '<div class="pagination-wrapper">';
    
    // Previous button
    html += `
        <button class="page-btn" onclick="changePage(${currentPage - 1}, '${type}')" ${currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-chevron-left"></i>
        </button>
    `;
    
    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
        html += `<button class="page-btn" onclick="changePage(1, '${type}')">1</button>`;
        if (startPage > 2) html += `<span class="page-dots">...</span>`;
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="changePage(${i}, '${type}')">
                ${i}
            </button>
        `;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span class="page-dots">...</span>`;
        html += `<button class="page-btn" onclick="changePage(${totalPages}, '${type}')">${totalPages}</button>`;
    }
    
    // Next button
    html += `
        <button class="page-btn" onclick="changePage(${currentPage + 1}, '${type}')" ${currentPage === totalPages ? 'disabled' : ''}>
            <i class="fas fa-chevron-right"></i>
        </button>
    `;
    
    // Info
    html += `<span class="page-info">Total: ${totalItems} data</span>`;
    html += '</div>';
    
    // Tambahkan style pagination jika belum ada
    if (!document.querySelector('#pagination-style')) {
        const style = document.createElement('style');
        style.id = 'pagination-style';
        style.textContent = `
            .pagination-wrapper {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 8px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            .page-btn {
                background: white;
                border: 1px solid #e2e8f0;
                padding: 8px 12px;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                color: #1e293b;
            }
            .page-btn:hover:not(:disabled) {
                background: #1e3a5f;
                color: white;
                border-color: #1e3a5f;
            }
            .page-btn.active {
                background: #1e3a5f;
                color: white;
                border-color: #1e3a5f;
            }
            .page-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .page-dots {
                padding: 0 4px;
                color: #64748b;
            }
            .page-info {
                margin-left: 12px;
                padding: 6px 12px;
                background: #f1f5f9;
                border-radius: 8px;
                font-size: 12px;
                color: #64748b;
            }
        `;
        document.head.appendChild(style);
    }
    
    paginationContainer.innerHTML = html;
}

// ===============================
// 🔄 CHANGE PAGE
// ===============================
function changePage(page, type) {
    if (page < 1) return;
    currentPage = page;
    
    const searchInput = document.getElementById('searchInput');
    const searchValue = searchInput ? searchInput.value : '';
    
    if (type === 'service') {
        loadServices(page, searchValue);
    } else if (type === 'contact') {
        loadContacts(page, searchValue);
    }
}

// ===============================
// 🔍 SEARCH FUNCTION
// ===============================
function searchTable() {
    currentPage = 1;
    const searchInput = document.getElementById('searchInput');
    const searchValue = searchInput ? searchInput.value : '';
    
    const path = window.location.pathname;
    
    if (path.includes('/services/')) {
        loadServices(1, searchValue);
    } else if (path.includes('/contacts/')) {
        loadContacts(1, searchValue);
    }
}

// ===============================
// ✏️ SERVICE CRUD
// ===============================
function openCreate() {
    currentEditId = null;
    
    document.getElementById('modalTitle').innerHTML = '<i class="fas fa-plus-circle"></i> Tambah Service';
    document.getElementById('serviceId').value = '';
    document.getElementById('name').value = '';
    document.getElementById('url').value = '';
    document.getElementById('service_type').value = 'HTTP';
    
    showModal();
}

function openEdit(id, name, url, type) {
    currentEditId = id;
    
    document.getElementById('modalTitle').innerHTML = '<i class="fas fa-edit"></i> Edit Service';
    document.getElementById('serviceId').value = id;
    document.getElementById('name').value = name;
    document.getElementById('url').value = url;
    document.getElementById('service_type').value = type;
    
    showModal();
}

async function saveService() {
    const payload = {
        name: document.getElementById('name').value.trim(),
        url: document.getElementById('url').value.trim(),
        service_type: document.getElementById('service_type').value
    };

    if (!payload.name || !payload.url) {
        showNotification('Nama dan URL wajib diisi', 'error');
        return;
    }

    try {
        if (currentEditId) {
            await apiFetch(`/api/services/${currentEditId}/`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            showNotification('Service berhasil diupdate');
        } else {
            await apiFetch('/api/services/', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            showNotification('Service berhasil ditambahkan');
        }

        closeModal();
        loadServices();

    } catch (error) {
        showNotification('Gagal simpan data', 'error');
    }
}

function confirmDeleteService(id, name) {
    currentDeleteId = id;
    currentDeleteType = 'service';
    
    const modal = document.getElementById('deleteModal');
    const text = document.getElementById('deleteText');
    
    text.innerHTML = `Yakin ingin menghapus <b>${escapeHtml(name)}</b>?`;
    modal.style.display = 'flex';
}

async function deleteService() {
    try {
        await apiFetch(`/api/services/${currentDeleteId}/`, {
            method: 'DELETE'
        });
        
        showNotification('Service berhasil dihapus');
        closeDeleteModal();
        loadServices();
        
    } catch (error) {
        showNotification('Gagal hapus service', 'error');
    }
}

// ===============================
// 👤 CONTACT CRUD
// ===============================
function openCreateContact() {
    currentEditId = null;
    
    document.getElementById('contactModalTitle').innerHTML = '<i class="fas fa-plus-circle"></i> Tambah Contact';
    document.getElementById('contactId').value = '';
    document.getElementById('contactName').value = '';
    document.getElementById('contactPhone').value = '';
    
    showContactModal();
}

function openEditContact(id, name, phone) {
    currentEditId = id;
    
    document.getElementById('contactModalTitle').innerHTML = '<i class="fas fa-edit"></i> Edit Contact';
    document.getElementById('contactId').value = id;
    document.getElementById('contactName').value = name;
    document.getElementById('contactPhone').value = phone;
    
    showContactModal();
}

async function saveContact() {
    const payload = {
        name: document.getElementById('contactName').value.trim(),
        phone_number: document.getElementById('contactPhone').value.trim()
    };

    if (!payload.name || !payload.phone_number) {
        showNotification('Nama dan Nomor WA wajib diisi', 'error');
        return;
    }

    try {
        if (currentEditId) {
            await apiFetch(`/api/contacts/${currentEditId}/`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            showNotification('Contact berhasil diupdate');
        } else {
            await apiFetch('/api/contacts/', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            showNotification('Contact berhasil ditambahkan');
        }

        closeContactModal();
        loadContacts();

    } catch (error) {
        showNotification('Gagal simpan data', 'error');
    }
}

function confirmDeleteContact(id, name) {
    currentDeleteId = id;
    currentDeleteType = 'contact';
    
    const modal = document.getElementById('deleteModal');
    const text = document.getElementById('deleteText');
    
    text.innerHTML = `Yakin ingin menghapus contact <b>${escapeHtml(name)}</b>?`;
    modal.style.display = 'flex';
}

async function deleteContact() {
    try {
        await apiFetch(`/api/contacts/${currentDeleteId}/`, {
            method: 'DELETE'
        });
        
        showNotification('Contact berhasil dihapus');
        closeDeleteModal();
        loadContacts();
        
    } catch (error) {
        showNotification('Gagal hapus contact', 'error');
    }
}

// ===============================
// 🗑️ CONFIRM DELETE (UNIVERSAL)
// ===============================
function confirmDelete() {
    if (currentDeleteType === 'service') {
        deleteService();
    } else if (currentDeleteType === 'contact') {
        deleteContact();
    }
}

// ===============================
// 📋 COPY TO CLIPBOARD
// ===============================
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Nomor berhasil disalin: ' + text, 'success');
    }).catch(() => {
        showNotification('Gagal menyalin nomor', 'error');
    });
}

// ===============================
// 🪟 MODAL CONTROL
// ===============================
function showModal() {
    document.getElementById('serviceModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('serviceModal').style.display = 'none';
}

function showContactModal() {
    document.getElementById('contactModal').style.display = 'flex';
}

function closeContactModal() {
    document.getElementById('contactModal').style.display = 'none';
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    currentDeleteId = null;
    currentDeleteType = null;
}

// ===============================
// ⚡ POWER API
// ===============================
let powerChart = null;
let powerRefreshInterval = null;

async function loadPowerData() {
    try {
        const data = await apiFetch('/api/power-data/');
        
        // Update current voltage
        if (data.voltage && data.voltage.length > 0) {
            const currentVoltage = data.voltage[data.voltage.length - 1];
            const voltageElement = document.getElementById('currentVoltage');
            if (voltageElement) {
                voltageElement.innerHTML = currentVoltage.toFixed(1) + ' V';
                updateVoltageStatus(currentVoltage);
            }
            
            // Update average
            const sum = data.voltage.reduce((a, b) => a + b, 0);
            const avg = (sum / data.voltage.length).toFixed(1);
            const avgElement = document.getElementById('avgVoltage');
            if (avgElement) {
                avgElement.innerHTML = avg + ' V';
            }
        }
        
        // Update chart
        if (powerChart && data.labels && data.voltage) {
            powerChart.data.labels = data.labels;
            powerChart.data.datasets[0].data = data.voltage;
            powerChart.update();
        }
        
        return data;
    } catch (error) {
        console.error('Error loading power data:', error);
    }
}

function updateVoltageStatus(voltage) {
    const statusElement = document.getElementById('voltageStatus');
    if (!statusElement) return;
    
    let statusText = '';
    let statusClass = '';
    
    if (voltage >= 210 && voltage <= 230) {
        statusText = '✓ Normal';
        statusClass = 'voltage-normal';
    } else if (voltage < 210) {
        statusText = '⚠ Low Voltage';
        statusClass = 'voltage-low';
    } else if (voltage > 230) {
        statusText = '⚠ High Voltage';
        statusClass = 'voltage-high';
    }
    
    statusElement.innerHTML = `<span class="voltage-status ${statusClass}">${statusText}</span>`;
}

function initPowerChart() {
    const ctx = document.getElementById('voltageChart');
    if (!ctx) return;
    
    powerChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Voltage (Volt)',
                data: [],
                borderColor: '#1e3a5f',
                backgroundColor: 'rgba(30, 58, 95, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#1e3a5f',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            aspectRatio: 2,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { usePointStyle: true, boxWidth: 10 }
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `Voltage: ${context.parsed.y.toFixed(1)} V`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Voltage (Volt)' },
                    ticks: { callback: (value) => value + ' V' }
                },
                x: {
                    title: { display: true, text: 'Waktu' }
                }
            }
        }
    });
    
    loadPowerData();
    
    if (powerRefreshInterval) clearInterval(powerRefreshInterval);
    powerRefreshInterval = setInterval(loadPowerData, 5000);
}

// ===============================
// 🧹 ESCAPE HTML
// ===============================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===============================
// 🚀 INITIALIZE PAGE
// ===============================
document.addEventListener('DOMContentLoaded', () => {
    console.log('App.js ready');
    
    // Close modals when clicking outside
    window.onclick = function(e) {
        const serviceModal = document.getElementById('serviceModal');
        const contactModal = document.getElementById('contactModal');
        const deleteModal = document.getElementById('deleteModal');
        
        if (e.target === serviceModal) closeModal();
        if (e.target === contactModal) closeContactModal();
        if (e.target === deleteModal) closeDeleteModal();
    };
    
    // Close modals with ESC key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeModal();
            closeContactModal();
            closeDeleteModal();
        }
    });
    
    // Load services if table exists
    if (document.getElementById('serviceTableBody')) {
        loadServices();
    }
    
    // Load contacts if table exists
    if (document.getElementById('contactTableBody')) {
        loadContacts();
    }
    
    // Initialize power chart if canvas exists
    if (document.getElementById('voltageChart')) {
        initPowerChart();
    }
});