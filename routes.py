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
    try:
        quotations = Quotation.query.order_by(Quotation.date.desc()).all()
        company = Company.query.first()
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        quotations = []
        company = None
    return render_template('dashboard.html', quotations=quotations, company=company)


def number_to_words(num):
    """Convert a number to its Indian English words representation.
    
    Supports values up to crores (Indian numbering system).
    
    Args:
        num: Numeric value to convert (int or float, will be truncated to int)
    
    Returns:
        String representation of the number in words
    """
    try:
        num = int(num)
    except (ValueError, TypeError):
        return "Zero"
    
    if num == 0:
        return "Zero"
    
    if num < 0:
        return "Negative " + number_to_words(abs(num))
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
             "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
            "Eighty", "Ninety"]
    
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
    if not company:
        flash('Company record not found. Please contact admin.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            address = request.form.get('address_line_1', '').strip()
            state = request.form.get('state', '').strip()
            gstin = request.form.get('gstin', '').strip()
            phone = request.form.get('phone', '').strip()
            
            # Validate required fields
            if not name or not address or not state or not gstin:
                flash('Name, Address, State and GSTIN are required.', 'error')
                return render_template('company_settings.html', company=company)
            
            company.name = name
            company.address_line_1 = address
            company.state = state
            company.gstin = gstin
            company.phone = phone
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
            name = request.form.get('name', '').strip()
            address = request.form.get('address', '').strip()
            gstin = request.form.get('gstin', '').strip()
            state = request.form.get('state', '').strip()
            
            if not name:
                flash('Customer name is required.', 'error')
                return redirect(url_for('main.customers'))
            
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
    try:
        query = request.args.get('q', '').strip()
        if query:
            customers = Customer.query.filter(Customer.name.ilike(f'%{query}%')).limit(10).all()
        else:
            customers = Customer.query.limit(20).all()
            
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'address': c.address or '',
            'gstin': c.gstin or '',
            'state': c.state or ''
        } for c in customers])
    except Exception as e:
        logger.error(f"Error searching customers: {e}")
        return jsonify([]), 500


@main_bp.route('/quotation/new', methods=['GET', 'POST'])
def create_quotation():
    company = Company.query.first()
    if request.method == 'POST':
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'Invalid request data'}), 400
            
            # Customer handling
            customer_data = data.get('customer', {})
            cust_id = customer_data.get('id')
            cust_name = customer_data.get('name', '').strip()
            cust_addr = customer_data.get('address', '').strip()
            cust_gst = customer_data.get('gstin', '').strip()
            cust_state = customer_data.get('state', '').strip()
            
            # Validate customer
            if not cust_name:
                return jsonify({'success': False, 'error': 'Customer name is required'}), 400
            
            # If ID provided, update or use existing. If not, create new.
            if cust_id:
                customer = db.session.get(Customer, int(cust_id))
                if not customer:
                    return jsonify({'success': False, 'error': 'Customer not found'}), 404
                customer.name = cust_name
                customer.address = cust_addr
                customer.gstin = cust_gst
                customer.state = cust_state
            else:
                customer = Customer(name=cust_name, address=cust_addr, gstin=cust_gst, state=cust_state)
                db.session.add(customer)
            
            db.session.flush()  # get ID
            
            # Create Quotation
            quotation_number = f"QT-{int(datetime.utcnow().timestamp())}"
            
            # Validate date
            date_str = data.get('date', '')
            if not date_str:
                return jsonify({'success': False, 'error': 'Date is required'}), 400
            
            try:
                q_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
            
            # Tax Logic: determine intra vs inter state
            company_obj = Company.query.first()
            company_gstin_prefix = (company_obj.gstin[:2] if company_obj and company_obj.gstin else '34')
            is_intra_state = (cust_gst and cust_gst[:2] == company_gstin_prefix)
            
            pct_cgst = 9.0 if is_intra_state else 0.0
            pct_sgst = 9.0 if is_intra_state else 0.0
            pct_igst = 18.0 if not is_intra_state else 0.0
            
            totals = data.get('totals', {})
            
            quotation = Quotation(
                quotation_number=quotation_number,
                date=q_date,
                customer_id=customer.id,
                place_of_supply=data.get('place_of_supply', cust_state) or cust_state,
                total_basic=float(totals.get('basic', 0)),
                total_gst=float(totals.get('gst', 0)),
                grand_total=float(totals.get('grand', 0)),
                percentage_cgst=pct_cgst,
                percentage_sgst=pct_sgst,
                percentage_igst=pct_igst,
                total_igst=float(totals.get('igst', 0))
            )
            db.session.add(quotation)
            db.session.flush()
            
            # Add Items
            items = data.get('items', [])
            if not items:
                return jsonify({'success': False, 'error': 'At least one item is required'}), 400
            
            for item in items:
                desc = (item.get('description', '') or '').strip()
                if not desc:
                    continue  # Skip empty items
                
                q_item = QuotationItem(
                    quotation_id=quotation.id,
                    description=desc,
                    qty=int(float(item.get('qty', 0))),
                    rate=float(item.get('rate', 0)),
                    unit=item.get('unit', 'NOS') or 'NOS',
                    gst_rate=float(item.get('gst_rate', 0)),
                    basic_amount=float(item.get('basic', 0)),
                    gst_amount=float(item.get('gst', 0)),
                    total_amount=float(item.get('total', 0))
                )
                db.session.add(q_item)
                
            db.session.commit()
            return jsonify({'success': True, 'redirect_url': url_for('main.view_quotation', id=quotation.id)})
        except ValueError as e:
            logger.error(f"Validation error creating quotation: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Invalid data: {str(e)}'}), 400
        except Exception as e:
            logger.error(f"Error creating quotation: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        
    return render_template('create_quotation.html', company=company)


@main_bp.route('/quotation/<int:id>')
def view_quotation(id):
    quotation = Quotation.query.get_or_404(id)
    company = Company.query.first()
    if not company:
        flash('Company settings not configured.', 'error')
        return redirect(url_for('main.dashboard'))
    
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
        
        name = request.form.get('name', '').strip()
        if not name:
            flash('Customer name is required.', 'error')
            return redirect(url_for('main.customers'))
        
        customer.name = name
        customer.gstin = request.form.get('gstin', '').strip()
        customer.address = request.form.get('address', '').strip()
        customer.state = request.form.get('state', '').strip()
        
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
        
        # Check if customer has existing quotations
        if customer.quotations:
            flash(f'Cannot delete customer "{customer.name}" — they have {len(customer.quotations)} linked quotation(s). Delete those first.', 'error')
            return redirect(url_for('main.customers'))
        
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting customer {id}: {e}")
        db.session.rollback()
        flash('Error deleting customer.', 'error')
    return redirect(url_for('main.customers'))


ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@main_bp.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Only PDF, PNG, JPG, JPEG are allowed.', 'error')
            return redirect(request.url)
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_FILE_SIZE:
            flash('File is too large. Maximum size is 10 MB.', 'error')
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        if not filename:
            flash('Invalid filename.', 'error')
            return redirect(request.url)
        
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            extracted_data = extract_details_from_file(filepath)
            if extracted_data is None:
                flash('Could not extract data from file. Please try a clearer image or PDF.', 'error')
                return redirect(request.url)
            # Render create_quotation with pre-filled data
            company = Company.query.first()
            return render_template('create_quotation.html', company=company, extracted=extracted_data)
        except Exception as e:
            logger.error(f"Error extracting details: {e}")
            flash('Error processing file. Please try again.', 'error')
            return redirect(request.url)
        finally:
            # Clean up uploaded file after processing
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as cleanup_err:
                logger.warning(f"Could not clean up upload file: {cleanup_err}")
    
    return render_template('upload.html')


def allowed_file(filename):
    """Check if uploaded filename has an allowed extension."""
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_details_from_file(filepath):
    """Use Gemini AI to extract invoice/bill details from a file.
    
    Args:
        filepath: Path to the uploaded file (PDF or image)
    
    Returns:
        dict: Extracted data with customer, items, date, place_of_supply
        None: If extraction fails
    """
    logger.info(f"Extracting details from {filepath}")
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    try:
        with open(filepath, 'rb') as f:
            file_data = f.read()
    except IOError as e:
        logger.error(f"Could not read file {filepath}: {e}")
        return None
    
    ext = filepath.lower()
    if ext.endswith('.pdf'):
        mime_type = 'application/pdf'
    elif ext.endswith(('.jpg', '.jpeg')):
        mime_type = 'image/jpeg'
    elif ext.endswith('.png'):
        mime_type = 'image/png'
    else:
        logger.error(f"Unsupported file type: {filepath}")
        return None
    
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
    Return ONLY the JSON object, no extra text.
    """
    
    try:
        response = model.generate_content([prompt] + parts)
        text = response.text.strip()
        logger.info(f"Gemini response: {text[:200]}...")
        
        # Remove markdown code blocks if present
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        
        # Validate the structure minimally
        if not isinstance(data, dict):
            logger.error("Extracted data is not a dictionary")
            return None
        
        logger.info(f"Extracted data keys: {list(data.keys())}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in extraction: {e}")
        return None
