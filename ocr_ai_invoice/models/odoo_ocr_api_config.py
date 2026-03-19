# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError


class OdooOcrApiConfig(models.Model):
    """Stores the fynix.ai OCR API credentials per company."""
    _name = 'odoo.ocr.api.config'
    _description = 'OCR API Configuration'

    server_url = fields.Char(
        string='Server URL',
        required=True,
        default='https://ai.fynix.app/tus_ocr_api',
        help='Must be exactly: https://ai.fynix.app/tus_ocr_api',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    api_key = fields.Char(
        string='Authentication Token',
        required=True,
        help='Token obtained from https://ai.fynix.app after registration.',
    )
    date_format = fields.Char(
        string='Date Format',
        required=True,
        default='%d-%m-%y',
        help='Python strptime format used to parse dates from OCR results.',
    )

    @api.constrains('company_id')
    def _check_unique_company(self):
        for rec in self:
            duplicate = self.search([
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Only one OCR API configuration is allowed per company.'
                ))

    def action_test_connection(self):
        """Open the fynix.ai portal in a new browser tab."""
        if not self.server_url:
            raise UserError(_('Please enter a valid Server URL.'))
        portal_url = self.server_url.replace('/tus_ocr_api', '')
        return {
            'type': 'ir.actions.act_url',
            'url': portal_url,
            'target': 'new',
        }