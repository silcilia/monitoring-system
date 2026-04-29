{% extends 'services/base.html' %}

{% block content %}

<style>
    :root {
        --primary: #4361ee;
        --primary-dark: #3a56d4;
        --danger: #ef476f;
        --warning: #fbbf24;
        --success: #06d6a0;
        --dark: #1e293b;
        --gray: #64748b;
        --light-gray: #f1f5f9;
    }

    .page-header {
        margin-bottom: 2rem;
        position: relative;
    }

    .page-header::before {
        content: '';
        position: absolute;
        top: -20px;
        left: -20px;
        right: -20px;
        bottom: -20px;
        background: linear-gradient(135deg, rgba(67, 97, 238, 0.05) 0%, rgba(67, 97, 238, 0.02) 100%);
        border-radius: 1.5rem;
        z-index: -1;
    }

    .header-content {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 1rem;
        padding: 1.5rem 2rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(67, 97, 238, 0.1);
        position: relative;
        overflow: hidden;
    }

    .header-content::before {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 150px;
        height: 150px;
        background: radial-gradient(circle, rgba(67, 97, 238, 0.1) 0%, transparent 70%);
        border-radius: 50%;
    }

    .header-content::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100px;
        height: 100px;
        background: radial-gradient(circle, rgba(6, 214, 160, 0.08) 0%, transparent 70%);
        border-radius: 50%;
    }

    .page-header h2 {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 0 0 0.5rem 0;
        position: relative;
        z-index: 1;
    }

    .page-header h2 i {
        font-size: 2rem;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        animation: pulse-icon 2s infinite;
    }

    .title-text {
        background: linear-gradient(135deg, var(--dark), var(--primary-dark));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        font-size: 1.75rem;
        font-weight: 800;
    }

    .page-header p {
        margin: 0.5rem 0 0 0;
        position: relative;
        z-index: 1;
        font-size: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
        color: var(--gray);
    }

    .page-header p i {
        color: var(--primary);
    }

    @keyframes pulse-icon {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }

    .power-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2rem;
    }

    .stat-card-mini {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 1rem;
        padding: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        border: 1px solid rgba(67, 97, 238, 0.1);
    }

    .stat-card-mini:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 20px -8px rgba(67, 97, 238, 0.2);
    }

    .stat-icon-mini {
        width: 60px;
        height: 60px;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        border-radius: 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(67, 97, 238, 0.3);
    }

    .stat-icon-mini i {
        font-size: 1.75rem;
        color: white;
    }

    .stat-info-mini {
        flex: 1;
    }

    .stat-info-mini h4 {
        margin: 0 0 0.5rem 0;
        color: var(--gray);
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .voltage-value {
        font-size: 2rem;
        font-weight: bold;
        color: var(--dark);
        line-height: 1;
    }

    .chart-container {
        background: white;
        border-radius: 1rem;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
    }

    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid var(--light-gray);
    }

    .chart-header h3 {
        margin: 0;
        color: var(--dark);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .chart-header h3 i {
        color: var(--primary);
    }

    .chart-controls {
        display: flex;
        gap: 0.5rem;
    }

    .chart-btn {
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        color: white;
        padding: 0.5rem 1rem;
        border: none;
        border-radius: 0.5rem;
        font-size: 0.875rem;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        transition: all 0.3s ease;
    }

    .chart-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(67, 97, 238, 0.3);
    }

    canvas {
        max-height: 400px;
        width: 100%;
    }

    .chart-note {
        margin-top: 1rem;
        padding: 0.75rem;
        background: var(--light-gray);
        border-radius: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: var(--gray);
        font-size: 0.875rem;
    }

    .chart-note i {
        color: var(--primary);
    }

    .voltage-status {
        display: inline-block;
        margin-left: 0.5rem;
        font-size: 0.75rem;
        padding: 0.25rem 0.5rem;
        border-radius: 0.375rem;
        font-weight: 600;
    }

    .voltage-normal {
        background: #d1fae5;
        color: #065f46;
    }

    .voltage-low {
        background: #fed7aa;
        color: #92400e;
    }

    .voltage-high {
        background: #fee2e2;
        color: #991b1b;
    }

    @media (max-width: 768px) {
        .power-stats { grid-template-columns: 1fr; }
        .chart-header { flex-direction: column; gap: 1rem; align-items: flex-start; }
        .voltage-value { font-size: 1.5rem; }
        .stat-icon-mini { width: 50px; height: 50px; }
        .stat-icon-mini i { font-size: 1.5rem; }
        .header-content { padding: 1rem; }
        .title-text { font-size: 1.25rem; }
        .page-header h2 i { font-size: 1.5rem; }
    }
</style>

<!-- HEADER -->
<div class="page-header">
    <div class="header-content">
        <h2>
            <i class="fas fa-bolt"></i>
            <span class="title-text">Power Monitoring</span>
        </h2>
        <p>
            <i class="fas fa-charging-station"></i>
            Real-time voltage monitoring system
        </p>
    </div>
</div>

<div class="power-stats">
    <div class="stat-card-mini">
        <div class="stat-icon-mini">
            <i class="fas fa-charging-station"></i>
        </div>
        <div class="stat-info-mini">
            <h4>Current Voltage</h4>
            <div class="voltage-value" id="currentVoltage">-- V</div>
            <div id="voltageStatus"></div>
        </div>
    </div>
    <div class="stat-card-mini">
        <div class="stat-icon-mini">
            <i class="fas fa-chart-line"></i>
        </div>
        <div class="stat-info-mini">
            <h4>Average Voltage</h4>
            <div class="voltage-value" id="avgVoltage">-- V</div>
            <small>Last 10 readings</small>
        </div>
    </div>
</div>

<div class="chart-container">
    <div class="chart-header">
        <h3>
            <i class="fas fa-waveform"></i> 
            Grafik Tegangan (Voltage)
        </h3>
        <div class="chart-controls">
            <button class="chart-btn" onclick="refreshChart()">
                <i class="fas fa-sync-alt"></i> Refresh
            </button>
        </div>
    </div>
    <canvas id="voltageChart"></canvas>
    <div class="chart-note">
        <i class="fas fa-info-circle"></i> 
        Data diperbarui setiap 5 detik | Grafik menunjukkan 10 data terakhir
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

<script>
let chart;
let refreshInterval;

// 🔥 PERBAIKAN: Gunakan session authentication (kirim cookie)
function loadData() {
    const stats = document.querySelectorAll('.stat-card-mini');
    stats.forEach(stat => stat.style.opacity = '0.6');
    
    // Kirim credentials: 'include' agar cookie session ikut terkirim
    fetch('/api/power/', {
        method: 'GET',
        credentials: 'same-origin',  // Kirim cookie session
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => {
        if (res.status === 401) {
            throw new Error('Unauthorized - Silakan login ulang');
        }
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        console.log('Power data received:', data);
        
        if (chart) {
            chart.data.labels = data.labels || [];
            chart.data.datasets[0].data = data.voltage || [];
            chart.update('active');
        }
        
        if (data.voltage && data.voltage.length > 0) {
            const currentVoltage = data.voltage[data.voltage.length - 1];
            document.getElementById('currentVoltage').innerHTML = currentVoltage.toFixed(1) + ' V';
            updateVoltageStatus(currentVoltage);
            addPulseAnimation('currentVoltage');
            
            const sum = data.voltage.reduce((a, b) => a + b, 0);
            const avg = (sum / data.voltage.length).toFixed(1);
            document.getElementById('avgVoltage').innerHTML = avg + ' V';
            addPulseAnimation('avgVoltage');
        }
        
        stats.forEach(stat => stat.style.opacity = '1');
    })
    .catch(error => {
        console.error('Error loading power data:', error);
        document.getElementById('currentVoltage').innerHTML = 'Error';
        document.getElementById('avgVoltage').innerHTML = '-- V';
        document.getElementById('voltageStatus').innerHTML = '<span class="voltage-status voltage-low">⛔ ' + error.message + '</span>';
        stats.forEach(stat => stat.style.opacity = '1');
        
        // Jika error 401, redirect ke login
        if (error.message.includes('Unauthorized')) {
            setTimeout(() => {
                window.location.href = '/login/';
            }, 2000);
        }
    });
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

function addPulseAnimation(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.transform = 'scale(1.05)';
        setTimeout(() => { element.style.transform = 'scale(1)'; }, 200);
    }
}

// Initialize Chart
function initChart() {
    const ctx = document.getElementById('voltageChart').getContext('2d');
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Voltage (Volt)',
                data: [],
                borderColor: 'rgb(67, 97, 238)',
                backgroundColor: 'rgba(67, 97, 238, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: 'rgb(67, 97, 238)',
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
                    labels: { usePointStyle: true, boxWidth: 10, font: { size: 12, weight: 'bold' } }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(67, 97, 238, 0.5)',
                    borderWidth: 1,
                    callbacks: { label: function(context) { return `Voltage: ${context.parsed.y.toFixed(1)} V`; } }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Voltage (Volt)', font: { weight: 'bold', size: 12 }, color: '#64748b' },
                    grid: { color: 'rgba(0, 0, 0, 0.05)' },
                    ticks: { stepSize: 20, callback: function(value) { return value + ' V'; } }
                },
                x: {
                    title: { display: true, text: 'Waktu', font: { weight: 'bold', size: 12 }, color: '#64748b' },
                    grid: { display: false },
                    ticks: { maxRotation: 45, minRotation: 45 }
                }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false },
            animation: { duration: 750, easing: 'easeInOutQuart' }
        }
    });
}

function refreshChart() {
    const btn = document.querySelector('.chart-btn');
    if (btn) {
        btn.style.transform = 'rotate(360deg)';
        btn.disabled = true;
        setTimeout(() => {
            btn.style.transform = 'rotate(0deg)';
            btn.disabled = false;
        }, 500);
    }
    loadData();
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    initChart();
    setTimeout(() => loadData(), 100);
    refreshInterval = setInterval(loadData, 5000);
});

// Cleanup
window.addEventListener('beforeunload', function() {
    if (refreshInterval) clearInterval(refreshInterval);
});

// Stop interval when page is hidden
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }
    } else {
        if (!refreshInterval) {
            refreshInterval = setInterval(loadData, 5000);
            loadData();
        }
    }
});
</script>

{% endblock %}