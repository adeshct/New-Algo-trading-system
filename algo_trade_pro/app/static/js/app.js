/**
 * AlgoTrade Pro - Main JavaScript Application
 * Handles UI interactions, tab switching, and real-time updates
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize application
    initializeApp();
    
    // Tab switching functionality
    setupTabSwitching();
    
    // Button event handlers
    setupEventHandlers();
    
    // Update current time
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
});

function initializeApp() {
    console.log('AlgoTrade Pro initialized');
    
    // Show loading states
    showLoadingStates();
}

function setupTabSwitching() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    navButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Update active nav button
            navButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Show target tab content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === targetTab) {
                    content.classList.add('active');
                }
            });
            
            console.log('Switched to tab:', targetTab);
        });
    });
}

function setupEventHandlers() {
    // Start Trading button
    const startBtn = document.getElementById('startTrading');
    const stopBtn = document.getElementById('stopTrading');
    
    if (startBtn) {
        startBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/v1/control/start', {method: 'POST'});
                const result = await response.json();
                
                if (result.status === 'started') {
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    showNotification('Trading engine started', 'success');
                }
            } catch (error) {
                showNotification('Failed to start trading engine', 'error');
                console.error('Start error:', error);
            }
        });
    }
    
    // Stop Trading button
    if (stopBtn) {
        stopBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/v1/control/stop', {method: 'POST'});
                const result = await response.json();
                
                if (result.status === 'stopped') {
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                    showNotification('Trading engine stopped', 'info');
                }
            } catch (error) {
                showNotification('Failed to stop trading engine', 'error');
                console.error('Stop error:', error);
            }
        });
    }
    
    // Emergency Stop button
    const emergencyBtn = document.getElementById('emergencyStop');
    if (emergencyBtn) {
        emergencyBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to perform an emergency stop? This will halt all trading immediately.')) {
                emergencyStop();
            }
        });
    }
    
    // Generate Report button
    const reportBtn = document.getElementById('generateReport');
    if (reportBtn) {
        reportBtn.addEventListener('click', generateReport);
    }
}

function updateCurrentTime() {
    const timeElement = document.getElementById('currentTime');
    if (timeElement) {
        const now = new Date();
        timeElement.textContent = now.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Asia/Kolkata'
        });
    }
}

async function emergencyStop() {
    try {
        const response = await fetch('/api/v1/control/stop', {method: 'POST'});
        const result = await response.json();
        
        showNotification('Emergency stop executed', 'warning');
        console.log('Emergency stop result:', result);
    } catch (error) {
        showNotification('Emergency stop failed', 'error');
        console.error('Emergency stop error:', error);
    }
}

async function generateReport() {
    try {
        showNotification('Generating report...', 'info');
        
        const response = await fetch('/api/v1/reports/generate', {method: 'POST'});
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `trade_report_${new Date().toISOString().split('T')[0]}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            showNotification('Report downloaded successfully', 'success');
        } else {
            showNotification('Failed to generate report', 'error');
        }
    } catch (error) {
        showNotification('Error generating report', 'error');
        console.error('Report generation error:', error);
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification--${type}`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Show with animation
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => document.body.removeChild(notification), 300);
    }, 5000);
}

function showLoadingStates() {
    const loadingElements = document.querySelectorAll('[hx-get]');
    loadingElements.forEach(el => {
        if (!el.innerHTML.trim() || el.innerHTML.includes('Loading')) {
            el.innerHTML = '<div class="loading">Loading...</div>';
        }
    });
}

// Global function for strategy toggling (called from templates)
window.toggleStrategy = function(name, enable) {
    fetch('/api/v1/strategies/control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({strategy_name: name, enable: enable})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            htmx.ajax('GET', '/dashboard/strategy-cards', {target: '#strategy-cards'});
            showNotification(`Strategy ${name} ${enable ? 'enabled' : 'disabled'}`, 'success');
        } else {
            showNotification(`Failed to ${enable ? 'enable' : 'disable'} strategy`, 'error');
        }
    })
    .catch(error => {
        console.error('Strategy toggle error:', error);
        showNotification('Error toggling strategy', 'error');
    });
};

// WebSocket connection status
let wsConnected = false;
let wsReconnectAttempts = 0;
const maxReconnectAttempts = 5;

window.addEventListener('beforeunload', function() {
    console.log('AlgoTrade Pro shutting down...');
});
