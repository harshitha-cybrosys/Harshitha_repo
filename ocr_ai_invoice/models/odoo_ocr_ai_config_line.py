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

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class OdooOcrAiConfigLine(models.Model):
    """One row in the field-mapping table: AI field title → Odoo field."""
    _name = 'odoo.ocr.ai.config.line'
    _description = 'OCR AI Config Line'

    model_id = fields.Many2one(
        comodel_name='odoo.ocr.ai.config',
        ondelete='cascade',
    )
    title = fields.Char(string='AI Field Title')
    ocr_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Odoo Field',
    )
    ttype = fields.Selection(related='ocr_field_id.ttype', readonly=True)
    ocr_ir_field_ids = fields.Many2many(
        comodel_name='ir.model.fields',
        string='Related Child Fields',
    )
    ocr_ir_field_ids_domain = fields.Char(
        compute='_compute_ocr_ir_field_ids_domain',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    create_if_not_found = fields.Boolean(string='Create Record if Not Found?')

    @api.depends('ocr_field_id')
    def _compute_ocr_ir_field_ids_domain(self):
        for rec in self:
            if rec.ocr_field_id and rec.ocr_field_id.relation:
                related_model = self.env['ir.model'].search(
                    [('model', '=', rec.ocr_field_id.relation)], limit=1)
                rec.ocr_ir_field_ids_domain = str([
                    ('model_id', '=', related_model.id),
                    ('ttype', 'in', [
                        'char', 'date', 'integer', 'selection', 'monetary',
                        'float', 'one2many', 'text', 'many2many', 'many2one',
                    ]),
                ])
            else:
                rec.ocr_ir_field_ids_domain = str([('model_id', '=', False)])

    @api.constrains('ocr_field_id', 'ocr_ir_field_ids')
    def _check_relational_child_fields(self):
        """
        Child fields are required only for one2many (line items).
        many2one fields like currency_id or partner_id are matched by a simple
        string value and do NOT require child fields.
        """
        for rec in self:
            if rec.ocr_field_id.ttype == 'one2many' and not rec.ocr_ir_field_ids:
                raise ValidationError(_(
                    'For One2many fields, "Related Child Fields" is mandatory. '
                    'Please update the field mapping for "%s".'
                ) % rec.title)

    @api.constrains('ocr_field_id', 'model_id')
    def _check_field_uniqueness_within_config(self):
        for rec in self:
            if rec.ocr_field_id and rec.model_id:
                duplicate = self.search_count([
                    ('ocr_field_id', '=', rec.ocr_field_id.id),
                    ('model_id', '=', rec.model_id.id),
                    ('id', '!=', rec.id),
                ])
                if duplicate:
                    raise ValidationError(_(
                        'The field "%s" is already mapped in another line of this configuration.'
                    ) % rec.ocr_field_id.field_description)