# -*- coding: utf-8 -*-
from odoo import models, fields


class OdooOcrAiMixin(models.AbstractModel):
    """Abstract mixin that adds OCR tracking fields to any model."""
    _name = 'odoo.ocr.ai.mixin'
    _description = 'Odoo OCR AI Mixin'

    is_created_ocr = fields.Boolean(
        string='Created via OCR?',
        default=False,
    )
    ocr_response_text = fields.Text(string='OCR Response')
    # ocr_uploaded_file removed — unused; file is tracked via ocr_attachment_id
    ocr_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        readonly=True,
        string='OCR Attachment',
    )