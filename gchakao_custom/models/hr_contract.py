from odoo import api, fields, models, http, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta

class HRContract(models.Model):
    _inherit = 'hr.contract'

    commission_usd = fields.Monetary(string='Comisión (USD)', tracking=True, currency_field='currency_id_dif')
    commission_bs = fields.Monetary(string='Comisión (Bs)', tracking=True,)

    bono_ayuda_usd = fields.Monetary(string='Complemento (USD)', tracking=True, currency_field='currency_id_dif')
    bono_ayuda_bs = fields.Monetary(string='Complemento (Bs)', tracking=True,)

    indicator_usd = fields.Monetary(string='Indicador (USD)', tracking=True, currency_field='currency_id_dif')
    indicator_bs = fields.Monetary(string='Indicador (Bs)', tracking=True,)

    is_discount_hc = fields.Boolean(string='Descuento HC',)
    discount_hc_usd = fields.Monetary(string='Monto', tracking=True, currency_field='currency_id_dif')

    is_average = fields.Boolean(string='Basado en salario promedio',)
    average_wage = fields.Monetary(string='Salario promedio', tracking=True, currency_field='currency_id_dif')
    
    calculate = fields.Boolean(
        string='Actualizar sueldos',
        help='Si esta activado, se van a actualizar los sueldos en Bs. a la última tasa confirmada desde el menu: "Actualizar sueldos"', 
        default=True
    )

    def _get_rate(self):
        rate = self.env['hr.contract.rate'].search([('state','=','confirmed')], order='id desc', limit=1).rate or 1
        return rate

    hr_rate_last = fields.Float(
        string='Última tasa de actualización',
        readonly=True, 
        default = 0
    )

    @api.onchange('commission_bs')
    def _onchange_commission_bs(self):
        for rec in self:
            rate = rec._get_rate()
            commission_usd = 0
            commission_bs = rec.commission_bs
            if commission_bs > 0:
                commission_usd = (commission_bs / rate)
            rec.commission_usd = commission_usd

    @api.onchange('commission_usd')
    def _onchange_commission_usd(self):
        for rec in self:
            rate = rec._get_rate()
            commission_bs = 0
            commission_usd = rec.commission_usd
            if commission_usd > 0:
                commission_bs =  (commission_usd * rate)
            rec.commission_bs = commission_bs
