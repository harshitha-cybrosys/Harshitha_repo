# -*- coding: utf-8 -*-
import base64
import json
import os
import tempfile
import datetime
import requests

from odoo import api, models, fields, _, http
from odoo.exceptions import UserError, ValidationError


class ImportViaOcr(models.TransientModel):
    """
    Wizard: Upload a PDF/image → call fynix.ai OCR API → preview response →
    create a draft Invoice or Vendor Bill with all fields pre-filled.
    """
    _name = 'import.via.ocr'
    _description = 'Import Document via OCR AI'

    # ── File upload ──────────────────────────────────────────────────────────
    file_upload = fields.Binary(string='Upload File')
    file_upload_name = fields.Char(string='File Name')

    # ── OCR response state ───────────────────────────────────────────────────
    ocr_response_received = fields.Boolean(default=False)
    response_text = fields.Text(string='AI Response (JSON)')
    file_previews = fields.Html(string='File Preview')
    status = fields.Boolean(string='API Status')

    # ── Token usage info ─────────────────────────────────────────────────────
    used_token = fields.Integer(string='Tokens Used (This Request)', readonly=True)
    total_purchase_token = fields.Integer(string='Total Purchased Tokens', readonly=True)
    total_used_token = fields.Integer(string='Total Used Tokens', readonly=True)
    total_available_token = fields.Integer(string='Total Available Tokens', readonly=True)

    # ── Linked records ───────────────────────────────────────────────────────
    chatgpt_config_id = fields.Many2one(
        comodel_name='odoo.ocr.ai.config',
        string='OCR AI Configuration',
    )
    ocr_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        readonly=True,
        string='Uploaded Attachment',
    )

    # ── Computed ─────────────────────────────────────────────────────────────
    mime_type = fields.Char(compute='_compute_mime_type', string='MIME Type')

    # Context-carried fields (not shown)
    move_type = fields.Char()
    picking_type_code = fields.Char()

    # ────────────────────────────────────────────────────────────────────────
    # Constraints & onchange
    # ────────────────────────────────────────────────────────────────────────
    @api.constrains('file_upload')
    def _check_file_format(self):
        allowed = ['pdf', 'png', 'jpg', 'jpeg']
        for rec in self:
            if rec.file_upload:
                ext = (rec.file_upload_name or '').rsplit('.', 1)[-1].lower()
                if ext not in allowed:
                    raise ValidationError(
                        _('Only PDF, PNG, JPG, and JPEG files are supported.')
                    )

    @api.onchange('file_upload')
    def _onchange_file_upload(self):
        if self.file_upload:
            self.response_text = False
            self.ocr_response_received = False

    @api.depends('file_upload', 'file_upload_name')
    def _compute_mime_type(self):
        mapping = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
        }
        for rec in self:
            if rec.file_upload and rec.file_upload_name:
                ext = rec.file_upload_name.rsplit('.', 1)[-1].lower()
                rec.mime_type = mapping.get(ext, False)
            else:
                rec.mime_type = False

    # ────────────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────────────
    def _get_date_format(self):
        """Return the date format from user language, falling back to API config."""
        lang = self.env['res.lang'].search([('code', '=', self.env.lang)], limit=1)
        if lang:
            return lang.date_format
        config = self.env['odoo.ocr.api.config'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        return config.date_format if config else '%d-%m-%Y'

    def _get_api_credentials(self):
        """Return (server_url, api_key) from the company OCR config."""
        config = self.env['odoo.ocr.api.config'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            raise UserError(_(
                'No OCR API configuration found for your company.\n'
                'Go to Settings → OCR AI Integration → API Configuration '
                'and add your fynix.ai token.'
            ))
        return config.server_url, config.api_key

    def _build_entities_structure(self, config_lines):
        """
        Convert field-mapping lines into the JSON 'entities' dict that
        the fynix.ai API expects, so it knows what to extract.
        """
        user_lang = self.env['res.lang'].search(
            [('code', '=', self.env.user.lang)], limit=1)

        simple_type_map = {
            'char': 'string',
            'text': 'string',
            'float': 'float',
            'monetary': 'float',
            'integer': 'integer',
            'date': user_lang.date_format if user_lang else '%d-%m-%Y',
            'datetime': user_lang.date_format if user_lang else '%d-%m-%Y',
            'many2one': 'string',
        }

        entities = {}
        for line in config_lines:
            if not line.title or not line.ocr_field_id:
                continue
            ftype = line.ocr_field_id.ttype
            if ftype in ['many2one', 'one2many'] and line.ocr_ir_field_ids:
                nested = {
                    f.name: simple_type_map.get(f.ttype)
                    for f in line.ocr_ir_field_ids
                    if simple_type_map.get(f.ttype)
                }
                entities[line.title] = nested if ftype == 'many2one' else [nested]
            else:
                mapped = simple_type_map.get(ftype)
                if mapped:
                    entities[line.title] = mapped
        return entities

    # ────────────────────────────────────────────────────────────────────────
    # Step 1 — Send file to OCR API
    # ────────────────────────────────────────────────────────────────────────
    def action_send_to_ocr(self):
        """Upload the document to fynix.ai and store the JSON response."""
        if not self.file_upload:
            raise UserError(_('Please upload a PDF or image file first.'))

        # Resolve active config
        active_model = self.env.context.get('active_model', 'account.move')
        config = self.chatgpt_config_id or self.env['odoo.ocr.ai.config'].search([
            ('model_id.model', '=', active_model),
            ('active', '=', True),
        ], limit=1)
        if not config:
            raise UserError(_(
                'No active OCR AI configuration found for model "%s".\n'
                'Go to Settings → OCR AI Integration → Model Configuration.'
            ) % active_model)
        self.chatgpt_config_id = config

        # File size guard (≤ 2 MB)
        file_bytes = base64.b64decode(self.file_upload)
        if len(file_bytes) / 1024 / 1024 > 2:
            raise UserError(_('File must be 2 MB or smaller.'))

        # Write to temp file for multipart upload
        tmp_path = os.path.join(tempfile.gettempdir(), self.file_upload_name or 'ocr_upload')
        with open(tmp_path, 'wb') as fh:
            fh.write(file_bytes)

        # Create (or replace) attachment
        self.env['ir.attachment'].search([('name', '=', self.file_upload_name)]).unlink()
        attachment = self.env['ir.attachment'].sudo().create({
            'name': self.file_upload_name,
            'mimetype': self.mime_type or 'application/pdf',
            'datas': self.file_upload,
            'description': self.file_upload_name,
        })

        server_url, auth_token = self._get_api_credentials()
        entities = self._build_entities_structure(
            config.model_ids.sorted('sequence'))

        payload = {
            'entities': json.dumps(entities),
            'auth_token': auth_token,
            'client_url': http.request.httprequest.host_url,
        }

        try:
            response = requests.post(
                server_url,
                files={'file': open(tmp_path, 'rb')},
                data=payload,
                timeout=60,
            )
            response.raise_for_status()
            res_json = response.json()
        except requests.exceptions.RequestException as exc:
            try:
                msg = response.json().get('message', str(exc))
            except Exception:
                msg = str(exc)
            raise UserError(_('OCR API request failed: %s') % msg)
        except Exception as exc:
            raise UserError(_('Unexpected error during OCR processing: %s') % str(exc))

        # Store response details
        self.ocr_response_received = True
        self.ocr_attachment_id = attachment.id
        self.status = res_json.get('status', False)

        usage = res_json.get('response', {}).get('request_usage', {})
        self.used_token = usage.get('Tokens Used', 0)
        self.total_purchase_token = usage.get('Total Purchase Token', 0)
        self.total_used_token = usage.get('Total Used Token', 0)
        self.total_available_token = usage.get('Total Available Token', 0)

        # Clean up and store response JSON
        res_json.pop('status', None)
        res_json.pop('status_code', None)
        res_json.get('response', {}).pop('request_usage', None)
        self.response_text = json.dumps(res_json, indent=4)

        # Re-open wizard to show result tabs
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import via OCR'),
            'res_model': 'import.via.ocr',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_ocr_attachment_id': attachment.id,
                'default_move_type': self.env.context.get('default_move_type'),
                'default_picking_type_code': self.env.context.get(
                    'restricted_picking_type_code'),
            },
        }

    # ────────────────────────────────────────────────────────────────────────
    # Step 2 — Map response → Odoo record values
    # ────────────────────────────────────────────────────────────────────────
    def action_create_record(self):
        """Parse the OCR JSON, map fields, and open the new draft record."""
        try:
            response_dict = json.loads(self.response_text or '{}')
        except json.JSONDecodeError as exc:
            raise UserError(_('Could not parse OCR response JSON: %s') % str(exc))

        if not response_dict.get('status', True):
            raise UserError(response_dict.get('message', _('OCR API returned an error.')))

        ocr_data = response_dict.get('response', {})
        config = self.env['odoo.ocr.ai.config'].browse(self.chatgpt_config_id.id)
        if not config:
            raise UserError(_('OCR AI configuration not found.'))

        date_fmt = self._get_date_format()

        # Base context values always passed to the new record
        ctx = {
            'default_ocr_response_text': ocr_data,
            'default_is_created_ocr': True,
            'default_ocr_attachment_id': self.ocr_attachment_id.id,
            'default_company_id': self.env.company.id,
        }

        SUPPORTED_TTYPES = [
            'char', 'date', 'datetime', 'integer',
            'monetary', 'many2one', 'one2many',
        ]

        for line in config.model_ids:
            if not line.title or line.ocr_field_id.ttype not in SUPPORTED_TTYPES:
                continue

            raw_value = ocr_data.get(line.title, '')
            if isinstance(raw_value, dict) and 'display_name' in raw_value:
                raw_value = raw_value['display_name']

            value = self._map_field_value(
                line, raw_value, date_fmt, config)

            ctx[f'default_{line.ocr_field_id.name}'] = value

        model_name = config.model_id.model

        # stock.picking needs a picking_type_id
        if model_name == 'stock.picking':
            op_code = (self.picking_type_code
                       or self.env.context.get('restricted_picking_type_code')
                       or 'outgoing')
            pt = self.env['stock.picking.type'].search([
                ('code', '=', op_code),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if pt:
                ctx['default_picking_type_id'] = pt.id

        # account.move needs the move_type (in_invoice / out_invoice)
        if model_name == 'account.move' and 'default_move_type' in self.env.context:
            ctx['default_move_type'] = self.env.context['default_move_type']

        return {
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'form',
            'context': ctx,
            'target': 'current',
        }

    # ────────────────────────────────────────────────────────────────────────
    # Field-value mapping helpers
    # ────────────────────────────────────────────────────────────────────────
    def _map_field_value(self, line, raw_value, date_fmt, config):
        """Dispatch field mapping by ttype."""
        ttype = line.ocr_field_id.ttype

        if ttype == 'char':
            return (raw_value or '').strip()

        elif ttype in ('date', 'datetime'):
            return self._parse_date(raw_value, date_fmt)

        elif ttype == 'integer':
            try:
                return int(raw_value) if str(raw_value).lstrip('-').isdigit() else 0
            except (ValueError, TypeError):
                return 0

        elif ttype == 'monetary':
            try:
                cleaned = str(raw_value).replace(',', '').replace('$', '').strip()
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        elif ttype == 'many2one':
            return self._resolve_many2one(line, raw_value, config)

        elif ttype == 'one2many':
            return self._resolve_one2many(line, raw_value, config)

        return raw_value

    def _parse_date(self, value, date_fmt):
        if not value:
            return False
        for fmt in [date_fmt, '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y']:
            try:
                return datetime.datetime.strptime(str(value), fmt).date()
            except (ValueError, TypeError):
                continue
        return False

    def _resolve_many2one(self, line, value, config):
        """Match or create a related record for a many2one field."""
        relation = line.ocr_field_id.relation

        # ── Currency ─────────────────────────────────────────────────────
        if relation == 'res.currency':
            rec = self.env['res.currency'].sudo().search(
                [('name', '=', value), ('active', '=', True)], limit=1)
            return rec.id if rec else self.env.company.currency_id.id

        # ── Employee ──────────────────────────────────────────────────────
        if relation == 'hr.employee' and isinstance(value, dict):
            for domain_field, dict_key in [
                ('name', 'name'),
                ('work_email', 'work_email'),
                ('work_phone', 'work_phone'),
            ]:
                v = value.get(dict_key)
                if v:
                    rec = self.env['hr.employee'].sudo().search([
                        (domain_field, '=', v),
                        ('company_id', 'in', [self.env.company.id, False]),
                    ], limit=1)
                    if rec:
                        return rec.id
            return False

        # ── Partner ───────────────────────────────────────────────────────
        if relation == 'res.partner' and isinstance(value, dict):
            return self._resolve_partner(value, line, config)

        # ── Generic many2one (search by name) ─────────────────────────────
        if isinstance(value, dict):
            search_name = value.get('name') or value.get('display_name', '')
        else:
            search_name = value or ''

        rec = self.env[relation].sudo().search(
            [('name', '=', search_name)], limit=1)
        if not rec and line.create_if_not_found and search_name:
            rec = self.env[relation].sudo().create({'name': search_name})
        return rec.id if rec else False

    def _resolve_partner(self, value, line, config):
        """Fuzzy-match partner by email → phone → name, or create if needed."""
        Partner = self.env['res.partner'].sudo()
        company_domain = ('company_id', 'in', [self.env.company.id, False])

        for domain_field, dict_key in [
            ('email', 'email'),
            ('phone', 'phone'),
            ('name', 'name'),
        ]:
            v = value.get(dict_key)
            if v:
                rec = Partner.search([(domain_field, '=', v), company_domain], limit=1)
                if rec:
                    return rec.id

        # Not found — optionally create
        if not line.create_if_not_found:
            return False

        country_id = False
        state_id = False
        country_name = (value.get('country_id') or '').strip().lower()
        state_name = (value.get('state_id') or '').strip().lower()

        if country_name:
            country = self.env['res.country'].sudo().search([]).filtered(
                lambda c: c.code.lower() == country_name or c.name.lower() == country_name
            )[:1]
            country_id = country.id if country else False

        if state_name and country_id:
            state = self.env['res.country.state'].sudo().search(
                [('country_id', '=', country_id)]
            ).filtered(
                lambda s: s.code.lower() == state_name or s.name.lower() == state_name
            )[:1]
            state_id = state.id if state else False

        partner_fields = self.env['res.partner']._fields.keys()
        contact_data = {k: v for k, v in value.items() if k in partner_fields and v}
        contact_data.update({
            'company_id': self.env.company.id,
            'country_id': country_id,
            'state_id': state_id,
        })
        new_partner = Partner.create(contact_data)
        return new_partner.id

    def _resolve_one2many(self, line, value, config):
        """Map a list of line-item dicts into Odoo (0, 0, vals) tuples."""
        if not isinstance(value, list):
            return False

        relation = line.ocr_field_id.relation
        related_model = self.env[relation]
        related_fields = related_model.fields_get()
        create_products = config.create_products_if_not_found

        result = []
        for item in value:
            mapped = {k: v for k, v in item.items() if k in related_fields and v is not None}

            # ── Product matching ──────────────────────────────────────────
            if 'product_id' in mapped:
                product = self._find_product(
                    mapped.get('product_id'),
                    mapped.get('name') or mapped.get('display_name', ''),
                    create_products,
                )
                mapped['product_id'] = product.id if product else False

            # ── UoM matching ──────────────────────────────────────────────
            if 'product_uom' in mapped:
                uom = self.env['uom.uom'].sudo().search(
                    [('name', '=', mapped['product_uom'])], limit=1)
                mapped['product_uom'] = uom.id if uom else False

            if mapped:
                result.append((0, 0, mapped))

        return result or False

    def _find_product(self, code_or_name, display_name, create_if_missing):
        """Search product by internal ref, barcode, or name; optionally create."""
        Product = self.env['product.product'].sudo()
        company_domain = ('company_id', 'in', [self.env.company.id, False])

        # 1. Internal reference
        if code_or_name:
            p = Product.search([
                ('default_code', '=', code_or_name),
                ('default_code', '!=', False),
                company_domain,
            ], limit=1)
            if p:
                return p

            # 2. Barcode
            p = Product.search([
                ('barcode', '=', code_or_name),
                ('barcode', '!=', False),
                company_domain,
            ], limit=1)
            if p:
                return p

        # 3. Name
        name = display_name or code_or_name or ''
        if name:
            p = Product.search([('name', '=', name), company_domain], limit=1)
            if p:
                return p

        # 4. Create
        if create_if_missing and name:
            return Product.create({
                'name': name,
                'is_storable': True,
                'default_code': code_or_name or False,
                'company_id': self.env.company.id,
            })

        return Product.browse()