# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class SaleOrderProductSelect(models.TransientModel):
    _name = "sale.order.product.select"
    _description = "Seleccionar productos por almacén"

    def _get_product_domain(self): 
        user_warehouse_ids = self.env.user.warehouse_ids.mapped('lot_stock_id.id') 
        product_ids = self.env['stock.quant'].search([('location_id', 'in', user_warehouse_ids), ('quantity', '>', 0) ]).mapped('product_id.id') 
        return [('id', 'in', product_ids), ('detailed_type','=','product')]

    product_id = fields.Many2one(
        'product.product', 
        string='Producto', 
        domain=lambda self: self._get_product_domain()
    )

    line_ids = fields.One2many(
        'sale.order.product.select.line',
        'sale_order_product_id',
    )

    order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        default=lambda self: self.env.context.get('default_sale_id')
    )

    company_id = fields.Many2one(
        'res.company',
        compute='_compute_company_id',
        store=True,
        string='Compañía'
    )

    @api.depends('order_id')
    def _compute_company_id(self):
        for record in self:
            if record.order_id:
                record.company_id = record.order_id.company_id

    def get_user(self):
        return self.env['res.users'].search([('partner_id', '=', self.partner_id.id)])

    @api.onchange('product_id','company_id')
    def _get_product(self):
        # Inicializa la lista de líneas
        lines = []
        # Verifica si el producto ya está en la orden
        if not self.env['sale.order.line'].search_count([
            ('order_id', '=', self.order_id.id),
            ('product_id', '=', self.product_id.id)
        ]):
            # Obtiene los almacenes asignados al usuario
            user_warehouse_ids = self.env.user.warehouse_ids

            # Itera sobre cada almacén asignado al usuario
            for warehouse in user_warehouse_ids:
                # Calcula la cantidad disponible en el almacén
                qty_available = sum(
                    (quant.available_quantity)
                    for quant in self.env['stock.quant'].search([
                        ('location_id', 'child_of', warehouse.lot_stock_id.id),
                        ('product_id', '=', self.product_id.id),
                        ('company_id', '=', self.company_id.id)
                    ])
                )
                # Si hay cantidad disponible, agrega los valores a la lista de líneas
                if qty_available > 0:
                    vals = {
                        'warehouse_id': warehouse.id,
                        'qty_available': qty_available,
                        'product_id': self.product_id.id,
                    }
                    # Verificamos si ya existe una línea con el mismo product_id y warehouse_id
                    existing_line = next(
                        (line for line in self.line_ids if line.product_id.id == vals['product_id'] and line.warehouse_id.id == vals['warehouse_id']),
                        False
                    )
                    if not existing_line:
                        lines.append((0, 0, vals))
        self.line_ids = lines

    def create_sale_order_lines(self):
        SaleOrderLine = self.env['sale.order.line']
        
        for line in self.line_ids:
            # Verificar la cantidad disponible en el almacén seleccionado
            if line.qty_done <= line.qty_available:
                if line.qty_done > 0:
                    # Buscar si ya existe una línea con el mismo producto en el pedido de venta
                    existing_line = SaleOrderLine.search([
                        ('order_id', '=', self.order_id.id),
                        ('product_id', '=', line.product_id.id)
                    ], limit=1)
                    warehouse_info_list = []
                    for l in self.line_ids:
                        if l.product_id.id == line.product_id.id:
                            # Agregar información al diccionario
                            warehouse_info_list.append({
                                'product_id': l.product_id.id,
                                'warehouse_id': l.warehouse_id.id,
                                'qty_done': l.qty_done,
                                'location_id': l.warehouse_id.lot_stock_id.id,
                            })
                    if existing_line:
                        # Actualizar la cantidad de la línea existente y agregar el nuevo almacén si es necesario
                        new_warehouse_ids = list(set(existing_line.warehouse_ids.ids + [line.warehouse_id.id]))
                        existing_line.write({
                            'product_uom_qty': existing_line.product_uom_qty + line.qty_done,
                            'warehouse_ids': [(6, 0, new_warehouse_ids)],
                        })
                        
                        # Actualizar el campo warehouse_info
                        existing_line.warehouse_info = str(warehouse_info_list)
                    else:
                        # Crear una nueva línea de pedido de venta
                        order_line_vals = {
                            'order_id': self.order_id.id,
                            'name': line.product_id.display_name,
                            'product_template_id': line.product_id.product_tmpl_id.id,
                            'product_id': line.product_id.id,
                            'is_downpayment': False,
                            'product_uom_qty': line.qty_done,
                            'warehouse_ids': [(6, 0, [line.warehouse_id.id])],
                            'warehouse_info': str(warehouse_info_list),
                            'company_id': self.company_id.id,
                        }
                        sale_order_line = SaleOrderLine.create(order_line_vals)

                    # Actualizar los montos del pedido de venta
                    self.order_id._compute_amounts()
            else:
                raise UserError('No hay suficiente cantidad disponible para el producto %s en el almacén %s.' % (line.product_id.name, line.warehouse_id.name))

class SaleOrderProductSelectLine(models.TransientModel):
    _name = "sale.order.product.select.line"
    _description = "Lista de productos para seleccionar"

    sale_order_product_id = fields.Many2one(
        'sale.order.product.select',
    )

    product_id = fields.Many2one('product.product', string='Producto')
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén')
    qty_available = fields.Float('Disponible', readonly=True)
    qty_done = fields.Float('Cantidad', default=0)