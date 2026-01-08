/**
 * RFP Answer Generator - Frontend Application
 */

// API Base URL
const API_BASE = '';

// State
let currentGenerateMode = 'question';
let generatedAnswers = [];

// DOM Elements
const elements = {
    statsBar: document.getElementById('stats-bar'),
    statPairs: document.getElementById('stat-pairs'),
    statChunks: document.getElementById('stat-chunks'),
    statFiles: document.getElementById('stat-files'),
    toastContainer: document.getElementById('toast-container'),
    resultsSection: document.getElementById('results-section'),
    resultsContainer: document.getElementById('results-container'),
    searchResults: document.getElementById('search-results'),
    pairsList: document.getElementById('pairs-list')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initForms();
    initGenerateOptions();
    initFileInputs();
    initManageActions();
    loadStats();
    loadPairs();
});

// Tab Navigation
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            // Update buttons
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update panels
            tabPanels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `${targetTab}-panel`) {
                    panel.classList.add('active');
                }
            });

            // Refresh data for manage tab
            if (targetTab === 'manage') {
                loadPairs();
            }
        });
    });
}

// Form Handlers
function initForms() {
    // Upload Pair Form
    document.getElementById('upload-pair-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleUploadPair(e.target);
    });

    // Upload Single Form
    document.getElementById('upload-single-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleUploadSingle(e.target);
    });

    // Single Question Form
    document.getElementById('single-question-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleSingleQuestion(e.target);
    });

    // Bulk Questions Form
    document.getElementById('bulk-questions-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleBulkQuestions(e.target);
    });

    // File Questions Form
    document.getElementById('file-questions-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleFileQuestions(e.target);
    });

    // Search Form
    document.getElementById('search-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleSearch(e.target);
    });

    // Export buttons
    document.getElementById('export-md')?.addEventListener('click', () => exportAnswers('markdown'));
    document.getElementById('export-json')?.addEventListener('click', () => exportAnswers('json'));
    document.getElementById('copy-all')?.addEventListener('click', copyAllAnswers);
}

// Generate Options Toggle
function initGenerateOptions() {
    const options = document.querySelectorAll('.option-card');
    const forms = {
        question: document.getElementById('single-question-form'),
        bulk: document.getElementById('bulk-questions-form'),
        file: document.getElementById('file-questions-form')
    };

    options.forEach(option => {
        option.addEventListener('click', () => {
            const mode = option.dataset.mode;
            currentGenerateMode = mode;

            // Update option cards
            options.forEach(o => o.classList.remove('active'));
            option.classList.add('active');

            // Show/hide forms
            Object.entries(forms).forEach(([key, form]) => {
                if (key === mode) {
                    form.classList.remove('hidden');
                } else {
                    form.classList.add('hidden');
                }
            });
        });
    });
}

// File Input Enhancement
function initFileInputs() {
    const fileInputs = document.querySelectorAll('input[type="file"]');

    fileInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            const wrapper = input.closest('.file-input-wrapper');
            const nameSpan = wrapper.querySelector('.file-name');

            if (input.files.length > 0) {
                nameSpan.textContent = input.files[0].name;
                wrapper.classList.add('has-file');
            } else {
                nameSpan.textContent = wrapper.querySelector('.file-name').dataset.default || 'Choose file...';
                wrapper.classList.remove('has-file');
            }
        });
    });
}

// Manage Actions
function initManageActions() {
    document.getElementById('clear-all-btn')?.addEventListener('click', async () => {
        if (confirm('Are you sure you want to delete ALL documents? This cannot be undone.')) {
            await clearAllDocuments();
        }
    });
}

// API Functions
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const data = await response.json();

        elements.statPairs.textContent = data.pairs || 0;
        elements.statChunks.textContent = data.total_chunks || 0;
        elements.statFiles.textContent = data.unique_files || 0;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadPairs() {
    try {
        const response = await fetch(`${API_BASE}/api/pairs`);
        const data = await response.json();

        if (data.pairs && data.pairs.length > 0) {
            elements.pairsList.innerHTML = data.pairs.map(pair => `
                <div class="pair-card">
                    <div class="pair-info">
                        <h4>${pair.rfp_file || 'Unknown RFP'} ↔ ${pair.answer_file || 'Unknown Answer'}</h4>
                        <p>${pair.rfp_chunks} RFP chunks, ${pair.answer_chunks} answer chunks</p>
                    </div>
                    <button class="btn btn-small btn-danger" onclick="deletePair('${pair.rfp_file}', '${pair.answer_file}')">Delete</button>
                </div>
            `).join('');
        } else {
            elements.pairsList.innerHTML = '<p class="info-text">No document pairs uploaded yet.</p>';
        }
    } catch (error) {
        console.error('Failed to load pairs:', error);
        elements.pairsList.innerHTML = '<p class="info-text">Failed to load document pairs.</p>';
    }
}

async function handleUploadPair(form) {
    const formData = new FormData(form);
    const btn = form.querySelector('button[type="submit"]');

    setButtonLoading(btn, true);

    try {
        const response = await fetch(`${API_BASE}/api/upload/pair`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Document pair uploaded successfully!', 'success');
            form.reset();
            resetFileInputs(form);
            loadStats();
            loadPairs();
        } else {
            showToast(data.detail || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload failed: ' + error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function handleUploadSingle(form) {
    const formData = new FormData(form);
    const btn = form.querySelector('button[type="submit"]');

    setButtonLoading(btn, true);

    try {
        const response = await fetch(`${API_BASE}/api/upload/single`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Document uploaded successfully!', 'success');
            form.reset();
            resetFileInputs(form);
            loadStats();
        } else {
            showToast(data.detail || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload failed: ' + error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function handleSingleQuestion(form) {
    const question = form.querySelector('[name="question"]').value;
    const useLlm = form.querySelector('[name="use_llm"]').checked;
    const btn = form.querySelector('button[type="submit"]');

    setButtonLoading(btn, true);

    try {
        const response = await fetch(`${API_BASE}/api/generate/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, use_llm: useLlm })
        });

        const data = await response.json();

        if (response.ok) {
            generatedAnswers = [data];
            displayResults([data]);
            showToast('Answer generated!', 'success');
        } else {
            showToast(data.detail || 'Generation failed', 'error');
        }
    } catch (error) {
        showToast('Generation failed: ' + error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function handleBulkQuestions(form) {
    const questionsText = form.querySelector('[name="questions"]').value;
    const useLlm = form.querySelector('[name="use_llm"]').checked;
    const btn = form.querySelector('button[type="submit"]');

    const questions = questionsText.split('\n').filter(q => q.trim());

    if (questions.length === 0) {
        showToast('Please enter at least one question', 'error');
        return;
    }

    setButtonLoading(btn, true);

    try {
        const response = await fetch(`${API_BASE}/api/generate/bulk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ questions, use_llm: useLlm })
        });

        const data = await response.json();

        if (response.ok) {
            generatedAnswers = data.answers;
            displayResults(data.answers);
            showToast(`Generated ${data.count} answers!`, 'success');
        } else {
            showToast(data.detail || 'Generation failed', 'error');
        }
    } catch (error) {
        showToast('Generation failed: ' + error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function handleFileQuestions(form) {
    const formData = new FormData(form);
    formData.append('use_llm', form.querySelector('[name="use_llm"]').checked);
    const btn = form.querySelector('button[type="submit"]');

    setButtonLoading(btn, true);

    try {
        const response = await fetch(`${API_BASE}/api/generate/from-file`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && data.success) {
            generatedAnswers = data.answers;
            displayResults(data.answers);
            showToast(`Extracted and answered ${data.extracted_questions} questions!`, 'success');
        } else if (response.ok && !data.success) {
            showToast(data.message || 'No questions found in document', 'error');
        } else {
            showToast(data.detail || 'Processing failed', 'error');
        }
    } catch (error) {
        showToast('Processing failed: ' + error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
        resetFileInputs(form);
    }
}

async function handleSearch(form) {
    const query = form.querySelector('[name="query"]').value;
    const documentType = form.querySelector('[name="document_type"]').value;
    const topK = parseInt(form.querySelector('[name="top_k"]').value);
    const btn = form.querySelector('button[type="submit"]');

    setButtonLoading(btn, true);

    try {
        const response = await fetch(`${API_BASE}/api/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                document_type: documentType || null,
                top_k: topK
            })
        });

        const data = await response.json();

        if (response.ok) {
            displaySearchResults(data.results);
            showToast(`Found ${data.results.length} results`, 'success');
        } else {
            showToast(data.detail || 'Search failed', 'error');
        }
    } catch (error) {
        showToast('Search failed: ' + error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function clearAllDocuments() {
    try {
        const response = await fetch(`${API_BASE}/api/clear`, {
            method: 'POST'
        });

        if (response.ok) {
            showToast('All documents cleared', 'success');
            loadStats();
            loadPairs();
        } else {
            showToast('Failed to clear documents', 'error');
        }
    } catch (error) {
        showToast('Failed to clear: ' + error.message, 'error');
    }
}

async function deletePair(rfpFile, answerFile) {
    if (!confirm(`Delete documents: ${rfpFile} and ${answerFile}?`)) {
        return;
    }

    try {
        await fetch(`${API_BASE}/api/document/${encodeURIComponent(rfpFile)}`, { method: 'DELETE' });
        await fetch(`${API_BASE}/api/document/${encodeURIComponent(answerFile)}`, { method: 'DELETE' });

        showToast('Documents deleted', 'success');
        loadStats();
        loadPairs();
    } catch (error) {
        showToast('Delete failed: ' + error.message, 'error');
    }
}

// Display Functions
function displayResults(answers) {
    elements.resultsSection.classList.remove('hidden');

    elements.resultsContainer.innerHTML = answers.map((ans, idx) => {
        const confidenceClass = ans.confidence_score > 0.7 ? 'high' :
            ans.confidence_score > 0.4 ? 'medium' : 'low';

        return `
            <div class="result-card">
                <div class="question">${escapeHtml(ans.question)}</div>
                <div class="meta">
                    <span class="confidence-badge confidence-${confidenceClass}">
                        ${Math.round(ans.confidence_score * 100)}% confidence
                    </span>
                    <span>Method: ${ans.method}</span>
                </div>
                <div class="answer">${formatAnswer(ans.answer)}</div>
                ${ans.sources && ans.sources.length > 0 ? `
                    <div class="sources">
                        <h4>Sources:</h4>
                        ${ans.sources.map(src => `
                            <span class="source-tag">${src.file} (${Math.round(src.similarity * 100)}%)</span>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

function displaySearchResults(results) {
    elements.searchResults.classList.remove('hidden');

    if (results.length === 0) {
        elements.searchResults.innerHTML = '<p class="info-text">No results found.</p>';
        return;
    }

    elements.searchResults.innerHTML = results.map(result => `
        <div class="search-result">
            <div class="source">
                <span><strong>${result.source_file}</strong></span>
                <span class="type-badge ${result.document_type}">${result.document_type.toUpperCase()}</span>
            </div>
            <div class="content">${escapeHtml(result.content)}</div>
            ${result.answer_content ? `
                <div class="answer-preview">
                    <h5>Related Answer:</h5>
                    <p>${escapeHtml(result.answer_content.substring(0, 300))}${result.answer_content.length > 300 ? '...' : ''}</p>
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Export Functions
function exportAnswers(format) {
    if (generatedAnswers.length === 0) {
        showToast('No answers to export', 'error');
        return;
    }

    let content;
    let filename;
    let mimeType;

    if (format === 'json') {
        content = JSON.stringify(generatedAnswers, null, 2);
        filename = 'rfp_answers.json';
        mimeType = 'application/json';
    } else {
        content = generateMarkdown(generatedAnswers);
        filename = 'rfp_answers.md';
        mimeType = 'text/markdown';
    }

    downloadFile(content, filename, mimeType);
}

function generateMarkdown(answers) {
    let md = '# RFP Response Draft\n\n';
    md += `*Generated ${new Date().toLocaleString()}*\n\n---\n\n`;

    answers.forEach((ans, idx) => {
        const emoji = ans.confidence_score > 0.7 ? '🟢' :
            ans.confidence_score > 0.4 ? '🟡' : '🔴';

        md += `## Question ${idx + 1}\n\n`;
        md += `**${ans.question}**\n\n`;
        md += `*Confidence: ${emoji} ${Math.round(ans.confidence_score * 100)}% | Method: ${ans.method}*\n\n`;
        md += `### Answer\n\n${ans.answer}\n\n`;

        if (ans.sources && ans.sources.length > 0) {
            md += `### Sources\n\n`;
            ans.sources.forEach(src => {
                md += `- ${src.file} (${Math.round(src.similarity * 100)}% match)\n`;
            });
            md += '\n';
        }

        md += '---\n\n';
    });

    return md;
}

function copyAllAnswers() {
    if (generatedAnswers.length === 0) {
        showToast('No answers to copy', 'error');
        return;
    }

    const text = generatedAnswers.map((ans, idx) =>
        `Q${idx + 1}: ${ans.question}\n\nA: ${ans.answer}\n\n---\n`
    ).join('\n');

    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

// Utility Functions
function setButtonLoading(btn, loading) {
    if (loading) {
        btn.classList.add('loading');
        btn.disabled = true;
    } else {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

function resetFileInputs(form) {
    form.querySelectorAll('.file-input-wrapper').forEach(wrapper => {
        wrapper.classList.remove('has-file');
        const nameSpan = wrapper.querySelector('.file-name');
        nameSpan.textContent = nameSpan.dataset.default || 'Choose file...';
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 4000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatAnswer(answer) {
    // Convert markdown-like formatting to HTML
    let formatted = escapeHtml(answer);

    // Bold text
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Make deletePair globally available
window.deletePair = deletePair;
