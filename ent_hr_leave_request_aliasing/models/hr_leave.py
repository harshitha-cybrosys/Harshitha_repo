# -*- coding: utf-8 -*-
################################################################################
#
#    A part of OpenHRMS Project <https://www.openhrms.com>
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0
#    (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the
#    Software or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
#    USE OR OTHER DEALINGS IN THE SOFTWARE.
#
################################################################################

import re
from datetime import datetime
from odoo import api, models
from odoo.tools import email_split


class HrLeave(models.Model):
    """Inherited hr leave to inherit the message_new function"""
    _inherit = 'hr.leave'

    def _get_leave_type_from_subject(self, subject, employee):
        """Try to match a leave type name from the email subject.
        Falls back to first available no-allocation type if no match found."""
        all_leave_types = self.env['hr.leave.type'].search([
            ('company_id', 'in', [employee.company_id.id, False])
        ])
        subject_lower = subject.lower()
        for leave_type in all_leave_types:
            if leave_type.name.lower() in subject_lower:
                return leave_type
        leave_type = all_leave_types.filtered(
            lambda l: l.requires_allocation == 'no_validation')[:1]
        if not leave_type:
            leave_type = all_leave_types.filtered(
                lambda l: l.requires_allocation == 'no')[:1]
        if not leave_type:
            leave_type = all_leave_types[:1]
        return leave_type

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """This function extracts required fields of hr.leave from incoming
        mail then creating records"""
        if custom_values is None:
            custom_values = {}
        msg_subject = msg_dict.get('subject', '')
        mail_from = msg_dict.get('email_from', '')
        msg_id = msg_dict.get('message_id', '')

        alias_prefix = self.env['ir.config_parameter'].sudo().get_param(
            'ent_hr_leave_request_aliasing.alias_prefix')
        alias_domain = self.env['ir.config_parameter'].sudo().get_param(
            'ent_hr_leave_request_aliasing.alias_domain')

        subject_match = re.search(
            alias_prefix, msg_subject, re.IGNORECASE) if alias_prefix else None
        domain_match = re.search(
            re.escape(alias_domain), mail_from, re.IGNORECASE) if alias_domain else None

        if subject_match and domain_match:
            if msg_id:
                existing = self.env['hr.leave'].sudo().search(
                    [('name', '=', msg_subject.strip())], limit=1)
                if existing:
                    return existing

            email_address = email_split(msg_dict.get('email_from', False))[0]
            employee = self.env['hr.employee'].sudo().search(
                ['|', ('work_email', 'ilike', email_address),
                 ('user_id.email', 'ilike', email_address)], limit=1)

            if not employee:
                return super().message_new(msg_dict, custom_values)

            msg_body = msg_dict.get('body', '')
            clean_body = re.sub(r'<br\s*/?>', ' ', msg_body, flags=re.IGNORECASE)
            clean_body = re.sub(r'<[^>]+>', ' ', clean_body)
            clean_body = clean_body.replace('&nbsp;', ' ').replace('&amp;', '&')

            date_list = re.findall(r'\d{2}/\d{2}/\d{4}', clean_body)

            if date_list:
                start_date = datetime.strptime(date_list[0], '%d/%m/%Y').date()
                date_to = datetime.strptime(
                    date_list[1], '%d/%m/%Y').date() if len(date_list) > 1 else start_date

                leave_type = self._get_leave_type_from_subject(msg_subject, employee)

                if leave_type:
                    return self.sudo().create({
                        'name': msg_subject.strip(),
                        'employee_id': employee.id,
                        'holiday_status_id': leave_type.id,
                        'request_date_from': start_date,
                        'request_date_to': date_to,
                    })

        return super().message_new(msg_dict, custom_values)