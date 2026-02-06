from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, jsonify
import pymysql
pymysql.install_as_MySQLdb()
from config import Config
from models import db, Company, Customer, Quotation, QuotationItem
from routes import main_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # Register Blueprint
    app.register_blueprint(main_bp)

    with app.app_context():
        # Create database tables for our data models
        db.create_all()
        
        # Ensure at least one company record exists
        if not Company.query.first():
            # Create a placeholder company
            default_company = Company(
                name="SRI VASAVI AGENCIES",
                address_line_1="No.54, West Car Street, Villianur, Puducherry-605 110.",
                state="Puducherry",
                gstin="34AGLPV5711E1ZC",
                phone="99436 77409"
            )
            db.session.add(default_company)
            db.session.commit()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True,host="0.0.0.0")
