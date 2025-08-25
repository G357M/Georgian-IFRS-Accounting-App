from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .models import Product
from georgian_accounting.database import db
from georgian_accounting.utils.decorators import permission_required
from .forms import ProductForm, DeleteForm 

inventory_bp = Blueprint(
    'inventory', 
    __name__, 
    template_folder='templates',
    url_prefix='/inventory'
)

@inventory_bp.route('/')
@login_required
@permission_required('view_inventory')
def dashboard():
    return render_template('inventory_dashboard.html')

@inventory_bp.route('/products')
@login_required
@permission_required('view_inventory')
def list_products():
    products = Product.query.order_by(Product.name).all()
    delete_form = DeleteForm()  # For CSRF protection on delete buttons
    return render_template('products.html', products=products, delete_form=delete_form)

@inventory_bp.route('/product/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_inventory')
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        new_product = Product()
        form.populate_obj(new_product)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('inventory.list_products'))
    return render_template('product_form.html', form=form, action="Add")

@inventory_bp.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@permission_required('manage_inventory')
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product, original_code=product.code)
    if form.validate_on_submit():
        form.populate_obj(product)
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('inventory.list_products'))
    return render_template('product_form.html', form=form, action="Edit")

@inventory_bp.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
@permission_required('manage_inventory')
def delete_product(product_id):
    form = DeleteForm()
    if form.validate_on_submit(): # This validates the CSRF token
        product = Product.query.get_or_404(product_id)
        try:
            db.session.delete(product)
            db.session.commit()
            flash('Product deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting product. It might be in use in transactions. Error: {e}', 'danger')
    else:
        flash('Invalid request. Could not delete product.', 'danger')
    return redirect(url_for('inventory.list_products'))

@inventory_bp.route('/transactions')
@login_required
@permission_required('view_inventory')
def list_transactions():
    # Will be implemented later
    return "<h1>List of Inventory Transactions</h1>"
