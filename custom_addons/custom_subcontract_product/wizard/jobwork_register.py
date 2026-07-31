import base64
import io
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

AGING_INPUT_DAYS = 365          # Section 143: inputs
AGING_ALERT_LEAD_DAYS = 60      # alert threshold before expiry (FR-51)


class JobworkRegisterWizard(models.TransientModel):
    _name = 'jobwork.register.wizard'
    _description = 'Job Work Reconciliation Register (FR-50/51/52)'

    period_mode = fields.Selection([
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('fiscal_year', 'Fiscal Year'),
        ('custom', 'Custom'),
    ], default='month', required=True)
    date_from = fields.Date(required=True,
                            default=lambda s: date.today().replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.today)
    principal_id = fields.Many2one('res.partner', string='Principal')
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    @api.onchange('period_mode')
    def _onchange_period_mode(self):
        """Presets resolve into the editable custom range (register
        platform convention)."""
        today = fields.Date.context_today(self)
        if self.period_mode == 'month':
            self.date_from = today.replace(day=1)
            self.date_to = (self.date_from
                            + relativedelta(months=1, days=-1))
        elif self.period_mode == 'quarter':
            q_start_month = 3 * ((today.month - 1) // 3) + 1
            self.date_from = today.replace(month=q_start_month, day=1)
            self.date_to = (self.date_from
                            + relativedelta(months=3, days=-1))
        elif self.period_mode == 'fiscal_year':
            company = self.env.company
            self.date_from, self.date_to = [
                fields.Date.to_date(d) for d in
                company.compute_fiscalyear_dates(today).values()][:2]

    # ------------------------------------------------------------------
    # data collection
    # ------------------------------------------------------------------
    def _jw_types(self):
        return self.env['stock.picking.type'].search(
            [('is_jw_challan', '=', True)])

    def _inward_lines(self):
        domain = [
            ('picking_id.picking_type_id.is_jw_challan', '=', True),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
            ('state', '=', 'done'),
            ('date', '<=', fields.Datetime.to_datetime(
                self.date_to) + timedelta(days=1)),
        ]
        if self.principal_id:
            domain.append(('owner_id', '=', self.principal_id.id))
        return self.env['stock.move.line'].search(domain, order='date')

    def _consumption_totals(self):
        """Raw consumption and scrap per (owner, product) up to date_to,
        plus the share attributable to delivered FG (pro-rata per MO).
        v1 allocation: FIFO by challan date at render time; refine per
        UAT if lot-level tracing is mandated."""
        totals = {}
        mos = self.env['mrp.production'].search([
            ('subcontract_owner_id', '!=', False),
            ('state', 'not in', ('draft', 'cancel')),
        ])
        for mo in mos:
            fg_done = sum(mo.move_finished_ids.filtered(
                lambda m: m.state == 'done').mapped('quantity'))
            fg_delivered = 0.0
            sale = mo.procurement_group_id.sale_id
            if sale:
                so_lines = sale.order_line.filtered(
                    lambda l: l.product_id == mo.product_id)
                fg_delivered = sum(so_lines.mapped('qty_delivered'))
            ratio = (min(1.0, fg_delivered / fg_done)
                     if fg_done else 0.0)
            for raw in mo.move_raw_ids.filtered(
                    lambda m: m.state == 'done'
                    and m.product_id.categ_id.is_jobwork_chain):
                key = (mo.subcontract_owner_id.id, raw.product_id.id)
                rec = totals.setdefault(
                    key, {'consumed': 0.0, 'in_delivered': 0.0,
                          'scrap': 0.0, 'byproduct': 0.0,
                          'returned': 0.0})
                rec['consumed'] += raw.quantity
                rec['in_delivered'] += raw.quantity * ratio
            # by-products (chips/turnings) attributed to the MO's chain RM
            chain_raws = mo.move_raw_ids.filtered(
                lambda m: m.state == 'done'
                and m.product_id.categ_id.is_jobwork_chain)
            byprod_qty = sum(mo.move_finished_ids.filtered(
                lambda m: m.state == 'done'
                and m.product_id != mo.product_id
                and m.product_id.categ_id.is_jobwork_chain
            ).mapped('quantity'))
            if byprod_qty and chain_raws:
                key = (mo.subcontract_owner_id.id,
                       chain_raws[0].product_id.id)
                totals.setdefault(
                    key, {'consumed': 0.0, 'in_delivered': 0.0,
                          'scrap': 0.0, 'byproduct': 0.0,
                          'returned': 0.0})
                totals[key].setdefault('byproduct', 0.0)
                totals[key]['byproduct'] += byprod_qty
        scraps = self.env['stock.move'].search([
            ('scrapped', '=', True), ('state', '=', 'done'),
            ('product_id.categ_id.is_jobwork_chain', '=', True),
        ])
        for sc in scraps:
            owner = sc.move_line_ids[:1].owner_id
            key = (owner.id, sc.product_id.id)
            totals.setdefault(
                key, {'consumed': 0.0, 'in_delivered': 0.0,
                      'scrap': 0.0, 'byproduct': 0.0, 'returned': 0.0}
            )['scrap'] += sc.quantity
        # returns to principal on outward challans (leftover RM,
        # by-products, recovered scrap) - non-FG chain products only
        returns = self.env['stock.move.line'].search([
            ('picking_id.picking_type_id.is_jw_challan', '=', True),
            ('picking_id.picking_type_id.code', '=', 'outgoing'),
            ('state', '=', 'done'),
            ('product_id.categ_id.is_jobwork_chain', '=', True),
            ('product_id.l10n_in_is_jobwork', '=', False),
        ])
        for ml in returns:
            key = (ml.owner_id.id, ml.product_id.id)
            totals.setdefault(
                key, {'consumed': 0.0, 'in_delivered': 0.0,
                      'scrap': 0.0, 'byproduct': 0.0, 'returned': 0.0}
            )['returned'] += ml.quantity
        return totals

    def _owner_exceptions(self):
        """Chain move lines without an owner (FR-52)."""
        return self.env['stock.move.line'].search([
            ('state', '=', 'done'),
            ('owner_id', '=', False),
            ('product_id.categ_id.is_jobwork_chain', '=', True),
            ('date', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('date', '<=', fields.Datetime.to_datetime(
                self.date_to) + timedelta(days=1)),
        ], order='date')

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------
    def action_generate(self):
        self.ensure_one()
        import xlsxwriter
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        head = wb.add_format({'bold': True, 'bg_color': '#D9E2F3',
                              'border': 1})
        num = wb.add_format({'num_format': '#,##0.00'})
        datef = wb.add_format({'num_format': 'dd-mm-yyyy'})

        ws = wb.add_worksheet('Reconciliation')
        cols = ['Principal', 'Challan No.', 'Challan Date',
                "Principal's Challan", 'Product', 'HSN', 'UoM',
                'Received', 'Consumed', 'In Delivered FG',
                'By-Product', 'Scrap', 'Returned', 'Balance',
                'Age (days)', 'SO Ref']
        for c, label in enumerate(cols):
            ws.write(0, c, label, head)
        totals = self._consumption_totals()
        remaining = {k: dict(v) for k, v in totals.items()}
        row = 1
        for ml in self._inward_lines():
            key = (ml.owner_id.id, ml.product_id.id)
            rem = remaining.get(
                key, {'consumed': 0.0, 'in_delivered': 0.0, 'scrap': 0.0})
            received = ml.quantity
            consumed = min(received, rem['consumed'])
            rem['consumed'] -= consumed
            in_dlv = min(consumed, rem['in_delivered'])
            rem['in_delivered'] -= in_dlv
            scrap = min(received - consumed, rem['scrap'])
            rem['scrap'] -= scrap
            byprod = min(consumed, rem.get('byproduct', 0.0))
            rem['byproduct'] = rem.get('byproduct', 0.0) - byprod
            returned = min(received - consumed - scrap,
                           rem.get('returned', 0.0))
            rem['returned'] = rem.get('returned', 0.0) - returned
            balance = received - consumed - scrap - returned
            pick = ml.picking_id
            ws.write(row, 0, ml.owner_id.display_name)
            ws.write(row, 1, pick.jobwork_challan_no or '')
            ws.write_datetime(row, 2, ml.date, datef)
            ws.write(row, 3, pick.principal_challan_no or '')
            ws.write(row, 4, ml.product_id.display_name)
            ws.write(row, 5, ml.product_id.l10n_in_hsn_code or '')
            ws.write(row, 6, ml.product_uom_id.name)
            ws.write(row, 7, received, num)
            ws.write(row, 8, consumed, num)
            ws.write(row, 9, in_dlv, num)
            ws.write(row, 10, byprod, num)
            ws.write(row, 11, scrap, num)
            ws.write(row, 12, returned, num)
            ws.write(row, 13, balance, num)
            ws.write(row, 14,
                     (fields.Date.today() - ml.date.date()).days
                     if balance > 0 else 0)
            ws.write(row, 15, pick.origin or '')
            row += 1

        ws2 = wb.add_worksheet('Documents Issued (T13)')
        for c, label in enumerate(['Series', 'From', 'To', 'Issued',
                                   'Cancelled']):
            ws2.write(0, c, label, head)
        r2 = 1
        for ptype in self._jw_types():
            picks = self.env['stock.picking'].search([
                ('picking_type_id', '=', ptype.id),
                ('jobwork_challan_no', '!=', False),
                ('date_done', '>=',
                 fields.Datetime.to_datetime(self.date_from)),
                ('date_done', '<=', fields.Datetime.to_datetime(
                    self.date_to) + timedelta(days=1)),
            ])
            cancelled = self.env['stock.picking'].search_count([
                ('picking_type_id', '=', ptype.id),
                ('jobwork_challan_no', '!=', False),
                ('state', '=', 'cancel'),
            ])
            nos = sorted(picks.mapped('jobwork_challan_no'))
            ws2.write(r2, 0, ptype.display_name)
            ws2.write(r2, 1, nos[0] if nos else '')
            ws2.write(r2, 2, nos[-1] if nos else '')
            ws2.write(r2, 3, len(nos))
            ws2.write(r2, 4, cancelled)
            r2 += 1

        ws3 = wb.add_worksheet('Owner Exceptions')
        for c, label in enumerate(['Date', 'Reference', 'Product',
                                   'Qty', 'From', 'To']):
            ws3.write(0, c, label, head)
        for r3, ml in enumerate(self._owner_exceptions(), start=1):
            ws3.write_datetime(r3, 0, ml.date, datef)
            ws3.write(r3, 1, ml.reference or '')
            ws3.write(r3, 2, ml.product_id.display_name)
            ws3.write(r3, 3, ml.quantity, num)
            ws3.write(r3, 4, ml.location_id.complete_name)
            ws3.write(r3, 5, ml.location_dest_id.complete_name)

        wb.close()
        self.write({
            'file_data': base64.b64encode(buf.getvalue()),
            'file_name': 'jobwork_register_%s_%s.xlsx' % (
                self.date_from, self.date_to),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/file_data/%s?download=true' % (
                self._name, self.id, self.file_name),
            'target': 'self',
        }

    # ------------------------------------------------------------------
    # Section 143 aging cron (FR-51)
    # ------------------------------------------------------------------
    @api.model
    def _cron_jw_section143_aging(self):
        threshold = fields.Datetime.now() - timedelta(
            days=AGING_INPUT_DAYS - AGING_ALERT_LEAD_DAYS)
        lines = self.env['stock.move.line'].search([
            ('picking_id.picking_type_id.is_jw_challan', '=', True),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
            ('state', '=', 'done'),
            ('date', '<=', threshold),
            ('owner_id', '!=', False),
        ])
        for pick in lines.picking_id:
            balance = sum(self.env['stock.quant'].search([
                ('owner_id', '=', pick.owner_id.id or
                 pick.partner_id.id),
                ('product_id', 'in',
                 pick.move_line_ids.product_id.ids),
                ('quantity', '>', 0),
            ]).mapped('quantity'))
            if balance and not pick.activity_ids.filtered(
                    lambda a: a.summary
                    and 'Section 143' in a.summary):
                pick.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Section 143 aging: job-work material '
                              'nearing the return deadline'),
                    user_id=(pick.user_id.id or self.env.ref(
                        'base.user_admin').id),
                )
