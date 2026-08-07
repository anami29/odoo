# -*- coding: utf-8 -*-
import io

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_date

LIQUIDITY_TYPES = ('asset_cash', 'liability_credit_card')

PL_TYPES = (
    'income', 'income_other',
    'expense', 'expense_depreciation', 'expense_direct_cost',
)

BS_TYPES = (
    'asset_receivable', 'asset_cash', 'asset_current', 'asset_prepayments',
    'asset_fixed', 'asset_non_current',
    'liability_payable', 'liability_credit_card', 'liability_current',
    'liability_non_current',
    'equity', 'equity_unaffected',
)

# Fallback classification of cash-flow counterpart accounts when no
# cash-flow tag (Operating / Investing / Financing) is set on the account.
CF_FALLBACK = {
    'asset_receivable': 'operating',
    'liability_payable': 'operating',
    'asset_current': 'operating',
    'asset_prepayments': 'operating',
    'liability_current': 'operating',
    'income': 'operating',
    'income_other': 'operating',
    'expense': 'operating',
    'expense_depreciation': 'operating',
    'expense_direct_cost': 'operating',
    'asset_fixed': 'investing',
    'asset_non_current': 'investing',
    'liability_non_current': 'financing',
    'equity': 'financing',
    'equity_unaffected': 'financing',
}

REPORT_TITLES = {
    'bs': 'Balance Sheet',
    'pl': 'Profit and Loss',
    'cf': 'Cash Flow Statement',
}

TARGET_MOVE_LABELS = {
    'posted': 'Posted Entries',
    'all': 'All Entries',
}


class CustomFinancialReport(models.AbstractModel):
    """Stateless engine behind the on-screen view, the PDF and the XLSX.

    Everything is a function of an ``options`` dict:
    ``report_type`` (bs/pl/cf), ``date_from``, ``date_to``,
    ``target_move`` (posted/all), ``comparison``
    (none/previous_period/previous_year), ``detail_level``
    (summary/detail). Company is the active company of the caller.
    """
    _name = 'custom.financial.report'
    _description = 'Financial Report Engine (BS / P&L / Cash Flow)'

    # ------------------------------------------------------------------
    # Access / options
    # ------------------------------------------------------------------
    def _check_group(self):
        if not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(_(
                'Financial statements require Invoicing/Accounting '
                'access rights.'))

    @api.model
    def _normalize_options(self, options):
        options = dict(options or {})
        report_type = options.get('report_type')
        if report_type not in REPORT_TITLES:
            raise UserError(_('Invalid report type.'))
        company = self.env.company

        def to_date(value):
            return fields.Date.to_date(value) if value else False

        date_to = to_date(options.get('date_to')) or fields.Date.context_today(self)
        date_from = to_date(options.get('date_from'))
        if report_type == 'bs':
            date_from = False
        elif not date_from:
            date_from = company.compute_fiscalyear_dates(date_to)['date_from']
        if date_from and date_from > date_to:
            raise UserError(_('Date From must precede Date To.'))

        comparison = options.get('comparison') or 'none'
        if comparison not in ('none', 'previous_period', 'previous_year'):
            comparison = 'none'
        if report_type == 'bs' and comparison == 'previous_period':
            comparison = 'previous_year'

        return {
            'report_type': report_type,
            'company_id': company.id,
            'date_from': date_from,
            'date_to': date_to,
            'target_move': ('all' if options.get('target_move') == 'all'
                            else 'posted'),
            'comparison': comparison,
            'detail_level': ('summary'
                            if options.get('detail_level') == 'summary'
                            else 'detail'),
        }

    @api.model
    def _serialize_options(self, options):
        out = dict(options)
        out['date_from'] = (fields.Date.to_string(options['date_from'])
                            if options['date_from'] else False)
        out['date_to'] = fields.Date.to_string(options['date_to'])
        return out

    # ------------------------------------------------------------------
    # Periods
    # ------------------------------------------------------------------
    @api.model
    def _get_periods(self, options):
        report_type = options['report_type']
        date_from, date_to = options['date_from'], options['date_to']
        if report_type == 'bs':
            base = {'date_from': False, 'date_to': date_to,
                    'label': _('As of %s', format_date(self.env, date_to))}
        else:
            base = {'date_from': date_from, 'date_to': date_to,
                    'label': '%s - %s' % (format_date(self.env, date_from),
                                          format_date(self.env, date_to))}
        periods = [base]
        if options['comparison'] == 'none':
            return periods

        if options['comparison'] == 'previous_year' or report_type == 'bs':
            df = date_from - relativedelta(years=1) if (
                date_from and report_type != 'bs') else False
            dt = date_to - relativedelta(years=1)
        else:  # previous_period, P&L / CF only
            dt = date_from - relativedelta(days=1)
            df = dt - (date_to - date_from)
        if report_type == 'bs':
            label = _('As of %s', format_date(self.env, dt))
        else:
            label = '%s - %s' % (format_date(self.env, df),
                                 format_date(self.env, dt))
        periods.append({'date_from': df, 'date_to': dt, 'label': label})
        return periods

    # ------------------------------------------------------------------
    # Low-level query
    # ------------------------------------------------------------------
    @api.model
    def _query_balances(self, options, date_from, date_to, account_types):
        """{account_id: company-currency balance} for the given scope."""
        domain = [
            ('company_id', '=', options['company_id']),
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('account_id.account_type', 'in', list(account_types)),
        ]
        if options['target_move'] == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        else:
            domain.append(('parent_state', 'in', ('posted', 'draft')))
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        rows = self.env['account.move.line']._read_group(
            domain, ['account_id'], ['balance:sum'])
        return {account.id: balance for account, balance in rows}

    # ------------------------------------------------------------------
    # Line helpers
    # ------------------------------------------------------------------
    @api.model
    def _make_line(self, key, name, level, amount=None, ltype='line',
                   parent_key=False, account_id=False):
        return {'key': key, 'name': name, 'level': level, 'amount': amount,
                'type': ltype, 'parent_key': parent_key,
                'account_id': account_id}

    @api.model
    def _detail_lines(self, options, key, per_account, level):
        """Account-level rows, sorted by code, zero rows dropped."""
        if options['detail_level'] != 'detail':
            return []
        currency = self.env['res.company'].browse(
            options['company_id']).currency_id
        rows = []
        for account, value in sorted(
                per_account.items(),
                key=lambda item: (item[0].code or '', item[0].name or '')):
            if currency.is_zero(value):
                continue
            label = '%s %s' % (account.code or '', account.name)
            rows.append(self._make_line(
                '%s:acc%s' % (key, account.id), label.strip(),
                level, value, 'account', parent_key=key,
                account_id=account.id))
        return rows

    @staticmethod
    def _aggregate(balances, accounts_by_id, account_types, sign):
        """(signed total, {account: signed value}) for the given types."""
        total = 0.0
        per_account = {}
        for account_id, balance in balances.items():
            account = accounts_by_id[account_id]
            if account.account_type in account_types:
                value = sign * balance
                total += value
                per_account[account] = per_account.get(account, 0.0) + value
        return total, per_account

    # ------------------------------------------------------------------
    # Balance Sheet
    # ------------------------------------------------------------------
    def _bs_lines(self, options, period):
        date_to = period['date_to']
        company = self.env['res.company'].browse(options['company_id'])
        fy = company.compute_fiscalyear_dates(date_to)
        prev_fy_end = fy['date_from'] - relativedelta(days=1)

        balances = self._query_balances(options, False, date_to, BS_TYPES)
        accounts = self.env['account.account'].browse(list(balances))
        accounts_by_id = {a.id: a for a in accounts}

        pl_current = sum(self._query_balances(
            options, fy['date_from'], date_to, PL_TYPES).values())
        pl_previous = sum(self._query_balances(
            options, False, prev_fy_end, PL_TYPES).values())

        lines = []

        def group(key, name, types, sign, level=2):
            total, per_account = self._aggregate(
                balances, accounts_by_id, types, sign)
            lines.append(self._make_line(key, name, level, total, 'group'))
            lines.extend(self._detail_lines(
                options, key, per_account, level + 1))
            return total

        # ---- ASSETS ----
        lines.append(self._make_line('assets', _('ASSETS'), 0, None, 'section'))
        lines.append(self._make_line(
            'cur_assets_h', _('Current Assets'), 1, None, 'header'))
        bank = group('bank_cash', _('Bank and Cash Accounts'), ('asset_cash',), 1)
        recv = group('receivables', _('Receivables'), ('asset_receivable',), 1)
        cur = group('cur_assets', _('Current Assets'), ('asset_current',), 1)
        prepay = group('prepayments', _('Prepayments'), ('asset_prepayments',), 1)
        total_cur_assets = bank + recv + cur + prepay
        lines.append(self._make_line(
            'total_cur_assets', _('Total Current Assets'), 1,
            total_cur_assets, 'total'))
        fixed = group('fixed_assets', _('Plus Fixed Assets'),
                      ('asset_fixed',), 1, level=1)
        non_cur = group('non_cur_assets', _('Plus Non-current Assets'),
                        ('asset_non_current',), 1, level=1)
        total_assets = total_cur_assets + fixed + non_cur
        lines.append(self._make_line(
            'total_assets', _('TOTAL ASSETS'), 0, total_assets, 'grand_total'))
        lines.append(self._make_line('sp1', '', 0, None, 'spacer'))

        # ---- LIABILITIES ----
        lines.append(self._make_line(
            'liabilities', _('LIABILITIES'), 0, None, 'section'))
        lines.append(self._make_line(
            'cur_liab_h', _('Current Liabilities'), 1, None, 'header'))
        pay = group('payables', _('Payables'), ('liability_payable',), -1)
        cc = group('credit_cards', _('Credit Cards'),
                   ('liability_credit_card',), -1)
        cur_liab = group('cur_liab', _('Current Liabilities'),
                         ('liability_current',), -1)
        total_cur_liab = pay + cc + cur_liab
        lines.append(self._make_line(
            'total_cur_liab', _('Total Current Liabilities'), 1,
            total_cur_liab, 'total'))
        non_cur_liab = group('non_cur_liab', _('Plus Non-current Liabilities'),
                             ('liability_non_current',), -1, level=1)
        total_liab = total_cur_liab + non_cur_liab
        lines.append(self._make_line(
            'total_liab', _('TOTAL LIABILITIES'), 0, total_liab, 'grand_total'))
        lines.append(self._make_line('sp2', '', 0, None, 'spacer'))

        # ---- EQUITY ----
        lines.append(self._make_line('equity', _('EQUITY'), 0, None, 'section'))
        eq = group('equity_acc', _('Equity'), ('equity',), -1, level=1)
        unaffected_total, unaffected_detail = self._aggregate(
            balances, accounts_by_id, ('equity_unaffected',), -1)
        current_earnings = -pl_current
        previous_earnings = -pl_previous + unaffected_total
        lines.append(self._make_line(
            'cur_earnings', _('Current Year Unallocated Earnings'), 1,
            current_earnings, 'group'))
        lines.append(self._make_line(
            'prev_earnings', _('Previous Years Unallocated Earnings'), 1,
            previous_earnings, 'group'))
        if options['detail_level'] == 'detail':
            lines.extend(self._detail_lines(
                options, 'prev_earnings', unaffected_detail, 2))
            if not company.currency_id.is_zero(pl_previous):
                lines.append(self._make_line(
                    'prev_earnings:pl', _('Prior P&L not yet allocated'),
                    2, -pl_previous, 'account', parent_key='prev_earnings'))
        total_equity = eq + current_earnings + previous_earnings
        lines.append(self._make_line(
            'total_equity', _('TOTAL EQUITY'), 0, total_equity, 'grand_total'))
        lines.append(self._make_line('sp3', '', 0, None, 'spacer'))
        lines.append(self._make_line(
            'liab_equity', _('LIABILITIES + EQUITY'), 0,
            total_liab + total_equity, 'grand_total'))
        return lines

    # ------------------------------------------------------------------
    # Profit and Loss
    # ------------------------------------------------------------------
    def _pl_lines(self, options, period):
        balances = self._query_balances(
            options, period['date_from'], period['date_to'], PL_TYPES)
        accounts = self.env['account.account'].browse(list(balances))
        accounts_by_id = {a.id: a for a in accounts}

        lines = []

        def group(key, name, types, sign, level=2):
            total, per_account = self._aggregate(
                balances, accounts_by_id, types, sign)
            lines.append(self._make_line(key, name, level, total, 'group'))
            lines.extend(self._detail_lines(
                options, key, per_account, level + 1))
            return total

        lines.append(self._make_line('income', _('INCOME'), 0, None, 'section'))
        lines.append(self._make_line(
            'gross_h', _('Gross Profit'), 1, None, 'header'))
        op_income = group('op_income', _('Operating Income'), ('income',), -1)
        cost_rev = group('cost_rev', _('Cost of Revenue'),
                         ('expense_direct_cost',), 1)
        gross = op_income - cost_rev
        lines.append(self._make_line(
            'gross_profit', _('Gross Profit'), 1, gross, 'total'))
        other_income = group('other_income', _('Other Income'),
                             ('income_other',), -1, level=1)
        total_income = gross + other_income
        lines.append(self._make_line(
            'total_income', _('TOTAL INCOME'), 0, total_income, 'grand_total'))
        lines.append(self._make_line('sp1', '', 0, None, 'spacer'))

        lines.append(self._make_line(
            'expenses', _('EXPENSES'), 0, None, 'section'))
        expenses = group('exp', _('Expenses'), ('expense',), 1, level=1)
        depreciation = group('dep', _('Depreciation'),
                             ('expense_depreciation',), 1, level=1)
        total_expenses = expenses + depreciation
        lines.append(self._make_line(
            'total_expenses', _('TOTAL EXPENSES'), 0,
            total_expenses, 'grand_total'))
        lines.append(self._make_line('sp2', '', 0, None, 'spacer'))
        lines.append(self._make_line(
            'net_profit', _('NET PROFIT'), 0,
            total_income - total_expenses, 'grand_total'))
        return lines

    # ------------------------------------------------------------------
    # Cash Flow Statement
    # ------------------------------------------------------------------
    def _cf_tag_map(self):
        mapping = {}
        for xmlid, category in (
                ('account.account_tag_operating', 'operating'),
                ('account.account_tag_investing', 'investing'),
                ('account.account_tag_financing', 'financing')):
            tag = self.env.ref(xmlid, raise_if_not_found=False)
            if tag:
                mapping[tag.id] = category
        return mapping

    def _cf_lines(self, options, period):
        date_from, date_to = period['date_from'], period['date_to']
        company = self.env['res.company'].browse(options['company_id'])
        currency = company.currency_id

        beginning = sum(self._query_balances(
            options, False, date_from - relativedelta(days=1),
            LIQUIDITY_TYPES).values())
        ending = sum(self._query_balances(
            options, False, date_to, LIQUIDITY_TYPES).values())

        AML = self.env['account.move.line']
        state_domain = ([('parent_state', '=', 'posted')]
                        if options['target_move'] == 'posted'
                        else [('parent_state', 'in', ('posted', 'draft'))])
        liquidity_lines = AML.search([
            ('company_id', '=', company.id),
            ('date', '>=', date_from), ('date', '<=', date_to),
            ('account_id.account_type', 'in', list(LIQUIDITY_TYPES)),
        ] + state_domain)
        counterparts = AML._read_group([
            ('move_id', 'in', liquidity_lines.move_id.ids),
            ('account_id.account_type', 'not in', list(LIQUIDITY_TYPES)),
            ('display_type', 'not in', ('line_section', 'line_note')),
        ] + state_domain, ['account_id'], ['balance:sum'])

        tag_map = self._cf_tag_map()
        categories = {'operating': {}, 'investing': {},
                      'financing': {}, 'unclassified': {}}
        for account, balance in counterparts:
            value = -balance  # cash impact attributed to this counterpart
            category = None
            for tag in account.tag_ids:
                if tag.id in tag_map:
                    category = tag_map[tag.id]
                    break
            if not category:
                category = CF_FALLBACK.get(
                    account.account_type, 'unclassified')
            categories[category][account] = \
                categories[category].get(account, 0.0) + value

        net = sum(sum(vals.values()) for vals in categories.values())
        adjustment = ending - beginning - net
        if not currency.is_zero(adjustment):
            # Moves dated in-period on liquidity accounts whose counterparts
            # fall outside the filters (e.g. mixed-state moves): keep the
            # statement tied to the real ledger balances.
            categories['unclassified'][None] = \
                categories['unclassified'].get(None, 0.0) + adjustment
            net += adjustment

        lines = [self._make_line(
            'beginning', _('Cash and cash equivalents, beginning of period'),
            0, beginning, 'grand_total')]
        titles = (
            ('operating', _('Cash flows from operating activities')),
            ('investing', _('Cash flows from investing activities')),
            ('financing', _('Cash flows from financing activities')),
            ('unclassified', _('Cash flows from unclassified activities')),
        )
        for key, title in titles:
            values = categories[key]
            total = sum(values.values())
            if key == 'unclassified' and currency.is_zero(total) and not values:
                continue
            lines.append(self._make_line(key, title, 1, total, 'group'))
            per_account = {a: v for a, v in values.items() if a is not None}
            detail = self._detail_lines(options, key, per_account, 2)
            for row in detail:
                row['account_id'] = False  # CF rows are not drillable
            lines.extend(detail)
            if None in values and options['detail_level'] == 'detail' \
                    and not currency.is_zero(values[None]):
                lines.append(self._make_line(
                    '%s:other' % key,
                    _('Unmatched / out-of-filter counterparts'),
                    2, values[None], 'account', parent_key=key))
        lines.append(self._make_line(
            'net_increase', _('Net increase in cash and cash equivalents'),
            0, net, 'grand_total'))
        lines.append(self._make_line(
            'closing', _('Cash and cash equivalents, closing balance'),
            0, beginning + net, 'grand_total'))
        return lines

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------
    def _build_period_lines(self, options, period):
        builder = {'bs': self._bs_lines, 'pl': self._pl_lines,
                   'cf': self._cf_lines}[options['report_type']]
        return builder(options, period)

    def get_report_lines(self, options):
        """(lines, periods): lines carry 'amount' and, when a comparison
        is requested, 'amount_cmp' matched by line key (base-period
        structure drives the layout)."""
        periods = self._get_periods(options)
        lines = self._build_period_lines(options, periods[0])
        if len(periods) > 1:
            cmp_amounts = {
                line['key']: line['amount']
                for line in self._build_period_lines(options, periods[1])
                if line['amount'] is not None}
            for line in lines:
                if line['amount'] is not None:
                    line['amount_cmp'] = cmp_amounts.get(line['key'], 0.0)
        parents = {l['parent_key'] for l in lines if l['parent_key']}
        for line in lines:
            line['unfoldable'] = line['key'] in parents
            line['clickable'] = bool(
                line['type'] == 'account' and line['account_id'])
        return lines, periods

    def _prepare_render_data(self, options):
        lines, periods = self.get_report_lines(options)
        company = self.env['res.company'].browse(options['company_id'])
        currency = company.currency_id
        iso = fields.Date.to_string
        return {
            'title': REPORT_TITLES[options['report_type']],
            'company_name': company.name,
            'lines': lines,
            'periods': [{
                'label': p['label'],
                'date_from': iso(p['date_from']) if p['date_from'] else False,
                'date_to': iso(p['date_to']),
            } for p in periods],
            'has_comparison': len(periods) > 1,
            'currency': {
                'id': currency.id,
                'symbol': currency.symbol,
                'position': currency.position,
                'decimal_places': currency.decimal_places,
            },
            'target_move_label': TARGET_MOVE_LABELS[options['target_move']],
            'drill': {
                'date_from': (iso(periods[0]['date_from'])
                              if periods[0]['date_from'] else False),
                'date_to': iso(periods[0]['date_to']),
                'states': (['posted'] if options['target_move'] == 'posted'
                           else ['posted', 'draft']),
            },
        }

    # ------------------------------------------------------------------
    # Public RPC API (on-screen view)
    # ------------------------------------------------------------------
    @api.model
    def compute_report(self, options):
        self._check_group()
        options = self._normalize_options(options)
        return {
            'options': self._serialize_options(options),
            'data': self._prepare_render_data(options),
        }

    @api.model
    def get_pdf_action(self, options):
        self._check_group()
        options = self._normalize_options(options)
        return self.env.ref(
            'custom_financial_reports.action_report_financial'
        ).report_action(None, data=self._serialize_options(options))

    # ------------------------------------------------------------------
    # XLSX
    # ------------------------------------------------------------------
    @api.model
    def build_xlsx(self, options):
        self._check_group()
        options = self._normalize_options(options)
        import xlsxwriter  # bundled with Odoo

        data = self._prepare_render_data(options)
        buf = io.BytesIO()
        workbook = xlsxwriter.Workbook(buf, {'in_memory': True})
        sheet = workbook.add_worksheet(data['title'][:31])

        money = '#,##0.00'
        fmt_title = workbook.add_format({'bold': True, 'font_size': 14})
        fmt_meta = workbook.add_format({'font_size': 9, 'italic': True})
        fmt_col = workbook.add_format(
            {'bold': True, 'bottom': 1, 'align': 'right'})
        fmt_col_left = workbook.add_format({'bold': True, 'bottom': 1})
        formats = {}

        def line_format(line, is_amount):
            ltype, level = line['type'], line['level']
            key = (ltype, level, is_amount)
            if key in formats:
                return formats[key]
            spec = {'indent': level}
            if is_amount:
                spec.update({'num_format': money, 'align': 'right',
                             'indent': 0})
            if ltype in ('section', 'grand_total'):
                spec['bold'] = True
                if ltype == 'grand_total':
                    spec['top'] = 1
            elif ltype in ('header', 'total'):
                spec['bold'] = True
                if ltype == 'total':
                    spec['top'] = 1
            elif ltype == 'account':
                spec['font_color'] = '#444444'
                spec['font_size'] = 9
            formats[key] = workbook.add_format(spec)
            return formats[key]

        sheet.set_column(0, 0, 55)
        sheet.set_column(1, 2, 18)

        row = 0
        sheet.write(row, 0, data['company_name'], fmt_title)
        row += 1
        sheet.write(row, 0, data['title'], fmt_title)
        row += 1
        sheet.write(row, 0, data['periods'][0]['label'], fmt_meta)
        row += 1
        sheet.write(row, 0, _('Target Moves: %s',
                              data['target_move_label']), fmt_meta)
        row += 2
        sheet.write(row, 0, _('Description'), fmt_col_left)
        sheet.write(row, 1, data['periods'][0]['label'], fmt_col)
        if data['has_comparison']:
            sheet.write(row, 2, data['periods'][1]['label'], fmt_col)
        sheet.freeze_panes(row + 1, 0)
        row += 1

        for line in data['lines']:
            if line['type'] == 'spacer':
                row += 1
                continue
            sheet.write(row, 0, line['name'], line_format(line, False))
            if line['amount'] is not None:
                sheet.write_number(
                    row, 1, line['amount'], line_format(line, True))
                if data['has_comparison']:
                    sheet.write_number(
                        row, 2, line.get('amount_cmp', 0.0),
                        line_format(line, True))
            row += 1

        workbook.close()
        buf.seek(0)
        return buf.read()

    @api.model
    def xlsx_filename(self, options):
        options = self._normalize_options(options)
        return '%s_%s.xlsx' % (
            REPORT_TITLES[options['report_type']].replace(' ', '_'),
            options['date_to'])
