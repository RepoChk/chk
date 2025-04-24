# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    warehouse_ids = fields.Many2many('stock.warehouse', string="Almacenes",)
    warehouse_info = fields.Char(string="Info. Almacenes",)
    filler = fields.Float(string='Filler', related='product_id.filler')
    fillert = fields.Float(string='FillerT', compute='_compute_fillert', store=True)
    invoice_line_id = fields.Many2one('account.move.line', string='Invoice Line')
    
    purchase_price = fields.Float(
        string="Costo", compute="_compute_purchase_price",
        digits='Product Price', store=True, copy=False, precompute=True,
        groups="base.group_user")

    profitability = fields.Float(
        string="Ganancia", compute='_compute_profitability',
        digits='Product Price', store=True, readonly=True, groups="base.group_user", precompute=True)

    profitability_percent = fields.Float(
        string="Rentabilidad", compute='_compute_profitability', store=True, readonly=True,
        groups="base.group_user", precompute=True, widget='percentage')  # Mostrar como porcentaje

    early_payment_discount = fields.Float(
        string='% Dsct. Pronto Pago', default=0.0, store=True)

    price_unit_discount = fields.Float(
        string="Precio Unitario con Dsct. Pronto Pago", compute='_compute_price_unit_discount',
        digits='Product Price', store=True, readonly=True)

    profitability_discount = fields.Float(
        string="Ganancia con Dsct. Pronto Pago", compute='_compute_profitability_discount',
        digits='Product Price', store=True, readonly=True, groups="base.group_user", precompute=True)

    profitability_percent_discount = fields.Float(
        string="Rentabilidad con Dsct. Pronto Pago", compute='_compute_profitability_discount',
        store=True, readonly=True, groups="base.group_user", widget='percentage')  # Mostrar como porcentaje

    detailed_type = fields.Selection(related='product_id.product_tmpl_id.detailed_type')

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom')
    def _compute_purchase_price(self):
        for line in self:
            if not line.product_id:
                line.purchase_price = 0.0
                continue
            # Obtener el precio estándar en USD
            if line.currency_id.name == "USD":
                standard_price = line.product_id.standard_price_usd
            else:
                standard_price = line.product_id.standard_price
            # Obtener el impuesto aplicable
            tax_rate = line.product_id.taxes_id[0].amount / 100 if line.product_id.taxes_id else 0
            # Calcular el precio de compra incluyendo el impuesto
            line.purchase_price = standard_price * (1 + tax_rate)
    
    # Cálculo de la rentabilidad 
    @api.depends('price_subtotal', 'product_uom_qty', 'purchase_price', 'discount', 
                 'tax_id', 'price_unit', 'order_id.currency_id', 'order_id.pricelist_id', 'product_id')
    def _compute_profitability(self):
        for line in self:
            # Calculamos el subtotal con impuestos
            subtotal_with_tax = line.price_subtotal
            if line.tax_id:
                taxes = line.tax_id.compute_all(
                    line.price_unit, line.order_id.currency_id, line.product_uom_qty,
                    product=line.product_id, partner=line.order_id.partner_id)
                subtotal_with_tax = taxes['total_included']
            # Aplicamos el descuento
            discounted_subtotal = subtotal_with_tax * (1 - line.discount / 100)
            # Calculamos la ganancia
            line.profitability = discounted_subtotal - (line.purchase_price * line.product_uom_qty)
            # Convertimos la rentabilidad a porcentaje
            line.profitability_percent = discounted_subtotal and (line.profitability / discounted_subtotal) * 100

    # Cálculo de la rentabilidad con descuento por pronto pago
    @api.depends('price_subtotal', 'product_uom_qty', 'purchase_price', 'early_payment_discount', 
                 'tax_id', 'discount', 'price_unit', 'order_id.currency_id', 'order_id.pricelist_id', 'product_id')
    def _compute_profitability_discount(self):
        for line in self:
            # Calculamos el subtotal con impuestos
            subtotal_with_tax = line.price_subtotal
            if line.tax_id:
                taxes = line.tax_id.compute_all(
                    line.price_unit, line.order_id.currency_id, line.product_uom_qty,
                    product=line.product_id, partner=line.order_id.partner_id)
                subtotal_with_tax = taxes['total_included']
            # Aplicamos el descuento inicial
            discounted_subtotal = subtotal_with_tax * (1 - line.discount / 100)        
            # Aplicamos el descuento por pronto pago sobre el subtotal ya descontado
            discountedpp_subtotal = discounted_subtotal * (1 - line.early_payment_discount / 100)
            # Calculamos la ganancia
            line.profitability_discount = discountedpp_subtotal - (line.purchase_price * line.product_uom_qty)
            # Convertimos la rentabilidad a porcentaje
            line.profitability_percent_discount = discountedpp_subtotal and (line.profitability_discount / discountedpp_subtotal) * 100

    # Cálculo del precio unitario con descuento por pronto pago
    @api.depends('price_unit', 'early_payment_discount')
    def _compute_price_unit_discount(self):
        """
        Calcula el precio unitario después de aplicar el descuento de pronto pago.
        """
        for line in self:
            # Aplica el descuento de pronto pago al precio unitario
            line.price_unit_discount = line.price_unit * (1 - line.early_payment_discount / 100)
            
    @api.depends('product_id', 'filler')
    def _compute_fillert(self):
        for rec in self:
            rec.fillert = rec.filler * rec.product_uom_qty

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res['purchase_price'] = self.purchase_price
        res['profitability'] = self.profitability
        res['profitability_percent'] = self.profitability_percent
        res['early_payment_discount'] = self.early_payment_discount
        res['price_unit_discount'] = self.price_unit_discount
        res['profitability_discount'] = self.profitability_discount
        res['profitability_percent_discount'] = self.profitability_percent_discount
        return res

    def write(self, vals):
        """
        Sobrescribe el método write para validar modificaciones en campos sensibles.
        """
        # Verificar si se está modificando el campo price_unit
        if 'price_unit' in vals or 'purchase_price' in vals:
            if not self.env.user.has_group('gchakao_custom.group_edit_price_unit'):
                raise ValidationError(_("No tienes permisos para modificar el precio unitario de venta y el costo unitario. Contacta al administrador"))
        
        # Verificar modificaciones en descuentos cuando el pedido está confirmado
        if 'discount' in vals or 'early_payment_discount' in vals:
            if self.order_id.state == 'sale':
                raise ValidationError(_("Ningún usuario puede modificar los descuentos cuando el pedido está confirmado. Debe cancelar el Pedido, y luego colocarlo en Borrador."))

        # Continuar con el proceso normal de escritura
        return super().write(vals)