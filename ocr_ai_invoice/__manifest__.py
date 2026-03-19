# -*- coding: utf-8 -*-
{
    'name': 'Odoo OCR Using AI - Invoices & Bills',
    'version': '19.0.1.0.0',
    'summary': """
        AI-powered OCR for Odoo Invoices & Bills.
        Upload a PDF or image invoice, let AI extract all fields,
        and create a draft Customer Invoice or Vendor Bill in one click.
        Supports multi-layout invoices. Works on Community & Enterprise.
    """,
    'description': """
        Leverage the power of AI and OCR in Odoo to automate invoice processing.
        This standalone module (no extra base module required) integrates with
        the fynix.ai OCR service to extract and digitise invoice data automatically.
    """,
    'category': 'Accounting',
    'sequence': 10,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ocr_model_data.xml',
        'wizards/import_via_ocr_wizard_view.xml',
        'views/odoo_ocr_ai_config_views.xml',
        'views/odoo_ocr_api_config_view.xml',
        'views/account_move_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ocr_ai_invoice/static/src/xml/**/*',
            'ocr_ai_invoice/static/src/js/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}