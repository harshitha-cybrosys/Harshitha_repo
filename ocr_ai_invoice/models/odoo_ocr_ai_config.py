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
    create_products_if_not_found = fields.Boolean(string='Create Products if Not Found?')
    create_products_if_not_found_invisible = fields.Boolean(
        compute='_compute_product_invisible',
        store=False,
    )

    @api.depends('model_id')
    def _compute_product_invisible(self):
        for rec in self:
            rec.create_products_if_not_found_invisible = (
                rec.model_id.model in ['hr.expense', 'stock.picking']
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
        if not self.model_id:
            return
        if self.model_id.model == 'hr.expense':
            self.model_ids = [(5, 0, 0)]
            mf = self.env['ir.model.fields'].sudo()
            desc_f  = mf.search([('model', '=', 'hr.expense'), ('name', '=', 'name')], limit=1)
            emp_f   = mf.search([('model', '=', 'hr.expense'), ('name', '=', 'employee_id')], limit=1)
            total_f = mf.search([('model', '=', 'hr.expense'), ('name', '=', 'total_amount_currency')], limit=1)
            date_f  = mf.search([('model', '=', 'hr.expense'), ('name', '=', 'date')], limit=1)
            rel_name  = mf.search([('model', '=', 'hr.employee'), ('name', '=', 'name')], limit=1)
            rel_email = mf.search([('model', '=', 'hr.employee'), ('name', '=', 'work_email')], limit=1)
            rel_phone = mf.search([('model', '=', 'hr.employee'), ('name', '=', 'work_phone')], limit=1)
            lines = []
            if desc_f:
                lines.append((0, 0, {'title': 'Expense Title', 'ocr_field_id': desc_f.id}))
            if emp_f:
                related = [f.id for f in [rel_name, rel_email, rel_phone] if f]
                lines.append((0, 0, {
                    'title': 'Employee',
                    'ocr_field_id': emp_f.id,
                    'create_if_not_found': False,
                    'ocr_ir_field_ids': [(6, 0, related)],
                }))
            if total_f:
                lines.append((0, 0, {'title': 'Expense Total', 'ocr_field_id': total_f.id}))
            if date_f:
                lines.append((0, 0, {'title': 'Expense Date', 'ocr_field_id': date_f.id}))
            self.model_ids = lines
        elif self._origin and self.model_id != self._origin.model_id:
            self.model_ids = [(5, 0, 0)]
