# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
    
class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    approval_type = fields.Selection(selection_add=[('sale_order', 'Crear Orden de Venta'), ('purchase_order', 'Crear Orden de Compra'), ('payment_order', 'Crear Orden de pago')])
    
    is_purchase = fields.Selection(string='Compras', selection=[
        ('required', 'Required'), ('optional', 'Optional'), ('no', 'Ninguno')], default='no')

    is_order = fields.Selection(string='Ventas', selection=[
        ('required', 'Requerido'), ('optional', 'Opcional'), ('no', 'Ninguno')], default='no')

    is_order_payment = fields.Selection(string='Orden de Pago', selection=[
        ('required', 'Requerido'), ('optional', 'Opcional'), ('no', 'Ninguno')], default='no')

    @api.onchange('approval_type')
    def _onchange_approval_type(self):
        if self.approval_type == 'sale_order':
            self.is_order = 'required'
        if self.approval_type == 'purchase_order':
            self.is_purchase = 'required'
        if self.approval_type == 'payment_order':
            self.is_order_payment = 'required'