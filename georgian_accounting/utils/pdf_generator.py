import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def generate_invoice_pdf(invoice):
    """Generates a PDF for a given invoice object."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(f"Invoice #{invoice.invoice_number}", styles['h1']))
    story.append(Spacer(1, 12))

    # Invoice Info
    party_type = "Customer" if invoice.customer else "Vendor"
    party_name = invoice.customer.name if invoice.customer else invoice.vendor.name
    info_data = [
        ['Invoice Date:', invoice.date.strftime('%Y-%m-%d')],
        [f'{party_type}:', party_name],
        ['Status:', invoice.status.title()],
    ]
    info_table = Table(info_data, hAlign='LEFT')
    story.append(info_table)
    story.append(Spacer(1, 24))

    # Items Table
    items_header = ['Description', 'Quantity', 'Unit Price', 'VAT', 'Total']
    items_data = [items_header]
    for item in invoice.items:
        total_item_price = item.net_amount + item.vat_amount
        items_data.append([
            item.description,
            str(item.quantity),
            f"{item.unit_price:.2f}",
            f"{item.vat_amount:.2f} ({item.vat_rate*100:.0f}%)",
            f"{total_item_price:.2f}"
        ])
    
    items_table = Table(items_data)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(items_table)
    story.append(Spacer(1, 24))

    # Totals
    totals_data = [
        ['Net Total:', f'{invoice.total_net:.2f} {invoice.currency}'],
        ['VAT Total:', f'{invoice.total_vat:.2f} {invoice.currency}'],
        ['Gross Total:', f'{invoice.total_gross:.2f} {invoice.currency}'],
    ]
    totals_table = Table(totals_data, hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(totals_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
