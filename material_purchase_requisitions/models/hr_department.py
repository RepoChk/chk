# -*- coding: utf-8 -*-

from odoo import models, fields

class HRDepartment(models.Model):
    _inherit = 'hr.department'

    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
    )

    gc_user_id = fields.Many2one(
        'res.users',
        string='Usario del Gerente',
        help='Acá debe asignar el usuario del gerente del departamento',
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
