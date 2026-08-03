# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from .plan import STAGES

SET_STATES = [('pending', 'Pending'), ('in_progress', 'In Progress'),
              ('screening', '100% Screening'), ('accepted', 'Accepted'),
              ('partially_accepted', 'Partially Accepted'), ('rejected', 'Rejected')]
OPEN_SET_STATES = ('pending', 'in_progress', 'screening')


class QualityInspectionSet(models.Model):
    """FR-TRG / FR-SMP / FR-EVAL - batch-level inspection run for one lot/trigger."""
    _name = 'quality.inspection.set'
    _description = 'Inspection Set'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    plan_id = fields.Many2one('quality.inspection.plan', required=True)
    plan_version = fields.Integer(readonly=True)
    stage = fields.Selection(STAGES, required=True)
    product_id = fields.Many2one('product.product', required=True)
    tracking = fields.Selection(related='product_id.tracking')
    lot_id = fields.Many2one('stock.lot', string='Lot')
    serial_ids = fields.Many2many('stock.lot', string='Serials')
    lot_qty = fields.Float(digits='Product Unit of Measure')
    picking_id = fields.Many2one('stock.picking')
    production_id = fields.Many2one('mrp.production')
    workorder_id = fields.Many2one('mrp.workorder')
    partner_id = fields.Many2one('res.partner', string='Vendor')
    ncr_origin_id = fields.Many2one('quality.ncr', string='Re-inspection of NCR')
    basis = fields.Selection([('full', '100%'), ('sampling', 'Sampling')], readonly=True)
    sample_qty = fields.Integer(readonly=True)
    ac = fields.Integer('Ac', readonly=True)
    re = fields.Integer('Re', readonly=True)
    code_letter = fields.Char(readonly=True)
    severity = fields.Char(readonly=True, default='normal')
    state = fields.Selection(SET_STATES, default='pending', tracking=True, copy=False)
    report_ids = fields.One2many('quality.inspection.report', 'set_id')
    report_count = fields.Integer(compute='_compute_counts')
    failed_count = fields.Integer(compute='_compute_counts')
    passed_count = fields.Integer(compute='_compute_counts')
    ncr_ids = fields.One2many('quality.ncr', 'set_id')
    decision_user_id = fields.Many2one('res.users', readonly=True)
    decision_date = fields.Datetime(readonly=True)
    skip_lot = fields.Boolean(readonly=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)

    @api.depends('report_ids.verdict', 'report_ids.state')
    def _compute_counts(self):
        for rec in self:
            done = rec.report_ids.filtered(lambda r: r.state == 'done' and not r.superseded)
            rec.report_count = len(rec.report_ids)
            rec.failed_count = len(done.filtered(lambda r: r.verdict == 'fail'))
            rec.passed_count = len(done.filtered(lambda r: r.verdict == 'pass'))

    # ------------------------------------------------------------------ create
    @api.model
    def create_for(self, plan, product, qty, lot=None, serials=None, picking=None,
                   production=None, workorder=None, partner=None, ncr=None):
        company = plan.company_id
        severity = 'normal'
        switch = None
        if partner and plan.stage == 'incoming':
            switch = self.env['quality.sampling.switch']._get(partner, product, company)
            severity = switch.severity
            # skip-lot (FR-TRG-06)
            n_skip = company.quality_skiplot_count
            if n_skip and switch.consec_accept >= n_skip and not ncr:
                rec = self.create({
                    'plan_id': plan.id, 'plan_version': plan.version, 'stage': plan.stage,
                    'product_id': product.id, 'lot_id': lot and lot.id,
                    'serial_ids': [(6, 0, serials.ids)] if serials else False,
                    'lot_qty': qty, 'picking_id': picking and picking.id,
                    'partner_id': partner.id, 'company_id': company.id,
                    'basis': 'sampling', 'sample_qty': 0, 'ac': 0, 're': 1,
                    'state': 'accepted', 'skip_lot': True, 'severity': severity,
                })
                rec._set_lot_state('accepted')
                rec.message_post(body='Skip-Lot Accepted (%s consecutive acceptances).'
                                      % switch.consec_accept)
                return rec
        sample = plan.sampling_rule_id.compute_sample(qty, severity=severity)
        rec = self.create({
            'plan_id': plan.id, 'plan_version': plan.version, 'stage': plan.stage,
            'product_id': product.id, 'lot_id': lot and lot.id,
            'serial_ids': [(6, 0, serials.ids)] if serials else False,
            'lot_qty': qty, 'picking_id': picking and picking.id,
            'production_id': production and production.id,
            'workorder_id': workorder and workorder.id,
            'partner_id': partner and partner.id, 'ncr_origin_id': ncr and ncr.id,
            'company_id': company.id, 'severity': severity,
            'basis': sample['basis'], 'sample_qty': sample['qty'],
            'ac': sample['ac'], 're': sample['re'], 'code_letter': sample['letter'],
        })
        rec._set_lot_state('pending')
        rec.action_generate_reports()
        notify = company.quality_notify_user_id
        if notify:
            rec.activity_schedule('mail.mail_activity_data_todo', user_id=notify.id,
                                  summary='Inspection due: %s' % rec.name)
        return rec

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.set') or 'New'
        return super().create(vals_list)

    def _set_lot_state(self, state):
        for rec in self:
            (rec.lot_id | rec.serial_ids).write({'quality_state': state})

    def _prepare_ir_line(self, pl):
        """Frozen copy of a plan line onto the IR (bridge extends this)."""
        return {'plan_line_id': pl.id, 'balloon_ref': pl.balloon_ref, 'name': pl.name,
                'char_type': pl.char_type, 'specification': pl.specification,
                'nominal_value': pl.nominal_value, 'tol_min': pl.tol_min,
                'tol_max': pl.tol_max, 'uom_id': pl.uom_id.id,
                'instrument_note': pl.instrument_note, 'method': pl.method,
                'mandatory': pl.mandatory}

    # ------------------------------------------------------- report generation
    def action_generate_reports(self):
        """FR-IR-01/02 - one IR per unit, batched create."""
        Report = self.env['quality.inspection.report']
        for rec in self:
            if rec.report_ids or rec.state == 'accepted':
                continue
            line_cmds = [(0, 0, rec._prepare_ir_line(pl))
                         for pl in rec.plan_id.line_ids]
            vals_list = []
            if rec.tracking == 'serial' and rec.serial_ids:
                units = rec.serial_ids.sorted('name')[:rec.sample_qty]
                for i, serial in enumerate(units, 1):
                    vals_list.append({'set_id': rec.id, 'unit_no': i,
                                      'serial_id': serial.id, 'line_ids': line_cmds})
            else:
                for i in range(1, rec.sample_qty + 1):
                    vals_list.append({'set_id': rec.id, 'unit_no': i,
                                      'line_ids': line_cmds})
            if vals_list:
                Report.create(vals_list)
            rec.state = 'in_progress'

    def action_generate_screening_reports(self):
        """FR-EVAL-02(a) - IRs for the balance units of the lot."""
        Report = self.env['quality.inspection.report']
        for rec in self:
            existing = len(rec.report_ids)
            total = int(rec.lot_qty)
            line_cmds = [(0, 0, rec._prepare_ir_line(pl))
                         for pl in rec.plan_id.line_ids]
            vals_list = []
            if rec.tracking == 'serial' and rec.serial_ids:
                done_serials = rec.report_ids.mapped('serial_id')
                rest = (rec.serial_ids - done_serials).sorted('name')
                for i, serial in enumerate(rest, existing + 1):
                    vals_list.append({'set_id': rec.id, 'unit_no': i,
                                      'serial_id': serial.id, 'line_ids': line_cmds})
            else:
                for i in range(existing + 1, total + 1):
                    vals_list.append({'set_id': rec.id, 'unit_no': i,
                                      'line_ids': line_cmds})
            if vals_list:
                Report.create(vals_list)
            rec.write({'state': 'screening', 'basis': 'full',
                       'sample_qty': total})
            rec.message_post(body='Sampling rejected - 100%% screening chosen by %s.'
                                  % self.env.user.name)

    # --------------------------------------------------------------- evaluate
    def action_evaluate(self):
        """FR-EVAL-01..04 - set verdict, release / reject, NCR creation."""
        self.ensure_one()
        rec = self
        if rec.state not in ('in_progress', 'screening'):
            raise UserError('Set %s is not under inspection.' % rec.name)
        open_reports = rec.report_ids.filtered(
            lambda r: r.state != 'done' and not r.superseded)
        if open_reports:
            raise UserError('%s report(s) still open on %s.' % (len(open_reports), rec.name))
        fails = rec.report_ids.filtered(
            lambda r: r.state == 'done' and not r.superseded and r.verdict == 'fail')
        if rec.basis == 'sampling' and rec.state != 'screening' and len(fails) >= rec.re:
            # rejected on sampling -> user must choose screening or lot rejection
            return {
                'type': 'ir.actions.act_window', 'res_model': 'quality.screening.wizard',
                'view_mode': 'form', 'target': 'new',
                'context': {'default_set_id': rec.id, 'default_failed': len(fails)},
            }
        rec._finalize(fails)
        return True

    def _finalize(self, fails, lot_rejected=False):
        self.ensure_one()
        rec = self
        rec.decision_user_id = self.env.user
        rec.decision_date = fields.Datetime.now()
        accepted = True
        if lot_rejected:
            rec.state = 'rejected'
            rec._set_lot_state('rejected')
            rec._raise_ncr(rec.report_ids.filtered(lambda r: r.verdict == 'fail'),
                           qty=rec.lot_qty)
            accepted = False
        elif not fails:
            rec.state = 'accepted'
            rec._release_all()
        elif rec.basis == 'sampling' and rec.state != 'screening' and len(fails) <= rec.ac:
            # lot accepted under AQL; failed sampled units individually rejected
            rec.state = 'partially_accepted'
            rec._release_all(exclude=fails)
            rec._raise_ncr(fails, qty=len(fails))
        else:
            passed = rec.passed_count
            if passed:
                rec.state = 'partially_accepted'
                rec._release_all(exclude=fails)
            else:
                rec.state = 'rejected'
                rec._set_lot_state('rejected')
            rec._raise_ncr(fails, qty=len(fails) if passed else rec.lot_qty)
            accepted = passed > 0 and len(fails) == 0
        if rec.partner_id and rec.stage == 'incoming' and not rec.skip_lot:
            switch = self.env['quality.sampling.switch']._get(
                rec.partner_id, rec.product_id, rec.company_id)
            switch.register_result(rec.state == 'accepted')
        # re-inspection closes / reopens the origin NCR (FR-NCR-03/07)
        if rec.ncr_origin_id:
            rec.ncr_origin_id._on_reinspection(rec)
        return accepted

    def _release_all(self, exclude=None):
        """FR-TRG-05 - accepted units released; QC->Stock best-effort move."""
        self.ensure_one()
        exclude = exclude or self.env['quality.inspection.report']
        failed_serials = exclude.mapped('serial_id')
        if self.tracking == 'serial' and self.serial_ids:
            (self.serial_ids - failed_serials).write({'quality_state': 'accepted'})
            failed_serials.write({'quality_state': 'rejected'})
        elif self.lot_id:
            self.lot_id.quality_state = 'partial' if exclude else 'accepted'
        qty_ok = self.lot_qty - len(exclude)
        self._move_quants(qty_ok, to_nc=False)
        if exclude:
            self._move_quants(len(exclude), to_nc=True)

    def _move_quants(self, qty, to_nc=False):
        """Best-effort physical move QC -> Stock (or QC -> NC). Silently skips
        when no quants sit in the QC location (single-step receipts)."""
        self.ensure_one()
        company = self.company_id
        src = company.quality_qc_location_id
        dst = company.quality_nc_location_id if to_nc else False
        if not src or qty <= 0:
            return
        lots = self.serial_ids if self.tracking == 'serial' else self.lot_id
        Quant = self.env['stock.quant']
        for lot in lots or [None]:
            dom = [('product_id', '=', self.product_id.id), ('location_id', '=', src.id),
                   ('quantity', '>', 0)]
            if lot:
                dom.append(('lot_id', '=', lot.id))
            quants = Quant.search(dom)
            if not quants:
                continue
            if not dst:
                wh = src.warehouse_id or self.env['stock.warehouse'].search(
                    [('company_id', '=', company.id)], limit=1)
                dst = wh.lot_stock_id
            move_qty = min(qty, sum(quants.mapped('quantity')))
            if move_qty <= 0:
                continue
            move = self.env['stock.move'].create({
                'name': self.name, 'product_id': self.product_id.id,
                'product_uom': self.product_id.uom_id.id, 'product_uom_qty': move_qty,
                'location_id': src.id, 'location_dest_id': dst.id,
                'company_id': company.id, 'origin': self.name,
            })
            move._action_confirm()
            move._action_assign()
            for ml in move.move_line_ids:
                ml.quantity = ml.quantity or move_qty
                if lot:
                    ml.lot_id = lot.id
            move.picked = True
            move.with_context(quality_bypass=True)._action_done()

    def _raise_ncr(self, failed_reports, qty):
        self.ensure_one()
        if self.ncr_ids.filtered(lambda n: n.state != 'cancel'):
            return self.ncr_ids[0]
        ncr = self.env['quality.ncr'].create({
            'set_id': self.id, 'product_id': self.product_id.id,
            'lot_id': self.lot_id.id, 'qty': qty,
            'report_ids': [(6, 0, failed_reports.ids)],
            'serial_ids': [(6, 0, failed_reports.mapped('serial_id').ids)],
            'company_id': self.company_id.id,
        })
        ncr.message_post(body='Auto-raised from %s (%s failed unit(s)).'
                              % (self.name, len(failed_reports)))
        notify = self.company_id.quality_notify_user_id
        if notify:
            ncr.activity_schedule('mail.mail_activity_data_todo', user_id=notify.id,
                                  summary='NCR awaiting disposition: %s' % ncr.name)
        return ncr

    @api.model
    def _cron_sla_overdue(self):
        for company in self.env['res.company'].search([]):
            hours = company.quality_sla_hours
            notify = company.quality_notify_user_id
            if not hours or not notify:
                continue
            limit = fields.Datetime.subtract(fields.Datetime.now(), hours=hours)
            overdue = self.search([('company_id', '=', company.id),
                                   ('state', 'in', list(OPEN_SET_STATES)),
                                   ('create_date', '<=', limit)])
            for rec in overdue:
                rec.activity_schedule('mail.mail_activity_data_todo', user_id=notify.id,
                                      summary='Inspection overdue (SLA %sh): %s'
                                              % (hours, rec.name))


class QualityInspectionReport(models.Model):
    """FR-IR-01..07 - the per-unit Inspection Report."""
    _name = 'quality.inspection.report'
    _description = 'Inspection Report (per unit)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'set_id desc, unit_no'

    name = fields.Char(default='New', readonly=True, copy=False)
    set_id = fields.Many2one('quality.inspection.set', required=True, ondelete='cascade')
    stage = fields.Selection(related='set_id.stage', store=True)
    product_id = fields.Many2one(related='set_id.product_id', store=True)
    lot_id = fields.Many2one(related='set_id.lot_id', store=True)
    plan_id = fields.Many2one(related='set_id.plan_id', store=True)
    unit_no = fields.Integer('Unit No.', readonly=True)
    serial_id = fields.Many2one('stock.lot', string='Serial', readonly=True)
    piece_mark = fields.Char()
    inspector_id = fields.Many2one('res.users', default=lambda s: s.env.user, tracking=True)
    employee_id = fields.Many2one('hr.employee',
                                  default=lambda s: s.env.user.employee_id)
    date_start = fields.Datetime(readonly=True)
    date_done = fields.Datetime(readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'),
                              ('done', 'Done')], default='draft', tracking=True, copy=False)
    verdict = fields.Selection([('pass', 'Pass'), ('fail', 'Fail')],
                               compute='_compute_verdict', store=True, tracking=True)
    superseded = fields.Boolean(readonly=True, copy=False)
    superseded_by_id = fields.Many2one('quality.inspection.report', readonly=True, copy=False)
    line_ids = fields.One2many('quality.inspection.report.line', 'report_id', copy=True)
    company_id = fields.Many2one(related='set_id.company_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        Set = self.env['quality.inspection.set']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                stage = Set.browse(vals.get('set_id')).stage
                code = {'incoming': 'quality.ir.iqc', 'inprocess': 'quality.ir.ipq',
                        'final': 'quality.ir.fqc'}.get(stage, 'quality.ir.iqc')
                vals['name'] = seq.next_by_code(code) or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.result', 'line_ids.mandatory', 'state')
    def _compute_verdict(self):
        for rec in self:
            lines = rec.line_ids.filtered('mandatory') or rec.line_ids
            if not lines or any(not l.result for l in lines):
                rec.verdict = False
            else:
                rec.verdict = 'fail' if any(l.result == 'fail' for l in lines) else 'pass'

    def _check_competence(self):
        """FR-CMP-01 - warn / block per configuration."""
        for rec in self:
            mode = rec.company_id.quality_competence_mode
            if mode == 'off' or not rec.employee_id:
                continue
            ok = self.env['quality.inspector.qualification'].is_qualified(
                rec.employee_id, rec.product_id, rec.stage)
            if ok:
                continue
            msg = ('Inspector %s holds no valid qualification for %s / %s stage '
                   '(ISO 9001 §7.2).' % (rec.employee_id.name,
                                         rec.product_id.display_name, rec.stage))
            if mode == 'block':
                raise UserError(msg)
            rec.message_post(body='Competence warning: ' + msg)

    def action_start(self):
        self._check_competence()
        self.filtered(lambda r: r.state == 'draft').write(
            {'state': 'in_progress', 'date_start': fields.Datetime.now()})

    def action_done(self):
        for rec in self:
            if rec.state == 'done':
                continue
            rec._check_competence()
            missing = rec.line_ids.filtered(lambda l: l.mandatory and not l.result)
            if missing:
                raise UserError('Unrecorded mandatory parameters on %s: %s'
                                % (rec.name, ', '.join(missing.mapped('name'))))
            rec._check_instruments()
            rec.write({'state': 'done', 'date_done': fields.Datetime.now(),
                       'date_start': rec.date_start or fields.Datetime.now()})

    def _check_instruments(self):
        """Hook - the calibration bridge overrides this (FR-QIP-07)."""
        return True

    def write(self, vals):
        allowed = {'state', 'date_done', 'date_start', 'superseded', 'superseded_by_id',
                   'message_follower_ids', 'activity_ids', 'message_ids'}
        for rec in self:
            if rec.state == 'done' and not set(vals) <= allowed:
                raise UserError('IR %s is Done and immutable (FR-IR-05). '
                                'Use Supersede to correct.' % rec.name)
        return super().write(vals)

    def action_open_supersede(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'quality.supersede.wizard',
                'view_mode': 'form', 'target': 'new',
                'context': {'default_report_id': self.id}}


class QualityInspectionReportLine(models.Model):
    """FR-IR-02/03 - frozen spec + observed value, auto verdict."""
    _name = 'quality.inspection.report.line'
    _description = 'Inspection Report Line'
    _order = 'report_id, id'

    report_id = fields.Many2one('quality.inspection.report', required=True,
                                ondelete='cascade')
    plan_line_id = fields.Many2one('quality.inspection.plan.line')
    balloon_ref = fields.Char('Balloon')
    name = fields.Char('Parameter', required=True)
    char_type = fields.Selection([('variable', 'Variable'), ('attribute', 'Attribute'),
                                  ('visual', 'Visual'), ('functional', 'Functional')])
    specification = fields.Char()
    nominal_value = fields.Float(digits=(16, 4))
    tol_min = fields.Float('LSL', digits=(16, 4))
    tol_max = fields.Float('USL', digits=(16, 4))
    uom_id = fields.Many2one('uom.uom', string='UoM')
    instrument_note = fields.Char('Instrument')
    method = fields.Char()
    mandatory = fields.Boolean(default=True)
    observed_value = fields.Float(digits=(16, 4))
    observed_recorded = fields.Boolean()
    observed_ok = fields.Selection([('ok', 'OK'), ('nok', 'Not OK')], string='OK / NOK')
    result = fields.Selection([('pass', 'Pass'), ('fail', 'Fail')],
                              compute='_compute_result', store=True)
    remark = fields.Char()

    @api.onchange('observed_value')
    def _onchange_observed(self):
        for line in self:
            line.observed_recorded = True

    def write(self, vals):
        if 'observed_value' in vals:
            vals.setdefault('observed_recorded', True)
        return super().write(vals)

    @api.depends('char_type', 'observed_value', 'observed_recorded', 'observed_ok',
                 'tol_min', 'tol_max')
    def _compute_result(self):
        for line in self:
            if line.char_type == 'variable':
                if not line.observed_recorded:
                    line.result = False
                else:
                    line.result = ('pass' if line.tol_min <= line.observed_value
                                   <= line.tol_max else 'fail')
            else:
                line.result = ({'ok': 'pass', 'nok': 'fail'}.get(line.observed_ok)
                               or False)
