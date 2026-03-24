# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Harshitha AP (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

{
    'name': 'Odoo OCR Using AI - Invoices, Bills, Purchase & Sale Orders',
    'version': '19.0.1.0.0',
    'summary': """
        AI-powered OCR for Odoo. Upload a PDF or image document, let AI extract
        all fields, and create a draft Vendor Bill, Customer Invoice, Purchase Order,
        or Sale Order in one click. Works on Community & Enterprise.
    """,
    'description': """
        Integrates with the fynix.ai OCR service to extract and digitise
        document data automatically. Supports invoices, vendor bills,
        purchase orders and sale orders.
    """,
    'category': 'Accounting',
    'sequence': 10,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['base', 'account', 'mail', 'purchase', 'sale_management', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ocr_model_data.xml',
        'wizards/import_via_ocr_wizard_view.xml',
        'views/odoo_ocr_ai_config_views.xml',
        'views/odoo_ocr_api_config_view.xml',
        'views/account_move_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
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