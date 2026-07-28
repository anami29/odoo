# -*- coding: utf-8 -*-
"""Structured content behind the Watson Logistics website.

Anything that repeats on the page — services, branches, team, certifications,
counters — is a record here rather than markup, so the client edits it from the
backend and the templates stay untouched.
"""

from odoo import api, fields, models


class WatsonService(models.Model):
    _name = 'watson.service'
    _description = 'Watson Service'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True, help="Card title, e.g. Sea Freight.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    code = fields.Selection(
        selection=[
            ('sea', 'Sea Freight'), ('air', 'Air Freight'), ('road', 'Road Transport'),
            ('cust', 'Customs Brokerage'), ('log', 'Logistics'), ('dist', 'Distribution'),
            ('ware', 'Warehousing'), ('proj', 'Project Cargo'), ('poe', 'POE / DDP'),
            ('us', 'US Expertise'),
        ],
        required=True,
        help="Selects the inline icon set used on the card, tab and badge.",
    )
    excerpt = fields.Text(translate=True, help="Short text on the service card.")
    tag = fields.Char(translate=True, help="Small label above the detail heading.")
    detail_title = fields.Char(translate=True)
    body = fields.Html(translate=True, sanitize=False,
                       help="Full description shown in the service detail tab.")
    badge_small = fields.Char(translate=True)
    badge_big = fields.Char(translate=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Each service code may only be used once.'),
    ]

    @api.depends('name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or ''


class WatsonBranch(models.Model):
    _name = 'watson.branch'
    _description = 'Watson Branch Office'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='City', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    contact_person = fields.Char()
    email = fields.Char()
    street = fields.Text(string='Address')
    phone = fields.Char(string='Phone (display)')
    phone_tel = fields.Char(string='Phone (dial)', help="Digits only, used for the tel: link.")
    mobile = fields.Char(string='Mobile (display)')
    mobile_tel = fields.Char(string='Mobile (dial)')
    # image_1920 from image.mixin holds the branch QR code.

    def _phone_link(self, value):
        return ''.join(c for c in (value or '') if c.isdigit() or c == '+')


class WatsonTeamMember(models.Model):
    _name = 'watson.team.member'
    _description = 'Watson Team Member'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    role = fields.Char(translate=True)
    initials = fields.Char(compute='_compute_initials', store=False,
                           help="Shown in place of a photo until one is uploaded.")

    @api.depends('name')
    def _compute_initials(self):
        for rec in self:
            parts = (rec.name or '').split()
            rec.initials = ''.join(p[0] for p in parts[:2]).upper()


class WatsonCertification(models.Model):
    _name = 'watson.certification'
    _description = 'Watson Certification / Membership'
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True, help="Used as the logo's alt text and tooltip.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class WatsonCounter(models.Model):
    _name = 'watson.counter'
    _description = 'Watson Headline Figure'
    _order = 'sequence, id'

    name = fields.Char(string='Label', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    value = fields.Integer(required=True)
    suffix = fields.Char(help="Appended to the number, e.g. + or /7.")


class WatsonIndustry(models.Model):
    _name = 'watson.industry'
    _description = 'Watson Industry Served'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    icon = fields.Selection(
        selection=[
            ('pharma', 'Pharma'), ('textiles', 'Textiles'), ('automobile', 'Automobile'),
            ('manufacturing', 'Manufacturing'), ('retail', 'Retail'), ('cargo', 'General Cargo'),
        ],
        default='cargo',
    )


class Website(models.Model):
    """Site-wide contact details, so templates never hard-code them."""
    _inherit = 'website'

    watson_phone = fields.Char(string='Watson phone (display)', default='+91 22 27575744')
    watson_phone_tel = fields.Char(string='Watson phone (dial)', default='+912227575744')
    watson_mobile = fields.Char(string='Watson mobile (display)', default='+91 9833352325')
    watson_mobile_tel = fields.Char(string='Watson mobile (dial)', default='+919833352325')
    watson_whatsapp = fields.Char(string='WhatsApp number', default='919833352325')
    watson_email = fields.Char(string='Watson email', default='info@watson-logistics.com')
    watson_hours = fields.Char(string='Working hours', default='Mon–Sat: 09:00 – 18:00')
    watson_head_office = fields.Text(
        string='Head office address',
        default='704-705, Mahavir Icon, Sector 15, CBD Belapur, Navi Mumbai, Maharashtra 400614',
    )
    watson_linkedin = fields.Char(default='https://www.linkedin.com/company/watson-logistics-pvt-ltd')
    watson_instagram = fields.Char(default='https://www.instagram.com/watson_logistic/')
    watson_established = fields.Char(string='Established', default='2007')
