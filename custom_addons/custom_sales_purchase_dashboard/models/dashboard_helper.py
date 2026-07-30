# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, datetime
import calendar

class CustomSalesPurchaseDashboard(models.AbstractModel):
    _name = 'custom.sales.purchase.dashboard'
    _description = 'Sales and Purchase Dashboard Helper'

    def _is_rc_tax(self, tax):
        name_lower = (tax.name or '').lower()
        if 'rcm' in name_lower or 'reverse charge' in name_lower:
            return True
        return False

    def _get_doc_rounding(self, move):
        rounding_lines = move.line_ids.filtered(lambda l: l.display_type == 'rounding')
        if rounding_lines:
            return abs(sum(rounding_lines.mapped('balance')))
        if move.invoice_cash_rounding_id:
            return abs(move.amount_total - sum(line.price_total for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')))
        return 0.0

    @api.model
    def retrieve_dashboard_data(self, params):
        dashboard_type = params.get('type', 'sales')  # 'sales' or 'purchase'
        basis = params.get('basis', 'accounting')  # 'accounting' or 'invoice'/'bill'
        date_from_str = params.get('date_from')
        date_to_str = params.get('date_to')
        limit = int(params.get('limit', 10))
        offset = int(params.get('offset', 0))
        search_query = params.get('search', '')

        # Fallback dates if empty
        if date_from_str:
            date_from = fields.Date.from_string(date_from_str)
        else:
            date_from = date.today().replace(day=1)
        if date_to_str:
            date_to = fields.Date.from_string(date_to_str)
        else:
            date_to = date.today()

        # Build Domain
        move_types = ('out_invoice', 'out_refund') if dashboard_type == 'sales' else ('in_invoice', 'in_refund')
        basis_field = 'date' if basis == 'accounting' else 'invoice_date'
        
        domain = [
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id),
            (basis_field, '>=', date_from),
            (basis_field, '<=', date_to)
        ]
        
        if search_query:
            domain += ['|', ('name', 'ilike', search_query), ('partner_id.name', 'ilike', search_query)]

        moves = self.env['account.move'].search(domain, order='date desc, name desc')

        # Raw lines extraction for KPI, graphs, and tables
        raw_lines = []
        doc_count = len(moves)
        
        total_subtotal = 0.0
        total_cgst = 0.0
        total_sgst = 0.0
        total_igst = 0.0
        total_tcs = 0.0
        total_tds = 0.0
        total_rounding = 0.0
        total_amount = 0.0

        monthly_trend_data = {}
        gst_rate_data = {}
        partner_data = {}

        for move in moves:
            sign = 1.0 if move.move_type in ('out_invoice', 'in_invoice') else -1.0
            
            # Format dates
            inv_date_str = move.invoice_date.strftime('%Y-%m-%d') if move.invoice_date else ''
            acc_date_str = move.date.strftime('%Y-%m-%d') if move.date else ''
            
            # Extract Partner info
            partner_name = move.partner_id.name or ''
            partner_vat = move.commercial_partner_id.vat or ''
            
            # GST Treatment
            gst_treatment_label = ''
            if hasattr(move, 'l10n_in_gst_treatment') and move.l10n_in_gst_treatment:
                sel = dict(self.env['account.move'].fields_get(['l10n_in_gst_treatment'])['l10n_in_gst_treatment']['selection'])
                gst_treatment_label = sel.get(move.l10n_in_gst_treatment, '')

            # Resolve PAN
            partner_pan = ''
            partner_rec = move.commercial_partner_id
            if hasattr(partner_rec, 'l10n_in_pan') and partner_rec.l10n_in_pan:
                partner_pan = partner_rec.l10n_in_pan
            elif partner_vat and len(partner_vat) >= 12:
                partner_pan = partner_vat[2:12]

            # Document-level cash rounding
            doc_round = round(sign * self._get_doc_rounding(move), 2)
            total_rounding += doc_round
            
            first_line = True
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                description = line.name or ''
                account_name = line.account_id.name or ''
                hsn_code = line.l10n_in_hsn_code or ''
                uom_name = line.product_uom_id.name or ''
                qty = line.quantity or 0.0
                price_unit = line.price_unit or 0.0
                discount = line.discount or 0.0
                applied_taxes = ",".join(line.tax_ids.mapped('name'))

                # Tax Rate aggregation
                tax_rate_gst = ''
                gst_rates = []
                igst_rates = []
                for tax in line.tax_ids:
                    group_name = tax.tax_group_id.name.upper() if tax.tax_group_id else ''
                    if 'CGST' in group_name or 'SGST' in group_name:
                        gst_rates.append(tax.amount)
                    elif 'IGST' in group_name:
                        igst_rates.append(tax.amount)
                if igst_rates:
                    tax_rate_gst = f"IGST {int(sum(igst_rates))}%"
                elif gst_rates:
                    tax_rate_gst = f"GST {int(sum(gst_rates))}%"
                else:
                    tax_rate_gst = 'Exempt/Nil'

                # Calculate Subtotal in Company Currency
                if line.currency_id == move.company_id.currency_id:
                    company_subtotal = line.price_subtotal
                else:
                    company_subtotal = abs(line.balance)
                
                subtotal_amount = round(sign * company_subtotal, 2)
                total_subtotal += subtotal_amount

                # Exchange rate for line
                rate = abs(line.balance) / abs(line.price_subtotal) if line.price_subtotal else 1.0

                # Compute Taxes using Odoo engine
                base = line.price_unit * (1 - line.discount / 100.0)
                res_taxes = line.tax_ids.compute_all(
                    base, currency=move.currency_id, quantity=line.quantity,
                    product=line.product_id, partner=move.partner_id,
                    is_refund=(move.move_type in ('out_refund', 'in_refund'))
                )

                cgst = sgst = igst = tcs = tds = rc_cgst = rc_sgst = rc_igst = tds_cgst = tds_sgst = 0.0
                for tax_item in res_taxes['taxes']:
                    tax_rec = self.env['account.tax'].browse(tax_item['id'])
                    t_group = tax_rec.tax_group_id.name.upper() if tax_rec.tax_group_id else ''
                    
                    t_amount_cc = tax_item['amount'] * rate
                    t_amount_signed = round(sign * t_amount_cc, 2)

                    if self._is_rc_tax(tax_rec):
                        if 'CGST' in t_group:
                            rc_cgst += t_amount_signed
                        elif 'SGST' in t_group:
                            rc_sgst += t_amount_signed
                        elif 'IGST' in t_group:
                            rc_igst += t_amount_signed
                    else:
                        if 'CGST' in t_group:
                            if 'TDS' in t_group or 'GST TDS' in t_group or 'GST-TDS' in t_group:
                                tds_cgst += t_amount_signed
                            else:
                                cgst += t_amount_signed
                        elif 'SGST' in t_group:
                            if 'TDS' in t_group or 'GST TDS' in t_group or 'GST-TDS' in t_group:
                                tds_sgst += t_amount_signed
                            else:
                                sgst += t_amount_signed
                        elif 'IGST' in t_group:
                            igst += t_amount_signed
                        elif 'TCS' in t_group:
                            tcs += t_amount_signed
                        elif 'TDS' in t_group:
                            tds += t_amount_signed
                        elif 'GST TDS' in t_group or 'GST-TDS' in t_group:
                            if 'CGST' in tax_rec.name.upper():
                                tds_cgst += t_amount_signed
                            elif 'SGST' in tax_rec.name.upper():
                                tds_sgst += t_amount_signed
                            else:
                                tds += t_amount_signed

                total_cgst += cgst
                total_sgst += sgst
                total_igst += igst
                total_tcs += tcs
                total_tds += (tds + tds_cgst + tds_sgst)

                # Line rounding
                line_rounding = doc_round if first_line else 0.0

                # Line total
                line_total = round(subtotal_amount + cgst + sgst + igst + tcs + tds + tds_cgst + tds_sgst + line_rounding, 2)
                total_amount += line_total

                # Buckets for UI Detailed List
                raw_lines.append({
                    'id': line.id,
                    'name': move.name,
                    'invoice_date': inv_date_str,
                    'accounting_date': acc_date_str,
                    'partner_name': partner_name,
                    'partner_vat': partner_vat,
                    'gst_treatment': gst_treatment_label,
                    'partner_pan': partner_pan,
                    'description': description,
                    'account_name': account_name,
                    'hsn_code': hsn_code,
                    'uom': uom_name,
                    'qty': qty,
                    'price_unit': price_unit,
                    'discount': discount,
                    'applied_taxes': applied_taxes,
                    'tax_rate_gst': tax_rate_gst,
                    'subtotal': subtotal_amount,
                    'cgst': cgst,
                    'sgst': sgst,
                    'igst': igst,
                    'tcs': tcs,
                    'tds': (tds + tds_cgst + tds_sgst),
                    'rounding': line_rounding,
                    'total': line_total,
                    'rc_cgst': rc_cgst,
                    'rc_sgst': rc_sgst,
                    'rc_igst': rc_igst,
                })

                # Aggregations for Graphs
                # 1. Monthly Trend
                month_key = move.date.strftime('%Y-%m')
                monthly_trend_data[month_key] = monthly_trend_data.get(month_key, 0.0) + subtotal_amount
                
                # 2. GST Rate Distribution
                gst_rate_data[tax_rate_gst] = gst_rate_data.get(tax_rate_gst, 0.0) + subtotal_amount

                # 3. Top Partners
                partner_data[partner_name] = partner_data.get(partner_name, 0.0) + subtotal_amount

                first_line = False

        # Format Graph 1: Monthly Trend
        sorted_months = sorted(monthly_trend_data.keys())
        monthly_trend = {
            'labels': sorted_months,
            'data': [round(monthly_trend_data[m], 2) for m in sorted_months]
        }

        # Format Graph 2: GST Rate Distribution
        gst_rates_labels = list(gst_rate_data.keys())
        gst_rate_dist = {
            'labels': gst_rates_labels,
            'data': [round(gst_rate_data[r], 2) for r in gst_rates_labels]
        }

        # Format Graph 3: Top Partners (top 5, rest as Others)
        sorted_partners = sorted(partner_data.items(), key=lambda x: abs(x[1]), reverse=True)
        top_partners_labels = [p[0] for p in sorted_partners[:5]]
        top_partners_data = [round(p[1], 2) for p in sorted_partners[:5]]
        
        others_sum = sum(p[1] for p in sorted_partners[5:])
        if others_sum:
            top_partners_labels.append('Others')
            top_partners_data.append(round(others_sum, 2))

        partner_dist = {
            'labels': top_partners_labels,
            'data': top_partners_data
        }

        # Tabular slice
        total_records = len(raw_lines)
        sliced_lines = raw_lines[offset:offset+limit]

        return {
            'kpis': {
                'total_subtotal': round(total_subtotal, 2),
                'total_cgst': round(total_cgst, 2),
                'total_sgst': round(total_sgst, 2),
                'total_igst': round(total_igst, 2),
                'total_tcs': round(total_tcs, 2),
                'total_tds': round(total_tds, 2),
                'total_rounding': round(total_rounding, 2),
                'total_amount': round(total_amount, 2),
                'doc_count': doc_count,
            },
            'graphs': {
                'monthly_trend': monthly_trend,
                'gst_rate_dist': gst_rate_dist,
                'partner_dist': partner_dist,
            },
            'table': {
                'records': sliced_lines,
                'total_count': total_records,
            }
        }

    @api.model
    def check_wizard_availability(self):
        """Check if custom sales and purchase register report wizards are installed"""
        return {
            'sales': bool(self.env['ir.model'].search([('model', '=', 'z.sales.register.wizard')])),
            'purchase': bool(self.env['ir.model'].search([('model', '=', 'z.purchase.register.wizard')]))
        }

    @api.model
    def trigger_excel_export(self, params):
        dashboard_type = params.get('type', 'sales')
        basis = params.get('basis', 'accounting')
        date_from_str = params.get('date_from')
        date_to_str = params.get('date_to')

        if date_from_str:
            date_from = fields.Date.from_string(date_from_str)
        else:
            date_from = date.today().replace(day=1)
        if date_to_str:
            date_to = fields.Date.from_string(date_to_str)
        else:
            date_to = date.today()

        if dashboard_type == 'sales':
            wizard_model = 'z.sales.register.wizard'
            basis_val = 'accounting' if basis == 'accounting' else 'invoice'
        else:
            wizard_model = 'z.purchase.register.wizard'
            basis_val = 'accounting' if basis == 'accounting' else 'bill'

        # Check if model exists
        if not self.env['ir.model'].search([('model', '=', wizard_model)]):
            return {
                'warning': _("The Excel export module is not installed. Please install 'custom_sales_register_report' or 'custom_purchase_register_report'.")
            }

        wizard = self.env[wizard_model].create({
            'period_mode': 'custom',
            'date_from': date_from,
            'date_to': date_to,
            'basis': basis_val,
            'company_id': self.env.company.id
        })
        
        return wizard.generate_report()
