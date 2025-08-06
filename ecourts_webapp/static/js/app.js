// e-Courts Case Management JavaScript

// Global state management
let pendingChanges = new Set();
let alertTimeout;
let currentFilters = {
    text: '',
    dateFrom: '',
    dateTo: '',
    advanced: {}
};
let filteredCases = [];
let allCasesData = [];

// Utility Functions
function showAlert(message, type = 'info') {
    clearTimeout(alertTimeout);
    
    // Remove existing alerts
    document.querySelectorAll('.alert.position-fixed').forEach(alert => alert.remove());
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    alertTimeout = setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function showLoading() {
    const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
    modal.show();
}

function hideLoading() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('loadingModal'));
    if (modal) modal.hide();
}

// Case Management Functions
function toggleChanges(cino) {
    const changesDiv = document.getElementById(`changes-${cino}`);
    const isVisible = changesDiv.style.display !== 'none';
    changesDiv.style.display = isVisible ? 'none' : 'block';
    
    const btn = event.target.closest('button');
    const icon = btn.querySelector('i');
    icon.className = isVisible ? 'fas fa-eye' : 'fas fa-eye-slash';
}

function markCaseModified(cino) {
    pendingChanges.add(cino);
    const card = document.querySelector(`[data-cino="${cino}"]`);
    if (card) {
        card.classList.add('border-info');
        
        let indicator = card.querySelector('.unsaved-indicator');
        if (!indicator) {
            indicator = document.createElement('span');
            indicator.className = 'badge bg-info position-absolute top-0 end-0 translate-middle unsaved-indicator';
            indicator.textContent = 'Modified';
            indicator.style.zIndex = '10';
            card.style.position = 'relative';
            card.appendChild(indicator);
        }
    }
    updateSaveAllButton();
}

function saveCase(cino) {
    const card = document.querySelector(`[data-cino="${cino}"]`);
    const notesInput = card.querySelector('.notes-input');
    const notes = notesInput ? notesInput.value : '';
    
    showLoading();
    
    fetch(`/case/${cino}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: notes })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        showAlert('Case saved successfully', 'success');
        
        pendingChanges.delete(cino);
        card.classList.remove('border-info');
        
        const indicator = card.querySelector('.unsaved-indicator');
        if (indicator) indicator.remove();
        
        if (card.dataset.changed === 'true') {
            card.classList.remove('border-warning');
            card.dataset.changed = 'false';
            
            const header = card.querySelector('.card-header');
            if (header) header.remove();
            
            updateStatistics();
        }
        
        updateSaveAllButton();
    })
    .catch(error => {
        hideLoading();
        showAlert('Failed to save case: ' + error.message, 'danger');
    });
}

function markReviewed(cino) {
    fetch(`/case/${cino}/mark_reviewed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        showAlert('Case marked as reviewed', 'success');
        
        const card = document.querySelector(`[data-cino="${cino}"]`);
        card.classList.remove('border-warning');
        card.dataset.changed = 'false';
        
        const header = card.querySelector('.card-header');
        if (header) header.remove();
        
        updateStatistics();
    })
    .catch(error => {
        showAlert('Failed to mark as reviewed: ' + error.message, 'danger');
    });
}

function openCaseDetail(cino) {
    window.location.href = `/case/${cino}`;
}

function updateSaveAllButton() {
    const saveAllBtn = document.querySelector('[onclick="saveAllCases()"]');
    if (saveAllBtn) {
        const count = pendingChanges.size;
        if (count > 0) {
            saveAllBtn.innerHTML = `<i class="fas fa-save me-2"></i>Save All (${count})`;
            saveAllBtn.classList.add('btn-warning');
            saveAllBtn.classList.remove('btn-light');
        } else {
            saveAllBtn.innerHTML = '<i class="fas fa-save me-2"></i>Save All';
            saveAllBtn.classList.remove('btn-warning');
            saveAllBtn.classList.add('btn-light');
        }
    }
}

function updateStatistics() {
    const changedCases = document.querySelectorAll('.case-card[data-changed="true"]').length;
    const totalCases = document.querySelectorAll('.case-card').length;
    const reviewedCases = totalCases - changedCases;
    
    const changedBadge = document.querySelector('#casesTabs .nav-link[href="#changed-cases"] .badge');
    if (changedBadge) changedBadge.textContent = changedCases;
    
    const reviewedCount = document.querySelector('#reviewedCount');
    if (reviewedCount) reviewedCount.textContent = reviewedCases;
    
    const warningCount = document.querySelector('.bg-warning h3');
    if (warningCount) warningCount.textContent = changedCases;
}

// Enhanced Search Functionality
function initializeSearch() {
    allCasesData = Array.from(document.querySelectorAll('.case-card')).map(card => {
        return {
            element: card.closest('.col-xl-4, .col-lg-6'),
            cino: card.dataset.cino,
            caseNo: card.querySelector('.card-title')?.textContent || '',
            petitioner: card.querySelector('.case-parties .col-6:first-child .fw-medium')?.textContent || '',
            respondent: card.querySelector('.case-parties .col-6:last-child .fw-medium')?.textContent || '',
            establishment: card.querySelector('.case-details')?.textContent || '',
            nextDate: extractDate(card.closest('.col-xl-4, .col-lg-6')) || '',
            isChanged: card.dataset.changed === 'true',
            hasNotes: card.querySelector('.notes-input')?.value.trim() !== ''
        };
    });
    
    populateAdvancedSearchOptions();
}

function handleSearch() {
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
    
    allCasesData.forEach(caseData => {
        let matches = true;
        
        if (currentFilters.text) {
            matches = matches && matchesTextSearch(caseData, currentFilters.text);
        }
        
        if (currentFilters.dateFrom || currentFilters.dateTo) {
            matches = matches && matchesDateRange(caseData, currentFilters.dateFrom, currentFilters.dateTo);
        }
        
        if (Object.keys(currentFilters.advanced).length > 0) {
            matches = matches && matchesAdvancedFilters(caseData, currentFilters.advanced);
        }
        
        if (caseData.element) {
            caseData.element.style.display = matches ? 'block' : 'none';
            if (matches) visibleCount++;
        }
    });
    
    updateSearchResultsCount(visibleCount);
    showNoResultsMessage(visibleCount === 0);
}

function matchesTextSearch(caseData, searchText) {
    const term = searchText.toLowerCase().trim();
    
    // Direct field matches
    const directMatches = [
        caseData.caseNo.toLowerCase(),
        caseData.petitioner.toLowerCase(),
        caseData.respondent.toLowerCase(),
        caseData.establishment.toLowerCase()
    ].some(field => field.includes(term));
    
    if (directMatches) return true;
    
    // Enhanced "vs" format matching
    if (term.includes(' vs ') || term.includes(' v ') || term.includes(' v. ')) {
        const vsVariations = [' vs ', ' v ', ' v. ', ' versus '];
        let petitionerPart = '';
        let respondentPart = '';
        
        for (const vsFormat of vsVariations) {
            if (term.includes(vsFormat)) {
                const parts = term.split(vsFormat);
                if (parts.length === 2) {
                    petitionerPart = parts[0].trim();
                    respondentPart = parts[1].trim();
                    break;
                }
            }
        }
        
        if (petitionerPart && respondentPart) {
            const petitionerMatch = caseData.petitioner.toLowerCase().includes(petitionerPart);
            const respondentMatch = caseData.respondent.toLowerCase().includes(respondentPart);
            
            const reverseMatch = caseData.petitioner.toLowerCase().includes(respondentPart) && 
                              caseData.respondent.toLowerCase().includes(petitionerPart);
            
            if (petitionerMatch && respondentMatch) return true;
            if (reverseMatch) return true;
        }
    }
    
    // Partial name matching
    const searchWords = term.split(' ').filter(word => word.length > 2);
    if (searchWords.length >= 2) {
        const petitionerWords = caseData.petitioner.toLowerCase().split(' ');
        const respondentWords = caseData.respondent.toLowerCase().split(' ');
        
        const allWordsInPetitioner = searchWords.every(word => 
            petitionerWords.some(pWord => pWord.includes(word))
        );
        const allWordsInRespondent = searchWords.every(word => 
            respondentWords.some(rWord => rWord.includes(word))
        );
        
        if (allWordsInPetitioner || allWordsInRespondent) return true;
    }
    
    return false;
}

function matchesDateRange(caseData, dateFrom, dateTo) {
    if (!caseData.nextDate) return !dateFrom && !dateTo;
    
    const caseDate = new Date(caseData.nextDate);
    
    if (dateFrom) {
        const fromDate = new Date(dateFrom);
        if (caseDate < fromDate) return false;
    }
    
    if (dateTo) {
        const toDate = new Date(dateTo);
        if (caseDate > toDate) return false;
    }
    
    return true;
}

function matchesAdvancedFilters(caseData, advancedFilters) {
    // Implementation for advanced filters
    if (advancedFilters.caseNo && !caseData.caseNo.toLowerCase().includes(advancedFilters.caseNo.toLowerCase())) {
        return false;
    }
    
    if (advancedFilters.petitioner && !caseData.petitioner.toLowerCase().includes(advancedFilters.petitioner.toLowerCase())) {
        return false;
    }
    
    if (advancedFilters.respondent && !caseData.respondent.toLowerCase().includes(advancedFilters.respondent.toLowerCase())) {
        return false;
    }
    
    if (advancedFilters.changed && !caseData.isChanged) {
        return false;
    }
    
    if (advancedFilters.withNotes && !caseData.hasNotes) {
        return false;
    }
    
    return true;
}

// Quick date filter functions
function setDateFilter(period) {
    const today = new Date();
    const dateFromInput = document.getElementById('dateFromInput');
    const dateToInput = document.getElementById('dateToInput');
    
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
    
    if (dateFromInput) dateFromInput.value = fromDate;
    if (dateToInput) dateToInput.value = toDate;
    
    document.querySelectorAll('.btn-group .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    handleSearch();
}

function clearDateFilter() {
    document.getElementById('dateFromInput').value = '';
    document.getElementById('dateToInput').value = '';
    
    document.querySelectorAll('.btn-group .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    handleSearch();
}

// Advanced search functions
function showAdvancedSearch() {
    const modal = new bootstrap.Modal(document.getElementById('advancedSearchModal'));
    modal.show();
}

function populateAdvancedSearchOptions() {
    // Extract unique values for dropdowns
    const establishments = [...new Set(allCasesData.map(c => {
        const text = c.establishment;
        if (text) {
            const match = text.match(/establishment_name[:\s]+([^\n]+)/i);
            return match ? match[1].trim() : '';
        }
        return '';
    }).filter(Boolean))];
    
    populateSelect('advEstablishment', establishments);
}

function populateSelect(selectId, options) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    while (select.children.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    options.forEach(option => {
        const optElement = document.createElement('option');
        optElement.value = option;
        optElement.textContent = option;
        select.appendChild(optElement);
    });
}

function applyAdvancedSearch() {
    const advancedFilters = {
        caseNo: document.getElementById('advCaseNo')?.value || '',
        cino: document.getElementById('advCino')?.value || '',
        petitioner: document.getElementById('advPetitioner')?.value || '',
        respondent: document.getElementById('advRespondent')?.value || '',
        vsFormat: document.getElementById('advVsFormat')?.value || '',
        establishment: document.getElementById('advEstablishment')?.value || '',
        changed: document.getElementById('advChanged')?.checked || false,
        withNotes: document.getElementById('advWithNotes')?.checked || false,
        reviewed: document.getElementById('advReviewed')?.checked || false
    };
    
    currentFilters.advanced = advancedFilters;
    filterCases();
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('advancedSearchModal'));
    if (modal) modal.hide();
    
    showAppliedFiltersIndicator();
}

function clearAdvancedSearch() {
    document.querySelectorAll('#advancedSearchModal input, #advancedSearchModal select').forEach(input => {
        if (input.type === 'checkbox') {
            input.checked = false;
        } else {
            input.value = '';
        }
    });
}

function clearAllFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('dateFromInput').value = '';
    document.getElementById('dateToInput').value = '';
    
    currentFilters = { text: '', dateFrom: '', dateTo: '', advanced: {} };
    
    document.querySelectorAll('.btn-group .btn.active').forEach(btn => {
        btn.classList.remove('active');
    });
    
    filterCases();
}

function updateSearchResultsCount(count) {
    const countElement = document.getElementById('searchResultsCount');
    if (countElement) {
        countElement.textContent = count;
        countElement.className = count > 0 ? 'badge bg-primary' : 'badge bg-warning';
    }
}

function showNoResultsMessage(show) {
    let noResultsMsg = document.getElementById('noResultsMessage');
    
    if (show && !noResultsMsg) {
        noResultsMsg = document.createElement('div');
        noResultsMsg.id = 'noResultsMessage';
        noResultsMsg.className = 'col-12 text-center py-5';
        noResultsMsg.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-search fa-2x mb-3"></i>
                <h5>No cases found</h5>
                <p class="mb-0">Try adjusting your search criteria or clearing filters.</p>
                <button class="btn btn-outline-primary btn-sm mt-2" onclick="clearAllFilters()">
                    Clear All Filters
                </button>
            </div>
        `;
        
        const activeTab = document.querySelector('.tab-pane.active .row');
        if (activeTab) {
            activeTab.appendChild(noResultsMsg);
        }
    } else if (!show && noResultsMsg) {
        noResultsMsg.remove();
    }
}

function showAppliedFiltersIndicator() {
    let indicator = document.getElementById('filtersIndicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'filtersIndicator';
        indicator.className = 'alert alert-info alert-sm mt-2';
        indicator.innerHTML = `
            <i class="fas fa-filter me-2"></i>Advanced filters applied
            <button class="btn btn-sm btn-outline-info ms-2" onclick="clearAllFilters()">
                Clear All
            </button>
        `;
        document.querySelector('.row.mb-3').appendChild(indicator);
    }
}

function exportFilteredCases() {
    const visibleCases = allCasesData.filter(caseData => 
        caseData.element.style.display !== 'none'
    );
    
    if (visibleCases.length === 0) {
        showAlert('No cases to export', 'warning');
        return;
    }
    
    const csvData = [
        ['Case No', 'CINO', 'Petitioner', 'Respondent', 'Next Date', 'Establishment', 'Notes']
    ];
    
    visibleCases.forEach(caseData => {
        const notes = caseData.element.querySelector('.notes-input')?.value || '';
        
        csvData.push([
            caseData.caseNo,
            caseData.cino,
            caseData.petitioner,
            caseData.respondent,
            caseData.nextDate,
            caseData.establishment.replace(/\n/g, ' ').trim(),
            notes
        ]);
    });
    
    const csv = csvData.map(row => 
        row.map(field => `"${field.toString().replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `filtered-cases-${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert(`Exported ${visibleCases.length} cases to CSV`, 'success');
}

function extractDate(element) {
    const dateText = element.querySelector('.case-details')?.textContent || '';
    const dateMatch = dateText.match(/\d{4}-\d{2}-\d{2}|\d{2}\/\d{2}\/\d{4}|\d{2}-\d{2}-\d{4}/);
    return dateMatch ? dateMatch[0] : '';
}

// Calendar Management Functions
function createCalendarEvents() {
    if (!confirm('Create calendar events for all cases with valid dates?\n\nThis will create events for cases that have a next hearing date set.')) {
        return;
    }
    
    showCalendarCreationProgress();
    
    fetch('/calendar_progress')
    .then(response => response.json())
    .then(progressData => {
        updateCalendarProgressDisplay(progressData);
        
        return fetch('/create_calendar_events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
    })
    .then(response => response.json())
    .then(data => {
        hideCalendarCreationProgress();
        
        if (data.error) {
            showAlert(`Calendar creation failed: ${data.error}`, 'danger');
        } else {
            const detailedMessage = `Calendar Updated Successfully!\n\n` +
                `ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ ${data.created} events created\n` +
                `ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚ÂÃƒâ€šÃ‚Â© ${data.skipped} events skipped (duplicates/invalid)\n` +
                `ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚ÂÃƒâ€¦Ã¢â‚¬â„¢ ${data.failed} events failed\n` +
                `ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒâ€šÃ‚Â ${data.cases_with_notes} cases had notes\n` +
                `ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾ ${data.cases_without_notes} cases without notes`;
            
            showAlert(detailedMessage, 'success');
            
            if (data.excel_file) {
                setTimeout(() => {
                    showAlert('ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œÃƒâ€šÃ‚Â Reference file created: ' + data.excel_file, 'info');
                }, 3000);
            }
        }
    })
    .catch(error => {
        hideCalendarCreationProgress();
        showAlert('Calendar creation failed: ' + error.message, 'danger');
    });
}

function showCalendarCreationProgress() {
    const modal = `
        <div class="modal fade" id="calendarCreationModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-calendar-plus me-2"></i>Creating Calendar Events
                        </h5>
                    </div>
                    <div class="modal-body">
                        <div id="calendarProgressContent">
                            <div class="text-center">
                                <div class="spinner-border text-primary mb-3"></div>
                                <p>Analyzing cases and creating events...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modal);
    const creationModal = new bootstrap.Modal(document.getElementById('calendarCreationModal'));
    creationModal.show();
}

function updateCalendarProgressDisplay(data) {
    const content = `
        <h6>Calendar Creation Analysis:</h6>
        <div class="row text-center mb-3">
            <div class="col-3">
                <div class="h4 text-primary">${data.total_cases}</div>
                <small class="text-muted">Total Cases</small>
            </div>
            <div class="col-3">
                <div class="h4 text-success">${data.cases_with_dates}</div>
                <small class="text-muted">With Dates</small>
            </div>
            <div class="col-3">
                <div class="h4 text-info">${data.cases_with_notes}</div>
                <small class="text-muted">With Notes</small>
            </div>
            <div class="col-3">
                <div class="h4 text-warning">${data.ready_for_calendar}</div>
                <small class="text-muted">Ready</small>
            </div>
        </div>
        <div class="progress mb-3">
            <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                 style="width: ${(data.cases_with_dates/data.total_cases)*100}%"></div>
        </div>
        <p class="small text-muted text-center">
            <i class="fas fa-cog fa-spin me-2"></i>Processing ${data.cases_with_dates} cases...
        </p>
    `;
    
    document.getElementById('calendarProgressContent').innerHTML = content;
}

function hideCalendarCreationProgress() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('calendarCreationModal'));
    if (modal) {
        modal.hide();
        setTimeout(() => {
            const modalElement = document.getElementById('calendarCreationModal');
            if (modalElement) {
                modalElement.remove();
            }
        }, 500);
    }
}

// Calendar Deletion Functions
function showDeleteCalendarModal() {
    const modal = new bootstrap.Modal(document.getElementById('deleteCalendarModal'));
    modal.show();
    
    document.getElementById('eventsPreview').style.display = 'none';
    document.getElementById('cleanupProgress').style.display = 'none';
    document.getElementById('previewBtn').style.display = 'inline-block';
    document.getElementById('cleanupBtn').style.display = 'none';
}

function previewCleanup() {
    const selectedOption = document.querySelector('input[name="cleanupOption"]:checked').value;
    const previewBtn = document.getElementById('previewBtn');
    const cleanupBtn = document.getElementById('cleanupBtn');
    
    previewBtn.disabled = true;
    previewBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
    
    if (selectedOption === 'complete' || selectedOption === 'calendar') {
        fetch('/calendar_events_preview')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showAlert(data.error, 'danger');
                return;
            }
            
            displayEventsPreview(data.events, data.total_count);
            document.getElementById('eventsPreview').style.display = 'block';
        })
        .catch(error => {
            showAlert('Failed to preview events: ' + error.message, 'danger');
        })
        .finally(() => {
            previewBtn.disabled = false;
            previewBtn.innerHTML = '<i class="fas fa-eye me-2"></i>Preview';
            previewBtn.style.display = 'none';
            cleanupBtn.style.display = 'inline-block';
            cleanupBtn.innerHTML = '<i class="fas fa-trash me-2"></i>' + getCleanupButtonText(selectedOption);
        });
    } else {
        previewBtn.disabled = false;
        previewBtn.innerHTML = '<i class="fas fa-eye me-2"></i>Preview';
        previewBtn.style.display = 'none';
        cleanupBtn.style.display = 'inline-block';
        cleanupBtn.innerHTML = '<i class="fas fa-trash me-2"></i>' + getCleanupButtonText(selectedOption);
    }
}

function getCleanupButtonText(option) {
    switch(option) {
        case 'complete': return 'Complete Cleanup';
        case 'calendar': return 'Delete Calendar Only';
        case 'local': return 'Clear Local Data Only';
        default: return 'Start Cleanup';
    }
}

function confirmCleanup() {
    const selectedOption = document.querySelector('input[name="cleanupOption"]:checked').value;
    
    let confirmMessage = 'Are you absolutely sure?\n\n';
    switch(selectedOption) {
        case 'complete':
            confirmMessage += 'This will delete ALL calendar events, database records, and local files. This action cannot be undone!';
            break;
        case 'calendar':
            confirmMessage += 'This will delete ALL court events from your Google Calendar only.';
            break;
        case 'local':
            confirmMessage += 'This will delete all local database records and files only.';
            break;
    }
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    document.getElementById('eventsPreview').style.display = 'none';
    document.getElementById('cleanupProgress').style.display = 'block';
    document.getElementById('cleanupBtn').style.display = 'none';
    document.getElementById('cancelBtn').textContent = 'Close';
    
    executeCleanup(selectedOption);
}

function executeCleanup(option) {
    const progressBar = document.getElementById('overallProgressBar');
    const currentStepText = document.getElementById('currentStepText');
    
    progressBar.style.width = '10%';
    currentStepText.textContent = 'Starting cleanup process...';
    
    let endpoint;
    let requestBody = {};
    
    switch(option) {
        case 'complete':
            endpoint = '/complete_system_cleanup';
            break;
        case 'calendar':
            endpoint = '/delete_calendar_events';
            requestBody = { method: 'auto' };
            break;
        case 'local':
            endpoint = '/clear_local_data';
            break;
    }
    
    fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showAlert(data.error, 'danger');
            currentStepText.textContent = 'Cleanup failed. Please try again.';
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-danger');
            return;
        }
        
        updateCleanupProgress(data, option);
        
        setTimeout(() => {
            const message = data.detailed_message || data.message;
            showAlert(message, 'success');
            
            setTimeout(() => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('deleteCalendarModal'));
                if (modal) modal.hide();
                
                setTimeout(() => location.reload(), 1000);
            }, 3000);
        }, 1000);
    })
    .catch(error => {
        showAlert('Cleanup failed: ' + error.message, 'danger');
        currentStepText.textContent = 'Cleanup failed. Please try again.';
        progressBar.classList.remove('progress-bar-animated');
        progressBar.classList.add('bg-danger');
    });
}

function updateCleanupProgress(data, option) {
    const progressBar = document.getElementById('overallProgressBar');
    const currentStepText = document.getElementById('currentStepText');
    const deletedCount = document.getElementById('deletedCount');
    const databaseCount = document.getElementById('databaseCount');
    const filesCount = document.getElementById('filesCount');

    if (option === 'complete') {
        updateStepStatus('backupStep', 'success');
        updateStepStatus('calendarStep', 'success');
        updateStepStatus('databaseStep', 'success');
        updateStepStatus('filesStep', 'success');

        deletedCount.textContent = data.calendar_deleted || 0;
        databaseCount.textContent = data.database_deleted || 0;
        filesCount.textContent = data.files_deleted || 0;
    } else if (option === 'calendar') {
        updateStepStatus('calendarStep', 'success');
        deletedCount.textContent = data.deleted || 0;
    } else if (option === 'local') {
        updateStepStatus('databaseStep', 'success');
        updateStepStatus('filesStep', 'success');
        
        var databaseDeleted = (data.database_result && data.database_result.cases_deleted) ? data.database_result.cases_deleted : 0;
        var filesDeleted = (data.file_result && data.file_result.total_deleted) ? data.file_result.total_deleted : 0;
        
        databaseCount.textContent = databaseDeleted;
        filesCount.textContent = filesDeleted;
    }

    progressBar.style.width = '100%';
    progressBar.classList.remove('progress-bar-animated');
    currentStepText.textContent = 'Cleanup completed successfully!';
}

function updateStepStatus(stepId, status) {
    const step = document.getElementById(stepId);
    if (step) {
        step.classList.remove('text-muted');
        if (status === 'success') {
            step.classList.add('text-success');
            const icon = step.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-check-circle fa-2x mb-2';
            }
        } else if (status === 'warning') {
            step.classList.add('text-warning');
            const icon = step.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-spinner fa-spin fa-2x mb-2';
            }
        }
    }
}

function displayEventsPreview(events, totalCount) {
    const eventsList = document.getElementById('eventsList');
    const previewCount = document.getElementById('previewCount');
    const totalEventsNote = document.getElementById('totalEventsNote');
    
    previewCount.textContent = totalCount;
    totalEventsNote.textContent = totalCount > 50 ? '(showing first 50)' : '';
    
    if (events.length === 0) {
        eventsList.innerHTML = '<div class="text-center text-muted">No court events found to delete.</div>';
        return;
    }
    
    const eventsHtml = events.map(function(event) {
        return `
            <div class="border-bottom py-2">
                <div class="fw-bold">${event.summary || 'No Title'}</div>
                <div class="text-muted small">
                    <i class="fas fa-calendar me-1"></i>${event.start || 'No Date'}
                </div>
                ${event.description ? `<div class="text-muted small">${event.description}</div>` : ''}
            </div>
        `;
    }).join('');
    
    eventsList.innerHTML = eventsHtml;
}

// Initialize when document loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize search functionality
    initializeSearch();
    
    // Bind search events
    document.getElementById('searchInput')?.addEventListener('input', handleSearch);
    document.getElementById('dateFromInput')?.addEventListener('change', handleSearch);
    document.getElementById('dateToInput')?.addEventListener('change', handleSearch);
    
    // Auto-expand changes for first 3 changed cases
    document.querySelectorAll('.change-summary').forEach((element, index) => {
        if (index < 3) {
            element.style.display = 'block';
        }
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            saveAllCases();
        }
        if (e.ctrlKey && e.key === 'u') {
            e.preventDefault();
            document.getElementById('fileInput').click();
        }
    });
    
    // Initialize tab switching with proper layout handling
    const tabLinks = document.querySelectorAll('[data-bs-toggle="tab"]');
    
    tabLinks.forEach(link => {
        link.addEventListener('shown.bs.tab', function(e) {
            const target = e.target.getAttribute('href');
            const targetPane = document.querySelector(target);
            
            if (targetPane) {
                targetPane.style.display = 'block';
                
                const cards = targetPane.querySelectorAll('.case-card');
                cards.forEach(card => {
                    card.style.height = 'auto';
                });
            }
        });
    });
});