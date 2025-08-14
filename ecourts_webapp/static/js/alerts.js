/**
 * Creative Alert System for Law Firm Case Management
 * Replaces all window.alert(), window.confirm(), and console alerts
 */

class CreativeAlerts {
    constructor() {
        this.alertContainer = null;
        this.confirmModal = null;
        this.alertQueue = [];
        this.maxAlerts = 5;
        this.defaultDuration = 5000;
        
        this.init();
    }

    // Initialize Alert System
    init() {
        this.createAlertContainer();
        this.createConfirmModal();
        this.injectStyles();
    }

    // Create Alert Container
    createAlertContainer() {
        this.alertContainer = document.createElement('div');
        this.alertContainer.id = 'alertContainer';
        this.alertContainer.className = 'alert-container';
        document.body.appendChild(this.alertContainer);
    }

    // Create Confirm Modal
    createConfirmModal() {
        const modalHTML = `
            <div id="confirmModal" class="confirm-modal">
                <div class="confirm-dialog">
                    <div id="confirmIcon" class="confirm-icon">
                        <i class="fas fa-question-circle"></i>
                    </div>
                    <div id="confirmTitle" class="confirm-title">Confirm Action</div>
                    <div id="confirmMessage" class="confirm-message">Are you sure you want to proceed?</div>
                    <div class="confirm-buttons">
                        <button id="confirmCancel" class="confirm-btn secondary">Cancel</button>
                        <button id="confirmOk" class="confirm-btn primary">Confirm</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.confirmModal = document.getElementById('confirmModal');
        this.initConfirmModalEvents();
    }

    // Inject Styles
    injectStyles() {
        if (document.getElementById('creative-alerts-styles')) return;
        
        const styles = `
            <style id="creative-alerts-styles">
                .alert-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    max-width: 400px;
                    pointer-events: none;
                }

                .creative-alert {
                    margin-bottom: 10px;
                    border-radius: 12px;
                    border: none;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
                    backdrop-filter: blur(10px);
                    pointer-events: all;
                    transform: translateX(100%);
                    opacity: 0;
                    transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
                    position: relative;
                    overflow: hidden;
                    padding: 1rem 1.25rem;
                }

                .creative-alert.show {
                    transform: translateX(0);
                    opacity: 1;
                }

                .creative-alert::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 4px;
                    height: 100%;
                    background: currentColor;
                }

                .creative-alert.alert-success {
                    background: linear-gradient(135deg, rgba(16, 185, 129, 0.95), rgba(52, 211, 153, 0.9));
                    color: white;
                    border-left: 4px solid #059669;
                }

                .creative-alert.alert-danger {
                    background: linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(248, 113, 113, 0.9));
                    color: white;
                    border-left: 4px solid #dc2626;
                }

                .creative-alert.alert-warning {
                    background: linear-gradient(135deg, rgba(245, 158, 11, 0.95), rgba(251, 191, 36, 0.9));
                    color: white;
                    border-left: 4px solid #d97706;
                }

                .creative-alert.alert-info {
                    background: linear-gradient(135deg, rgba(6, 182, 212, 0.95), rgba(34, 211, 238, 0.9));
                    color: white;
                    border-left: 4px solid #0891b2;
                }

                .creative-alert.alert-primary {
                    background: linear-gradient(135deg, rgba(37, 99, 235, 0.95), rgba(59, 130, 246, 0.9));
                    color: white;
                    border-left: 4px solid #1d4ed8;
                }

                .alert-icon {
                    font-size: 1.2rem;
                    margin-right: 12px;
                    min-width: 20px;
                    animation: bounceIn 0.6s ease;
                }

                .alert-content {
                    flex: 1;
                }

                .alert-title {
                    font-weight: 700;
                    font-size: 0.95rem;
                    margin-bottom: 2px;
                }

                .alert-message {
                    font-size: 0.85rem;
                    opacity: 0.95;
                    line-height: 1.4;
                }

                .alert-close {
                    background: none;
                    border: none;
                    color: inherit;
                    font-size: 1.2rem;
                    cursor: pointer;
                    opacity: 0.8;
                    transition: opacity 0.2s ease;
                    margin-left: 10px;
                }

                .alert-close:hover {
                    opacity: 1;
                }

                .alert-progress {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    height: 3px;
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 0 0 12px 12px;
                    transition: width linear;
                }

                .confirm-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(5px);
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    opacity: 0;
                    visibility: hidden;
                    transition: all 0.3s ease;
                }

                .confirm-modal.show {
                    opacity: 1;
                    visibility: visible;
                }

                .confirm-dialog {
                    background: white;
                    border-radius: 16px;
                    padding: 2rem;
                    max-width: 450px;
                    width: 90%;
                    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
                    transform: scale(0.7);
                    transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
                }

                .confirm-modal.show .confirm-dialog {
                    transform: scale(1);
                }

                .confirm-icon {
                    width: 60px;
                    height: 60px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 1.5rem;
                    font-size: 1.5rem;
                }

                .confirm-icon.warning {
                    background: linear-gradient(135deg, #fef3c7, #fed7aa);
                    color: #d97706;
                }

                .confirm-icon.danger {
                    background: linear-gradient(135deg, #fee2e2, #fecaca);
                    color: #dc2626;
                }

                .confirm-icon.info {
                    background: linear-gradient(135deg, #dbeafe, #bfdbfe);
                    color: #2563eb;
                }

                .confirm-title {
                    font-size: 1.25rem;
                    font-weight: 700;
                    color: #1f2937;
                    text-align: center;
                    margin-bottom: 0.5rem;
                }

                .confirm-message {
                    color: #6b7280;
                    text-align: center;
                    margin-bottom: 2rem;
                    line-height: 1.5;
                }

                .confirm-buttons {
                    display: flex;
                    gap: 12px;
                    justify-content: center;
                }

                .confirm-btn {
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: 8px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    min-width: 100px;
                }

                .confirm-btn.primary {
                    background: linear-gradient(135deg, #2563eb, #3b82f6);
                    color: white;
                }

                .confirm-btn.primary:hover {
                    background: linear-gradient(135deg, #1d4ed8, #2563eb);
                    transform: translateY(-1px);
                }

                .confirm-btn.danger {
                    background: linear-gradient(135deg, #ef4444, #f87171);
                    color: white;
                }

                .confirm-btn.danger:hover {
                    background: linear-gradient(135deg, #dc2626, #ef4444);
                    transform: translateY(-1px);
                }

                .confirm-btn.secondary {
                    background: #f3f4f6;
                    color: #374151;
                    border: 1px solid #d1d5db;
                }

                .confirm-btn.secondary:hover {
                    background: #e5e7eb;
                    transform: translateY(-1px);
                }

                .loading-spinner {
                    display: inline-block;
                    width: 16px;
                    height: 16px;
                    border: 2px solid rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    border-top-color: white;
                    animation: spin 1s ease-in-out infinite;
                    margin-right: 8px;
                }

                @keyframes spin {
                    to { transform: rotate(360deg); }
                }

                @keyframes bounceIn {
                    0% {
                        transform: scale(0.3);
                        opacity: 0;
                    }
                    50% {
                        transform: scale(1.05);
                    }
                    70% {
                        transform: scale(0.9);
                    }
                    100% {
                        transform: scale(1);
                        opacity: 1;
                    }
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }

    // Show Alert
    showAlert(message, type = 'info', title = null, duration = null) {
        if (this.alertQueue.length >= this.maxAlerts) {
            this.removeAlert(this.alertQueue[0]);
        }

        const alertElement = this.createAlertElement(message, type, title, duration);
        this.alertContainer.appendChild(alertElement);
        this.alertQueue.push(alertElement);

        setTimeout(() => {
            alertElement.classList.add('show');
        }, 100);

        const alertDuration = duration || this.defaultDuration;
        if (alertDuration > 0) {
            this.startProgressBar(alertElement, alertDuration);
            setTimeout(() => {
                this.removeAlert(alertElement);
            }, alertDuration);
        }

        return alertElement;
    }

    // Create Alert Element
    createAlertElement(message, type, title, duration) {
        const alert = document.createElement('div');
        alert.className = `creative-alert alert-${type}`;
        
        const icon = this.getIcon(type);
        const alertTitle = title || this.getDefaultTitle(type);

        alert.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="alert-icon">
                    <i class="fas fa-${icon}"></i>
                </div>
                <div class="alert-content">
                    <div class="alert-title">${alertTitle}</div>
                    <div class="alert-message">${message}</div>
                </div>
                <button class="alert-close" onclick="window.alertSystem.removeAlert(this.parentElement.parentElement)">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            ${duration && duration > 0 ? '<div class="alert-progress"></div>' : ''}
        `;

        return alert;
    }

    // Get Icon for Alert Type
    getIcon(type) {
        const icons = {
            success: 'check-circle',
            danger: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle',
            primary: 'bell'
        };
        return icons[type] || 'info-circle';
    }

    // Get Default Title
    getDefaultTitle(type) {
        const titles = {
            success: 'Success!',
            danger: 'Error!',
            warning: 'Warning!',
            info: 'Information',
            primary: 'Notice'
        };
        return titles[type] || 'Notice';
    }

    // Start Progress Bar
    startProgressBar(alertElement, duration) {
        const progressBar = alertElement.querySelector('.alert-progress');
        if (progressBar) {
            progressBar.style.width = '100%';
            setTimeout(() => {
                progressBar.style.width = '0%';
                progressBar.style.transition = `width ${duration}ms linear`;
            }, 100);
        }
    }

    // Remove Alert
    removeAlert(alertElement) {
        if (!alertElement || !alertElement.parentNode) return;
        
        alertElement.classList.remove('show');
        setTimeout(() => {
            if (alertElement.parentNode) {
                alertElement.parentNode.removeChild(alertElement);
                const index = this.alertQueue.indexOf(alertElement);
                if (index > -1) {
                    this.alertQueue.splice(index, 1);
                }
            }
        }, 400);
    }

    // Show Confirmation Dialog
    showConfirm(message, type = 'warning', title = null) {
        return new Promise((resolve) => {
            const confirmTitle = title || this.getConfirmTitle(type);
            const iconClass = this.getConfirmIcon(type);
            
            document.getElementById('confirmTitle').textContent = confirmTitle;
            document.getElementById('confirmMessage').textContent = message;
            
            const confirmIcon = document.getElementById('confirmIcon');
            confirmIcon.className = `confirm-icon ${type}`;
            confirmIcon.innerHTML = `<i class="fas fa-${iconClass}"></i>`;
            
            const confirmBtn = document.getElementById('confirmOk');
            confirmBtn.className = `confirm-btn ${type === 'danger' ? 'danger' : 'primary'}`;
            
            this.confirmModal.classList.add('show');
            
            const handleConfirm = () => {
                this.confirmModal.classList.remove('show');
                cleanup();
                resolve(true);
            };
            
            const handleCancel = () => {
                this.confirmModal.classList.remove('show');
                cleanup();
                resolve(false);
            };
            
            const handleEscape = (e) => {
                if (e.key === 'Escape') {
                    handleCancel();
                }
            };
            
            const cleanup = () => {
                confirmBtn.removeEventListener('click', handleConfirm);
                document.getElementById('confirmCancel').removeEventListener('click', handleCancel);
                document.removeEventListener('keydown', handleEscape);
            };
            
            confirmBtn.addEventListener('click', handleConfirm);
            document.getElementById('confirmCancel').addEventListener('click', handleCancel);
            document.addEventListener('keydown', handleEscape);
        });
    }

    // Get Confirm Title
    getConfirmTitle(type) {
        const titles = {
            warning: 'Confirm Action',
            danger: 'Dangerous Action',
            info: 'Please Confirm'
        };
        return titles[type] || 'Confirm';
    }

    // Get Confirm Icon
    getConfirmIcon(type) {
        const icons = {
            warning: 'exclamation-triangle',
            danger: 'skull-crossbones',
            info: 'question-circle'
        };
        return icons[type] || 'question-circle';
    }

    // Initialize Confirm Modal Events
    initConfirmModalEvents() {
        this.confirmModal.addEventListener('click', (e) => {
            if (e.target === this.confirmModal) {
                this.confirmModal.classList.remove('show');
            }
        });
    }

    // Show Loading Alert
    showLoadingAlert(message = 'Processing...', type = 'info') {
        const alertElement = this.createLoadingAlert(message, type);
        this.alertContainer.appendChild(alertElement);
        
        setTimeout(() => {
            alertElement.classList.add('show');
        }, 100);
        
        return alertElement;
    }

    // Create Loading Alert
    createLoadingAlert(message, type) {
        const alert = document.createElement('div');
        alert.className = `creative-alert alert-${type}`;
        
        alert.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="loading-spinner"></div>
                <div class="alert-content">
                    <div class="alert-message">${message}</div>
                </div>
            </div>
        `;

        return alert;
    }

    // Clear all alerts
    clearAll() {
        this.alertQueue.forEach(alert => this.removeAlert(alert));
    }
}

// Initialize Alert System
document.addEventListener('DOMContentLoaded', function() {
    if (!window.alertSystem) {
        window.alertSystem = new CreativeAlerts();
        
        // Global Functions for Easy Use
        window.showAlert = function(message, type = 'info', title = null, duration = null) {
            return window.alertSystem.showAlert(message, type, title, duration);
        };

        window.showConfirm = function(message, type = 'warning', title = null) {
            return window.alertSystem.showConfirm(message, type, title);
        };

        window.showLoadingAlert = function(message = 'Processing...', type = 'info') {
            return window.alertSystem.showLoadingAlert(message, type);
        };

        // Replace browser alert and confirm
        window.alert = function(message) {
            return window.alertSystem.showAlert(message, 'info');
        };

        window.confirm = function(message) {
            return window.alertSystem.showConfirm(message, 'warning');
        };

        console.log('✅ Creative Alert System initialized and browser alerts replaced');
    }
});
