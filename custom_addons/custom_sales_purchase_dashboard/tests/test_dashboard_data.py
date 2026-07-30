# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from datetime import date

class TestDashboardData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env['custom.sales.purchase.dashboard']
        cls.company = cls.env.company

        # Create partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer Odoo',
            'vat': '27AAAAA1111A1Z1',
        })

        # Create a basic product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Service Product',
            'type': 'service',
        })

        # Create a tax group for CGST/SGST/IGST
        cls.tax_group_cgst = cls.env['account.tax.group'].create({'name': 'CGST'})
        cls.tax_group_sgst = cls.env['account.tax.group'].create({'name': 'SGST'})

        # Create taxes
        cls.tax_cgst = cls.env['account.tax'].create({
            'name': 'CGST 9%',
            'amount': 9.0,
            'tax_group_id': cls.tax_group_cgst.id,
            'amount_type': 'percent',
        })
        cls.tax_sgst = cls.env['account.tax'].create({
            'name': 'SGST 9%',
            'amount': 9.0,
            'tax_group_id': cls.tax_group_sgst.id,
            'amount_type': 'percent',
        })

        # Create a posted invoice
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'invoice_date': date.today(),
            'date': date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Line 1',
                'product_id': cls.product.id,
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, [cls.tax_cgst.id, cls.tax_sgst.id])],
            })]
        })
        cls.invoice.action_post()

    def test_retrieve_dashboard_data_sales(self):
        params = {
            'type': 'sales',
            'basis': 'accounting',
            'date_from': str(date.today()),
            'date_to': str(date.today()),
            'limit': 10,
            'offset': 0,
            'search': 'Test Customer'
        }
        res = self.Dashboard.retrieve_dashboard_data(params)
        
        self.assertIn('kpis', res)
        self.assertIn('graphs', res)
        self.assertIn('table', res)
        
        kpis = res['kpis']
        self.assertEqual(kpis['doc_count'], 1)
        self.assertAlmostEqual(kpis['total_subtotal'], 1000.0)
        self.assertAlmostEqual(kpis['total_cgst'], 90.0)
        self.assertAlmostEqual(kpis['total_sgst'], 90.0)
        self.assertAlmostEqual(kpis['total_amount'], 1180.0)

        # Check table
        self.assertEqual(len(res['table']['records']), 1)
        record = res['table']['records'][0]
        self.assertEqual(record['partner_name'], 'Test Customer Odoo')
        self.assertAlmostEqual(record['subtotal'], 1000.0)
        self.assertAlmostEqual(record['cgst'], 90.0)
        self.assertAlmostEqual(record['sgst'], 90.0)

    def test_check_wizard_availability(self):
        res = self.Dashboard.check_wizard_availability()
        self.assertIn('sales', res)
        self.assertIn('purchase', res)
