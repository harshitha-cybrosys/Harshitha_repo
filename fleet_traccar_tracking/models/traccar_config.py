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

import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class TraccarConfig(models.Model):
    """
    Singleton configuration model for Traccar server settings.
    Access via Fleet > Configuration > Traccar Configuration.
    """
    _name = 'fleet.traccar.config'
    _description = 'Traccar Server Configuration'
    _inherit = ['mail.thread']

    name = fields.Char(default='Traccar Configuration', required=True)

    # --- Server ---
    traccar_url = fields.Char(
        string='Traccar Server URL',
        required=True,
        help='e.g. http://traccar.example.com:8082 (no trailing slash)',
        tracking=True,
    )
    traccar_username = fields.Char(string='Username', required=True, tracking=True)
    traccar_password = fields.Char(string='Password', required=True, password=True)

    # --- Map ---
    map_provider = fields.Selection(
        [('osm', 'OpenStreetMap (Free)'), ('google', 'Google Maps')],
        string='Map Provider',
        default='osm',
        required=True,
    )
    google_maps_api_key = fields.Char(string='Google Maps API Key')

    # --- Sync ---
    sync_interval_minutes = fields.Integer(
        string='Sync Interval (minutes)',
        default=2,
        help='How often the cron job polls Traccar for fresh positions.',
    )
    webhook_secret = fields.Char(
        string='Webhook Secret Token',
        help='Optional. Set the same value in Traccar event forwarding header X-Webhook-Token.',
    )

    # --- Status ---
    connection_status = fields.Char(string='Connection Status', readonly=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)

    # ── Singleton enforcement ────────────────────────────────────────────────

    @api.model
    def get_config(self):
        """Return the single config record, creating it if absent."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({
                'name': 'Traccar Configuration',
                'traccar_url': '',
                'traccar_username': '',
                'traccar_password': '',
            })
        return config

    @api.model
    def action_open_config(self):
        """Always open the singleton record — used by the menu item."""
        config = self.get_config()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Traccar Configuration',
            'res_model': 'fleet.traccar.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
        }

    # ── API helpers ──────────────────────────────────────────────────────────

    def _get_auth(self):
        self.ensure_one()
        if not self.traccar_url or not self.traccar_username:
            raise UserError(_('Please configure Traccar URL and credentials first.'))
        return (self.traccar_username, self.traccar_password)

    def _api_get(self, endpoint, params=None, timeout=15):
        """Perform a GET request against the Traccar REST API."""
        self.ensure_one()
        url = self.traccar_url.rstrip('/') + endpoint
        try:
            resp = requests.get(url, auth=self._get_auth(), params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise UserError(_('Cannot reach Traccar server at %s. Check the URL and network.') % self.traccar_url)
        except requests.exceptions.Timeout:
            raise UserError(_('Traccar server timed out.'))
        except requests.exceptions.HTTPError as e:
            raise UserError(_('Traccar API error: %s') % str(e))

    def _api_get_safe(self, endpoint, params=None, timeout=15):
        """Like _api_get but returns None on error (for cron use)."""
        try:
            return self._api_get(endpoint, params=params, timeout=timeout)
        except Exception as e:
            _logger.warning('Traccar API call failed for %s: %s', endpoint, e)
            return None

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_test_connection(self):
        self.ensure_one()
        try:
            data = self._api_get('/api/server')
            self.write({
                'connection_status': '✅ Connected — server v%s' % data.get('version', '?'),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connected to Traccar server successfully!'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except UserError as e:
            self.connection_status = '❌ ' + str(e)
            raise

    def action_sync_devices(self):
        """Import / update all Traccar devices into fleet.traccar.device."""
        self.ensure_one()
        devices = self._api_get('/api/devices')
        device_model = self.env['fleet.traccar.device']
        count = 0
        for d in devices:
            existing = device_model.search([('traccar_id', '=', d['id'])], limit=1)
            vals = {
                'name': d.get('name', ''),
                'traccar_id': d['id'],
                'unique_id': d.get('uniqueId', ''),
                'status': d.get('status', 'offline'),
                'category': d.get('category', ''),
            }
            if existing:
                existing.write(vals)
            else:
                device_model.create(vals)
                count += 1
        self.last_sync = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devices Synced'),
                'message': _('%d new device(s) imported from Traccar.') % count,
                'type': 'success',
                'sticky': False,
            },
        }