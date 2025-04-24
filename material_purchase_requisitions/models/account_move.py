# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = "account.move"

    custom_requisition_id = fields.Many2one(
        'material.purchase.requisition',
        string='Requisición',
        copy=False
    )

    @api.onchange('custom_requisition_id')
    def _onchange_gc_requisition_ids(self):
        invoice_lines = [(5, 0, 0)]
        
        for req in self.custom_requisition_id:
            # Buscar las líneas de requisición originales
            for line in req.requisition_line_ids:
                # Solo agregar líneas que requieran factura
                if line.action_type in ['cxp']:
                    invoice_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.description,
                        'quantity': line.qty,
                        'product_uom_id': line.uom.id,
                        'price_unit': line.product_id.standard_price,
                        'analytic_distribution': line.analytic_distribution,
                        'custom_requisition_line_id': line.id,
                    }))
        
        if invoice_lines:
            self.invoice_line_ids = invoice_lines