# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from email.policy import default
from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
import base64
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

class HRContractRate(models.Model):
    _name = 'hr.contract.rate'
    _description = 'Tasa de Cambio para Contratos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc, id desc'

    name = fields.Date(string='Fecha', default=lambda self: fields.datetime.now(), required=True, readonly=True)
    rate = fields.Float(string='Tipo de Cambio', default=1, tracking=True, required=True,)
    state = fields.Selection([
        ('draft', 'Borrador'), 
        ('confirmed', 'Confirmado'), 
        ('done', 'Hecho')], 
        default='draft', 
        help='Borrador: estatus por defecto al momento de crear el registro\nConfirmado: este estatus permite recalcular los montos en bolivares del contrato\nHecho: en este estatus queda en desuso la tasa', 
        string='Estatus', 
        tracking=True,
    )
    
    def button_confirmed(self):
        confirmed = self.env['hr.contract.rate'].search([('state', '=', 'confirmed')], limit=1)
        if confirmed:
            raise UserError('Ya existe una tasa con el estatus "Confirmado"')
        self.state='confirmed'
    
    def button_draft(self):
        self.state='draft'

    def button_calculate(self):
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('calculate', '=', True),
            ('company_id', '=', self.env.company.id)
        ])
        
        update = False
        rate = self.rate
        for res in contracts:
            if self.state != 'confirmed':
                raise UserError('Solo puede completar este proceso en estatus "Confirmado"')
            wage = rate * res.wage_usd
            bono_ayuda_bs = rate * res.bono_ayuda_usd if res.bono_ayuda_usd > 0 else 0
            commission_bs = rate * res.commission_usd if res.commission_usd > 0 else 0
            indicator_bs = rate * res.indicator_usd if res.indicator_usd > 0 else 0
            HED = rate * res.HED_usd if res.HED_usd > 0 else 0
            HEN = rate * res.HEN_usd if res.HEN_usd > 0 else 0

            update = res.write({
                'wage': wage,
                'bono_ayuda_bs': bono_ayuda_bs,
                'commission_bs': commission_bs,
                'indicator_bs': indicator_bs,
                'HED': HED,
                'HEN': HEN,
                'hr_rate_last': self.rate,
            })

        if update:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Proceso exitoso'),
                    'message': _('Sueldos actualizados de manera exitosa'),
                    'sticky': False, # Si es True, la notificación no desaparece hasta que el usuario la cierre
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    }
                }
            }

    def button_done(self):
        self.state='done'