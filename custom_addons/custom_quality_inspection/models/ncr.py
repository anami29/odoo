# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class QualityNcr(models.Model):
    """FR-NCR / FR-ACC - non-conformance with disposition, M Report and loss."""
    _name = 'quality.ncr'
    _description = 'Non-Conformance Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    set_id = fields.Many2one('quality.inspection.set', readonly=True)
    stage = fields.Selection(related='set_id.stage', store=True)
    report_ids = fields.Many2many('quality.inspection.report', string='Failed IRs')
    product_id = fields.Many2one('product.product', required=True)
    lot_id = fields.Many2one('stock.lot')
    serial_ids = fields.Many2many('stock.lot', 'ncr_serial_rel', string='Serials')
    qty = fields.Float(digits='Product Unit of Measure')
    picking_id = fields.Many2one(related='set_id.picking_id', store=True)
    production_id = fields.Many2one(related='set_id.production_id', store=True)
    partner_id = fields.Many2one(related='set_id.partner_id', store=True, string='Vendor')
    state = fields.Selection([('open', 'Open'), ('approved', 'Disposition Approved'),
                              ('closed', 'Closed'), ('cancel', 'Cancelled')],
                             default='open', tracking=True, copy=False)
    # accountability (FR-ACC-01)
    defect_ids = fields.Many2many('quality.defect.code', string='Defect Codes')
    cause_id = fields.Many2one('quality.cause.code', string='Cause Code')
    cause_note = fields.Text('Cause Description')
    resp_type = fields.Selection([
        ('vendor', 'Vendor'), ('workcenter', 'Production - Work Centre'),
        ('operator', 'Operator'), ('design', 'Design'),
        ('stores', 'Stores - Handling'), ('subcontractor', 'Subcontractor'),
        ('other', 'Other')], string='Responsibility', tracking=True)
    resp_partner_id = fields.Many2one('res.partner', string='Responsible Vendor')
    resp_workcenter_id = fields.Many2one('mrp.workcenter', string='Responsible Work Centre')
    resp_employee_id = fields.Many2one('hr.employee', string='Responsible Employee')
    resp_department_id = fields.Many2one('hr.department', string='Responsible Department')
    # loss (FR-ACC-02/03)
    currency_id = fields.Many2one(related='company_id.currency_id')
    material_cost = fields.Monetary(tracking=True)
    conversion_cost = fields.Monetary(tracking=True)
    total_loss = fields.Monetary(compute='_compute_total_loss', store=True, tracking=True)
    loss_adjust_reason = fields.Char()
    # disposition (FR-NCR-02..06)
    disposition = fields.Selection([('rework', 'Rework'), ('scrap', 'Scrap (M Report)'),
                                    ('rtv', 'Return to Vendor'),
                                    ('deviation', 'Deviation (Use-As-Is)')],
                                   tracking=True)
    repair_order_id = fields.Many2one('repair.order', readonly=True, copy=False)
    rework_mo_id = fields.Many2one('mrp.production', readonly=True, copy=False)
    scrap_id = fields.Many2one('stock.scrap', readonly=True, copy=False)
    return_picking_id = fields.Many2one('stock.picking', readonly=True, copy=False)
    debit_note_ref = fields.Char('Debit Note Ref.')
    reinspection_set_id = fields.Many2one('quality.inspection.set', readonly=True, copy=False)
    # M Report (FR-NCR-04, FR-ACC-03)
    mr_name = fields.Char('M Report No.', readonly=True, copy=False)
    mr_state = fields.Selection([('none', 'N/A'), ('to_approve', 'Awaiting Approval'),
                                 ('approved', 'Approved')], default='none', tracking=True,
                                copy=False)
    plant_required = fields.Boolean(compute='_compute_plant_required', store=True)
    qm_approver_id = fields.Many2one('res.users', readonly=True, copy=False)
    qm_approve_date = fields.Datetime(readonly=True, copy=False)
    plant_approver_id = fields.Many2one('res.users', readonly=True, copy=False)
    plant_approve_date = fields.Datetime(readonly=True, copy=False)
    disposal_instruction = fields.Char()
    # deviation (FR-NCR-06)
    dev_name = fields.Char('Concession No.', readonly=True, copy=False)
    dev_qty = fields.Float()
    dev_valid_until = fields.Date()
    dev_justification = fields.Text()
    dev_approver_id = fields.Many2one('res.users', readonly=True, copy=False)
    # CAPA (FR-ACC-06 / FR-CAPA-03)
    capa_ids = fields.Many2many('quality.capa', string='CAPA')
    capa_required = fields.Boolean(compute='_compute_capa_required')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.ncr') or 'New'
        recs = super().create(vals_list)
        for rec in recs:
            rec._default_loss()
        return recs

    @api.depends('material_cost', 'conversion_cost')
    def _compute_total_loss(self):
        for rec in self:
            rec.total_loss = rec.material_cost + rec.conversion_cost

    @api.depends('total_loss', 'company_id.quality_mr_approval_limit')
    def _compute_plant_required(self):
        for rec in self:
            limit = rec.company_id.quality_mr_approval_limit
            rec.plant_required = bool(limit) and rec.total_loss > limit

    @api.depends('disposition', 'company_id.quality_capa_on_scrap',
                 'company_id.quality_capa_on_deviation')
    def _compute_capa_required(self):
        for rec in self:
            rec.capa_required = (
                (rec.disposition == 'scrap' and rec.company_id.quality_capa_on_scrap)
                or (rec.disposition == 'deviation'
                    and rec.company_id.quality_capa_on_deviation))

    def _default_loss(self):
        """FR-ACC-02 - material + optional conversion cost to the failing stage."""
        for rec in self:
            rec.material_cost = rec.product_id.standard_price * rec.qty
            conv = 0.0
            if rec.company_id.quality_include_conversion and rec.production_id:
                prod = rec.production_id
                stop_seq = rec.set_id.workorder_id.id or 10 ** 9
                for wo in prod.workorder_ids:
                    if wo.id > stop_seq:
                        continue
                    hours = (wo.duration or wo.duration_expected or 0.0) / 60.0
                    conv += hours * wo.workcenter_id.costs_hour
                if prod.product_qty:
                    conv = conv * rec.qty / prod.product_qty
            rec.conversion_cost = conv

    def action_recompute_loss(self):
        self._default_loss()

    # ------------------------------------------------------------ disposition
    def _check_accountability(self):
        for rec in self:
            missing = []
            if not rec.defect_ids:
                missing.append('Defect Code(s)')
            if not rec.cause_id:
                missing.append('Cause Code')
            if not rec.resp_type:
                missing.append('Responsibility Type')
            resp_map = {'vendor': rec.resp_partner_id,
                        'workcenter': rec.resp_workcenter_id,
                        'operator': rec.resp_employee_id,
                        'subcontractor': rec.resp_partner_id}
            if rec.resp_type in resp_map and not resp_map[rec.resp_type]:
                missing.append('Responsible record for type "%s"' % rec.resp_type)
            if missing:
                raise UserError('FR-ACC-01: complete before approval - %s.'
                                % ', '.join(missing))

    def _check_manager(self):
        if not self.env.user.has_group(
                'custom_quality_inspection.group_quality_manager'):
            raise UserError('Only a Quality Manager may approve dispositions.')

    def action_approve_disposition(self):
        """FR-NCR-02 - QM approval, then execute the disposition."""
        self._check_manager()
        for rec in self:
            if rec.state != 'open':
                raise UserError('%s is not open.' % rec.name)
            if not rec.disposition:
                raise UserError('Select a disposition on %s.' % rec.name)
            rec._check_accountability()
            rec.state = 'approved'
            getattr(rec, '_do_%s' % rec.disposition)()

    def _do_rework(self):
        """FR-NCR-03 - repair order or rework MO per product category."""
        self.ensure_one()
        vehicle = self.product_id.categ_id.quality_rework_vehicle or 'repair'
        loc = self.company_id.quality_nc_location_id
        if vehicle == 'repair':
            vals = {'product_id': self.product_id.id,
                    'product_qty': self.qty or 1.0,
                    'product_uom': self.product_id.uom_id.id,
                    'ncr_id': self.id}
            if self.serial_ids[:1]:
                vals['lot_id'] = self.serial_ids[0].id
            elif self.lot_id:
                vals['lot_id'] = self.lot_id.id
            if loc:
                vals['location_id'] = loc.id
            self.repair_order_id = self.env['repair.order'].create(vals)
        else:
            bom = self.env['mrp.bom']._bom_find(self.product_id).get(self.product_id)
            if not bom:
                raise UserError('No BoM found for rework MO of %s.'
                                % self.product_id.display_name)
            self.rework_mo_id = self.env['mrp.production'].create({
                'product_id': self.product_id.id, 'product_qty': self.qty or 1.0,
                'product_uom_id': self.product_id.uom_id.id, 'bom_id': bom.id,
                'origin': self.name, 'rework_ncr_id': self.id,
                'company_id': self.company_id.id})
        self.message_post(body='Rework created: %s' % (
            self.repair_order_id.name or self.rework_mo_id.name))

    def trigger_reinspection(self):
        """Called by repair/MO completion hooks - mandatory re-inspection."""
        for rec in self:
            if rec.reinspection_set_id:
                continue
            plan = rec.set_id.plan_id
            rec.reinspection_set_id = self.env['quality.inspection.set'].create_for(
                plan, rec.product_id, rec.qty or 1.0, lot=rec.lot_id,
                serials=rec.serial_ids, production=rec.production_id, ncr=rec)
            rec.message_post(body='Re-inspection set %s created (FR-NCR-03).'
                                  % rec.reinspection_set_id.name)

    def _on_reinspection(self, iset):
        for rec in self:
            if iset.state in ('accepted', 'partially_accepted') and not iset.failed_count:
                rec._close()
            else:
                rec.write({'state': 'open', 'disposition': False,
                           'reinspection_set_id': False})
                rec.message_post(body='Re-inspection %s failed - NCR reopened for a '
                                      'fresh disposition.' % iset.name)

    def _do_scrap(self):
        """FR-NCR-04 - M Report to approval; posting only after approval."""
        self.ensure_one()
        self.mr_name = self.env['ir.sequence'].next_by_code('quality.mr')
        self.mr_state = 'to_approve'
        self.state = 'open'  # remains open until MR approved & posted
        self.message_post(body='M Report %s generated - awaiting approval '
                              '(loss %s %s).' % (self.mr_name, self.total_loss,
                                                 self.currency_id.name))

    def action_mr_approve_qm(self):
        self._check_manager()
        for rec in self.filtered(lambda r: r.mr_state == 'to_approve'):
            rec._check_accountability()
            rec.qm_approver_id = self.env.user
            rec.qm_approve_date = fields.Datetime.now()
            if not rec.plant_required:
                rec._mr_post()
            elif rec.plant_approver_id:
                rec._mr_post()
            else:
                rec.message_post(body='QM approved; Plant-level approval pending '
                                      '(loss above limit).')

    def action_mr_approve_plant(self):
        if not self.env.user.has_group(
                'custom_quality_inspection.group_quality_plant'):
            raise UserError('Plant-level approver group required.')
        for rec in self.filtered(lambda r: r.mr_state == 'to_approve'):
            rec.plant_approver_id = self.env.user
            rec.plant_approve_date = fields.Datetime.now()
            if rec.qm_approver_id:
                rec._mr_post()

    def _mr_post(self):
        """Approval complete -> stock.scrap from NC location (FR-NCR-04)."""
        for rec in self:
            rec.mr_state = 'approved'
            rec._check_capa_gate()
            loc = rec.company_id.quality_nc_location_id
            scrap_vals = {'product_id': rec.product_id.id,
                          'scrap_qty': rec.qty or 1.0,
                          'product_uom_id': rec.product_id.uom_id.id,
                          'company_id': rec.company_id.id,
                          'origin': rec.mr_name}
            if loc:
                scrap_vals['location_id'] = loc.id
            lot = rec.serial_ids[:1] or rec.lot_id
            if lot:
                scrap_vals['lot_id'] = lot.id
            scrap = self.env['stock.scrap'].create(scrap_vals)
            try:
                scrap.with_context(quality_bypass=True).action_validate()
            except Exception as exc:  # inventory shortfall etc. - keep MR approved
                rec.message_post(body='Scrap %s created but not validated: %s'
                                      % (scrap.name, exc))
            rec.scrap_id = scrap
            rec._close()

    def _do_rtv(self):
        """FR-NCR-05 - vendor return referencing the origin receipt."""
        self.ensure_one()
        pick = self.picking_id
        if not pick:
            raise UserError('No origin receipt on %s for Return to Vendor.' % self.name)
        wiz = self.env['stock.return.picking'].with_context(
            active_id=pick.id, active_ids=pick.ids,
            active_model='stock.picking').create({})
        for line in wiz.product_return_moves:
            line.quantity = self.qty if line.product_id == self.product_id else 0.0
        res = wiz.action_create_returns() if hasattr(wiz, 'action_create_returns') \
            else wiz.create_returns()
        self.return_picking_id = self.env['stock.picking'].browse(res.get('res_id'))
        self.message_post(body='Vendor return %s created.' % self.return_picking_id.name)

    def _do_deviation(self):
        """FR-NCR-06 - concession requires the Plant-level approver."""
        self.ensure_one()
        if not self.env.user.has_group(
                'custom_quality_inspection.group_quality_plant'):
            self.state = 'open'
            raise UserError('Deviation requires the designated Plant-level approver '
                            '(FR-NCR-02).')
        if not self.dev_justification:
            self.state = 'open'
            raise UserError('Record the deviation justification first.')
        self._check_capa_gate()
        self.dev_name = self.env['ir.sequence'].next_by_code('quality.dev')
        self.dev_approver_id = self.env.user
        self.dev_qty = self.dev_qty or self.qty
        (self.serial_ids | self.lot_id).write({'quality_state': 'accepted'})
        self.message_post(body='Concession %s approved - %s unit(s) released '
                              'use-as-is; lot flagged.' % (self.dev_name, self.dev_qty))
        self._close()

    def _check_capa_gate(self):
        for rec in self:
            if rec.capa_required and not rec.capa_ids:
                raise UserError('FR-CAPA-03: a linked CAPA is required before closing '
                                '%s (disposition %s).' % (rec.name, rec.disposition))

    def _close(self):
        for rec in self:
            rec._check_capa_gate()
            rec.state = 'closed'
            rec.message_post(body='NCR closed.')

    def action_close(self):
        for rec in self:
            if rec.disposition == 'rework' and (
                    not rec.reinspection_set_id
                    or rec.reinspection_set_id.state not in
                    ('accepted', 'partially_accepted')):
                raise UserError('FR-NCR-07: rework NCRs close only on accepted '
                                're-inspection.')
            if rec.disposition == 'rtv' and rec.return_picking_id.state != 'done':
                raise UserError('Vendor return not yet validated.')
            rec._close()

    def action_cancel(self):
        self._check_manager()
        self.write({'state': 'cancel'})

    def action_create_capa(self):
        self.ensure_one()
        capa = self.env['quality.capa'].create({
            'ncr_ids': [(6, 0, self.ids)],
            'problem': 'From %s: %s x %s' % (self.name, self.qty,
                                             self.product_id.display_name),
            'company_id': self.company_id.id})
        self.capa_ids = [(4, capa.id)]
        return {'type': 'ir.actions.act_window', 'res_model': 'quality.capa',
                'res_id': capa.id, 'view_mode': 'form'}

    @api.model
    def check_repeat_defects(self, product, defects, company):
        """FR-ACC-05 - repeat-defect escalation."""
        n = 3
        notify = company.quality_notify_user_id
        for defect in defects:
            count = self.search_count([
                ('product_id', '=', product.id), ('defect_ids', 'in', defect.id),
                ('company_id', '=', company.id),
                ('create_date', '>=', fields.Datetime.subtract(
                    fields.Datetime.now(), days=90))])
            if count >= n and notify:
                recs = self.search([('product_id', '=', product.id),
                                    ('defect_ids', 'in', defect.id)], limit=1)
                recs.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=notify.id,
                    summary='Repeat defect %s on %s (%s in 90 days) - CAPA advised'
                            % (defect.code, product.display_name, count))

    def write(self, vals):
        res = super().write(vals)
        if 'defect_ids' in vals:
            for rec in self:
                rec.check_repeat_defects(rec.product_id, rec.defect_ids, rec.company_id)
        return res
