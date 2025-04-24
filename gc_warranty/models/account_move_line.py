# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def action_add_product(self):
        warranty_id = self.env.context.get('warranty_id')
        product_type = self.env.context.get('product_type')
        product_id = self.env.context.get('default_product_id')
        product_tmpl_id = self.env['product.product'].browse(product_id).product_tmpl_id
        invoice_id = self.env.context.get('default_invoice_id')
        
        values = {
            'invoice_id' : invoice_id,
            'product_id' : product_tmpl_id,
            'manual' : True,
        }
        warranty = self.env['warranty.request'].browse(warranty_id)
        warranty.write(values)