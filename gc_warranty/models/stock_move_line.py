# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def action_add_serial(self):
        warranty_id = self.env.context.get('warranty_id')
        product_type = self.env.context.get('product_type')
        product_id = self.env.context.get('product_id')
        product_tmpl_id = self.env['product.product'].browse(product_id).product_tmpl_id
        invoice_id = self.picking_id.mapped('sale_id.invoice_ids').filtered(lambda l: l.move_type == 'out_invoice' and l.state == 'posted')[0].id
        
        values = {
            'lot_id' : self.lot_id.id,
            'invoice_id' : invoice_id,
            'product_id' : product_tmpl_id,
            'manual' : True,
        }
        warranty = self.env['warranty.request'].browse(warranty_id)
        warranty.write(values)

        return True