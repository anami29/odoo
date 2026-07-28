# -*- coding: utf-8 -*-
import base64
import io
import calendar
from datetime import date, datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ZPurchaseRegisterWizard(models.TransientModel):
    _name = 'z.purchase.register.wizard'
    _description = 'Z Purchase Register Wizard'

    period_mode = fields.Selection([
        ('custom', 'Custom Dates'),
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('year', 'Fiscal Year')
    ], string='Period Mode', default='custom', required=True)

    fiscal_year = fields.Selection('_get_fiscal_years', string='Fiscal Year')
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Month')
    quarter = fields.Selection([
        ('q1', 'Q1'), ('q2', 'Q2'), ('q3', 'Q3'), ('q4', 'Q4')
    ], string='Quarter')

    date_from = fields.Date(string='Date From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.context_today)

    basis = fields.Selection([
        ('accounting', 'Accounting Date'),
        ('bill', 'Bill Date')
    ], string='Basis', default='accounting', required=True)

    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company)
    
    file = fields.Binary(string='File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    @api.model
    def _get_fiscal_years(self):
        years = []
        current_year = date.today().year
        for y in range(current_year - 3, current_year + 3):
            years.append((f"{y}-{str(y+1)[2:]}", f"FY {y}-{str(y+1)[2:]}"))
        return years

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise UserError(_("Start Date cannot be greater than End Date."))

    @api.onchange('period_mode', 'fiscal_year', 'month', 'quarter')
    def _onchange_period(self):
        if self.period_mode != 'custom':
            self.date_from, self.date_to = self._resolve_period()

    def _resolve_period(self):
        self.ensure_one()
        if not self.fiscal_year:
            return self.date_from, self.date_to
        
        # Read fiscal year settings from company
        last_month = self.company_id.fiscalyear_last_month or 3
        last_day = self.company_id.fiscalyear_last_day or 31
        start_month = (last_month % 12) + 1

        start_year = int(self.fiscal_year.split('-')[0])
        end_year = start_year + 1

        if self.period_mode == 'year':
            date_from = date(start_year, start_month, 1)
            date_to = date(end_year, last_month, last_day)
            return date_from, date_to

        elif self.period_mode == 'quarter':
            if not self.quarter:
                return self.date_from, self.date_to
            q = int(self.quarter[1])
            m1 = start_month + (q - 1) * 3
            m3 = m1 + 2
            
            cal_month_start = ((m1 - 1) % 12) + 1
            cal_year_start = start_year + ((m1 - 1) // 12)
            
            cal_month_end = ((m3 - 1) % 12) + 1
            cal_year_end = start_year + ((m3 - 1) // 12)
            
            _, last_day_q = calendar.monthrange(cal_year_end, cal_month_end)
            return date(cal_year_start, cal_month_start, 1), date(cal_year_end, cal_month_end, last_day_q)

        elif self.period_mode == 'month':
            if not self.month:
                return self.date_from, self.date_to
            m = int(self.month)
            cal_year = end_year if m < start_month else start_year
            _, last_day_m = calendar.monthrange(cal_year, m)
            return date(cal_year, m, 1), date(cal_year, m, last_day_m)

        return self.date_from, self.date_to

    def _is_rc_tax(self, tax, move):
        name_lower = (tax.name or '').lower()
        if 'rcm' in name_lower or 'reverse charge' in name_lower:
            return True
        return False

    def doc_rounding(self, move):
        rounding_lines = move.line_ids.filtered(lambda l: l.display_type == 'rounding')
        if rounding_lines:
            return abs(sum(rounding_lines.mapped('balance')))
        if move.invoice_cash_rounding_id:
            return abs(move.amount_total - sum(line.price_total for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')))
        return 0.0

    def generate_report(self):
        self.ensure_one()
        # Resolve basis field
        basis_field = 'date' if self.basis == 'accounting' else 'invoice_date'
        domain = [
            ('move_type', 'in', ('in_invoice', 'in_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            (basis_field, '>=', self.date_from),
            (basis_field, '<=', self.date_to)
        ]
        moves = self.env['account.move'].search(domain, order='date desc, name desc')

        # Excel Setup
        output = io.BytesIO()
        import xlsxwriter
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Z Purchase Register Report')

        # Formatting
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#DBE9FA',
            'font_name': 'Calibri',
            'font_size': 11
        })
        text_format = workbook.add_format({
            'font_name': 'Calibri',
            'font_size': 11
        })
        amount_format = workbook.add_format({
            'font_name': 'Calibri',
            'font_size': 11,
            'num_format': '#,##0.00'
        })
        date_format = workbook.add_format({
            'font_name': 'Calibri',
            'font_size': 11,
            'num_format': 'yyyy-mm-dd'
        })

        # Columns definition (Purchase Specific)
        headers = [
            'Company', 'Bill Number', 'Bill Date', 'Accounting Date', 'Vendor Name',
            'Vendor Tax ID', 'Vendor GST Treatment', 'Journal Name', 'Reference Number', 'Vendor PAN',
            'Bill Description', 'Account Name', 'HSN Code', 'Product HSN/SAC Description', 'Unit of Measure',
            'Quantity', 'Unit Price', 'Discount (%)', 'Applied Taxes', 'Tax Rate (GST %)',
            'Subtotal Amount', 'Credit Amount', 'Debit Amount', 'CGST Amount', 'SGST Amount',
            'IGST Amount', 'TCS Amount', 'Cash Rounding Adjustment', 'Total Amount', 'CGST RC Amount',
            'SGST RC Amount', 'IGST RC Amount', 'TDS Amount', 'CGST TDS Amount', 'SGST TDS Amount'
        ]

        for col_num, header in enumerate(headers):
            sheet.write(0, col_num, header, header_format)

        row_num = 1
        for move in moves:
            sign = 1.0 if move.move_type == 'in_invoice' else -1.0
            
            # 1. Company
            company_name = move.company_id.name or ''
            # 2. Bill Number
            bill_num = move.name or ''
            # 3. Bill Date
            bill_date = move.invoice_date.strftime('%Y-%m-%d') if move.invoice_date else ''
            # 4. Accounting Date
            accounting_date = move.date.strftime('%Y-%m-%d') if move.date else ''
            # 5. Vendor Name
            vendor_name = move.partner_id.name or ''
            # 6. Vendor Tax ID (GSTIN)
            vendor_tax_id = move.commercial_partner_id.vat or ''
            # 7. Vendor GST Treatment
            gst_treatment = ''
            if hasattr(move, 'l10n_in_gst_treatment') and move.l10n_in_gst_treatment:
                gst_treatment = dict(self.env['account.move'].fields_get(['l10n_in_gst_treatment'])['l10n_in_gst_treatment']['selection']).get(move.l10n_in_gst_treatment, '')
            # 8. Journal Name
            journal_name = move.journal_id.name or ''
            # 9. Reference Number
            ref_num = move.ref or ''
            # 10. Vendor PAN
            vendor_pan = ''
            partner = move.commercial_partner_id
            if hasattr(partner, 'l10n_in_pan') and partner.l10n_in_pan:
                vendor_pan = partner.l10n_in_pan
            elif partner.vat and len(partner.vat) >= 12:
                vendor_pan = partner.vat[2:12]

            first_line = True
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                # 11. Description
                description = line.name or ''
                # 12. Account Name
                account_name = line.account_id.name or ''
                # 13. HSN Code
                hsn_code = line.l10n_in_hsn_code or ''
                # 14. Product HSN/SAC Description
                hsn_desc = ''
                if hasattr(line.product_id, 'l10n_in_hsn_description') and line.product_id.l10n_in_hsn_description:
                    hsn_desc = line.product_id.l10n_in_hsn_description
                elif hasattr(line.product_id.product_tmpl_id, 'l10n_in_hsn_description') and line.product_id.product_tmpl_id.l10n_in_hsn_description:
                    hsn_desc = line.product_id.product_tmpl_id.l10n_in_hsn_description
                # 15. Unit of Measure
                uom = line.product_uom_id.name or ''
                # 16. Quantity
                quantity = line.quantity or 0.0
                # 17. Unit Price
                unit_price = line.price_unit or 0.0
                # 18. Discount
                discount = line.discount or 0.0
                # 19. Applied Taxes
                applied_taxes = ",".join(line.tax_ids.mapped('name'))
                
                # 20. Tax Rate (GST %)
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
                    tax_rate_gst = f"IGST {int(sum(igst_rates))}"
                elif gst_rates:
                    tax_rate_gst = f"GST {int(sum(gst_rates))}"

                # Calculate Subtotal in Company Currency
                if line.currency_id == move.company_id.currency_id:
                    company_subtotal = line.price_subtotal
                else:
                    company_subtotal = abs(line.balance)
                
                subtotal_amount = round(sign * company_subtotal, 2)
                
                # Document exchange rate
                rate = abs(line.balance) / abs(line.price_subtotal) if line.price_subtotal else 1.0

                # Compute Taxes using Odoo engine
                base = line.price_unit * (1 - line.discount / 100.0)
                res_taxes = line.tax_ids.compute_all(
                    base, currency=move.currency_id, quantity=line.quantity,
                    product=line.product_id, partner=move.partner_id,
                    is_refund=(move.move_type == 'in_refund')
                )

                cgst = sgst = igst = tcs = tds = rc_cgst = rc_sgst = rc_igst = tds_cgst = tds_sgst = 0.0
                for tax_item in res_taxes['taxes']:
                    tax_rec = self.env['account.tax'].browse(tax_item['id'])
                    t_group = tax_rec.tax_group_id.name.upper() if tax_rec.tax_group_id else ''
                    
                    # Compute tax amount in company currency
                    t_amount_cc = tax_item['amount'] * rate
                    t_amount_signed = round(sign * t_amount_cc, 2)

                    if self._is_rc_tax(tax_rec, move):
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

                # 22. Credit Amount, 23. Debit Amount
                credit_amount = subtotal_amount if move.move_type == 'in_invoice' else 0.0
                debit_amount = subtotal_amount if move.move_type == 'in_refund' else 0.0

                # 28. Cash Rounding
                rounding = round(sign * self.doc_rounding(move), 2) if first_line else 0.0

                # 29. Total Amount
                total_amount = round(subtotal_amount + cgst + sgst + igst + tcs + tds + rounding, 2)

                # Write row data
                sheet.write(row_num, 0, company_name, text_format)
                sheet.write(row_num, 1, bill_num, text_format)
                sheet.write(row_num, 2, bill_date, text_format)
                sheet.write(row_num, 3, accounting_date, text_format)
                sheet.write(row_num, 4, vendor_name, text_format)
                sheet.write(row_num, 5, vendor_tax_id, text_format)
                sheet.write(row_num, 6, gst_treatment, text_format)
                sheet.write(row_num, 7, journal_name, text_format)
                sheet.write(row_num, 8, ref_num, text_format)
                sheet.write(row_num, 9, vendor_pan, text_format)
                sheet.write(row_num, 10, description, text_format)
                sheet.write(row_num, 11, account_name, text_format)
                sheet.write(row_num, 12, hsn_code, text_format)
                sheet.write(row_num, 13, hsn_desc, text_format)
                sheet.write(row_num, 14, uom, text_format)
                sheet.write(row_num, 15, quantity, amount_format)
                sheet.write(row_num, 16, unit_price, amount_format)
                sheet.write(row_num, 17, discount, amount_format)
                sheet.write(row_num, 18, applied_taxes, text_format)
                sheet.write(row_num, 19, tax_rate_gst, text_format)
                sheet.write(row_num, 20, subtotal_amount, amount_format)
                sheet.write(row_num, 21, credit_amount, amount_format)
                sheet.write(row_num, 22, debit_amount, amount_format)
                sheet.write(row_num, 23, cgst, amount_format)
                sheet.write(row_num, 24, sgst, amount_format)
                sheet.write(row_num, 25, igst, amount_format)
                sheet.write(row_num, 26, tcs, amount_format)
                sheet.write(row_num, 27, rounding, amount_format)
                sheet.write(row_num, 28, total_amount, amount_format)
                sheet.write(row_num, 29, rc_cgst, amount_format)
                sheet.write(row_num, 30, rc_sgst, amount_format)
                sheet.write(row_num, 31, rc_igst, amount_format)
                sheet.write(row_num, 32, tds, amount_format)
                sheet.write(row_num, 33, tds_cgst, amount_format)
                sheet.write(row_num, 34, tds_sgst, amount_format)

                first_line = False
                row_num += 1

        workbook.close()
        file_data = base64.b64encode(output.getvalue())
        output.close()

        # Build filename
        date_from_str = self.date_from.strftime('%d_%m_%Y')
        date_to_str = self.date_to.strftime('%d_%m_%Y')
        filename = f"Z Purchase Register Report - {date_from_str} to {date_to_str}.xlsx"

        self.write({
            'file': file_data,
            'file_name': filename
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/file/{self.file_name}?download=true',
            'target': 'self'
        }
