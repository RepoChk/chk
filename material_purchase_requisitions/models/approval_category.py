# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
    
class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    has_requisition_request = fields.Selection(
        string='Requisición', selection=[('required', 'Required'), ('optional', 'Optional'), ('no', 'None')], default='no'
    )

    has_analytic_request = fields.Selection(
        string='Cuenta Analitica', selection=[('required', 'Required'), ('optional', 'Optional'), ('no', 'None')], default='no'
    )

    is_cxp = fields.Selection(string='Pago directo CXP', selection=[
        ('required', 'Requerido'), ('optional', 'Opcional'), ('no', 'Ninguno')], default='no')

    is_amount = fields.Boolean(string='Limitar por monto')

    currency_id_dif = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id_dif.id)
    amount = fields.Monetary('Monto máximo', currency_field='currency_id_dif')
