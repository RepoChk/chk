# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderDiscount(models.TransientModel):
    _inherit = 'sale.order.discount'

    early_payment_discount = fields.Float(string='Dsct. Pronto Pago')


    def action_apply_discount(self):
        res = super().action_apply_discount()
        if self.discount_type == 'sol_discount':
            self.sale_order_id.order_line.write({'early_payment_discount': self.early_payment_discount*100})

        return res
    