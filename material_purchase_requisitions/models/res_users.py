from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'

    approving_leader_req_ids= fields.Many2many('res.users', 'approver_id', 'users_id', string='Lider Aprobador Requisiciones')