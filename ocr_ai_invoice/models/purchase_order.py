# -*- coding: utf-8 -*-
from odoo import api, models


class OcrAiPurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'odoo.ocr.ai.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.is_created_ocr and record.ocr_attachment_id:
                record.ocr_attachment_id.sudo().write({
                    'res_id': record.id,
                    'res_model': self._name,
                })
        return records

    @api.model
    def check_active_ocr_config(self, active_model, *args):
        config = self.env['odoo.ocr.ai.config'].search([
            ('active', '=', True),
            ('model_id.model', '=', active_model),
        ], limit=1)
        if config:
            return {'active': True, 'record_id': config.id}
        return {'active': False}