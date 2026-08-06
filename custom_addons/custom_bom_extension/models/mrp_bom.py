from odoo import fields, models


class MrpBom(models.Model):
  _inherit = 'mrp.bom'

  custom_drawing_number = fields.Char(
      string='Drawing / Doc Number',
      help='Reference drawing number for this Bill of Materials',
  )
  custom_notes = fields.Text(
      string='Custom Production Notes',
      help='Internal notes for manufacturing this BOM',
  )
