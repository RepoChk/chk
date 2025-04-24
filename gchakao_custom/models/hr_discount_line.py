# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrDiscountLine(models.Model):
    _name = 'hr.discount.line'
    _description = 'Lienas de Descuentos en Nómina'

    name = fields.Char(
        string='Nombre',
    )

    discount_id = fields.Many2one(
        'hr.discount',
        string='Descuento',
    )

    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Recibo de nómina',
    )

    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Lote',
        store=True,
    )

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Divisa de Referencia",
                                      default=lambda self: self.env.company.currency_id_dif)
    currency_id_company = fields.Many2one("res.currency",
                                          string="Divisa compañia",
                                          default=lambda self: self.env.company.currency_id)
    employee_id = fields.Many2one('hr.employee', string='Empleado', related='payslip_id.employee_id', store=True,)
    discount_type_id = fields.Many2one('hr.discount.type', string='Tipo descuento')
    amount_usd = fields.Monetary(string='Monto USD', currency_field='currency_id_dif',)
    amount_bs = fields.Monetary(string='Monto', currency_field='currency_id_company',)
    rate = fields.Float(string="Tasa", related='payslip_id.tasa_cambio', digits='Dual_Currency_rate', store=True,)
    date_from = fields.Date(string='', related='payslip_id.date_from', store=True)
    date_to = fields.Date(string='', related='payslip_id.date_to', store=True)

    @api.onchange('rate','amount_bs')
    def _onchange_amount_bs(self):
        for rec in self:
            rate = rec.rate or 1
            rec.amount_usd = rec.amount_bs / rate if rec.amount_bs > 0 else 0

    @api.onchange('rate','amount_usd')
    def _onchange_amount_usd(self):
        for rec in self:
            rate = rec.rate or 1
            rec.amount_bs = rec.amount_usd * rate if rec.amount_usd > 0 else 0
