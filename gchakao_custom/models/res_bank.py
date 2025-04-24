# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    
    doc_identificate = fields.Char(
        string='Documento de Identificación',
    )
    