# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import ustr


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    warranty_id = fields.Many2one('warranty.request', string='Petición de garantia')
    is_warranty = fields.Selection(related="category_id.is_warranty")

class ApprovalCategory(models.Model):
    _inherit = 'approval.category'
    
    is_warranty = fields.Selection(string='Garantia', selection=[
        ('required', 'Required'), ('optional', 'Optional'), ('no', 'Ninguno')], default='no')
