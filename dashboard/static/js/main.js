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

// Log app initialization
console.log('⚡ EconoGrid Planner Dashboard initialized');
