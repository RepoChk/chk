# -*- coding: utf-8 -*-

from odoo import models, _, fields, api
from odoo.exceptions import UserError, ValidationError


class VoidInvoice(models.TransientModel):
    _name = 'void.invoice'
    _description = 'Wizard para anula factura'

    
    reason_cancellation = fields.Char(
        string='Razón de la Anulacións',
    )

    
    def action_void_invoice(self):
        move_id = self.env.context.get('default_move_id')
        move = self.env['account.move'].search([('id','=',move_id)])

        if self.reason_cancellation != False:
            if move.amount_residual == move.amount_total:
                move.write({
                    'partner_id': 100007,
                    'partner_shipping_id': 100007,
                    'reason_cancellation': self.reason_cancellation,
                    'void_invoice': True
                })
                alicuota=self.env['account.move.line.resumen'].search(['&',('invoice_id','=',move_id),('state','=','posted')]).unlink()
                move.button_cancel()
            else:
                raise ValidationError("Debe retirar todos los documentos que afectan a este documento.")
        else:
            raise ValidationError("Ingrese la informacion del Motivo de Anulación")
        