# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    filler = fields.Float(
        string='Filler', digits=(12, 4), tracking=True
    )

    brand_id = fields.Many2one(
        'product.brand', string='Marca', tracking=True
    )

    measure = fields.Char(
        string='Medida', tracking=True
    )

    model = fields.Char(
        string='Modelo', tracking=True
    )

    tarps = fields.Char(
        string='Lonas', tracking=True
    )

    load_speed = fields.Char(
        string='Load/Speed', tracking=True
    )

    rin = fields.Float(
        string='Rin', tracking=True
    )

    tier = fields.Selection(
        selection=[
            ('1', 'TIER-1'),
            ('2', 'TIER-2'),
            ('3', 'TIER-3'),
            ('4', 'TIER-4'),
            ('5', 'TIER-5'),
            ],
        string='TIER', tracking=True
    )

    type_tire = fields.Char(
        string='Tipo de Caucho', tracking=True
    )

    construction_type = fields.Selection(
        string='Tipo de Construcción', selection=[('c', 'C'), ('r', 'R')], tracking=True
    )

    tire_class = fields.Char(
        string='Clase', tracking=True
    )

    qty_hq = fields.Char(
        string='Qty Of 40HQ', tracking=True
    )

    is_battery = fields.Boolean(
        string='Es batería', 
        help='Marcar si el producto es batería: Esto facilitara la asignación de seriales al momento de su compra/venta',
    )

    is_sequence = fields.Boolean(related='categ_id.is_sequence')

    customer_no_fiscal_taxes_ids = fields.Many2many(
        'account.tax', string="Impuesto para Cliente No Fiscal",
        help="Especifique los impuestos no fiscales aplicables a este producto."
    )
    
    @api.depends('product_variant_ids.default_code', 'categ_id')
    def _compute_default_code(self):
        for record in self:
            record._compute_template_field_from_variant_field('default_code')
            if record.categ_id.is_sequence:
                if not record.default_code or record.default_code == '':
                    record.default_code = record.categ_id.category_seq_number_next

    
    @api.onchange('is_battery')
    def onchange_is_battery(self):
        if self.is_battery:
            self.tracking = 'serial'
        else:
            self.tracking = 'none'

    @api.constrains('filler')
    def _chek_filler(self):
        for rec in self:
            if rec.categ_id.type_category == 'N':
                if rec.filler <= 0.0:
                    raise ValidationError('Disculpe, el campo Fille no debe ser menor a 0.')    

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            categ_id = self.env['product.category'].browse(vals.get('categ_id'))
            if categ_id.is_sequence and categ_id.category_seq_id:
                seq = self.env['ir.sequence'].next_by_code(categ_id.category_seq_id.code)
                _logger.info(f"Generated sequence: {seq} for category: {categ_id.name}")
                vals['default_code'] = seq
        return super(ProductTemplate, self).create(vals_list)

    def assign_sequence_to_storable_products(self):
        storable_products = self.search([('categ_id.is_sequence', '=', True),])
        storable_products = storable_products.sorted(key=lambda p: p.categ_id.name)
        for product in storable_products:
            if product.categ_id and product.categ_id.is_sequence:
                seq = self.env["ir.sequence"].next_by_code(product.categ_id.category_seq_id.code)
                product.default_code = seq
