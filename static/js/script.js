// Mobile Navigation
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    if (sidebar && overlay) {
        sidebar.classList.toggle('active');
        overlay.classList.toggle('active');
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

// Tax Logic
let currentTaxType = 'inter'; // 'intra' (CGST+SGST) or 'inter' (IGST)


function addItemRow() {
    const tbody = document.querySelector('#itemsTable tbody');
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="desc" placeholder="Item Name"></td>
        <td><input type="number" class="qty" value="1" oninput="calcRow(this)"></td>
        <td><input type="number" class="rate" value="0" oninput="calcRow(this)"></td>
        <td>
            <select class="unit">
                <option value="NOS">NOS</option>
                <option value="KGS">KGS</option>
                <option value="LTS">LTS</option>
                <option value="PKTS">PKTS</option>
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
        <td><button onclick="this.closest('tr').remove(); calcTotals()" class="btn-sm btn-danger">&times;</button></td>
    `;
    tbody.appendChild(tr);
}

function calcRow(input) {
    const tr = input.closest('tr');
    const qty = parseFloat(tr.querySelector('.qty').value) || 0;
    const rate = parseFloat(tr.querySelector('.rate').value) || 0;
    const gstRate = parseFloat(tr.querySelector('.gst-rate').value) || 0;

    const basic = qty * rate;
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

    document.getElementById('displayBasic').textContent = totalBasic.toFixed(2);
    document.getElementById('displayGst').textContent = totalGst.toFixed(2);
    document.getElementById('displayGrand').textContent = grandTotal.toFixed(2);

    // Update Tax Breakdown Display
    const taxDiv = document.getElementById('taxBreakdown');
    if (taxDiv) {
        taxDiv.style.display = 'block';
        if (currentTaxType === 'intra') {
            const halfGst = totalGst / 2;
            taxDiv.innerHTML = `CGST: ${halfGst.toFixed(2)} | SGST: ${halfGst.toFixed(2)}`;
        } else {
            taxDiv.innerHTML = `IGST: ${totalGst.toFixed(2)}`;
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

// Check Tax Type based on GSTIN
function updateTaxType() {
    const gstin = document.getElementById('custGst').value || '';
    if (gstin.startsWith('34')) {
        currentTaxType = 'intra';
    } else {
        currentTaxType = 'inter';
    }
    calcTotals();
}

// Auto-trigger tax check on manual entry
if (document.getElementById('custGst')) {
    document.getElementById('custGst').addEventListener('input', updateTaxType);
}


// Customer Search Logic
let searchTimeout = null;
async function searchCustomer(query) {
    const resultsDiv = document.getElementById('custSearchResults');
    if (!query || query.length < 2) {
        resultsDiv.style.display = 'none';
        return;
    }

    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/api/customers?q=${encodeURIComponent(query)}`);
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
            console.error(e);
        }
    }, 300);
}

function selectCustomer(c) {
    document.getElementById('custName').value = c.name;
    document.getElementById('custId').value = c.id;
    document.getElementById('custAddr').value = c.address || '';
    document.getElementById('custGst').value = c.gstin || '';
    document.getElementById('custState').value = c.state || '';

    document.getElementById('custSearchResults').style.display = 'none';

    updateTaxType();
}

// Close dropdown if clicked outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) {
        const results = document.getElementById('custSearchResults');
        if (results) results.style.display = 'none';
    }
});


async function saveQuotation() {
    // Validation
    const custName = document.getElementById('custName').value.trim();
    const custGst = document.getElementById('custGst').value.trim();
    const custAddr = document.getElementById('custAddr').value.trim();
    const custState = document.getElementById('custState').value.trim();

    if (!custName || !custGst || !custAddr || !custState) {
        alert("Please fill in all Customer Details (Name, GSTIN, Address, State).");
        return;
    }

    const totals = calcTotals();

    const items = [];
    document.querySelectorAll('#itemsTable tbody tr').forEach(tr => {
        items.push({
            description: tr.querySelector('.desc').value,
            qty: tr.querySelector('.qty').value,
            rate: tr.querySelector('.rate').value,
            unit: tr.querySelector('.unit').value,
            basic: tr.dataset.basic || 0,
            gst: tr.dataset.gst || 0,
            gst_rate: tr.dataset.gstRate || 0,
            total: tr.dataset.total || 0
        });
    });

    const data = {
        date: document.getElementById('qDate').value,
        place_of_supply: document.getElementById('placeOfSupply').value,
        customer: {
            id: document.getElementById('custId').value,
            name: document.getElementById('custName').value,
            address: document.getElementById('custAddr').value,
            gstin: document.getElementById('custGst').value,
            state: document.getElementById('custState').value,
        },
        items: items,
        totals: totals
    };

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
            alert('Error saving quotation');
        }
    } catch (e) {
        console.error(e);
        alert('Failed to save');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Setup mobile navigation
    setupMobileNav();

    // Initialize quotation form if present
    if (document.getElementById('qDate')) {
        document.getElementById('qDate').valueAsDate = new Date();
    }

    // Add initial item row if on quotation page
    if (document.getElementById('itemsTable')) {
        addItemRow();
    }
});
