# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.onchange('date')
    def onchange_date(self):
        for rec in self:
            if rec.date:
                rate = self.env['res.currency.rate'].search([('currency_id', '=', rec.currency_id_dif.id), ('name', '=', rec.date)]).inverse_company_rate
                if not rate:
                    raise UserError(_(f"No existe tasa de cambio para la fecha {rec.date.strftime('%d-%m-%Y')}."))
                rec.tax_today = rate
