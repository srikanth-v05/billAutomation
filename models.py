from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address_line_1 = db.Column(db.String(200), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    gstin = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            'name': self.name,
            'address_line_1': self.address_line_1,
            'state': self.state,
            'gstin': self.gstin,
            'phone': self.phone,
        }


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    gstin = db.Column(db.String(20), nullable=True)
    state = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'gstin': self.gstin,
            'state': self.state,
        }


class Quotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(20), unique=True, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    customer = db.relationship('Customer', backref=db.backref('quotations', lazy=True))

    place_of_supply = db.Column(db.String(100), nullable=True)

    total_basic = db.Column(db.Float, default=0.0)
    total_gst = db.Column(db.Float, default=0.0)
    grand_total = db.Column(db.Float, default=0.0)
    percentage_cgst = db.Column(db.Float, default=9.0)
    percentage_sgst = db.Column(db.Float, default=9.0)
    total_igst = db.Column(db.Float, default=0.0)
    percentage_igst = db.Column(db.Float, default=18.0)

    items = db.relationship(
        'QuotationItem', backref='quotation', lazy=True, cascade='all, delete-orphan'
    )


class QuotationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotation.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(10), default='NOS')
    gst_rate = db.Column(db.Float, default=18.0)
    basic_amount = db.Column(db.Float, nullable=False)
    gst_amount = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)


class Invoice(db.Model):
    __tablename__ = 'invoice'
    id = db.Column(db.Integer, primary_key=True)

    # Invoice number as string (e.g. "24-25/001") and integer for ordering/gap detection
    invoice_number = db.Column(db.String(30), unique=True, nullable=False)
    invoice_number_int = db.Column(db.Integer, nullable=False)
    financial_year = db.Column(db.String(10), nullable=False)  # e.g. "24-25"

    date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    customer = db.relationship('Customer', backref=db.backref('invoices', lazy=True))

    # Optional link back to the source quotation
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotation.id'), nullable=True)
    quotation = db.relationship(
        'Quotation', backref=db.backref('invoice', uselist=False, lazy=True)
    )

    place_of_supply = db.Column(db.String(100), nullable=True)
    is_intra_state = db.Column(db.Boolean, default=True)

    # Financial totals
    total_basic = db.Column(db.Float, default=0.0)
    total_cgst = db.Column(db.Float, default=0.0)
    total_sgst = db.Column(db.Float, default=0.0)
    total_igst = db.Column(db.Float, default=0.0)
    total_gst = db.Column(db.Float, default=0.0)
    grand_total = db.Column(db.Float, default=0.0)

    # Tax rates applied
    percentage_cgst = db.Column(db.Float, default=9.0)
    percentage_sgst = db.Column(db.Float, default=9.0)
    percentage_igst = db.Column(db.Float, default=0.0)

    items = db.relationship(
        'InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan'
    )


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_item'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)

    description = db.Column(db.String(255), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(10), default='NOS')
    gst_rate = db.Column(db.Float, default=18.0)

    basic_amount = db.Column(db.Float, nullable=False)
    cgst_amount = db.Column(db.Float, default=0.0)
    sgst_amount = db.Column(db.Float, default=0.0)
    igst_amount = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
