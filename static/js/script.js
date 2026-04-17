// ─── Mobile Navigation ───────────────────────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (!sidebar || !overlay) return;
    sidebar.classList.toggle('active');
    overlay.classList.toggle('active');
    document.body.style.overflow = sidebar.classList.contains('active') ? 'hidden' : '';
}

function setupMobileNav() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) toggleSidebar();
        });
    });
}

window.addEventListener('resize', function () {
    if (window.innerWidth > 768) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        if (sidebar) sidebar.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// ─── Tax State ────────────────────────────────────────────────────────────────
// 'intra' = CGST+SGST  |  'inter' = IGST
let currentTaxType = 'inter';

// ─── Items Table ─────────────────────────────────────────────────────────────
function addItemRow() {
    const tbody = document.querySelector('#itemsTable tbody');
    if (!tbody) return;

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="desc" placeholder="Item name / description"></td>
        <td><input type="number" class="qty"  value="1"  min="0" step="1"    oninput="calcRow(this)"></td>
        <td><input type="number" class="rate" value="0"  min="0" step="0.01" oninput="calcRow(this)"></td>
        <td>
            <select class="unit">
                <option>NOS</option><option>KGS</option><option>LTS</option>
                <option>PKTS</option><option>MTR</option><option>SET</option>
            </select>
        </td>
        <td><span class="row-basic">0.00</span></td>
        <td>
            <select class="gst-rate" onchange="calcRow(this)">
                <option value="0">0%</option>
                <option value="5">5%</option>
                <option value="12">12%</option>
                <option value="18" selected>18%</option>
                <option value="28">28%</option>
            </select>
        </td>
        <td><span class="row-total">0.00</span></td>
        <td><button onclick="removeItemRow(this)" class="btn btn-sm btn-danger" title="Remove">&times;</button></td>
    `;
    tbody.appendChild(tr);
}

function removeItemRow(btn) {
    btn.closest('tr')?.remove();
    calcTotals();
}

function calcRow(input) {
    const tr = input.closest('tr');
    if (!tr) return;

    const qty     = Math.max(0, parseFloat(tr.querySelector('.qty').value)  || 0);
    const rate    = Math.max(0, parseFloat(tr.querySelector('.rate').value) || 0);
    const gstRate = parseFloat(tr.querySelector('.gst-rate').value) || 0;

    const basic = qty * rate;
    const gst   = basic * (gstRate / 100);
    const total = basic + gst;

    tr.querySelector('.row-basic').textContent = basic.toFixed(2);
    tr.querySelector('.row-total').textContent = total.toFixed(2);
    tr.dataset.basic   = basic;
    tr.dataset.gst     = gst;
    tr.dataset.total   = total;
    tr.dataset.gstRate = gstRate;

    calcTotals();
}

function calcTotals() {
    let totalBasic = 0;
    let totalGst   = 0;

    document.querySelectorAll('#itemsTable tbody tr').forEach(tr => {
        totalBasic += parseFloat(tr.dataset.basic) || 0;
        totalGst   += parseFloat(tr.dataset.gst)   || 0;
    });

    const grandTotal = totalBasic + totalGst;

    const elBasic = document.getElementById('displayBasic');
    const elGst   = document.getElementById('displayGst');
    const elGrand = document.getElementById('displayGrand');

    if (elBasic) elBasic.textContent = '₹' + totalBasic.toFixed(2);
    if (elGst)   elGst.textContent   = '₹' + totalGst.toFixed(2);
    if (elGrand) elGrand.textContent = '₹' + grandTotal.toFixed(2);

    // Tax breakdown display
    const taxDiv = document.getElementById('taxBreakdown');
    if (taxDiv && totalGst > 0) {
        taxDiv.style.display = 'flex';
        if (currentTaxType === 'intra') {
            const half = totalGst / 2;
            taxDiv.innerHTML = `<span>CGST (9%):</span><span>₹${half.toFixed(2)}</span>`;
            // inject SGST too
            const sgstDiv = document.getElementById('taxBreakdownSgst');
            if (sgstDiv) {
                sgstDiv.style.display = 'flex';
                sgstDiv.innerHTML = `<span>SGST (9%):</span><span>₹${half.toFixed(2)}</span>`;
            }
        } else {
            taxDiv.innerHTML = `<span>IGST (18%):</span><span>₹${totalGst.toFixed(2)}</span>`;
            const sgstDiv = document.getElementById('taxBreakdownSgst');
            if (sgstDiv) sgstDiv.style.display = 'none';
        }
    } else if (taxDiv) {
        taxDiv.style.display = 'none';
    }

    return {
        basic: totalBasic,
        gst:   totalGst,
        grand: grandTotal,
        igst:  currentTaxType === 'inter' ? totalGst : 0,
        cgst:  currentTaxType === 'intra' ? totalGst / 2 : 0,
        sgst:  currentTaxType === 'intra' ? totalGst / 2 : 0,
    };
}

// ─── Tax type based on GSTIN ──────────────────────────────────────────────────
function updateTaxType() {
    const gstInput = document.getElementById('custGst');
    if (!gstInput) return;
    const gstin = gstInput.value.trim();
    // Default company GSTIN prefix is 34 (Puducherry); detect from input
    const companyPrefix = window.COMPANY_GSTIN_PREFIX || '34';
    currentTaxType = (gstin.length >= 2 && gstin.substring(0, 2) === companyPrefix) ? 'intra' : 'inter';
    calcTotals();
}

// ─── Customer Search ──────────────────────────────────────────────────────────
let _searchTimer = null;

function searchCustomer(query) {
    const resultsDiv = document.getElementById('custSearchResults');
    if (!resultsDiv) return;

    if (!query || query.length < 2) {
        resultsDiv.style.display = 'none';
        return;
    }

    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/api/customers?q=${encodeURIComponent(query)}`);
            if (!res.ok) return;
            const customers = await res.json();
            resultsDiv.innerHTML = '';
            if (customers.length > 0) {
                customers.forEach(c => {
                    const div = document.createElement('div');
                    div.className = 'dropdown-item';
                    div.textContent = c.name;
                    div.onclick = () => selectCustomer(c);
                    resultsDiv.appendChild(div);
                });
                resultsDiv.style.display = 'block';
            } else {
                resultsDiv.style.display = 'none';
            }
        } catch (e) {
            console.error('Customer search error:', e);
        }
    }, 300);
}

function selectCustomer(c) {
    const map = { custName: c.name, custId: c.id, custAddr: c.address, custGst: c.gstin, custState: c.state };
    for (const [id, val] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el) el.value = val || '';
    }
    const placeEl = document.getElementById('placeOfSupply');
    if (placeEl && !placeEl.value) placeEl.value = c.state || '';

    const results = document.getElementById('custSearchResults');
    if (results) results.style.display = 'none';
    updateTaxType();
}

document.addEventListener('click', e => {
    if (!e.target.closest('.search-container')) {
        const r = document.getElementById('custSearchResults');
        if (r) r.style.display = 'none';
    }
});

// ─── Add extracted item row (AI pre-fill) ─────────────────────────────────────
function addExtractedItemRow(item) {
    const tbody = document.querySelector('#itemsTable tbody');
    if (!tbody || !item) return;

    const desc    = (item.description || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    const qty     = parseInt(item.qty)     || 1;
    const rate    = parseFloat(item.rate)  || 0;
    const unit    = (item.unit || 'NOS').replace(/"/g, '&quot;');
    const gstRate = parseFloat(item.gst_rate) || 18;

    const unitOpts = ['NOS','KGS','LTS','PKTS','MTR','SET'];
    const gstOpts  = [0, 5, 12, 18, 28];

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="desc" value="${desc}" placeholder="Item name"></td>
        <td><input type="number" class="qty"  value="${qty}"  min="0" step="1"    oninput="calcRow(this)"></td>
        <td><input type="number" class="rate" value="${rate}" min="0" step="0.01" oninput="calcRow(this)"></td>
        <td>
            <select class="unit">
                ${unitOpts.map(u => `<option${u === unit ? ' selected' : ''}>${u}</option>`).join('')}
            </select>
        </td>
        <td><span class="row-basic">0.00</span></td>
        <td>
            <select class="gst-rate" onchange="calcRow(this)">
                ${gstOpts.map(g => `<option value="${g}"${g === gstRate ? ' selected' : ''}>${g}%</option>`).join('')}
            </select>
        </td>
        <td><span class="row-total">0.00</span></td>
        <td><button onclick="removeItemRow(this)" class="btn btn-sm btn-danger">&times;</button></td>
    `;
    tbody.appendChild(tr);
    calcRow(tr.querySelector('.qty'));
}

// ─── Save Quotation ───────────────────────────────────────────────────────────
async function saveQuotation() {
    const custName  = (document.getElementById('custName')?.value  || '').trim();
    const custGst   = (document.getElementById('custGst')?.value   || '').trim();
    const custAddr  = (document.getElementById('custAddr')?.value  || '').trim();
    const custState = (document.getElementById('custState')?.value || '').trim();
    const qDate     = (document.getElementById('qDate')?.value     || '').trim();

    if (!custName)  { alert('Please enter Customer Name.');    document.getElementById('custName')?.focus();  return; }
    if (!custGst)   { alert('Please enter Customer GSTIN.');   document.getElementById('custGst')?.focus();   return; }
    if (!custAddr)  { alert('Please enter Customer Address.'); document.getElementById('custAddr')?.focus();  return; }
    if (!custState) { alert('Please enter Customer State.');   document.getElementById('custState')?.focus(); return; }
    if (!qDate)     { alert('Please select a date.');          document.getElementById('qDate')?.focus();     return; }

    const itemRows = document.querySelectorAll('#itemsTable tbody tr');
    if (itemRows.length === 0) { alert('Please add at least one item.'); return; }

    const totals = calcTotals();
    const items  = [];
    let hasError = false;

    itemRows.forEach((tr, i) => {
        const desc = (tr.querySelector('.desc')?.value || '').trim();
        if (!desc) {
            hasError = true;
            alert(`Enter description for item ${i + 1}.`);
            tr.querySelector('.desc')?.focus();
            return;
        }
        items.push({
            description: desc,
            qty:      tr.querySelector('.qty')?.value  || 1,
            rate:     tr.querySelector('.rate')?.value || 0,
            unit:     tr.querySelector('.unit')?.value || 'NOS',
            basic:    tr.dataset.basic    || 0,
            gst:      tr.dataset.gst      || 0,
            gst_rate: tr.dataset.gstRate  || 0,
            total:    tr.dataset.total    || 0,
        });
    });
    if (hasError) return;

    const data = {
        date:            qDate,
        place_of_supply: (document.getElementById('placeOfSupply')?.value || '').trim(),
        customer: {
            id:      document.getElementById('custId')?.value || '',
            name:    custName,
            address: custAddr,
            gstin:   custGst,
            state:   custState,
        },
        items,
        totals,
    };

    await _submitForm('/quotation/new', data);
}

// ─── Common form submit helper ────────────────────────────────────────────────
async function _submitForm(url, data) {
    const saveBtn = document.querySelector('.form-actions .btn-primary');
    let orig = '';
    if (saveBtn) {
        orig = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        saveBtn.disabled = true;
    }
    try {
        const response = await fetch(url, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(data),
        });
        const result = await response.json();
        if (result.success) {
            window.location.href = result.redirect_url;
        } else {
            alert('Error: ' + (result.error || 'Unknown error'));
            if (saveBtn) { saveBtn.innerHTML = orig; saveBtn.disabled = false; }
        }
    } catch (e) {
        console.error(e);
        alert('Network error. Please check your connection and try again.');
        if (saveBtn) { saveBtn.innerHTML = orig; saveBtn.disabled = false; }
    }
}

// ─── Active Nav Highlight ─────────────────────────────────────────────────────
function highlightActiveNav() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
        const href = item.getAttribute('href');
        if (!href) return;
        if (href === path || (href !== '/' && path.startsWith(href))) {
            item.classList.add('active');
        }
    });
}

// ─── Pre-fill editing data (invoice edit page) ───────────────────────────────
function prefillEditing(editingData) {
    if (!editingData) return;
    const c = editingData.customer || {};
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    set('custName',      c.name);
    set('custId',        c.id);
    set('custAddr',      c.address);
    set('custGst',       c.gstin);
    set('custState',     c.state);
    set('qDate',         editingData.date);
    set('placeOfSupply', editingData.place_of_supply);

    const tbody = document.querySelector('#itemsTable tbody');
    if (tbody) tbody.innerHTML = '';
    (editingData.items || []).forEach(item => addExtractedItemRow(item));

    updateTaxType();
}

// ─── Initialise ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    setupMobileNav();
    highlightActiveNav();

    // Set today's date if no value already
    const dateInput = document.getElementById('qDate');
    if (dateInput && !dateInput.value) {
        const hasExtracted = typeof extracted !== 'undefined' && extracted !== null;
        if (!hasExtracted || !extracted.date) {
            dateInput.valueAsDate = new Date();
        }
    }

    // Initialise items table
    const itemsTable = document.getElementById('itemsTable');
    if (itemsTable) {
        const tbody = itemsTable.querySelector('tbody');

        // Invoice edit mode
        if (typeof editing !== 'undefined' && editing !== null) {
            if (tbody) tbody.innerHTML = '';
            prefillEditing(editing);
        }
        // AI-extracted quotation pre-fill
        else if (typeof extracted !== 'undefined' && extracted !== null && extracted.items?.length > 0) {
            if (tbody) tbody.innerHTML = '';
            extracted.items.forEach(item => addExtractedItemRow(item));
            // Pre-fill customer fields from extracted
            const c = extracted.customer || {};
            const set = (id, v) => { const el = document.getElementById(id); if (el && v) el.value = v; };
            set('custName',      c.name);
            set('custAddr',      c.address);
            set('custGst',       c.gstin);
            set('custState',     c.state);
            set('placeOfSupply', extracted.place_of_supply);
            if (extracted.date) {
                const d = document.getElementById('qDate');
                if (d) d.value = extracted.date;
            }
            updateTaxType();
        }
        // Default: one empty row
        else if (!tbody || tbody.querySelectorAll('tr').length === 0) {
            addItemRow();
        }
    }

    // Auto-dismiss flash messages
    document.querySelectorAll('.flash-msg').forEach(msg => {
        setTimeout(() => {
            msg.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-8px)';
            setTimeout(() => msg.remove(), 500);
        }, 5000);
    });
});
