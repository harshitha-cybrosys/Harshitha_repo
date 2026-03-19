# -*- coding: utf-8 -*-
from odoo import models, fields


class IrModel(models.Model):
    """Extension of ir.model to mark OCR-enabled models."""
    _inherit = 'ir.model'

    is_ocr_tus = fields.Boolean(string="Is OCR Enabled", default=False)