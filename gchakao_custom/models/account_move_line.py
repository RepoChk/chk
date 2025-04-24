# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_bs = fields.Monetary(
        currency_field='currency_id', string='Descuento', required=True, default=0.0, compute='_compute_discount', store=True,
    )

    discount_usd = fields.Monetary(
        currency_field='currency_id_dif', string='Descuento $', required=True, default=0.0, compute='_compute_discount', store=True,
    )

    filler = fields.Float(
        string='Filler', related='product_id.filler'
    )

    fillert = fields.Float(
        string='FillerT',
        compute='_compute_fillert',
        store=True
    )
    purchase_price = fields.Float(string="Costo", store=True, readonly=True)
    profitability = fields.Float(string="Ganancia", store=True, readonly=True)
    profitability_percent = fields.Float(string="Rentabilidad", store=True, readonly=True)
    early_payment_discount = fields.Float(string='% Descuento Pronto Pago', default=0.0, store=True)
    price_unit_discount = fields.Float(string="Precio Unitario con Dsct. Pronto Pago", store=True, readonly=True)
    profitability_discount = fields.Float(string="Ganancia con Dsct. Pronto Pago", store=True, readonly=True)
    profitability_percent_discount = fields.Float(string="Rentabilidad con Dsct. Pronto Pago", store=True, readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    
    @api.depends('discount','price_unit','price_unit_usd')
    def _compute_discount(self):
        for rec in self:
            discount_bs = 0
            discount_usd = 0
            if rec.discount:
                discount_bs = ((rec.discount * (rec.price_unit * rec.quantity)) / 100)
                discount_usd = ((rec.discount * (rec.price_unit_usd * rec.quantity)) / 100)
            rec.discount_bs = discount_bs
            rec.discount_usd = discount_usd

    @api.depends('product_id', 'filler', 'quantity', 'move_id.motive')
    def _compute_fillert(self):
        for line in self:
            if line.move_id.motive in ['d','dr', 'dreu', 'dgar', False]:
                line.fillert = line.filler * line.quantity
            else:
                line.fillert = 0

    analytic_distribution_char = fields.Char(
        string='Distribución Analitica GC',
        compute='_compute_analytic_distribution_char',
        readonly=False,
        store=True,
    )

    @api.depends('analytic_distribution')
    def _compute_analytic_distribution_char(self):
        for rec in self:
            rec.analytic_distribution_char = ''
            if rec.analytic_distribution:
                if isinstance(rec.analytic_distribution, str):
                    analytic_distribution_list = json.loads(rec.analytic_distribution)
                else:
                    analytic_distribution_list = rec.analytic_distribution

                names = []
                for distribution in analytic_distribution_list:
                    account = self.env['account.analytic.account'].browse(int(distribution))
                    if account.exists():
                        names.append(f'[{account[0].code}] {account[0].name}')
                
                rec.analytic_distribution_char = ', '.join(names)

    def _convert_analytic_distribution(self, analytic_distribution_char):
        account = self.env['account.analytic.account'].search([('code', '=', analytic_distribution_char.strip())], limit=1)
        
        analytic_distribution = {}

        if account:
            analytic_distribution[str(account.id)] = 100.0
        return analytic_distribution

    @api.model
    def create(self, vals):
        if 'analytic_distribution_char' in vals and vals['analytic_distribution_char']:
            analytic_distribution = self._convert_analytic_distribution(vals['analytic_distribution_char'])
            if analytic_distribution:
                vals['analytic_distribution'] = analytic_distribution

        return super(AccountMoveLine, self).create(vals)

    @api.model
    def write(self, vals):
        if 'analytic_distribution_char' in vals and vals['analytic_distribution_char']:
            analytic_distribution = self._convert_analytic_distribution(vals['analytic_distribution_char'])
            if analytic_distribution:
                vals['analytic_distribution'] = analytic_distribution

        return super(AccountMoveLine, self).write(vals)

