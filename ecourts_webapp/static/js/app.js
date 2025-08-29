// Law Firm Case Management JavaScript - NO BROWSER ALERTS VERSION



// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing Law Firm Case Management...');
    initializeSearch();
    setupNotesChangeHandlers();
    initializeSelectAllButtons();
    console.log('App initialized successfully');
});

// Initialize select all button event listeners
function initializeSelectAllButtons() {
    document.querySelectorAll('[data-toggle-select]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation(); // Prevent tab switching
            const tabId = this.dataset.toggleSelect;
            toggleAllSelection(tabId);
        });
    });
}

// Tab switching with filter memory
function switchTab(tabId) {
    console.log('Switching to tab:', tabId);
    
    currentTab = tabId;
    selectedCases.clear();
    hideBulkMenu();
    
    // Reset ALL toggle buttons to initial state
    document.querySelectorAll('[data-toggle-select] span').forEach(span => {
        span.textContent = 'Select All';
        span.parentElement.classList.remove('btn-primary');
        span.parentElement.classList.add('btn-outline-primary');
    });

    updateBulkActions();
}

function getActiveFilterButton() {
    const activeBtn = document.querySelector('#dateFilterGroup .btn.active');
    if (activeBtn) {
        const onclick = activeBtn.getAttribute('onclick');
        if (onclick) {
            const match = onclick.match(/setDateFilter\('(.+?)'\)/);
            return match ? match[1] : null;
        }
    }
    return null;
}

function updateToggleButtonText(tabId) {
    const toggleTexts = {
        'all-cases': 'toggleAllText',
        'petitioner-cases': 'togglePetitionerText',
        'respondent-cases': 'toggleRespondentText',
        'unassigned-cases': 'toggleUnassignedText',
        'upcoming-cases': 'toggleUpcomingText',
        'reviewed-cases': 'toggleReviewedText'
    };
    
    Object.values(toggleTexts).forEach(textId => {
        const element = document.getElementById(textId);
        if (element) element.textContent = 'Select All';
    });
}

function initializeSearch() {
    console.log('Search initialized');
    allCasesData = Array.from(document.querySelectorAll('.case-card')).map(card => {
        const container = card.closest('.col-xl-4, .col-lg-6');
        return {
            element: container,
            cino: card.dataset.cino,
            caseNo: card.querySelector('.card-title')?.textContent || '',
            petitioner: card.querySelector('.case-parties .col-6:first-child .fw-medium')?.textContent || '',
            respondent: card.querySelector('.case-parties .col-6:last-child .fw-medium')?.textContent || '',
            establishment: card.querySelector('.case-details')?.textContent || '',
            nextDate: extractDateFromCard(card) || '',
            isChanged: card.dataset.changed === 'true',
            hasNotes: card.querySelector('.notes-input')?.value.trim() !== ''
        };
    });
    console.log(`Search initialized with ${allCasesData.length} cases`);
}

function extractDateFromCard(card) {
    try {
        const detailsText = card.querySelector('.case-details')?.textContent || '';
        const dateMatch = detailsText.match(/Next Hearing:\s*(\d{4}-\d{2}-\d{2})/i);
        return dateMatch ? dateMatch[1] : '';
    } catch (e) {
        return '';
    }
}


function setDateFilter(period) {
    console.log('Setting date filter:', period);
    
    const today = new Date();
    const dateFromInput = document.getElementById('dateFromInput');
    const dateToInput = document.getElementById('dateToInput');
    
    if (!dateFromInput || !dateToInput) {
        console.error('Date input fields not found');
        return;
    }
    
    let fromDate, toDate;

    switch (period) {
        case 'today':
            fromDate = toDate = today.toISOString().split('T')[0];
            break;
            
        case 'thisWeek':
            const startOfWeek = new Date(today);
            startOfWeek.setDate(today.getDate() - today.getDay());
            const endOfWeek = new Date(startOfWeek);
            endOfWeek.setDate(startOfWeek.getDate() + 6);
            fromDate = startOfWeek.toISOString().split('T')[0];
            toDate = endOfWeek.toISOString().split('T');
            break;
        case 'thisMonth':
            fromDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T');
            toDate = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T');
            break;
        case 'nextWeek':
            const nextWeekStart = new Date(today);
            nextWeekStart.setDate(today.getDate() + (7 - today.getDay()));
            const nextWeekEnd = new Date(nextWeekStart);
            nextWeekEnd.setDate(nextWeekStart.getDate() + 6);
            fromDate = nextWeekStart.toISOString().split('T');
            toDate = nextWeekEnd.toISOString().split('T');
            break;
        case 'all':
                fromDate = toDate = '';
                break;
        default:
            console.error('Unknown period:', period);
            return;
    }

    // Update input fields
    dateFromInput.value = fromDate;
    dateToInput.value = toDate;

    // Update current filters
    currentFilters.dateFrom = fromDate;
    currentFilters.dateTo = toDate;

    // Update active button state
    document.querySelectorAll('#dateFilterGroup .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Find and activate the correct button
    const targetBtn = document.querySelector(`[onclick="setDateFilter('${period}')"]`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }

    console.log(`Date filter set: ${fromDate} to ${toDate}`);
    
    // Apply the filter
    filterCases();
}

function clearDateFilter() {
    const dateFromInput = document.getElementById('dateFromInput');
    const dateToInput = document.getElementById('dateToInput');
    
    if (dateFromInput) dateFromInput.value = '';
    if (dateToInput) dateToInput.value = '';
    
    document.querySelectorAll('#dateFilterGroup .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    handleSearch();
}

function clearAllFilters() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
        searchInput.addEventListener('keyup', handleSearch);
    }
    
    const dateFromInput = document.getElementById('dateFromInput');
    if (dateFromInput) {
        dateFromInput.addEventListener('change', handleSearch);
        dateFromInput.addEventListener('input', handleSearch);
    }
    
    const dateToInput = document.getElementById('dateToInput');
    if (dateToInput) {
        dateToInput.addEventListener('change', handleSearch);
        dateToInput.addEventListener('input', handleSearch);
    }

    if (searchInput) searchInput.value = '';
    if (dateFromInput) dateFromInput.value = '';
    if (dateToInput) dateToInput.value = '';

    // Clear filter object
    currentFilters = { text: '', dateFrom: '', dateTo: '', advanced: {} };

    // Remove active states
    document.querySelectorAll('#dateFilterGroup .btn.active').forEach(btn => {
        btn.classList.remove('active');
    });

    // Apply cleared filters
    filterCases();
    updateTabCounts();
}

// FIXED: Handle search function
function handleSearch() {
    console.log('Handling search...');
    
    // Get current values from inputs
    const searchText = document.getElementById('searchInput')?.value || '';
    const dateFrom = document.getElementById('dateFromInput')?.value || '';
    const dateTo = document.getElementById('dateToInput')?.value || '';

    // Update current filters
    currentFilters = {
        text: searchText.trim(),
        dateFrom: dateFrom,
        dateTo: dateTo,
        advanced: currentFilters.advanced || {}
    };

    console.log('Current filters:', currentFilters);
    
    // Apply filters
    filterCases();
}

function filterCases() {
    let visibleCount = 0;
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (!activeTabPane) return;

    const casesToFilter = activeTabPane.querySelectorAll('.case-card');
    
    casesToFilter.forEach(card => {
        const container = card.closest('.col-xl-4, .col-lg-6');
        if (!container) return;

        let matches = true

        // FIXED: Use data attributes for reliable data access
        const caseData = {
            cino: card.dataset.cino || '',
            caseNo: card.dataset.caseNo || '',
            petitioner: card.dataset.petitioner || '',
            respondent: card.dataset.respondent || '',
            establishment: card.dataset.establishment || '',
            nextDate: card.dataset.nextDate || ''
        };

        // Text search filtering
        if (currentFilters.text) {
            const searchTerm = currentFilters.text.toLowerCase();
            matches = matches && (
                caseData.cino.toLowerCase().includes(searchTerm) ||
                caseData.caseNo.toLowerCase().includes(searchTerm) ||
                caseData.petitioner.toLowerCase().includes(searchTerm) ||
                caseData.respondent.toLowerCase().includes(searchTerm) ||
                caseData.establishment.toLowerCase().includes(searchTerm)
            );
        }

        // FIXED: Date filtering with proper comparison
        if ((currentFilters.dateFrom || currentFilters.dateTo) && caseData.nextDate) {
            try {
                const caseDate = new Date(caseData.nextDate);
                
                // Check if the case date is valid
                if (!isNaN(caseDate.getTime())) {
                    if (currentFilters.dateFrom) {
                        const fromDate = new Date(currentFilters.dateFrom);
                        if (caseDate < fromDate) {
                            matches = false;
                        }
                    }
                    
                    if (currentFilters.dateTo) {
                        const toDate = new Date(currentFilters.dateTo);
                        // Include the entire end date
                        toDate.setHours(23, 59, 59, 999);
                        if (caseDate > toDate) {
                            matches = false;
                        }
                    }
                } else {
                    // If date is invalid, exclude from date-filtered results
                    if (currentFilters.dateFrom || currentFilters.dateTo) {
                        matches = false;
                    }
                }
            } catch (e) {
                console.error('Date parsing error:', e);
                matches = false;
            }
        } else if (currentFilters.dateFrom || currentFilters.dateTo) {
            // If filtering by date but case has no date, exclude it
            matches = false;
        }

        // Apply visibility
        container.style.display = matches ? 'block' : 'none';
        if (matches) visibleCount++;
    });

    updateSearchResultsCount(visibleCount);
    updateToggleButtonState();
    updateTabCounts();
}

function updateSearchResultsCount(count) {
    const countElement = document.getElementById('searchResultsCount');
    if (countElement) {
        countElement.textContent = count;
        countElement.className = count > 0 ? 'badge bg-primary' : 'badge bg-warning';
    }
}

function markAsReviewed(cino) {
    console.log('Marking case as reviewed:', cino);
    
    const card = document.querySelector(`[data-cino="${cino}"]`);
    if (!card) {
        console.error('Card not found for CINO:', cino);
        showAlert('Error: Case not found', 'danger');
        return;
    }
    
    const notesInput = card.querySelector('.notes-input');
    const notes = notesInput ? notesInput.value.trim() : '';
    
    // Get the button that triggered this
    const saveBtn = event.target.closest('button');
    if (!saveBtn) {
        console.error('Save button not found');
        return;
    }
    
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    
    fetch(`/case/${cino}/update`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            notes: notes
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        console.log('Case updated successfully:', data);
        showAlert('Case marked as reviewed successfully', 'success');
        
        // Update the card UI
        card.dataset.changed = 'false';
        card.classList.remove('border-warning');
        card.classList.add('border-success');
        
        // Reload after a short delay
        setTimeout(() => {
            location.reload();
        }, 1000);
    })
    .catch(error => {
        console.error('Mark as reviewed error:', error);
        showAlert('Failed to mark as reviewed: ' + error.message, 'danger');
    })
    .finally(() => {
        // Restore button state
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    });
}


// UPDATED: Remove from reviewed and revert notes - WITH LOADING
function removeFromReviewed(cino, clearNotes = true) {
    const actionText = clearNotes ? 
        'remove this case from reviewed and clear all notes' : 
        'remove this case from reviewed and revert notes to previous state';
    
    showConfirm(`Are you sure you want to ${actionText}?`, 'warning')
        .then(confirmed => {
            if (!confirmed) return;

            const button = event.target.closest('button');
            const originalText = button ? button.innerHTML : '';

            if (button) {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing...';
            }

            fetch('/remove_from_reviewed_and_revert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    cinos: [cino],
                    clear_notes: clearNotes
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }

                const successMessage = clearNotes ? 
                    'Case removed from reviewed and all notes cleared' : 
                    'Case removed from reviewed and notes reverted to previous state';
                
                showAlert(successMessage, 'success');
                
                setTimeout(() => {
                    location.reload();
                }, 1000);
            })
            .catch(error => {
                showAlert('Failed to remove: ' + error.message, 'danger');
            })
            .finally(() => {
                if (button) {
                    button.disabled = false;
                    button.innerHTML = originalText;
                }
            });
        });
}

function removeFromReviewedComprehensive(cino, actionType = 'revert') {
    const actionText = actionType === 'clear' ? 
        'remove this case from reviewed and clear all user fields (notes, dates, user side)' : 
        'remove this case from reviewed and restore all fields to their exact previous state';
    
    showConfirm(`Are you sure you want to ${actionText}?`, 'warning')
        .then(confirmed => {
            if (!confirmed) return;

            const button = event.target.closest('button');
            const originalText = button ? button.innerHTML : '';

            if (button) {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            }

            fetch('/remove_from_reviewed_comprehensive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    cinos: [cino],
                    action_type: actionType
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }

                const successMessage = actionType === 'clear' ? 
                    'Case removed from reviewed and all fields cleared' : 
                    'Case removed from reviewed and all fields restored to previous state';
                
                showAlert(successMessage, 'success');
                
                // Show detailed restoration info if available
                if (data.details) {
                    console.log('Restoration details:', data.details);
                }
                
                setTimeout(() => {
                    location.reload();
                }, 1000);
            })
            .catch(error => {
                showAlert('Failed to process: ' + error.message, 'danger');
            })
            .finally(() => {
                if (button) {
                    button.disabled = false;
                    button.innerHTML = originalText;
                }
            });
        });
}

function removeFromReviewedComplete(cino, actionType = 'restore_complete') {
    const actionText = actionType === 'clear_user_data' ? 
        'remove this case from reviewed and clear only user-added data (notes, dates, user side)' : 
        'remove this case from reviewed and restore ALL fields (Purpose, Court, Type, Parties, etc.) to their exact previous state';
    
    showConfirm(`Are you sure you want to ${actionText}?`, 'warning')
        .then(confirmed => {
            if (!confirmed) return;

            const button = event.target.closest('button');
            const originalText = button ? button.innerHTML : '';

            if (button) {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restoring...';
            }

            fetch('/remove_from_reviewed_comprehensive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    cinos: [cino],
                    action_type: actionType
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }

                const successMessage = actionType === 'clear_user_data' ? 
                    'Case removed from reviewed and user data cleared' : 
                    'Case removed from reviewed and ALL FIELDS restored to previous state';
                
                showAlert(successMessage, 'success');
                
                // Show which fields were restored
                if (data.fields_restored && data.fields_restored.length > 0) {
                    console.log('Fields restored:', data.fields_restored);
                }
                
                setTimeout(() => {
                    location.reload();
                }, 1000);
            })
            .catch(error => {
                showAlert('Failed to process: ' + error.message, 'danger');
            })
            .finally(() => {
                if (button) {
                    button.disabled = false;
                    button.innerHTML = originalText;
                }
            });
        });
}


// Updated bulk function with comprehensive options
function bulkRemoveFromReviewedWithComprehensiveChoice() {
    if (selectedCases.size === 0) {
        showAlert('Please select cases first', 'warning');
        return;
    }

    // Show a custom choice dialog with comprehensive options
    showChoiceDialog(
        'Remove from Reviewed Section',
        'How do you want to handle ALL the fields (notes, dates, user side) for the selected cases?',
        [
            {
                text: 'Clear All Fields',
                class: 'btn-danger',
                action: () => bulkRemoveFromReviewedComprehensive('clear')
            },
            {
                text: 'Revert All Fields to Previous State',
                class: 'btn-warning', 
                action: () => bulkRemoveFromReviewedComprehensive('revert')
            },
            {
                text: 'Legacy Mode (Notes Only)',
                class: 'btn-info',
                action: () => bulkRemoveFromReviewed(true) 
            },
            {
                text: 'Cancel',
                class: 'btn-secondary',
                action: () => {} // Do nothing
            }
        ]
    );
}

function bulkRemoveFromReviewedComprehensive(actionType = 'revert') {
    const caseArray = Array.from(selectedCases);
    const actionText = actionType === 'clear' ? 'clear all user fields' : 'revert all fields to previous state';
    
    showLoadingOverlay(`Processing ${caseArray.length} cases - ${actionText}...`);

    fetch('/remove_from_reviewed_comprehensive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            cinos: caseArray,
            action_type: actionType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }

        showAlert(data.message, 'success');
        clearSelection();
        
        setTimeout(() => {
            location.reload();
        }, 1500);
    })
    .catch(error => {
        showAlert('Bulk operation failed: ' + error.message, 'danger');
    })
    .finally(() => {
        hideLoadingOverlay();
    });
}

// Enhanced choice dialog for better UX
function showChoiceDialog(title, message, choices) {
    return new Promise((resolve) => {
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop';
        backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 9998;
            display: flex;
            justify-content: center;
            align-items: center;
        `;
        
        const modal = document.createElement('div');
        modal.className = 'modal-content';
        modal.style.cssText = `
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            width: 90%;
            text-align: center;
        `;
        
        const buttonsHtml = choices.map((choice, index) => 
            `<button class="btn ${choice.class} mb-2 mx-1" id="choice${index}" style="min-width: 150px;">${choice.text}</button>`
        ).join('');
        
        modal.innerHTML = `
            <div class="mb-3">
                <i class="fas fa-question-circle text-warning" style="font-size: 3rem;"></i>
            </div>
            <h5 class="mb-3">${title}</h5>
            <p class="mb-4">${message}</p>
            <div class="d-flex flex-column align-items-center">
                ${buttonsHtml}
            </div>
        `;
        
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        
        // Handle button clicks
        choices.forEach((choice, index) => {
            const btn = modal.querySelector(`#choice${index}`);
            btn.addEventListener('click', () => {
                backdrop.remove();
                choice.action();
                resolve(true);
            });
        });
        
        // Close on backdrop click
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                backdrop.remove();
                resolve(false);
            }
        });
    });
}


// Add a new function for bulk operations with clear choice
function bulkRemoveFromReviewedWithChoice() {
    if (selectedCases.size === 0) {
        showAlert('Please select cases first', 'warning');
        return;
    }

    // Show a custom choice dialog
    showChoiceDialog(
        'Remove from Reviewed Section',
        'How do you want to handle the notes for the selected cases?',
        [
            {
                text: 'Clear All Notes',
                class: 'btn-danger',
                action: () => bulkRemoveFromReviewed(true)
            },
            {
                text: 'Revert to Previous Notes',
                class: 'btn-warning', 
                action: () => bulkRemoveFromReviewed(false)
            },
            {
                text: 'Cancel',
                class: 'btn-secondary',
                action: () => {} // Do nothing
            }
        ]
    );
}

function bulkRemoveFromReviewed(clearNotes = true) {
    const caseArray = Array.from(selectedCases);
    const actionText = clearNotes ? 'clear all notes' : 'revert notes to previous state';
    
    showLoadingOverlay(`Removing ${caseArray.length} cases from reviewed and ${actionText}...`);

    fetch('/remove_from_reviewed_and_revert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            cinos: caseArray,
            clear_notes: clearNotes
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }

        showAlert(data.message, 'success');
        clearSelection();
        
        setTimeout(() => {
            location.reload();
        }, 1500);
    })
    .catch(error => {
        showAlert('Bulk removal failed: ' + error.message, 'danger');
    })
    .finally(() => {
        hideLoadingOverlay();
    });
}

// Clear all selected cases
function clearSelection() {
    selectedCases.clear();
    
    // Uncheck all checkboxes
    document.querySelectorAll('.case-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Update UI elements
    updateBulkActions();
    hideBulkMenu();
    
    // Reset toggle buttons
    document.querySelectorAll('[data-toggle-select] span').forEach(span => {
        span.textContent = 'Select All';
        span.parentElement.classList.remove('btn-primary');
        span.parentElement.classList.add('btn-outline-primary');
    });
    
    console.log('Selection cleared');
}


// Loading overlay functions
function showLoadingOverlay(message = 'Processing...') {
    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
        color: white;
        font-size: 18px;
    `;
    
    overlay.innerHTML = `
        <div style="text-align: center;">
            <div class="spinner-border text-light mb-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <div>${message}</div>
        </div>
    `;
    
    document.body.appendChild(overlay);
}

// Hide loading overlay
function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.remove();
    }
}


function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.remove('show');
        setTimeout(() => {
            overlay.remove();
        }, 300); // Wait for fade out transition
    }
}





function toggleAllSelection(tabId) {
    console.log('Toggling selection for tab:', tabId);
    
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (!activeTabPane) return;

    // Get only visible checkboxes (not filtered out)
    const visibleCheckboxes = Array.from(activeTabPane.querySelectorAll('.case-selection')).filter(checkbox => {
        const container = checkbox.closest('.col-xl-4, .col-lg-6');
        return container && container.style.display !== 'none';
    });

    if (visibleCheckboxes.length === 0) return;

    // Check if all visible checkboxes are selected
    const allSelected = visibleCheckboxes.every(checkbox => checkbox.checked);

    // Get the SINGLE toggle button for this tab
    const toggleButton = document.querySelector(`[data-toggle-select="${tabId}"] span`);
    
    if (allSelected) {
        // Deselect all
        visibleCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
            selectedCases.delete(checkbox.dataset.cino);
        });
        
        if (toggleButton) {
            toggleButton.textContent = 'Select All';
            toggleButton.parentElement.classList.remove('btn-primary');
            toggleButton.parentElement.classList.add('btn-outline-primary');
        }
        
        hideBulkMenu();
        
    } else {
        // Select all
        visibleCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
            selectedCases.add(checkbox.dataset.cino);
        });
        
        if (toggleButton) {
            toggleButton.textContent = 'Deselect All';
            toggleButton.parentElement.classList.remove('btn-outline-primary');
            toggleButton.parentElement.classList.add('btn-primary');
        }
        
        showBulkMenu();
    }

    updateBulkActions();
    console.log(`${allSelected ? 'Deselected' : 'Selected'} ${visibleCheckboxes.length} cases`);
}

function showBulkMenu() {
    const bulkContainer = document.getElementById('bulkActionsContainer');
    if (bulkContainer) {
        bulkContainer.style.display = 'block';
        bulkContainer.classList.add('show');
    }
}

// Hide bulk actions menu  
function hideBulkMenu() {
    const bulkContainer = document.getElementById('bulkActionsContainer');
    if (bulkContainer) {
        bulkContainer.style.display = 'none';
        bulkContainer.classList.remove('show');
    }
}

// Also update the getContainerByTabId function to include changed-cases
function getContainerByTabId(tabId) {
    switch(tabId) {
        case 'all-cases':
            return document.getElementById('allCasesContainer');
        case 'changed-cases':
            return document.getElementById('changedCasesContainer');
        case 'reviewed-cases':
            return document.getElementById('reviewedCasesContainer');
        case 'upcoming-cases':
            return document.getElementById('upcomingCasesContainer');
        default:
            return document.getElementById('allCasesContainer');
    }
}


function updateCaseSelection() {
    selectedCases.clear();
    const checkedBoxes = document.querySelectorAll('.case-selection:checked');
    
    checkedBoxes.forEach(checkbox => {
        selectedCases.add(checkbox.dataset.cino);
    });

    updateBulkActions();
    updateToggleButtonState();
}

function updateToggleButtonState() {
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (!activeTabPane) return;

    const tabId = activeTabPane.id;
    const toggleButton = document.querySelector(`[data-toggle-select="${tabId}"] span`);
    
    if (toggleButton) {
        const visibleCheckboxes = Array.from(activeTabPane.querySelectorAll('.case-selection')).filter(checkbox => {
            const container = checkbox.closest('.col-xl-4, .col-lg-6');
            return container && container.style.display !== 'none';
        });

        const checkedCount = visibleCheckboxes.filter(cb => cb.checked).length;
        const allSelected = visibleCheckboxes.length > 0 && checkedCount === visibleCheckboxes.length;
        
        toggleButton.textContent = allSelected ? 'Deselect All' : 'Select All';
        
        // Update button styling
        const buttonElement = toggleButton.parentElement;
        if (allSelected) {
            buttonElement.classList.remove('btn-outline-primary');
            buttonElement.classList.add('btn-primary');
        } else {
            buttonElement.classList.remove('btn-primary');
            buttonElement.classList.add('btn-outline-primary');
        }
    }
}


function updateBulkActions() {
    const count = selectedCases.size;
    const container = document.getElementById('bulkActionsContainer');
    const text = document.getElementById('selectedCasesText');
    const markBtn = document.getElementById('bulkMarkReviewedBtn');
    const removeBtn = document.getElementById('bulkRemoveReviewedBtn');
    const calendarBtn = document.getElementById('bulkCalendarBtn');

    if (count > 0) {
        showBulkMenu();
        if (text) text.textContent = `${count} case${count > 1 ? 's' : ''} selected`;
        if (markBtn) markBtn.disabled = false;
        if (removeBtn) removeBtn.disabled = false;
        if (calendarBtn) calendarBtn.disabled = false;
    } else {
        hideBulkMenu();
        if (text) text.textContent = '0 cases selected';
        if (markBtn) markBtn.disabled = true;
        if (removeBtn) removeBtn.disabled = true;
        if (calendarBtn) calendarBtn.disabled = true;
    }
}

// UPDATED: Execute bulk action with revert option
// UPDATED: Execute bulk action with loading states
function executeBulkAction(action) {
    if (selectedCases.size === 0) {
        showAlert('Please select at least one case', 'warning');
        return;
    }

    let confirmMessage = '';
    let endpoint = '';
    let confirmType = 'warning';
    let loadingMessage = '';

    if (action === 'mark_reviewed') {
        confirmMessage = `Mark ${selectedCases.size} cases as reviewed?`;
        endpoint = '/toggle_case_selection';
        loadingMessage = `Marking ${selectedCases.size} cases as reviewed...`;
    } else if (action === 'remove_from_reviewed') {
        confirmMessage = `Remove ${selectedCases.size} cases from reviewed section and revert their notes to previous state?`;
        endpoint = '/remove_from_reviewed_and_revert';
        loadingMessage = `Removing ${selectedCases.size} cases from reviewed section...`;
    }

    showConfirm(confirmMessage, confirmType).then(confirmed => {
        if (!confirmed) return;

        // Show loading overlay
        showLoadingOverlay(loadingMessage);

        // Disable bulk action buttons
        const bulkButtons = document.querySelectorAll('#bulkActionsContainer button');
        bulkButtons.forEach(btn => {
            btn.disabled = true;
            if (btn.innerHTML.includes(action === 'mark_reviewed' ? 'Mark' : 'Remove')) {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Processing...';
            }
        });

        const requestBody = endpoint === '/toggle_case_selection' 
            ? { cinos: Array.from(selectedCases), action: action }
            : { cinos: Array.from(selectedCases) };

        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            const message = action === 'mark_reviewed' 
                ? `Successfully marked ${data.marked_count || data.success_count} cases as reviewed`
                : `Successfully removed ${data.success_count} cases from reviewed section and reverted notes`;
                
            showAlert(message, 'success');
            
            setTimeout(() => {
                location.reload();
            }, 1500);
        })
        .catch(error => {
            showAlert('Bulk action failed: ' + error.message, 'danger');
        })
        .finally(() => {
            // Hide loading overlay
            hideLoadingOverlay();
            
            // Re-enable buttons (though page will reload)
            bulkButtons.forEach(btn => {
                btn.disabled = false;
            });
        });
    });
}


// UPDATED: User side selection modal - No browser alerts
function showUserSideModal(cino, currentSide) {
    const modalHtml = `
        <div class="modal fade" id="userSideModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Select Client Side</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p>Which side does your law firm represent in this case?</p>
                        <div class="d-grid gap-2">
                            <button class="btn btn-info btn-lg" onclick="updateUserSide('${cino}', 'petitioner')">
                                <i class="fas fa-user-tie me-2"></i>Petitioner
                            </button>
                            <button class="btn btn-warning btn-lg" onclick="updateUserSide('${cino}', 'respondent')">
                                <i class="fas fa-user-shield me-2"></i>Respondent
                            </button>
                        </div>
                        ${currentSide ? `<p class="mt-3 text-muted">Currently set as: <strong>${currentSide}</strong></p>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    const existing = document.getElementById('userSideModal');
    if (existing) existing.remove();
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    const modal = new bootstrap.Modal(document.getElementById('userSideModal'));
    modal.show();
}

// UPDATED: Update user side - No browser alerts
function updateUserSide(cino, userSide) {
    fetch(`/case/${cino}/update_user_side`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_side: userSide
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // REPLACED: Browser alert with custom alert
        showAlert(`Client side updated to ${userSide}`, 'success');
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('userSideModal'));
        if (modal) modal.hide();
        
        setTimeout(() => {
            location.reload();
        }, 1000);
    })
    .catch(error => {
        // REPLACED: Browser alert with custom alert
        showAlert('Failed to update client side: ' + error.message, 'danger');
    });
}

// UPDATED: Calendar functions - No browser alerts
function showCalendarActionModal() {
    console.log('📅 Opening calendar action modal');
    console.log('📊 Selected cases:', Array.from(selectedCases));
    
    const activeTab = document.querySelector('.nav-link.active');
    const tabText = activeTab ? activeTab.textContent.trim().split('\n')[0] : 'Unknown';
    
    const activeTabPane = document.querySelector('.tab-pane.active');
    const allCasesInTab = activeTabPane ? activeTabPane.querySelectorAll('.case-card').length : 0;
    
    const modalCount = document.getElementById('modalSelectedCount');
    const modalAllCount = document.getElementById('modalAllCount');
    const modalTabName = document.getElementById('modalTabName');
    const casesList = document.getElementById('selectedCasesList');
    
    if (modalCount) modalCount.textContent = selectedCases.size;
    if (modalAllCount) modalAllCount.textContent = allCasesInTab;
    if (modalTabName) modalTabName.textContent = tabText;
    
    const hasSelection = selectedCases.size > 0;
    const selectedOptions = document.getElementById('selectedCasesOptions');
    const allCasesOptions = document.getElementById('allCasesOptions');
    
    if (selectedOptions) {
        selectedOptions.style.display = hasSelection ? 'block' : 'none';
    }
    if (allCasesOptions) {
        allCasesOptions.style.display = 'block';
    }
    
    const selectedCountBadge = document.getElementById('selectedCountBadge');
    const allCountBadge = document.getElementById('allCountBadge');
    if (selectedCountBadge) selectedCountBadge.textContent = selectedCases.size;
    if (allCountBadge) allCountBadge.textContent = allCasesInTab;
    
    if (casesList && hasSelection) {
        let casesHtml = '';
        let casesWithDates = 0;
        
        selectedCases.forEach(cino => {
            const card = document.querySelector(`[data-cino="${cino}"]`);
            if (card) {
                const title = card.querySelector('.card-title')?.textContent || cino;
                const nextHearing = extractDateFromCard(card) || 'Not scheduled';
                
                if (nextHearing !== 'Not scheduled' && nextHearing !== '') {
                    casesWithDates++;
                }
                
                casesHtml += `
                    <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                        <div>
                            <strong>${title}</strong>
                            <div class="small text-muted">CINO: ${cino}</div>
                        </div>
                        <span class="badge ${nextHearing === 'Not scheduled' ? 'bg-warning' : 'bg-info'}">${nextHearing}</span>
                    </div>
                `;
            }
        });
        
        casesList.innerHTML = casesHtml;
        
        const selectedWithDatesSpan = document.getElementById('selectedWithDates');
        if (selectedWithDatesSpan) {
            selectedWithDatesSpan.textContent = casesWithDates;
        }
    }
    
    const modal = new bootstrap.Modal(document.getElementById('calendarActionModal'));
    modal.show();
}

function executeCalendarAction(action, scope = 'selected') {
    console.log('📅 Executing calendar action:', action, 'scope:', scope);
    
    let casesToProcess = [];
    let filterType = '';
    
    if (scope === 'selected') {
        if (selectedCases.size === 0) {
            showAlert('No cases selected', 'warning');
            return;
        }
        
        selectedCases.forEach(cino => {
            const card = document.querySelector(`[data-cino="${cino}"]`);
            const caseData = extractCaseDataFromCard(card, true); // Pass true to include form data
            if (caseData) {
                casesToProcess.push(caseData);
            }
        });
        
        filterType = 'selected_cases_only';
        
    } else if (scope === 'all') {
        const activeTabPane = document.querySelector('.tab-pane.active');
        if (activeTabPane) {
            const allCards = activeTabPane.querySelectorAll('.case-card');
            allCards.forEach(card => {
                const caseData = extractCaseDataFromCard(card, true); // Pass true to include form data
                if (caseData) {
                    casesToProcess.push(caseData);
                }
            });
        }
        
        filterType = 'current_tab_all';
    }
    
    console.log('📊 Processing', casesToProcess.length, 'cases');
    
    if (casesToProcess.length === 0) {
        showAlert('No cases to process', 'warning');
        return;
    }
    
    if (action === 'create') {
        // First, save all pending changes for selected cases
        saveAllPendingChanges(casesToProcess).then(() => {
            // Then create calendar events
            createCalendarEvents(casesToProcess, filterType, scope);
        }).catch(error => {
            showAlert('Failed to save pending changes: ' + error.message, 'danger');
        });
        
    } else if (action === 'delete') {
        const confirmMessage = scope === 'selected' 
            ? `Delete calendar events for ${casesToProcess.length} selected cases?`
            : `Delete calendar events for all ${casesToProcess.length} cases in current tab?`;
            
        showConfirm(confirmMessage, 'danger').then(confirmed => {
            if (!confirmed) return;
            
            fetch('/delete_selected_calendar_events', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    cases: casesToProcess,
                    scope: scope
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                
                showAlert(`Deleted ${data.deleted} calendar events`, 'success');
                
                const modal = bootstrap.Modal.getInstance(document.getElementById('calendarActionModal'));
                if (modal) modal.hide();
            })
            .catch(error => {
                showAlert('Delete failed: ' + error.message, 'danger');
            });
        });
    }
}

function saveAllPendingChanges(casesToProcess) {
    return new Promise((resolve, reject) => {
        const savePromises = [];
        
        casesToProcess.forEach(caseData => {
            const cino = caseData.cino;
            const card = document.querySelector(`[data-cino="${cino}"]`);
            const notesInput = card?.querySelector('.notes-input');
            const hearingDateInput = card?.querySelector('input[name="next_hearing_date"]');
            const decisionDateInput = card?.querySelector('input[name="date_of_decision"]');
            
            // Check if there are any unsaved changes
            if (notesInput?.value.trim() || hearingDateInput?.value || decisionDateInput?.value) {
                const saveData = {
                    notes: notesInput?.value || '',
                    next_hearing_date: hearingDateInput?.value || '',
                    date_of_decision: decisionDateInput?.value || ''
                };
                
                const savePromise = fetch(`/case/${cino}/update_notes_only`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(saveData)
                }).then(response => response.json());
                
                savePromises.push(savePromise);
            }
        });
        
        if (savePromises.length === 0) {
            resolve();
            return;
        }
        
        Promise.all(savePromises)
            .then(results => {
                const failed = results.filter(r => r.error);
                if (failed.length > 0) {
                    reject(new Error(`Failed to save ${failed.length} cases`));
                } else {
                    resolve();
                }
            })
            .catch(reject);
    });
}

function createCalendarEvents(casesToProcess, filterType, scope) {
    showCalendarCreationProgress({
        total_cases: casesToProcess.length,
        cases_with_dates: casesToProcess.filter(c => c.date_next_list && c.date_next_list !== 'Not scheduled').length,
        scope: scope
    });
    
    fetch('/create_calendar_events', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filter: filterType,
            cases: casesToProcess,
            scope: scope
        })
    })
    .then(response => response.json())
    .then(data => {
        hideCalendarCreationProgress();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        showAlert(`Calendar events created: ${data.created} created, ${data.updated || 0} updated`, 'success');
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('calendarActionModal'));
        if (modal) modal.hide();
        
        if (scope === 'selected' && currentTab === 'reviewed-cases') {
            setTimeout(() => {
                removeSelectedFromReviewed();
            }, 1500);
        }
    })
    .catch(error => {
        hideCalendarCreationProgress();
        showAlert('Calendar creation failed: ' + error.message, 'danger');
    });
}

// UPDATED: Extract case data from card with form data option
function extractCaseDataFromCard(card, includeFormData = false) {
    if (!card) return null;
    
    const baseData = {
        cino: card.dataset.cino || '',
        case_no: card.dataset.caseNo || '',
        petparty_name: card.dataset.petitioner || '',
        resparty_name: card.dataset.respondent || '',
        establishment_name: card.dataset.establishment || '',
        date_next_list: card.dataset.nextDate || '',
        state_name: card.dataset.state || '',
        district_name: card.dataset.district || '',
        purpose_name: card.dataset.purpose || '',
        type_name: card.dataset.type || '',
        court_no_desg_name: card.dataset.court || '',
        user_side: card.dataset.userSide || '',
        reg_no: card.dataset.regNo || '',
        reg_year: card.dataset.regYear || ''
    };
    
    if (includeFormData) {
        // Get current form values if they exist
        const notesInput = card.querySelector('.notes-input');
        const hearingDateInput = card.querySelector('input[name="next_hearing_date"]');
        const decisionDateInput = card.querySelector('input[name="date_of_decision"]');
        const userSideSelect = card.querySelector('select[name="user_side"]');
        
        if (notesInput) baseData.user_notes = notesInput.value;
        if (hearingDateInput) baseData.date_next_list = hearingDateInput.value || baseData.date_next_list;
        if (decisionDateInput) baseData.date_of_decision = decisionDateInput.value;
        if (userSideSelect) baseData.user_side = userSideSelect.value || baseData.user_side;
    }
    
    return baseData;
}

function removeSelectedFromReviewed() {
    if (selectedCases.size === 0) return;
    
    fetch('/toggle_case_selection', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            cinos: Array.from(selectedCases),
            action: 'remove_from_reviewed'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // REPLACED: Browser alert with custom alert
        showAlert(`Removed ${data.removed_count} cases from reviewed section`, 'success');
        
        setTimeout(() => {
            location.reload();
        }, 1000);
    })
    .catch(error => {
        console.error('Remove from reviewed error:', error);
    });
}

// Utility functions
function extractCaseDataFromCard(card) {
    return {
        cino: card.dataset.cino || '',
        case_no: card.dataset.caseNo || '',
        petparty_name: card.dataset.petitioner || '',
        resparty_name: card.dataset.respondent || '',
        establishment_name: card.dataset.establishment || '',
        court_no_desg_name: card.dataset.court || '',
        date_next_list: card.dataset.nextDate || '',
        type_name: card.dataset.type || '',
        user_side: card.dataset.userSide || '',
        user_notes: card.dataset.notes || ''
    };
}

function extractFromDetails(text, field) {
    const regex = new RegExp(`${field}:\\s*([^\\n]+)`, 'i');
    const match = text.match(regex);
    return match ? match[1].trim() : '';
}

function showCalendarCreationProgress(data) {
    console.log('📊 Showing calendar progress for', data.total_cases, 'cases');
    
    let modal = document.getElementById('calendarCreationModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'calendarCreationModal';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-body text-center p-4" id="calendarProgressContent">
                        <div class="spinner-border text-primary mb-3" role="status">
                            <span class="visually-hidden">Creating...</span>
                        </div>
                        <h6>Creating Calendar Events</h6>
                        <p class="mb-0">Processing <strong>${data.cases_with_dates}</strong> cases with hearing dates...</p>
                        <small class="text-muted">${data.scope === 'selected' ? 'Selected cases only' : 'All cases in current tab'}</small>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
}

function hideCalendarCreationProgress() {
    const modal = document.getElementById('calendarCreationModal');
    if (modal) {
        const bootstrapModal = bootstrap.Modal.getInstance(modal);
        if (bootstrapModal) {
            bootstrapModal.hide();
        }
        setTimeout(() => {
            if (modal.parentNode) {
                modal.remove();
            }
        }, 500);
    }
}

function setupNotesChangeHandlers() {
    document.addEventListener('input', function(event) {
        if (event.target.classList.contains('notes-input')) {
            const card = event.target.closest('.case-card');
            if (card) {
                const cino = card.dataset.cino;
                if (cino) {
                    markCaseModified(cino);
                }
            }
        }
    });
}

function markCaseModified(cino) {
    pendingChanges.add(cino);
}

function openCaseDetail(cino) {
    window.location.href = `/case/${cino}`;
}

// Add these alert functions at the top of your app.js file

function showAlert(message, type = 'info') {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.custom-alert');
    existingAlerts.forEach(alert => alert.remove());
    
    // Create new alert
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} custom-alert`;
    alertDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-radius: 8px;
        animation: slideIn 0.3s ease-out;
    `;
    
    alertDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <span>${message}</span>
            <button type="button" class="btn-close" aria-label="Close"></button>
        </div>
    `;
    
    // Add CSS animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(alertDiv);
    
    // Close button functionality
    const closeBtn = alertDiv.querySelector('.btn-close');
    closeBtn.addEventListener('click', () => {
        alertDiv.remove();
    });
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (document.body.contains(alertDiv)) {
            alertDiv.remove();
        }
    }, 5000);
}

function showConfirm(message, type = 'warning') {
    return new Promise((resolve) => {
        // Create backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop';
        backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 9998;
            display: flex;
            justify-content: center;
            align-items: center;
        `;
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal-content';
        modal.style.cssText = `
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            max-width: 400px;
            width: 90%;
            text-align: center;
        `;
        
        modal.innerHTML = `
            <div class="mb-3">
                <i class="fas fa-exclamation-triangle text-${type}" style="font-size: 3rem;"></i>
            </div>
            <h5 class="mb-3">Confirm Action</h5>
            <p class="mb-4">${message}</p>
            <div class="d-flex gap-2 justify-content-center">
                <button class="btn btn-${type}" id="confirmYes">Yes, Continue</button>
                <button class="btn btn-secondary" id="confirmNo">Cancel</button>
            </div>
        `;
        
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        
        // Handle button clicks
        const yesBtn = modal.querySelector('#confirmYes');
        const noBtn = modal.querySelector('#confirmNo');
        
        yesBtn.addEventListener('click', () => {
            backdrop.remove();
            resolve(true);
        });
        
        noBtn.addEventListener('click', () => {
            backdrop.remove();
            resolve(false);
        });
        
        // Close on backdrop click
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                backdrop.remove();
                resolve(false);
            }
        });
    });
}


// UPDATED: Delete all functionality - No browser alerts
function showDeleteAllModal() {
    const modal = new bootstrap.Modal(document.getElementById('deleteAllModal'));
    document.getElementById('confirmationText').value = '';
    document.getElementById('confirmDeleteDataCheck').checked = false;
    document.getElementById('confirmDeleteAllBtn').disabled = true;
    modal.show();
}

function validateDeletionForm() {
    const confirmationText = document.getElementById('confirmationText')?.value;
    const isChecked = document.getElementById('confirmDeleteDataCheck')?.checked;
    const btn = document.getElementById('confirmDeleteAllBtn');
    
    if (btn) {
        btn.disabled = !(confirmationText === 'DELETE_ALL_FOREVER' && isChecked);
    }
}

function executeDeleteAll() {
    showConfirm('This action will delete all cases and calendar events permanently. Proceed?', 'danger')
    .then(confirmed => {
        if (!confirmed) return;
        
        const loadingAlert = showLoadingAlert('Deleting all cases and calendar events...', 'danger');
        
        fetch('/delete_all_cases_and_calendar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirmation: 'DELETE_ALL_FOREVER' })
        })
        .then(response => response.json())
        .then(data => {
            if (window.alertSystem && loadingAlert) window.alertSystem.removeAlert(loadingAlert);
            if (data.error) throw new Error(data.error);
            
            showAlert('All cases and calendar events deleted successfully!', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteAllModal'));
            if (modal) modal.hide();
            
            setTimeout(() => { window.location.href = '/upload_page'; }, 3000);
        })
        .catch(error => {
            if (window.alertSystem && loadingAlert) window.alertSystem.removeAlert(loadingAlert);
            showAlert('Deletion failed: ' + error.message, 'danger');
        });
    });
}

function handleGlobalSelectAll() {
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (!activeTabPane) return;

    const visibleCheckboxes = Array.from(activeTabPane.querySelectorAll('.case-selection')).filter(checkbox => {
        const container = checkbox.closest('.col-xl-4, .col-lg-6');
        return container && container.style.display !== 'none';
    });

    const allSelected = visibleCheckboxes.length > 0 && visibleCheckboxes.every(cb => cb.checked);

    if (allSelected) {
        // Deselect all
        visibleCheckboxes.forEach(cb => {
            cb.checked = false;
            selectedCases.delete(cb.dataset.cino);
        });
        document.getElementById('globalSelectAllText').textContent = 'Select All';
    } else {
        // Select all
        visibleCheckboxes.forEach(cb => {
            cb.checked = true;
            selectedCases.add(cb.dataset.cino);
        });
        document.getElementById('globalSelectAllText').textContent = 'Deselect All';
    }

    updateBulkActions();
}

function updateGlobalSelectAllText() {
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (!activeTabPane) return;
    const visibleCheckboxes = Array.from(activeTabPane.querySelectorAll('.case-selection')).filter(checkbox => {
        const container = checkbox.closest('.col-xl-4, .col-lg-6');
        return container && container.style.display !== 'none';
    });
    const allSelected = visibleCheckboxes.length > 0 && visibleCheckboxes.every(cb => cb.checked);
    document.getElementById('globalSelectAllText').textContent = allSelected ? 'Deselect All' : 'Select All';
}

// Function to update tab counts based on current filters
function updateTabCounts() {
    const tabs = [
        { id: 'all-cases', countId: 'all-cases-count' },
        { id: 'active-cases', countId: 'active-cases-count' },
        { id: 'changed-cases', countId: 'changed-cases-count' },
        { id: 'upcoming-cases', countId: 'upcoming-cases-count' },
        { id: 'reviewed-cases', countId: 'reviewed-cases-count' },
        { id: 'disposed-cases', countId: 'disposed-cases-count' }
    ];

    tabs.forEach(tab => {
        const count = getFilteredCaseCount(tab.id);
        const countElement = document.getElementById(tab.countId);
        if (countElement) {
            countElement.textContent = count;
        }
    });
}

// Function to get filtered case count for a specific tab
function getFilteredCaseCount(tabId) {
    const tabPane = document.getElementById(tabId);
    if (!tabPane) return 0;

    const casesToFilter = tabPane.querySelectorAll('.case-card');
    let visibleCount = 0;

    casesToFilter.forEach(card => {
        const container = card.closest('.col-xl-4, .col-lg-6');
        if (!container) return;

        let matches = true;

        // Get case data
        const caseData = {
            cino: card.dataset.cino || '',
            caseNo: card.dataset.caseNo || '',
            petitioner: card.dataset.petitioner || '',
            respondent: card.dataset.respondent || '',
            establishment: card.dataset.establishment || '',
            nextDate: card.dataset.nextDate || ''
        };

        // Text search filtering
        if (currentFilters.text) {
            const searchTerm = currentFilters.text.toLowerCase();
            matches = matches && (
                caseData.cino.toLowerCase().includes(searchTerm) ||
                caseData.caseNo.toLowerCase().includes(searchTerm) ||
                caseData.petitioner.toLowerCase().includes(searchTerm) ||
                caseData.respondent.toLowerCase().includes(searchTerm) ||
                caseData.establishment.toLowerCase().includes(searchTerm)
            );
        }

        // Date filtering
        if ((currentFilters.dateFrom || currentFilters.dateTo) && caseData.nextDate) {
            try {
                const caseDate = new Date(caseData.nextDate);
                
                if (!isNaN(caseDate.getTime())) {
                    if (currentFilters.dateFrom) {
                        const fromDate = new Date(currentFilters.dateFrom);
                        if (caseDate < fromDate) {
                            matches = false;
                        }
                    }
                    if (currentFilters.dateTo) {
                        const toDate = new Date(currentFilters.dateTo);
                        toDate.setHours(23, 59, 59, 999);
                        if (caseDate > toDate) {
                            matches = false;
                        }
                    }
                } else {
                    if (currentFilters.dateFrom || currentFilters.dateTo) {
                        matches = false;
                    }
                }
            } catch (e) {
                matches = false;
            }
        } else if (currentFilters.dateFrom || currentFilters.dateTo) {
            matches = false;
        }

        if (matches) visibleCount++;
    });

    return visibleCount;
}

// function to export the cases in the current tab as CSV
function exportCurrentTabAsCSV() {
    const activeTabPane = document.querySelector('.tab-pane.active');
    if (!activeTabPane) {
        showAlert('No active tab found for export', 'warning');
        return;
    }

    const tabId = activeTabPane.id;
    const casesToExport = [];

    const allCards = activeTabPane.querySelectorAll('.case-card');
    allCards.forEach(card => {
        const caseData = extractCaseDataFromCard(card);
        if (caseData) {
            casesToExport.push(caseData);
        }
    });

    if (casesToExport.length === 0) {
        showAlert('No cases available for export in this tab', 'info');
        return;
    }

    // Convert cases to CSV format
    const headers = ['CINO', 'Case No', 'Petitioner', 'Respondent', 'Establishment', 'Court', 'Next Hearing Date', 'Type', 'User Side', 'User Notes'];
    const csvRows = [headers.join(',')];

    casesToExport.forEach(caseItem => {
        const row = [
            `"${caseItem.cino}"`,
            `"${caseItem.case_no}"`,
            `"${caseItem.petparty_name.replace(/"/g, '""')}"`,
            `"${caseItem.resparty_name.replace(/"/g, '""')}"`,
            `"${caseItem.establishment_name.replace(/"/g, '""')}"`,
            `"${caseItem.court_no_desg_name.replace(/"/g, '""')}"`,
            `"${caseItem.date_next_list}"`,
            `"${caseItem.type_name.replace(/"/g, '""')}"`,
            `"${caseItem.user_side}"`,
            `"${caseItem.user_notes.replace(/"/g, '""')}"`
        ];
        csvRows.push(row.join(','));
    });

    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${tabId}_cases_export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
    
    showAlert(`Exported ${casesToExport.length} cases from current tab as CSV`, 'success');
    console.log(`Exported ${casesToExport.length} cases from tab ${tabId}`);
}

//function to export all cases details as txt
// details id INTEGER PRIMARY KEY AUTOINCREMENT,
            // cino TEXT UNIQUE,
            // case_no TEXT,
            // petparty_name TEXT,
            // resparty_name TEXT,
            // establishment_name TEXT,
            // state_name TEXT,
            // district_name TEXT,
            // date_next_list TEXT,
            // date_last_list TEXT,
            // purpose_name TEXT,
            // type_name TEXT,
            // court_no_desg_name TEXT,
            // disp_name TEXT,
            // updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            // user_notes TEXT DEFAULT '',
            // is_changed BOOLEAN DEFAULT FALSE,
            // change_summary TEXT DEFAULT '',
            // raw_data TEXT,
            // user_side TEXT DEFAULT '',
            // reg_no INTEGER,
            // reg_year INTEGER,
            // date_of_decision TEXT DEFAULT NULL
// case details in a structured format 
// "{\"cino\":\"MHPU040389712018\",\"type_name\":\"Cri.M.A.\",\"case_no\":\"201900028562018\",\"reg_year\":2018,\"reg_no\":2856,\"petparty_name\":\"Vaishali Uday Rawal\",\"resparty_name\":\"Uday Mukund Rawal\",\"fil_year\":\"0\",\"fil_no\":\"0\",\"establishment_name\":\"J.M.F.C.COURT PUNE MAHARASHTRA\",\"establishment_code\":\"MHPU04\",\"state_code\":\"1\",\"district_code\":\"25\",\"state_name\":\"Maharashtra\",\"district_name\":\"Pune\",\"date_next_list\":\"2025-09-12\",\"date_of_decision\":null,\"date_last_list\":\"2025-08-13\",\"updated\":true,\"ltype_name\":\"फौजदारी किरकोळ अर्ज\",\"lestablishment_name\":\"दिवाणी व फौजदारी न्यायालय, पुणे\",\"lstate_name\":\"\",\"ldistrict_name\":\"पुणे\"}", 
async function exportAllCasesAsTxt() {
    try {
        // Fetch cases from Flask API
        const response = await fetch('/api/cases');
        if (!response.ok) {
            throw new Error('Failed to fetch cases');
        }

        const cases = await response.json();

        // Convert each object into stringified JSON
        const formattedCases = cases.map(c => JSON.stringify(c));

        // Wrap inside array (same format as myCases.txt)
        const textData = JSON.stringify(formattedCases, null, 4);

        // Download as text file
        const blob = new Blob([textData], { type: "text/plain" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "mCases.txt";
        link.click();
        URL.revokeObjectURL(link.href);

    } catch (err) {
        console.error("Error exporting cases:", err);
        alert("Failed to export cases. Check console for details.");
    }
}


function saveCaseChanges(cino) {
        console.log('Saving notes for case:', cino);

        // Try multiple selectors to find the notes input
        let notesInput = document.querySelector('#notes-input') ||
            document.querySelector('.notes-input') ||
            document.querySelector('textarea[name="notes"]') ||
            document.querySelector('textarea');

        if (!notesInput) {
            showAlert('Notes input field not found!', 'danger');
            console.error('Could not find notes input field');
            return;
        }

        let notes = notesInput.value.trim();
        console.log('Notes content:', notes);

        if (!notes) {
            showAlert('Please enter some notes before saving', 'warning');
            return;
        }

        // Disable button during save
        let saveButton = event.target;
        let originalText = saveButton.innerHTML;
        saveButton.disabled = true;
        saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Saving...';

        fetch(`/case/${cino}/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    notes: notes
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showAlert('Failed to save notes: ' + data.error, 'danger');
                } else {
                    showAlert('Notes saved successfully!', 'success');
                }
            })
            .catch(error => {
                console.error('Save error:', error);
                showAlert('Failed to save notes: ' + error.message, 'danger');
            })
            .finally(() => {
                // Re-enable button
                saveButton.disabled = false;
                saveButton.innerHTML = originalText;
            });
    }

    
