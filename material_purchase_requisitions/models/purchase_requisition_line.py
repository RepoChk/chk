# -*- coding: utf-8 -*-

from odoo import _, models, fields, api
import odoo.addons.decimal_precision as dp
from odoo.exceptions import ValidationError

class MaterialPurchaseRequisitionLine(models.Model):
    _name = "material.purchase.requisition.line"
    _description = 'Material Purchase Requisition Lines'
    _inherit = ['analytic.mixin']

    
    requisition_id = fields.Many2one(
        'material.purchase.requisition',
        string='Requisitions', 
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        tracking=True
    )
#     layout_category_id = fields.Many2one(
#         'sale.layout_category',
#         string='Section',
#     )
    description = fields.Char(
        string='Description',
        required=True,
    )
    detail = fields.Char(
        string='Detalle',
        tracking=True
    )
    qty = fields.Float(
        string='Quantity',
        default=1,
        required=True,
        tracking=True
    )
    qty_ordered = fields.Float(
        string='Cantidad Ordenada',
        # compute="_compute_ordered_qty",
        store=True,
    )

    uom = fields.Many2one(
        'uom.uom',#product.uom in odoo11
        related = 'product_id.uom_id',
        string='Unit of Measure',
        store=True,
    )
    
    action_type = fields.Selection(
        selection=[
            ('internal','Traslado Interno'),
            ('purchase','Pedido de Compra'),
            ('service_purchase','Compra de Servicios'),
            ('cxp','Pago a Proveedor'),
        ],
        string='Requisition Action',
        related='requisition_id.requisition_type'
    )
    
    require_invoice = fields.Boolean(
        string='Requiere Orden de Compra o Factura', 
        default=False, 
        tracking=True
    )

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            # rec.description = rec.product_id.name
            rec.description = rec.product_id.display_name
            rec.uom = rec.product_id.uom_id.id

    # @api.depends('requisition_id.purchase_order_ids.purchase_order_id.state')
    # def _compute_ordered_qty(self):
    #     line_found = set()
    #     for line in self:
    #         total = 0.0
    #         for po in line.requisition_id.purchase_order_ids.purchase_order_id.filtered(lambda purchase_order: purchase_order.state in ['purchase', 'done']):
    #             for po_line in po.order_line.filtered(lambda order_line: order_line.product_id.id == line.product_id.id and line.product_id.detailed_type == 'product'):
    #                 if po_line.product_uom != line.uom:
    #                     total += po_line.product_uom._compute_quantity(po_line.product_qty, line.uom)
    #                 else:
    #                     total += po_line.product_qty
                    
    #                 # Validación para no exceder la cantidad solicitada
    #                 if total > line.qty:
    #                     raise ValidationError(_(
    #                         '¡La cantidad ordenada (%s) excede la cantidad solicitada (%s) '
    #                         'para el producto "%s"!'
    #                     ) % (total, line.qty, line.product_id.name))
                    
    #         if line.product_id not in line_found:
    #             line.qty_ordered = total
    #             line_found.add(line.product_id)
    #         else:
    #             line.qty_ordered = 0
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
