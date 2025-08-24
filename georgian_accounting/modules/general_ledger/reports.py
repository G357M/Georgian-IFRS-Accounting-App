from datetime import datetime
from decimal import Decimal

def generate_balance_sheet(company, period_start, period_end):
    """
    Placeholder function to generate a Balance Sheet.
    In a real application, this would query GL accounts and transactions.
    """
    # Dummy data for demonstration
    assets = {
        'Current Assets': {
            'Cash': Decimal('15000.00'),
            'Accounts Receivable': Decimal('10000.00'),
            'Inventory': Decimal('5000.00')
        },
        'Non-Current Assets': {
            'Property, Plant & Equipment': Decimal('50000.00')
        }
    }
    liabilities = {
        'Current Liabilities': {
            'Accounts Payable': Decimal('8000.00'),
            'Short-term Loans': Decimal('2000.00')
        },
        'Non-Current Liabilities': {
            'Long-term Loans': Decimal('15000.00')
        }
    }
    equity = {
        'Share Capital': Decimal('30000.00'),
        'Retained Earnings': Decimal('25000.00')
    }

    total_assets = sum(sum(cat.values()) for cat in assets.values())
    total_liabilities = sum(sum(cat.values()) for cat in liabilities.values())
    total_equity = sum(equity.values())

    return {
        'company': company.name,
        'period_start': period_start,
        'period_end': period_end,
        'assets': assets,
        'total_assets': total_assets,
        'liabilities': liabilities,
        'total_liabilities': total_liabilities,
        'equity': equity,
        'total_equity': total_equity,
        'balance_check': total_assets == (total_liabilities + total_equity)
    }

def generate_income_statement(company, period_start, period_end):
    """
    Placeholder function to generate an Income Statement.
    In a real application, this would query GL accounts and transactions.
    """
    # Dummy data for demonstration
    revenue = {
        'Sales Revenue': Decimal('100000.00'),
        'Other Income': Decimal('2000.00')
    }
    expenses = {
        'Cost of Goods Sold': Decimal('60000.00'),
        'Operating Expenses': Decimal('15000.00'),
        'Administrative Expenses': Decimal('5000.00')
    }

    total_revenue = sum(revenue.values())
    total_expenses = sum(expenses.values())
    net_income = total_revenue - total_expenses

    return {
        'company': company.name,
        'period_start': period_start,
        'period_end': period_end,
        'revenue': revenue,
        'total_revenue': total_revenue,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'net_income': net_income
    }
