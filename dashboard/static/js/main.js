/**
 * Main JavaScript — Shared Utilities for EconoGrid Planner Dashboard.
 *
 * Provides table rendering, formatting, and common UI functions
 * used across all module pages.
 */

/**
 * Build an HTML table from an array of row objects.
 *
 * @param {Array<Object>} data - Array of row objects.
 * @param {Array<string>} columns - Column headers to display.
 * @returns {string} HTML table string.
 */
function buildTable(data, columns) {
    if (!data || data.length === 0) {
        return '<p style="color:var(--text-muted);font-style:italic;">No data available</p>';
    }

    let html = '<table class="data-table"><thead><tr>';
    columns.forEach(col => {
        html += `<th>${escapeHtml(col)}</th>`;
    });
    html += '</tr></thead><tbody>';

    data.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            let value = row[col];
            if (value === null || value === undefined) value = '—';
            else if (typeof value === 'number') value = formatNumber(value);
            html += `<td>${escapeHtml(String(value))}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    return html;
}

/**
 * Format a number for display.
 *
 * @param {number} num - Number to format.
 * @returns {string} Formatted string.
 */
function formatNumber(num) {
    if (Number.isNaN(num) || num === null || num === undefined) return '—';

    const abs = Math.abs(num);

    // Very small numbers — scientific notation
    if (abs > 0 && abs < 0.0001) return num.toExponential(4);

    // Percentages and small decimals
    if (abs < 1) return num.toFixed(6);

    // Normal numbers
    if (abs < 1000) return num.toFixed(4);

    // Large numbers with commas
    return num.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

/**
 * Escape HTML special characters.
 *
 * @param {string} str - String to escape.
 * @returns {string} Escaped string.
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * Format currency value.
 *
 * @param {number} value - Dollar amount.
 * @returns {string} Formatted currency string.
 */
function formatCurrency(value) {
    if (!value && value !== 0) return '—';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0
    }).format(value);
}

/**
 * Format percentage.
 *
 * @param {number} value - Decimal value (e.g., 0.08 for 8%).
 * @returns {string} Formatted percentage string.
 */
function formatPercent(value) {
    if (!value && value !== 0) return '—';
    return (value * 100).toFixed(2) + '%';
}

window.latestAnalysisByModule = {
    regression: null,
    scenario: null,
    financial: null,
};

function setLatestAnalysis(module, inputs, results) {
    window.latestAnalysisByModule[module] = { inputs, results };
}

async function populateProjectSelect(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;

    try {
        const response = await fetch('/api/projects');
        const payload = await response.json();
        if (payload.status !== 'success') return;

        select.innerHTML = '<option value="">Select saved project</option>';
        payload.projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.project_id;
            option.textContent = `${project.project_name} (${project.version_count} versions)`;
            select.appendChild(option);
        });
    } catch (err) {
        console.error('Failed to load project list', err);
    }
}

async function saveProjectSnapshot(module, projectNameInputId, statusTargetId) {
    const projectName = document.getElementById(projectNameInputId)?.value?.trim();
    const latest = window.latestAnalysisByModule[module];
    const statusNode = document.getElementById(statusTargetId);

    if (!projectName) {
        if (statusNode) statusNode.textContent = 'Enter a project name first.';
        return;
    }
    if (!latest) {
        if (statusNode) statusNode.textContent = 'Run an analysis before saving.';
        return;
    }

    try {
        const response = await fetch('/api/projects/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_name: projectName,
                module,
                inputs: latest.inputs,
                results: latest.results,
            })
        });
        const payload = await response.json();
        if (payload.status === 'success') {
            if (statusNode) statusNode.textContent = `Saved ${payload.project.project_name} (${payload.project.project_id}).`;
        } else if (statusNode) {
            statusNode.textContent = payload.message || 'Save failed.';
        }
    } catch (err) {
        if (statusNode) statusNode.textContent = err.message;
    }
}

async function loadLatestProjectVersion(module, selectId) {
    const projectId = document.getElementById(selectId)?.value;
    if (!projectId) return null;

    const response = await fetch(`/api/projects/${projectId}/latest/${module}`);
    const payload = await response.json();
    if (payload.status !== 'success') {
        throw new Error(payload.message || 'Failed to load project version.');
    }
    return payload.version;
}

async function refreshProjectLibrary() {
    const target = document.getElementById('project-library');
    if (!target) return;

    try {
        const response = await fetch('/api/projects');
        const payload = await response.json();
        if (payload.status !== 'success' || !payload.projects.length) {
            target.innerHTML = '<p style="color:var(--text-muted);font-style:italic;">No saved projects yet.</p>';
            return;
        }

        target.innerHTML = payload.projects.map(project => `
            <div class="project-card">
                <div>
                    <h3>${escapeHtml(project.project_name)}</h3>
                    <p>${escapeHtml(project.modules.join(', ') || 'No modules')}</p>
                    <p class="help-text">Updated ${escapeHtml(project.updated_at)}</p>
                </div>
                <div class="project-card-actions">
                    <a class="btn btn-secondary btn-sm" href="/api/projects/${project.project_id}/report">Download PDF</a>
                </div>
            </div>
        `).join('');
    } catch (err) {
        target.innerHTML = `<p style="color:var(--error);">Failed to load projects: ${escapeHtml(err.message)}</p>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    refreshProjectLibrary();
});

// Log app initialization
console.log('⚡ EconoGrid Planner Dashboard initialized');
