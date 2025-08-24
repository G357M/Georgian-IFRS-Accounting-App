from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from georgian_accounting.utils.decorators import permission_required
from .models import Product
from georgian_accounting.database import db

inventory_bp = Blueprint(
    'inventory', 
    __name__, 
    template_folder='templates',
    url_prefix='/inventory'
)

@inventory_bp.route('/')
@login_required
@permission_required('view_inventory')
def index():
    return render_template('inventory_dashboard.html')

@inventory_bp.route('/products')
@login_required
@permission_required('view_inventory')
def list_products():
    products = Product.query.order_by(Product.name).all()
    return render_template('products.html', products=products)

@inventory_bp.route('/product/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_inventory')
def add_product():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        category = request.form.get('category')
        unit_of_measure = request.form.get('unit_of_measure')
        is_vat_exempt = 'is_vat_exempt' in request.form
        is_active = 'is_active' in request.form

        if Product.query.filter_by(code=code).first():
            flash('Product with this code already exists.', 'danger')
        else:
            new_product = Product(
                code=code,
                name=name,
                category=category,
                unit_of_measure=unit_of_measure,
                is_vat_exempt=is_vat_exempt,
                is_active=is_active
            )
            db.session.add(new_product)
            db.session.commit()
            flash('Product added successfully!', 'success')
            return redirect(url_for('inventory.list_products'))
            
    return render_template('product_form.html', action="Add")

@inventory_bp.route('/transactions')
@login_required
@permission_required('view_inventory')
def list_transactions():
    # Will be implemented later
    return "<h1>List of Inventory Transactions</h1>"
