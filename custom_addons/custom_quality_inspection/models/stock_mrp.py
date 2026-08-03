# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from .inspection import OPEN_SET_STATES


class StockLot(models.Model):
    _inherit = 'stock.lot'

    quality_state = fields.Selection([
        ('pending', 'Quality Pending'), ('accepted', 'Accepted'),
        ('rejected', 'Rejected'), ('partial', 'Partially Accepted')],
        string='Quality Status', tracking=True, copy=False,
        help='Set by inspection sets; empty = not under quality control.')


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _quality_blocked_lots(self):
        """Lots on this move that must not leave quality hold."""
        self.ensure_one()
        lots = self.move_line_ids.mapped('lot_id')
        return lots.filtered(lambda l: l.quality_state in ('pending', 'rejected'))

    def _action_done(self, cancel_backorder=False):
        # ---- gate BEFORE validation (FR-TRG-03/04) -------------------------
        if not self.env.context.get('quality_bypass'):
            for move in self:
                gated = (move.picking_id.picking_type_id.code == 'outgoing'
                         or bool(move.raw_material_production_id))
                if not gated:
                    continue
                blocked = move._quality_blocked_lots()
                if blocked:
                    raise UserError(
                        'Quality gate (FR-TRG-03): lot/serial %s of %s is %s. '
                        'Release requires an accepted inspection; the only '
                        'sanctioned bypass is an approved Deviation (FR-TRG-07).'
                        % (', '.join(blocked.mapped('name')),
                           move.product_id.display_name,
                           ', '.join(set(blocked.mapped('quality_state')))))
        res = super()._action_done(cancel_backorder=cancel_backorder)
        # ---- trigger AFTER receipt validation (FR-TRG-01) ------------------
        Plan = self.env['quality.inspection.plan']
        Set = self.env['quality.inspection.set']
        for move in self:
            if move.state != 'done':
                continue
            picking = move.picking_id
            if not picking or picking.picking_type_id.code != 'incoming':
                continue
            plan = Plan.find_plan(move.product_id, 'incoming',
                                  company=move.company_id)
            if not plan:
                continue
            partner = picking.partner_id
            if move.product_id.tracking == 'serial':
                serials = move.move_line_ids.mapped('lot_id')
                if not serials:
                    continue
                existing = Set.search_count([('picking_id', '=', picking.id),
                                             ('serial_ids', 'in', serials.ids)])
                if existing:
                    continue
                Set.create_for(plan, move.product_id, len(serials),
                               serials=serials, picking=picking, partner=partner)
            else:
                for ml in move.move_line_ids:
                    lot = ml.lot_id
                    qty = ml.quantity
                    if not qty:
                        continue
                    if lot and Set.search_count([('picking_id', '=', picking.id),
                                                 ('lot_id', '=', lot.id)]):
                        continue
                    Set.create_for(plan, move.product_id, qty, lot=lot,
                                   picking=picking, partner=partner)
        return res


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    inspection_set_ids = fields.One2many('quality.inspection.set', 'workorder_id')

    def button_start(self):
        """FR-TRG-02 - block start while earlier stage inspections are open."""
        for wo in self:
            open_sets = self.env['quality.inspection.set'].search([
                ('production_id', '=', wo.production_id.id),
                ('workorder_id', '!=', wo.id),
                ('state', 'in', list(OPEN_SET_STATES))])
            if open_sets:
                raise UserError(
                    'Quality gate (FR-TRG-02): open in-process inspection %s must '
                    'be completed before starting %s.'
                    % (', '.join(open_sets.mapped('name')), wo.name))
        return super().button_start()

    def button_finish(self):
        res = super().button_finish()
        Plan = self.env['quality.inspection.plan']
        Set = self.env['quality.inspection.set']
        for wo in self:
            prod = wo.production_id
            plan = Plan.find_plan(prod.product_id, 'inprocess',
                                  operation=wo.operation_id, company=wo.company_id)
            if not plan:
                continue
            if Set.search_count([('workorder_id', '=', wo.id)]):
                continue
            Set.create_for(plan, prod.product_id, prod.product_qty,
                           lot=prod.lot_producing_id, production=prod, workorder=wo)
        return res


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    rework_ncr_id = fields.Many2one('quality.ncr', string='Rework of NCR',
                                    readonly=True, copy=False)
    inspection_set_ids = fields.One2many('quality.inspection.set', 'production_id')

    def button_mark_done(self):
        Plan = self.env['quality.inspection.plan']
        Set = self.env['quality.inspection.set']
        for prod in self:
            if prod.rework_ncr_id:
                continue  # rework MOs re-inspect via the NCR hook below
            plan = Plan.find_plan(prod.product_id, 'final', company=prod.company_id)
            if not plan:
                continue
            fqc = Set.search([('production_id', '=', prod.id),
                              ('stage', '=', 'final')], limit=1, order='id desc')
            if not fqc:
                fqc = Set.create_for(plan, prod.product_id,
                                     prod.qty_producing or prod.product_qty,
                                     lot=prod.lot_producing_id, production=prod)
                raise UserError('Quality gate (FR-TRG-02): FQC set %s created - '
                                'complete the final inspection before closing %s.'
                                % (fqc.name, prod.name))
            if fqc.state in OPEN_SET_STATES:
                raise UserError('Quality gate: FQC set %s is still open on %s.'
                                % (fqc.name, prod.name))
            if fqc.state == 'rejected':
                raise UserError('FQC set %s is rejected - disposition via NCR '
                                'before closing %s.' % (fqc.name, prod.name))
        res = super().button_mark_done()
        for prod in self:
            if prod.rework_ncr_id and prod.state == 'done':
                prod.rework_ncr_id.trigger_reinspection()
        return res


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    ncr_id = fields.Many2one('quality.ncr', string='NCR', readonly=True, copy=False)

    def write(self, vals):
        was = {r.id: r.state for r in self}
        res = super().write(vals)
        if vals.get('state') == 'done':
            for rec in self:
                if rec.ncr_id and was.get(rec.id) != 'done':
                    rec.ncr_id.trigger_reinspection()
        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    inspection_set_ids = fields.One2many('quality.inspection.set', 'picking_id')
    inspection_set_count = fields.Integer(compute='_compute_set_count')

    def _compute_set_count(self):
        for pick in self:
            pick.inspection_set_count = len(pick.inspection_set_ids)

    def action_view_inspection_sets(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Inspection Sets',
                'res_model': 'quality.inspection.set', 'view_mode': 'list,form',
                'domain': [('picking_id', '=', self.id)]}

    def button_validate(self):
        res = super().button_validate()
        # NCR RTV closure hook (FR-NCR-05)
        ncrs = self.env['quality.ncr'].search([
            ('return_picking_id', 'in', self.ids), ('state', '!=', 'closed')])
        for ncr in ncrs:
            if ncr.return_picking_id.state == 'done':
                ncr.message_post(body='Vendor return %s validated.'
                                      % ncr.return_picking_id.name)
        return res
