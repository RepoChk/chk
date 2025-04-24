# coding: utf-8
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'
    
    term_type = fields.Selection([
        ('cash', 'Contado'),
        ('credit', 'Crédito')], string="Tipo", default='credit', required=True,)