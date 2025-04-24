# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    
    invoice_user_id = fields.Many2one('res.users', string='Vendedor', store=True)
    account_holder_name = fields.Char(string='Nombre y Apellido del Titular de la Cuenta', store=True)
    account_holder_id_number = fields.Char(string='Documento de Identidad del Titular de la Cuenta', store=True)

    @api.model
    def _default_invoice_user(self):
        return self.env.user

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
        payment_vals.update({
            'invoice_user_id': self.invoice_user_id.id,
            'account_holder_name': self.account_holder_name,
            'account_holder_id_number':self.account_holder_id_number,
        })
        return payment_vals
