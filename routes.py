from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, current_app
from models import db, Company, Customer, Quotation, QuotationItem
from datetime import datetime
import logging
import google.generativeai as genai
from config import Config
import os
from werkzeug.utils import secure_filename
import json

logger = logging.getLogger(__name__)
genai.configure(api_key=Config.GEMINI_API_KEY)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    quotations = Quotation.query.order_by(Quotation.date.desc()).all()
    company = Company.query.first()
    return render_template('dashboard.html', quotations=quotations, company=company)

def number_to_words(num):
    num = int(num)
    if num == 0:
        return "Zero"
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert_chunk(n):
        if n < 20:
            return units[n]
        elif n < 100:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        elif n < 1000:
            return units[n // 100] + " Hundred" + (" and " + convert_chunk(n % 100) if n % 100 != 0 else "")
        return ""

    parts = []
    
    # Crores
    if num >= 10000000:
        crores = num // 10000000
        parts.append(convert_chunk(crores) + " Crore")
        num %= 10000000
    
    # Lakhs
    if num >= 100000:
        lakhs = num // 100000
        parts.append(convert_chunk(lakhs) + " Lakh")
        num %= 100000
        
    # Thousands
    if num >= 1000:
        thousands = num // 1000
        parts.append(convert_chunk(thousands) + " Thousand")
        num %= 1000
        
    # Remaining
    if num > 0:
        parts.append(convert_chunk(num))
        
    return " ".join(parts)


@main_bp.route('/company', methods=['GET', 'POST'])
def company_settings():
    company = Company.query.first()
    if request.method == 'POST':
        try:
            company.name = request.form.get('name')
            company.address_line_1 = request.form.get('address_line_1')
            company.state = request.form.get('state')
            company.gstin = request.form.get('gstin')
            company.phone = request.form.get('phone')
            db.session.commit()
            flash('Company settings updated successfully.', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.error(f"Error updating company: {e}")
            db.session.rollback()
            flash('Error updating company settings.', 'error')
    return render_template('company_settings.html', company=company)

@main_bp.route('/customers', methods=['GET', 'POST'])
def customers():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            address = request.form.get('address')
            gstin = request.form.get('gstin')
            state = request.form.get('state')
            
            customer = Customer(name=name, address=address, gstin=gstin, state=state)
            db.session.add(customer)
            db.session.commit()
            flash('Customer added successfully.', 'success')
            return redirect(url_for('main.customers'))
        except Exception as e:
            logger.error(f"Error adding customer: {e}")
            db.session.rollback()
            flash('Error adding customer.', 'error')
        
    customers = Customer.query.order_by(Customer.name).all()
    company = Company.query.first()
    return render_template('customers.html', customers=customers, company=company)

@main_bp.route('/api/customers')
def api_customers():
    query = request.args.get('q', '')
    if query:
        customers = Customer.query.filter(Customer.name.ilike(f'%{query}%')).limit(10).all()
    else:
        customers = Customer.query.limit(20).all()
        
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'address': c.address,
        'gstin': c.gstin,
        'state': c.state
    } for c in customers])

@main_bp.route('/quotation/new', methods=['GET', 'POST'])
def create_quotation():
    company = Company.query.first()
    if request.method == 'POST':
        try:
            data = request.json 
            
            # Customer handling
            cust_id = data.get('customer', {}).get('id')
            cust_name = data.get('customer', {}).get('name')
            cust_addr = data.get('customer', {}).get('address')
            cust_gst = data.get('customer', {}).get('gstin')
            cust_state = data.get('customer', {}).get('state')
            
            # If ID provided, update or use existing. If not, create new.
            if cust_id:
                customer = Customer.query.get(cust_id)
                # Optional: update details if they changed?
                # For now, let's assume we trust the ID or just update blindly
                customer.name = cust_name
                customer.address = cust_addr
                customer.gstin = cust_gst
                customer.state = cust_state
            else:
                customer = Customer(name=cust_name, address=cust_addr, gstin=cust_gst, state=cust_state)
                db.session.add(customer)
            
            db.session.flush() # get ID
            
            # Create Quotation
            quotation_number = f"QT-{int(datetime.utcnow().timestamp())}"
            
            # Tax Logic from Backend (Verify/Fallback)
            # However, we expect frontend to send the calculated totals
            # But we should determine the percentage split based on logic to be safe
            is_intra_state = (cust_gst and cust_gst.startswith('34'))
            pct_cgst = 9.0 if is_intra_state else 0.0
            pct_sgst = 9.0 if is_intra_state else 0.0
            pct_igst = 18.0 if not is_intra_state else 0.0
            
            quotation = Quotation(
                quotation_number=quotation_number,
                date=datetime.strptime(data.get('date'), '%Y-%m-%d'),
                customer_id=customer.id,
                place_of_supply=data.get('place_of_supply', cust_state),  # Default to customer state
                total_basic=data.get('totals', {}).get('basic'),
                total_gst=data.get('totals', {}).get('gst'),
                grand_total=data.get('totals', {}).get('grand'),
                percentage_cgst=pct_cgst,
                percentage_sgst=pct_sgst,
                percentage_igst=pct_igst,
                total_igst=data.get('totals', {}).get('igst', 0.0) # We might need to calc this if not sent
            )
            db.session.add(quotation)
            db.session.flush()
            
            # Add Items
            items = data.get('items', [])
            for item in items:
                q_item = QuotationItem(
                    quotation_id=quotation.id,
                    description=item.get('description'),
                    qty=int(item.get('qty', 0)),
                    rate=float(item.get('rate', 0)),
                    unit=item.get('unit', 'NOS'), # Capture unit
                    gst_rate=float(item.get('gst_rate', 0)), # Capture GST Rate
                    basic_amount=float(item.get('basic', 0)),
                    gst_amount=float(item.get('gst', 0)),
                    total_amount=float(item.get('total', 0))
                )
                db.session.add(q_item)
                
            db.session.commit()
            return jsonify({'success': True, 'redirect_url': url_for('main.view_quotation', id=quotation.id)})
        except Exception as e:
            logger.error(f"Error creating quotation: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        
    return render_template('create_quotation.html', company=company)

@main_bp.route('/quotation/<int:id>')
def view_quotation(id):
    quotation = Quotation.query.get_or_404(id)
    company = Company.query.first()
    amount_in_words = number_to_words(round(quotation.grand_total)) + " Only"
    return render_template('view_quotation.html', quotation=quotation, company=company, amount_in_words=amount_in_words)

@main_bp.route('/quotation/delete/<int:id>', methods=['POST'])
def delete_quotation(id):
    try:
        quotation = Quotation.query.get_or_404(id)
        db.session.delete(quotation)
        db.session.commit()
        flash('Quotation deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting quotation {id}: {e}")
        db.session.rollback()
        flash('Error deleting quotation.', 'error')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/customers/edit/<int:id>', methods=['POST'])
def edit_customer(id):
    try:
        customer = Customer.query.get_or_404(id)
        customer.name = request.form.get('name')
        customer.gstin = request.form.get('gstin')
        customer.address = request.form.get('address')
        customer.state = request.form.get('state')
        
        db.session.commit()
        flash('Customer updated successfully.', 'success')
    except Exception as e:
        logger.error(f"Error updating customer {id}: {e}")
        db.session.rollback()
        flash('Error updating customer.', 'error')
    return redirect(url_for('main.customers'))

@main_bp.route('/customers/delete/<int:id>', methods=['POST'])
def delete_customer(id):
    try:
        customer = Customer.query.get_or_404(id)
        # Check if used in quotations? Maybe setup cascade delete or warn
        # For now, standard delete
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting customer {id}: {e}")
        db.session.rollback()
        flash('Error deleting customer.', 'error')
    return redirect(url_for('main.customers'))

@main_bp.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                extracted_data = extract_details_from_file(filepath)
                if extracted_data is None:
                    flash('Error processing file.', 'error')
                    return redirect(request.url)
                # Render create_quotation with pre-filled data
                company = Company.query.first()
                return render_template('create_quotation.html', company=company, extracted=extracted_data)
            except Exception as e:
                logger.error(f"Error extracting details: {e}")
                flash('Error processing file.', 'error')
                return redirect(request.url)
    return render_template('upload.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg'}

def extract_details_from_file(filepath):
    logger.info(f"Extracting details from {filepath}")
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    with open(filepath, 'rb') as f:
        file_data = f.read()
    
    if filepath.endswith('.pdf'):
        mime_type = 'application/pdf'
    elif filepath.endswith(('.jpg', '.jpeg')):
        mime_type = 'image/jpeg'
    else:
        mime_type = 'image/png'
    
    parts = [{'mime_type': mime_type, 'data': file_data}]
    
    prompt = """
    Extract details from this invoice or bill document. Return a JSON object with the following structure:
    {
        "customer": {
            "name": "string",
            "address": "string",
            "gstin": "string",
            "state": "string"
        },
        "items": [
            {
                "description": "string",
                "qty": number,
                "rate": number,
                "unit": "string",
                "gst_rate": number
            }
        ],
        "date": "YYYY-MM-DD",
        "place_of_supply": "string"
    }
    If any field is not available, use null or empty string/array.
    """
    
    try:
        response = model.generate_content([prompt] + parts)
        text = response.text.strip()
        logger.info(f"Gemini response: {text}")
        # Remove markdown code blocks if present
        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        data = json.loads(text)
        logger.info(f"Extracted data: {data}")
        return data
    except Exception as e:
        logger.error(f"Error in extraction: {e}")
        return None
