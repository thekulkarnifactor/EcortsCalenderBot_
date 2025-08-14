// Law Firm Case Management JavaScript - NO BROWSER ALERTS VERSION
let pendingChanges = new Set();
let selectedCases = new Set();
let allCasesData = [];
let currentFilters = { text: '', dateFrom: '', dateTo: '', advanced: {} };
let currentTab = 'all-cases';
let filterMemory = {};

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing Law Firm Case Management...');
    
    initializeSearch();
    setupNotesChangeHandlers();
    
    console.log('App initialized successfully');
});

// Tab switching with filter memory
function switchTab(tabId) {
    console.log('Switching to tab:', tabId);
    
    if (currentTab) {
        filterMemory[currentTab] = {
            text: document.getElementById('searchInput')?.value || '',
            dateFrom: document.getElementById('dateFromInput')?.value || '',
            dateTo: document.getElementById('dateToInput')?.value || '',
            activeFilter: getActiveFilterButton()
        };
    }
    
    currentTab = tabId;
    selectedCases.clear();
    updateBulkActions();
    
    if (filterMemory[tabId]) {
        const savedFilters = filterMemory[tabId];
        
        const searchInput = document.getElementById('searchInput');
        const dateFromInput = document.getElementById('dateFromInput');
        const dateToInput = document.getElementById('dateToInput');
        
        if (searchInput) searchInput.value = savedFilters.text;
        if (dateFromInput) dateFromInput.value = savedFilters.dateFrom;
        if (dateToInput) dateToInput.value = savedFilters.dateTo;
        
        document.querySelectorAll('#dateFilterGroup .btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        if (savedFilters.activeFilter) {
            const activeBtn = document.querySelector(`[onclick="setDateFilter('${savedFilters.activeFilter}')"]`);
            if (activeBtn) {
                activeBtn.classList.add('active');
            }
        }
        
        currentFilters = {
            text: savedFilters.text,
            dateFrom: savedFilters.dateFrom,
            dateTo: savedFilters.dateTo,
            advanced: {}
        };
        
        setTimeout(() => {
            filterCases();
        }, 100);
    } else {
        clearAllFilters();
    }
    
    updateToggleButtonText(tabId);
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
            toDate = endOfWeek.toISOString().split('T')[0];
            break;
        case 'thisMonth':
            fromDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
            toDate = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
            break;
        case 'nextWeek':
            const nextWeekStart = new Date(today);
            nextWeekStart.setDate(today.getDate() + (7 - today.getDay()));
            const nextWeekEnd = new Date(nextWeekStart);
            nextWeekEnd.setDate(nextWeekStart.getDate() + 6);
            fromDate = nextWeekStart.toISOString().split('T')[0];
            toDate = nextWeekEnd.toISOString().split('T')[0];
            break;
    }

    dateFromInput.value = fromDate;
    dateToInput.value = toDate;

    document.querySelectorAll('#dateFilterGroup .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        const targetBtn = document.querySelector(`[onclick="setDateFilter('${period}')"]`);
        if (targetBtn) {
            targetBtn.classList.add('active');
        }
    }

    handleSearch();
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
    const dateFromInput = document.getElementById('dateFromInput');
    const dateToInput = document.getElementById('dateToInput');
    
    if (searchInput) searchInput.value = '';
    if (dateFromInput) dateFromInput.value = '';
    if (dateToInput) dateToInput.value = '';
    
    currentFilters = { text: '', dateFrom: '', dateTo: '', advanced: {} };
    
    document.querySelectorAll('#dateFilterGroup .btn.active').forEach(btn => {
        btn.classList.remove('active');
    });
    
    handleSearch();
}

function handleSearch() {
    console.log('Handling search...');
    const searchText = document.getElementById('searchInput')?.value || '';
    const dateFrom = document.getElementById('dateFromInput')?.value || '';
    const dateTo = document.getElementById('dateToInput')?.value || '';

    currentFilters = {
        text: searchText,
        dateFrom: dateFrom,
        dateTo: dateTo,
        advanced: currentFilters.advanced || {}
    };

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
        
        let matches = true;
        const caseData = {
            caseNo: card.querySelector('.card-title')?.textContent || '',
            petitioner: card.querySelector('.case-parties .col-6:first-child .fw-medium')?.textContent || '',
            respondent: card.querySelector('.case-parties .col-6:last-child .fw-medium')?.textContent || '',
            establishment: card.querySelector('.case-details')?.textContent || '',
            nextDate: extractDateFromCard(card) || ''
        };

        if (currentFilters.text) {
            const searchTerm = currentFilters.text.toLowerCase();
            matches = matches && (
                caseData.caseNo.toLowerCase().includes(searchTerm) ||
                caseData.petitioner.toLowerCase().includes(searchTerm) ||
                caseData.respondent.toLowerCase().includes(searchTerm) ||
                caseData.establishment.toLowerCase().includes(searchTerm)
            );
        }

        if ((currentFilters.dateFrom || currentFilters.dateTo) && caseData.nextDate) {
            const caseDate = new Date(caseData.nextDate);
            if (currentFilters.dateFrom) {
                const fromDate = new Date(currentFilters.dateFrom);
                if (caseDate < fromDate) matches = false;
            }
            if (currentFilters.dateTo) {
                const toDate = new Date(currentFilters.dateTo);
                if (caseDate > toDate) matches = false;
            }
        }

        container.style.display = matches ? 'block' : 'none';
        if (matches) visibleCount++;
    });

    updateSearchResultsCount(visibleCount);
}

function updateSearchResultsCount(count) {
    const countElement = document.getElementById('searchResultsCount');
    if (countElement) {
        countElement.textContent = count;
        countElement.className = count > 0 ? 'badge bg-primary' : 'badge bg-warning';
    }
}

// UPDATED: Mark case as reviewed - No browser alerts
function markAsReviewed(cino) {
    console.log('Marking case as reviewed:', cino);
    
    const card = document.querySelector(`[data-cino="${cino}"]`);
    const notesInput = card?.querySelector('.notes-input');
    const notes = notesInput ? notesInput.value : '';
    
    const saveBtn = event.target.closest('button');
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
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // REPLACED: Browser alert with custom alert
        showAlert('Case marked as reviewed successfully', 'success');
        
        card.dataset.changed = 'false';
        card.classList.remove('border-warning');
        
        setTimeout(() => {
            location.reload();
        }, 1000);
    })
    .catch(error => {
        console.error('Mark as reviewed error:', error);
        // REPLACED: Browser alert with custom alert
        showAlert('Failed to mark as reviewed: ' + error.message, 'danger');
    })
    .finally(() => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    });
}

// UPDATED: Remove from reviewed - No browser alerts
function removeFromReviewed(cino) {
    // REPLACED: Browser confirm with custom confirm
    showConfirm('Remove this case from reviewed? It will appear in pending cases again.', 'warning')
    .then(confirmed => {
        if (!confirmed) return;
        
        fetch('/toggle_case_selection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                cinos: [cino],
                action: 'remove_from_reviewed'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // REPLACED: Browser alert with custom alert
            showAlert('Case removed from reviewed section', 'success');
            
            setTimeout(() => {
                location.reload();
            }, 1000);
        })
        .catch(error => {
            // REPLACED: Browser alert with custom alert
            showAlert('Failed to remove from reviewed: ' + error.message, 'danger');
        });
    });
}

function toggleAllSelection(tabId) {
    const container = getContainerByTabId(tabId);
    const checkboxes = container.querySelectorAll('.case-selection');
    const toggleBtn = event?.target?.closest('button');
    const toggleText = toggleBtn?.querySelector('span');
    
    if (!toggleText) {
        console.error('Toggle button or text not found');
        return;
    }
    
    const isSelectAll = toggleText.textContent.trim() === 'Select All';
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = isSelectAll;
        if (isSelectAll) {
            selectedCases.add(checkbox.dataset.cino);
        } else {
            selectedCases.delete(checkbox.dataset.cino);
        }
    });
    
    toggleText.textContent = isSelectAll ? 'Deselect All' : 'Select All';
    updateBulkActions();
}

function getContainerByTabId(tabId) {
    switch(tabId) {
        case 'all-cases': return document.getElementById('allCasesContainer');
        case 'petitioner-cases': return document.getElementById('petitionerCasesContainer');
        case 'respondent-cases': return document.getElementById('respondentCasesContainer');
        case 'unassigned-cases': return document.getElementById('unassignedCasesContainer');
        case 'upcoming-cases': return document.getElementById('upcomingCasesContainer');
        case 'reviewed-cases': return document.getElementById('reviewedCasesContainer');
        default: return document.getElementById('allCasesContainer');
    }
}

function updateCaseSelection() {
    selectedCases.clear();
    const checkedBoxes = document.querySelectorAll('.case-selection:checked');
    checkedBoxes.forEach(checkbox => {
        selectedCases.add(checkbox.dataset.cino);
    });
    
    updateBulkActions();
}

function updateBulkActions() {
    const count = selectedCases.size;
    const container = document.getElementById('bulkActionsContainer');
    const text = document.getElementById('selectedCasesText');
    const markBtn = document.getElementById('bulkMarkReviewedBtn');
    const removeBtn = document.getElementById('bulkRemoveReviewedBtn');
    const calendarBtn = document.getElementById('bulkCalendarBtn');
    
    if (count > 0) {
        container.style.display = 'block';
        text.textContent = `${count} case${count > 1 ? 's' : ''} selected`;
        if (markBtn) markBtn.disabled = false;
        if (removeBtn) removeBtn.disabled = false;
        if (calendarBtn) calendarBtn.disabled = false;
    } else {
        container.style.display = 'none';
    }
}

// UPDATED: Execute bulk action - No browser alerts
function executeBulkAction(action) {
    if (selectedCases.size === 0) {
        // REPLACED: Browser alert with custom alert
        showAlert('Please select at least one case', 'warning');
        return;
    }
    
    let confirmMessage = '';
    let confirmType = 'warning';
    
    if (action === 'mark_reviewed') {
        confirmMessage = `Mark ${selectedCases.size} cases as reviewed?`;
    } else if (action === 'remove_from_reviewed') {
        confirmMessage = `Remove ${selectedCases.size} cases from reviewed section?`;
    }
    
    // REPLACED: Browser confirm with custom confirm
    showConfirm(confirmMessage, confirmType).then(confirmed => {
        if (!confirmed) return;
        
        fetch('/toggle_case_selection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                cinos: Array.from(selectedCases),
                action: action
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            const message = action === 'mark_reviewed' 
                ? `Successfully marked ${data.marked_count || data.removed_count} cases as reviewed`
                : `Successfully removed ${data.removed_count || data.marked_count} cases from reviewed section`;
                
            // REPLACED: Browser alert with custom alert
            showAlert(message, 'success');
            
            setTimeout(() => {
                location.reload();
            }, 1500);
        })
        .catch(error => {
            // REPLACED: Browser alert with custom alert
            showAlert('Bulk action failed: ' + error.message, 'danger');
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

// UPDATED: Execute calendar action - No browser alerts
function executeCalendarAction(action, scope = 'selected') {
    console.log('📅 Executing calendar action:', action, 'scope:', scope);
    
    let casesToProcess = [];
    let filterType = '';
    
    if (scope === 'selected') {
        if (selectedCases.size === 0) {
            // REPLACED: Browser alert with custom alert
            showAlert('No cases selected', 'warning');
            return;
        }
        
        selectedCases.forEach(cino => {
            const card = document.querySelector(`[data-cino="${cino}"]`);
            const caseData = extractCaseDataFromCard(card);
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
                const caseData = extractCaseDataFromCard(card);
                if (caseData) {
                    casesToProcess.push(caseData);
                }
            });
        }
        
        filterType = 'current_tab_all';
    }
    
    console.log('📊 Processing', casesToProcess.length, 'cases');
    
    if (casesToProcess.length === 0) {
        // REPLACED: Browser alert with custom alert
        showAlert('No cases to process', 'warning');
        return;
    }
    
    if (action === 'create') {
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
            
            // REPLACED: Browser alert with custom alert
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
            // REPLACED: Browser alert with custom alert
            showAlert('Calendar creation failed: ' + error.message, 'danger');
        });
        
    } else if (action === 'delete') {
        const confirmMessage = scope === 'selected' 
            ? `Delete calendar events for ${casesToProcess.length} selected cases?`
            : `Delete calendar events for all ${casesToProcess.length} cases in current tab?`;
            
        // REPLACED: Browser confirm with custom confirm
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
                
                // REPLACED: Browser alert with custom alert
                showAlert(`Deleted ${data.deleted} calendar events`, 'success');
                
                const modal = bootstrap.Modal.getInstance(document.getElementById('calendarActionModal'));
                if (modal) modal.hide();
            })
            .catch(error => {
                // REPLACED: Browser alert with custom alert
                showAlert('Delete failed: ' + error.message, 'danger');
            });
        });
    }
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
    try {
        const cino = card.dataset.cino;
        const title = card.querySelector('.card-title')?.textContent || '';
        const caseDetails = card.querySelector('.case-details')?.textContent || '';
        const parties = card.querySelector('.case-parties');
        const notesInput = card.querySelector('.notes-input');
        
        let petparty_name = '';
        let resparty_name = '';
        
        if (parties) {
            const partyElements = parties.querySelectorAll('.fw-medium');
            if (partyElements.length >= 2) {
                petparty_name = partyElements[0].textContent.trim();
                resparty_name = partyElements[1].textContent.trim();
            }
        }
        
        const hearingMatch = caseDetails.match(/Next Hearing:\s*(\d{4}-\d{2}-\d{2})/i);
        const dateNextList = hearingMatch ? hearingMatch[1] : '';
        
        return {
            cino: cino,
            case_no: title,
            petparty_name: petparty_name,
            resparty_name: resparty_name,
            establishment_name: extractFromDetails(caseDetails, 'Establishment') || '',
            date_next_list: dateNextList,
            purpose_name: extractFromDetails(caseDetails, 'Purpose') || '',
            court_no_desg_name: extractFromDetails(caseDetails, 'Court') || '',
            user_notes: notesInput ? notesInput.value : ''
        };
        
    } catch (error) {
        console.error('Error extracting case data:', error);
        return null;
    }
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

// DEPRECATED: Old showAlert function replaced by creative alert system
// This function is kept for backward compatibility but now uses the new system
function showAlert(message, type = 'info') {
    // This will be handled by the new alert system automatically
    if (window.alertSystem) {
        return window.alertSystem.showAlert(message, type);
    } else {
        // Fallback for immediate use before alert system loads
        console.log(`Alert (${type}): ${message}`);
    }
}

// UPDATED: Delete all functionality - No browser alerts
function showDeleteAllModal() {
    const modal = new bootstrap.Modal(document.getElementById('deleteAllModal'));
    modal.show();
}

function validateDeletionForm() {
    const confirmationText = document.getElementById('confirmationText')?.value;
    const checkboxes = document.querySelectorAll('#deleteAllModal .form-check-input');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    
    const isValid = confirmationText === 'DELETE_ALL_FOREVER' && allChecked;
    
    const btn = document.getElementById('confirmDeleteAllBtn');
    if (btn) btn.disabled = !isValid;
}

// UPDATED: Execute delete all - No browser alerts
function executeDeleteAll() {
    // REPLACED: Browser confirm with custom confirm
    showConfirm('This is your FINAL WARNING!\n\nAre you absolutely sure?', 'danger', 'Final Confirmation')
    .then(confirmed => {
        if (!confirmed) return;
        
        const loadingAlert = showLoadingAlert('Deleting all cases and calendar events...', 'danger');
        
        fetch('/delete_all_cases_and_calendar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                confirmation: 'DELETE_ALL_FOREVER'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (loadingAlert && window.alertSystem) {
                window.alertSystem.removeAlert(loadingAlert);
            }
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // REPLACED: Browser alert with custom alert
            showAlert('All cases and calendar events deleted successfully!', 'success');
            
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteAllModal'));
            if (modal) modal.hide();
            
            setTimeout(() => {
                window.location.href = '/upload_page';
            }, 3000);
        })
        .catch(error => {
            if (loadingAlert && window.alertSystem) {
                window.alertSystem.removeAlert(loadingAlert);
            }
            // REPLACED: Browser alert with custom alert
            showAlert('Deletion failed: ' + error.message, 'danger');
        });
    });
}