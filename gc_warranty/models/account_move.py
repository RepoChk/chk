# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    warranty_id = fields.Many2one(
        'warranty.request',
        string='Garantía',
        readonly=True, 
    )