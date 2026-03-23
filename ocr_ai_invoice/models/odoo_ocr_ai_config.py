# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class OdooOcrAiConfig(models.Model):
    _name = 'odoo.ocr.ai.config'
    _description = 'OCR AI Configuration'
    _rec_name = 'model_id'

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Model',
        domain=[('is_ocr_tus', '=', True)],
    )
    model_ids = fields.One2many(
        comodel_name='odoo.ocr.ai.config.line',
        inverse_name='model_id',
        string='Field Mapping',
    )
    active = fields.Boolean(string='Active', default=True)
    create_products_if_not_found = fields.Boolean(
        string='Create Products if Not Found?',
        help='Auto-create products in Odoo when they are not found during line-item mapping.',
    )

    @api.constrains('model_id', 'active')
    def _check_unique_active_model(self):
        for rec in self:
            if rec.active and rec.model_id:
                if self.search_count([
                    ('model_id', '=', rec.model_id.id),
                    ('active', '=', True),
                    ('id', '!=', rec.id),
                ]):
                    raise ValidationError(_(
                        'An active OCR configuration for model "%s" already exists.'
                    ) % rec.model_id.name)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Clear field mapping lines when the model changes."""
        if self._origin and self.model_id != self._origin.model_id:
            self.model_ids = [(5, 0, 0)]