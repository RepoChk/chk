# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import ustr
from odoo.exceptions import UserError


class ManualWizard(models.TransientModel):
    _name = 'manual.wizard'
    _description = 'Selección de datos manuales'

    def _default_product_id(self):
        product_id = self.env['product.product'].search([('product_tmpl_id', '=', self.env.context.get('default_product_id'))])
        return product_id

    product_ids = fields.Many2many(
        'product.template',
        compute='_compute_product_ids'
    )

    warranty_id = fields.Many2one(
        'warranty.request',
        default=lambda self: self.env.context.get('default_warranty_id') or False,
    )

    product_type = fields.Selection([
        ('bateria', "Batería"), 
        ('neumatico', "Neumático"),
        ], string='Tipo de producto', required=True, default=lambda self: self.env.context.get('default_product_type') or False,)

    @api.depends('product_type')
    def _compute_product_ids(self):
        for rec in self:
            domain = [('is_warranty', '=', True),('is_battery', '=', False)]
            if rec.product_type == 'bateria':
                domain = [('is_warranty', '=', True),('is_battery', '=', True)]
            rec.product_ids = self.env['product.template'].search(domain).ids

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )

    product_id = fields.Many2one(
        'product.template',
        string='Producto',
        default=lambda self: self.env.context.get('default_product_id') or False,
        domain="[('id','in',product_ids), ]"
    )

    related_invoice_ids = fields.Many2many(
        'account.move',
        string='Facturas relacionadas',
        compute='_compute_related_invoice_ids',
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        domain="[('id', 'in', related_invoice_ids)]",
    )

    seller_id = fields.Many2one(
        'res.users',
        string='Vendedor',
        default=lambda self: self.env.context.get('default_seller_id')
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        default=lambda self: self.env.context.get('default_partner_id')
    )

    @api.depends('invoice_id','seller_id','product_id','partner_id')
    def _compute_related_invoice_ids(self):
        for rec in self:
            domain = [('state', '=', 'posted'),('move_type', '=', 'out_invoice')]
            if rec.product_id:
                domain.append(('invoice_line_ids.product_id.product_tmpl_id', '=', rec.product_id.id))
            if rec.seller_id:
                domain.append(('invoice_user_id', '=', rec.seller_id.id))
            if rec.partner_id:
                domain.append(('partner_id', '=', rec.partner_id.id))
            rec.related_invoice_ids = self.env['account.move'].search(domain, limit=100) or []

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.invoice_id = False

    line_ids = fields.Many2many(
        'account.move.line',
        compute='_compute_line_ids',
        string='Lineas de movimientos',
    )

    @api.depends('invoice_id')
    def _compute_line_ids(self):
        for rec in self:
            rec.line_ids = []
            if rec.invoice_id:
                rec.line_ids = rec.invoice_id.invoice_line_ids.ids or False