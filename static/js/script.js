// ─── Mobile Navigation ───
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    if (sidebar && overlay) {
        sidebar.classList.toggle('active');
        overlay.classList.toggle('active');

        // Prevent body scroll when sidebar is open
        if (sidebar.classList.contains('active')) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    }
}

// Close sidebar when clicking on nav items on mobile
function setupMobileNav() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                toggleSidebar();
            }
        });
    });
}

// Handle window resize – close sidebar if resizing to desktop
window.addEventListener('resize', function () {
    if (window.innerWidth > 768) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        if (sidebar) sidebar.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// ─── Tax Logic ───
let currentTaxType = 'inter'; // 'intra' (CGST+SGST) or 'inter' (IGST)

function addItemRow() {
    const tbody = document.querySelector('#itemsTable tbody');
    if (!tbody) return;

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="desc" placeholder="Item Name"></td>
        <td><input type="number" class="qty" value="1" min="0" step="1" oninput="calcRow(this)"></td>
        <td><input type="number" class="rate" value="0" min="0" step="0.01" oninput="calcRow(this)"></td>
        <td>
            <select class="unit">
                <option value="NOS">NOS</option>
                <option value="KGS">KGS</option>
                <option value="LTS">LTS</option>
                <option value="PKTS">PKTS</option>
                <option value="MTR">MTR</option>
                <option value="SET">SET</option>
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
        <td><button onclick="removeItemRow(this)" class="btn btn-sm btn-danger" title="Remove item">&times;</button></td>
    `;
    tbody.appendChild(tr);
}

function removeItemRow(btn) {
    const tr = btn.closest('tr');
    if (tr) {
        tr.remove();
        calcTotals();
    }
}

function calcRow(input) {
    const tr = input.closest('tr');
    if (!tr) return;

    const qty = parseFloat(tr.querySelector('.qty').value) || 0;
    const rate = parseFloat(tr.querySelector('.rate').value) || 0;
    const gstRate = parseFloat(tr.querySelector('.gst-rate').value) || 0;

    // Prevent negative values
    const safeQty = Math.max(0, qty);
    const safeRate = Math.max(0, rate);

    const basic = safeQty * safeRate;
    const gst = basic * (gstRate / 100);
    const total = basic + gst;

    tr.querySelector('.row-basic').textContent = basic.toFixed(2);
    tr.querySelector('.row-total').textContent = total.toFixed(2);

    // Store data attributes
    tr.dataset.basic = basic;
    tr.dataset.gst = gst;
    tr.dataset.total = total;
    tr.dataset.gstRate = gstRate;

    calcTotals();
}

function calcTotals() {
    let totalBasic = 0;
    let totalGst = 0;

    document.querySelectorAll('#itemsTable tbody tr').forEach(tr => {
        totalBasic += (parseFloat(tr.dataset.basic) || 0);
        totalGst += (parseFloat(tr.dataset.gst) || 0);
    });

    const grandTotal = totalBasic + totalGst;

    const displayBasic = document.getElementById('displayBasic');
    const displayGst = document.getElementById('displayGst');
    const displayGrand = document.getElementById('displayGrand');

    if (displayBasic) displayBasic.textContent = '₹' + totalBasic.toFixed(2);
    if (displayGst) displayGst.textContent = '₹' + totalGst.toFixed(2);
    if (displayGrand) displayGrand.textContent = '₹' + grandTotal.toFixed(2);

    // Update Tax Breakdown Display
    const taxDiv = document.getElementById('taxBreakdown');
    if (taxDiv) {
        taxDiv.style.display = 'block';
        if (currentTaxType === 'intra') {
            const halfGst = totalGst / 2;
            taxDiv.innerHTML = `CGST: ₹${halfGst.toFixed(2)} | SGST: ₹${halfGst.toFixed(2)}`;
        } else {
            taxDiv.innerHTML = `IGST: ₹${totalGst.toFixed(2)}`;
        }
    }

    return {
        basic: totalBasic,
        gst: totalGst,
        grand: grandTotal,
        igst: currentTaxType === 'inter' ? totalGst : 0,
        cgst: currentTaxType === 'intra' ? totalGst / 2 : 0,
        sgst: currentTaxType === 'intra' ? totalGst / 2 : 0
    };
}

// ─── Check Tax Type based on GSTIN ───
function updateTaxType() {
    const gstInput = document.getElementById('custGst');
    if (!gstInput) return;

    const gstin = gstInput.value.trim();
    if (gstin.startsWith('34')) {
        currentTaxType = 'intra';
    } else {
        currentTaxType = 'inter';
    }
    calcTotals();
}

// Auto-trigger tax check on manual entry
(function () {
    const gstInput = document.getElementById('custGst');
    if (gstInput) {
        gstInput.addEventListener('input', updateTaxType);
    }
})();

// ─── Customer Search Logic ───
let searchTimeout = null;

async function searchCustomer(query) {
    const resultsDiv = document.getElementById('custSearchResults');
    if (!resultsDiv) return;

    if (!query || query.length < 2) {
        resultsDiv.style.display = 'none';
        return;
    }

    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/api/customers?q=${encodeURIComponent(query)}`);
            if (!res.ok) {
                console.error('Customer search failed:', res.status);
                return;
            }

            const customers = await res.json();

            resultsDiv.innerHTML = '';
            if (customers.length > 0) {
                customers.forEach(c => {
                    const div = document.createElement('div');
                    div.className = 'dropdown-item';
                    div.textContent = c.name; // Safe: textContent prevents XSS
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
    const fields = {
        'custName': c.name,
        'custId': c.id,
        'custAddr': c.address,
        'custGst': c.gstin,
        'custState': c.state,
    };

    for (const [id, value] of Object.entries(fields)) {
        const el = document.getElementById(id);
        if (el) el.value = value || '';
    }

    const resultsDiv = document.getElementById('custSearchResults');
    if (resultsDiv) resultsDiv.style.display = 'none';

    updateTaxType();
}

// Close dropdown if clicked outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) {
        const results = document.getElementById('custSearchResults');
        if (results) results.style.display = 'none';
    }
});

// ─── Save Quotation ───
async function saveQuotation() {
    // Validation
    const custName = (document.getElementById('custName')?.value || '').trim();
    const custGst = (document.getElementById('custGst')?.value || '').trim();
    const custAddr = (document.getElementById('custAddr')?.value || '').trim();
    const custState = (document.getElementById('custState')?.value || '').trim();
    const qDate = (document.getElementById('qDate')?.value || '').trim();

    if (!custName) {
        alert('Please enter the Customer Name.');
        document.getElementById('custName')?.focus();
        return;
    }
    if (!custGst) {
        alert('Please enter the Customer GSTIN.');
        document.getElementById('custGst')?.focus();
        return;
    }
    if (!custAddr) {
        alert('Please enter the Customer Address.');
        document.getElementById('custAddr')?.focus();
        return;
    }
    if (!custState) {
        alert('Please enter the Customer State.');
        document.getElementById('custState')?.focus();
        return;
    }
    if (!qDate) {
        alert('Please select a date.');
        document.getElementById('qDate')?.focus();
        return;
    }

    // Validate items
    const itemRows = document.querySelectorAll('#itemsTable tbody tr');
    if (itemRows.length === 0) {
        alert('Please add at least one item.');
        return;
    }

    const totals = calcTotals();

    const items = [];
    let hasInvalidItem = false;

    itemRows.forEach((tr, index) => {
        const desc = (tr.querySelector('.desc')?.value || '').trim();
        const qty = tr.querySelector('.qty')?.value || 0;
        const rate = tr.querySelector('.rate')?.value || 0;

        if (!desc) {
            hasInvalidItem = true;
            alert(`Please enter a description for item ${index + 1}.`);
            tr.querySelector('.desc')?.focus();
            return;
        }

        items.push({
            description: desc,
            qty: qty,
            rate: rate,
            unit: tr.querySelector('.unit')?.value || 'NOS',
            basic: tr.dataset.basic || 0,
            gst: tr.dataset.gst || 0,
            gst_rate: tr.dataset.gstRate || 0,
            total: tr.dataset.total || 0
        });
    });

    if (hasInvalidItem) return;

    const data = {
        date: qDate,
        place_of_supply: (document.getElementById('placeOfSupply')?.value || '').trim(),
        customer: {
            id: document.getElementById('custId')?.value || '',
            name: custName,
            address: custAddr,
            gstin: custGst,
            state: custState,
        },
        items: items,
        totals: totals
    };

    // Disable button to prevent double-submit
    const saveBtn = document.querySelector('.form-actions .btn-primary');
    let originalBtnText = '';
    if (saveBtn) {
        originalBtnText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        saveBtn.disabled = true;
    }

    try {
        const response = await fetch('/quotation/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        if (result.success) {
            window.location.href = result.redirect_url;
        } else {
            alert('Error saving quotation: ' + (result.error || 'Unknown error'));
            if (saveBtn) {
                saveBtn.innerHTML = originalBtnText;
                saveBtn.disabled = false;
            }
        }
    } catch (e) {
        console.error('Save error:', e);
        alert('Failed to save quotation. Please check your connection and try again.');
        if (saveBtn) {
            saveBtn.innerHTML = originalBtnText;
            saveBtn.disabled = false;
        }
    }
}

// ─── Add Extracted Item Row (from AI extraction) ───
function addExtractedItemRow(item) {
    const tbody = document.querySelector('#itemsTable tbody');
    if (!tbody || !item) return;

    const tr = document.createElement('tr');

    // Safely escape values for attributes
    const desc = (item.description || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    const qty = parseInt(item.qty) || 1;
    const rate = parseFloat(item.rate) || 0;
    const unit = (item.unit || 'NOS').replace(/"/g, '&quot;');
    const gstRate = parseFloat(item.gst_rate) || 18;

    const unitOptions = ['NOS', 'KGS', 'LTS', 'PKTS', 'MTR', 'SET'];
    const gstOptions = [0, 5, 12, 18, 28];

    tr.innerHTML = `
        <td><input type="text" class="desc" placeholder="Item Name" value="${desc}"></td>
        <td><input type="number" class="qty" value="${qty}" min="0" step="1" oninput="calcRow(this)"></td>
        <td><input type="number" class="rate" value="${rate}" min="0" step="0.01" oninput="calcRow(this)"></td>
        <td>
            <select class="unit">
                ${unitOptions.map(u => `<option value="${u}" ${u === unit ? 'selected' : ''}>${u}</option>`).join('')}
            </select>
        </td>
        <td><span class="row-basic">0.00</span></td>
        <td>
             <select class="gst-rate" onchange="calcRow(this)">
                ${gstOptions.map(g => `<option value="${g}" ${g === gstRate ? 'selected' : ''}>${g}%</option>`).join('')}
            </select>
        </td>
        <td><span class="row-total">0.00</span></td>
        <td><button onclick="removeItemRow(this)" class="btn btn-sm btn-danger" title="Remove item">&times;</button></td>
    `;
    tbody.appendChild(tr);
    // Trigger calc
    calcRow(tr.querySelector('.qty'));
}

// ─── Active Nav Highlight ───
function highlightActiveNav() {
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href && currentPath === href) {
            item.classList.add('active');
        } else if (href === '/' && currentPath === '/') {
            item.classList.add('active');
        }
    });
}

// ─── Initialize ───
document.addEventListener('DOMContentLoaded', () => {
    // Setup mobile navigation
    setupMobileNav();

    // Highlight active nav item
    highlightActiveNav();

    // Initialize quotation form if present
    const dateInput = document.getElementById('qDate');
    if (dateInput) {
        // `extracted` is only defined on the create_quotation page
        const hasExtracted = typeof extracted !== 'undefined' && extracted !== null;
        if (!hasExtracted || !extracted.date) {
            dateInput.valueAsDate = new Date();
        }
    }

    // Add initial item row if on quotation page
    const itemsTable = document.getElementById('itemsTable');
    if (itemsTable) {
        const hasExtracted = typeof extracted !== 'undefined' && extracted !== null;
        if (hasExtracted && extracted.items && extracted.items.length > 0) {
            // Clear initial rows
            const tbody = itemsTable.querySelector('tbody');
            if (tbody) tbody.innerHTML = '';
            extracted.items.forEach(item => addExtractedItemRow(item));
        } else {
            addItemRow();
        }
    }

    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-msg');
    flashMessages.forEach(msg => {
        setTimeout(() => {
            msg.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-8px)';
            setTimeout(() => msg.remove(), 500);
        }, 5000);
    });
});
