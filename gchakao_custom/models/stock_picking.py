# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    dispatch_id = fields.Many2one(
        'dispatch.control', string='Control de Despacho',
        help='Despacho asociado a este picking', index=True, copy=False)
     
    dispatch_assigned= fields.Boolean(   
        default=False,
        copy=False,
        compute="_compute_assignment",
        store=True
    )

    filler_total = fields.Float(
        string='Filler Total', compute='_compute_filler_total', store=True
    )
    weight_total = fields.Float(
        string='Peso Total', compute='_compute_weight_total', store=True
    )
    filler_billed = fields.Float(
        string='Filler Facturado (%)', compute='_compute_filler_billed', store=True
    )
    street = fields.Char(
        related="partner_id.street", string="Dirección"
    )
    street2 = fields.Char(
        related="partner_id.street2", string="Dirección #2"
    )
    city_id = fields.Char(
        related="partner_id.city", string="Ciudad"
    )
    state_id = fields.Many2one(
        related="partner_id.state_id", string="Estado"
    )
    zip = fields.Char(
        related="partner_id.zip", string="Código Postal"
    )
    country_id = fields.Many2one(
        related="partner_id.country_id", string="País"
    )
    delivery_request = fields.Boolean(
        string='Requiere Delivery', related='sale_id.delivery_request', tracking=True, copy=False
    )
    exhibitor_request = fields.Boolean(
        string='¿Solicitar Exhibidores?', related='sale_id.exhibitor_request', tracking=True
    )
    logistic_active = fields.Boolean(
        string='¿Requiere despacho?', related='sale_id.logistic_active', tracking=True
    )
    logistic_use = fields.Boolean(
        string='¿Despacho en proceso?', related='sale_id.logistic_use', tracking=True
    )
    truck_payment = fields.Boolean(
        string='¿Pago contra camión?"', related='sale_id.truck_payment', tracking=True
    )
    date_delivered_to= fields.Datetime(
        string='Fecha de Entrega', tracking = True
    )
    invoice_ids = fields.Many2many(
        'account.move',
        string='Facturas',
        related='sale_id.invoice_ids',
        help='Facturas asociadas al pedido de venta'
    )
    
    @api.depends('sale_id', 'sale_id.fillert')
    def _compute_filler_billed(self):
        for rec in self:
            rec.filler_billed = rec.sale_id.fillert

    @api.depends('move_ids_without_package.product_uom_qty', 'move_ids_without_package.quantity', 'move_ids_without_package.filler')
    def _compute_filler_total(self):
        for rec in self:
            fillert = 0
            for line in rec.move_ids_without_package:
                if line.filler:
                    cantidad = line.product_uom_qty * line.filler if line.product_uom_qty > 0 else line.quantity * line.filler
                    fillert += cantidad
            rec.filler_total = fillert

    @api.depends('move_ids_without_package.product_uom_qty', 'move_ids_without_package.quantity', 'move_ids_without_package.weight')
    def _compute_weight_total(self):
        for rec in self:
            weightt = 0
            for line in rec.move_ids_without_package:
                if line.weight:
                    cantidad = line.product_uom_qty * line.weight if line.product_uom_qty > 0 else line.quantity * line.weight
                    weightt += cantidad
            rec.weight_total = weightt

    def button_validate(self):
        line_ids = self.move_line_ids
        lot = self.env['stock.lot']
        for line in line_ids:
            product = line.product_id
            if product and product.is_battery:
                if not line.tracking_number and self.picking_type_id.code == 'outgoing':
                    raise UserError(_('Debes asignar un numero de seguimiento %s.') % product.display_name)
            lot.search([('id','=',line.lot_id.id)]).write({'tracking_number':line.tracking_number})

        return super(StockPicking, self).button_validate()

    def get_product_price(self, origen, producto):
	    if origen:
		    pedido = self.env['sale.order'].search([('name', '=', origen)])
		    for line in pedido.order_line:
			    if line.product_id.id == producto:
				    iva = 0
				    if line.tax_id:
					    iva = (line.tax_id[0].amount * line.price_unit) / 100
				    monto = line.price_unit + iva
				    descuento = (monto * line.discount) / 100 
				    precio = (monto - descuento) * pedido.currency_rate
				    return precio
	    else:
		    return False

    @api.onchange('date_delivered_to')
    def _onchange_date_delivered_to(self):
        for rec in self:
            # Verificamos si hay facturas asociadas al pedido de venta
            invoice = rec.sale_id.mapped('invoice_ids')

            if invoice:
                for inv in invoice:
                    inv.sudo().write({'delivery_date': rec.date_delivered_to})
                    if inv.delivery_date and inv.invoice_date_due:
                        strf = datetime.strptime
                        # inv.invoice_date_due = inv.needed_terms and max(
                        #     (k['date_maturity'] for k in inv.needed_terms.keys() if k),
                        #     default=False,
                        # )
                        
                        fecha_factura = inv.invoice_date
                        fecha_entrega = rec.date_delivered_to.date()
                        dias_diferencia = (fecha_entrega - fecha_factura).days
                        fecha_vencimiento_real = inv.invoice_date_due + timedelta(days=dias_diferencia)

                        inv.invoice_date_due_aux = fecha_vencimiento_real
                        inv.invoice_date_due = fecha_vencimiento_real
                        inv.date_delivered_on = True

                        for line in inv.line_ids:
                            if line.date_maturity:
                                line.date_maturity = inv.invoice_date_due

    def action_cancel(self):
        res = super().action_cancel()
        for picking in self:
            if picking.dispatch_id and any(picking.state != 'cancel' for picking in picking.dispatch_id.picking_ids):
                picking.dispatch_id = None
        return res

    @api.depends('dispatch_id')
    def _compute_assignment(self):
        for item in self:
            if item.dispatch_id:
                item.dispatch_assigned = True
            else:
                item.dispatch_assigned = False

    def action_view_dispatch(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dispatch.control',
            'res_id': self.dispatch_id.id,
            'view_mode': 'form'
        }

    # def button_validate(self):
    #     for rec in self:
    #         sale_id = rec.group_id.sale_id
    #         if sale_id and sale_id.situation in ('apartado','analisis','en_proceso','cancelado') and sale_id.is_approval:
    #             raise UserError('La ventas debe estar en situación de Aprobado o Facturado para poder validar el despacho.')
    #     return super(StockPicking, self).button_validate()