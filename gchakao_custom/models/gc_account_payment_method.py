# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from email.policy import default
from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
import base64
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

class GCAccountPaymentMethod(models.Model):
    _name = 'gc.account.payment.method'
    _description = "Metodos de pago para diarios"

    name = fields.Char(
        string='Nombre',
    )

    payment_type = fields.Selection(
        string='Tipo', 
        selection=[('inbound', 'Entrantes'), ('outbound', 'Salientes')], 
    )

    requires_conciliation = fields.Boolean(
        string='Requiere conciliación',
    )

    @api.onchange('requires_conciliation')
    def _onchange_requires_conciliation(self):
        if not isinstance(self.name, str):
            self.name = str(self.name)
            
        if self.requires_conciliation:
            if '(requiere conciliación)' not in self.name:
                self.name = f"{self.name} (requiere conciliación)"
        else:
            if '(requiere conciliación)' in self.name:
                self.name = self.name.replace(' (requiere conciliación)', '')

