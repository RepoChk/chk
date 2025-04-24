# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    anticipo = fields.Boolean('Anticipo', default=False)

    def action_post(self):
        for rec in self:
            models_active = self.env.context.get('active_model')
            print('models_active', models_active)
            if models_active == 'account.payment' or models_active == 'account.move':
                if rec.anticipo:
                    if rec.partner_id:
                        if rec.payment_type == 'inbound' and rec.partner_id.cuenta_anticipo_clientes_id:
                            rec.destination_account_id = rec.partner_id.cuenta_anticipo_clientes_id
                        elif rec.payment_type == 'outbound' and rec.partner_id.cuenta_anticipo_proveedores_id:
                            rec.destination_account_id = rec.partner_id.cuenta_anticipo_proveedores_id
                else:
                    if rec.partner_id:
                        if rec.payment_type == 'inbound' and rec.partner_id.cuenta_anticipo_clientes_id:
                            rec.destination_account_id = rec.partner_id.property_account_receivable_id
                        elif rec.payment_type == 'outbound' and rec.partner_id.cuenta_anticipo_proveedores_id:
                            rec.destination_account_id = rec.partner_id.property_account_payable_id
        res = super(AccountPayment, self).action_post()

        return res

    def _synchronize_to_moves(self, changed_fields):
        super(AccountPayment, self)._synchronize_to_moves(changed_fields)
        for pay in self.with_context(skip_account_move_synchronization=True):
            models_active = self.env.context.get('active_model')
            if (models_active == 'account.payment' or models_active == 'account.move'):
                if pay.anticipo:
                    if self.partner_id:
                        if self.payment_type == 'inbound' and self.partner_id.cuenta_anticipo_clientes_id:
                            pay.move_id.with_context(skip_invoice_sync=True).line_ids.filtered(lambda x: x.account_id.account_type == 'asset_receivable').write({'account_id': self.partner_id.cuenta_anticipo_clientes_id.id})
                        elif self.payment_type == 'outbound' and self.partner_id.cuenta_anticipo_proveedores_id:
                            pay.move_id.with_context(skip_invoice_sync=True).line_ids.filtered(lambda x: x.account_id.account_type == 'liability_payable').write({'account_id': self.partner_id.cuenta_anticipo_proveedores_id.id})
                else:
                    if self.partner_id:
                        #verifica si el asiento contable existe la cuenta de anticipos y la cambia por la cuenta por defecto
                        if self.payment_type == 'inbound' and self.partner_id.cuenta_anticipo_clientes_id:
                            pay.move_id.with_context(skip_invoice_sync=True).line_ids.filtered(lambda x: x.account_id.id == self.partner_id.cuenta_anticipo_clientes_id.id and x.credit > 0).write({'account_id': self.partner_id.property_account_receivable_id.id})
                        elif self.payment_type == 'outbound' and self.partner_id.cuenta_anticipo_proveedores_id:
                            pay.move_id.with_context(skip_invoice_sync=True).line_ids.filtered(lambda x: x.account_id.id == self.partner_id.cuenta_anticipo_proveedores_id.id and x.debit > 0).write({'account_id': self.partner_id.property_account_payable_id.id})
