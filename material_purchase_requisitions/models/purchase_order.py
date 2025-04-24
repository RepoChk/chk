# -*- coding: utf-8 -*-

from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    gc_requisition_ids = fields.One2many(
        'gc.purchase.requisition.line',
        'purchase_order_id',
        string='Requisiciones',
        ondelete='cascade'
    )

    is_requisition = fields.Boolean(string='Es requisición')

    @api.onchange('gc_requisition_ids')
    def _onchange_gc_requisition_ids(self):
        order_lines = []

        for requisition_line in self.gc_requisition_ids:
            req = requisition_line.requisition_id
            
            # Buscar las líneas de requisición originales
            for line in req.requisition_line_ids:
                # Solo agregar líneas que sean para compra
                if line.action_type in ['purchase', 'service_purchase']:
                    order_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.description,
                        'product_qty': line.qty,
                        'product_uom': line.uom.id,
                        'price_unit': line.product_id.standard_price,
                        'analytic_distribution': line.analytic_distribution,
                        'date_planned': fields.Date.today(),
                        'custom_requisition_line_id': line.id,
                    }))
        
        if order_lines:
            self.order_line = order_lines
    
    @api.ondelete(at_uninstall=False)
    def _clean_requisition_lines(self):
        for order in self:
            requisition_lines = self.env['gc.purchase.requisition.line'].search([
                ('purchase_order_id', '=', order.id)
            ])
            if requisition_lines:
                requisition_lines.write({'requisition_id': False})

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    custom_requisition_line_id = fields.Many2one(
        'material.purchase.requisition.line',
        string='Requisitions Line',
        copy=False
    )

class PurchaseRequisitionLine(models.Model):
    _name = 'gc.purchase.requisition.line'
    _description = 'Lista de requisiciones en las compras'
    
    
    requisition_id = fields.Many2one(
        'material.purchase.requisition',
        string='Requisición',
        ondelete='cascade'
    )
    purchase_order_id = fields.Many2one('purchase.order', ondelete='cascade')
    name = fields.Char(related='requisition_id.name', string='Número')
    request_date = fields.Date(related='requisition_id.request_date', string='Fecha requisición')
    user_id = fields.Many2one(related='requisition_id.user_id', string='Solicitante')
    department_id = fields.Many2one(related='requisition_id.department_id', string='Departamento')

    @api.model
    def _gc_clean_orphan_lines(self):
        orphan_lines = self.search([
            ('purchase_order_id', '=', False),
            ('requisition_id', '=', False)
        ])
        if orphan_lines:
            orphan_lines.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._gc_clean_orphan_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._gc_clean_orphan_lines()
        return res