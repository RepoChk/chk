# -*- coding: UTF-8 -*-
from odoo import fields, models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    cuenta_anticipo_proveedores_id = fields.Many2one('account.account', string='Cuenta Anticipo Proveedores',
                                                        help='Cuenta contable para los anticipos de proveedores')

    cuenta_anticipo_clientes_id = fields.Many2one('account.account', string='Cuenta Anticipo Clientes',
                                                        help='Cuenta contable para los anticipos de clientes')

