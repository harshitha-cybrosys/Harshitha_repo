# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
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

from odoo import models, fields

class TraccarDevice(models.Model):
    """
    Mirrors a device registered in the Traccar server.
    Linked to fleet.vehicle via fleet_vehicle.traccar_device_id.
    """
    _name = 'fleet.traccar.device'
    _description = 'Traccar Device'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Device Name', required=True)
    traccar_id = fields.Integer(string='Traccar Server ID', readonly=True, index=True)
    unique_id = fields.Char(string='Unique Identifier (IMEI/custom)', index=True)
    status = fields.Char(string='Status')
    category = fields.Char(string='Category')

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Linked Vehicle',
        ondelete='set null',
    )

    position_count = fields.Integer(
        compute='_compute_position_count',
        string='Positions',
    )

    def _compute_position_count(self):
        Position = self.env['fleet.traccar.position']
        for rec in self:
            rec.position_count = Position.search_count([('device_id', '=', rec.id)])

    def action_view_positions(self):
        return {
            'name': 'Positions',
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.traccar.position',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
        }