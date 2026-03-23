# -*- coding: utf-8 -*-
from odoo import api, models


class OcrAiInvoice(models.Model):
    """
    Extends account.move (Invoice / Vendor Bill) with OCR AI fields
    and the one-click OCR import capability.
    """
    _name = 'account.move'
    _inherit = ['account.move', 'odoo.ocr.ai.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        """Link the OCR attachment to the newly created invoice/bill record."""
        records = super().create(vals_list)
        for record in records:
            if record.is_created_ocr and record.ocr_attachment_id:
                record.ocr_attachment_id.sudo().write({
                    'res_id': record.id,
                    'res_model': self._name,
                })
        return records

    @api.model
    def check_active_boolean_invoice(self, active_model, default_move_type=None):
        """
        Called by the JS button to check whether an active OCR config
        exists for this model before opening the upload wizard.

        :param active_model:      e.g. 'account.move'
        :param default_move_type: e.g. 'in_invoice' or 'out_invoice'
        :return: {'active': True/False, 'record_id': <config id>}
        """
        config = self.env['odoo.ocr.ai.config'].search([
            ('active', '=', True),
            ('model_id.model', '=', active_model),
        ], limit=1)

        if config:
            return {'active': True, 'record_id': config.id}
        return {'active': False}