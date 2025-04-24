from odoo import api, fields, models, _
from datetime import datetime, date
from odoo.exceptions import UserError, ValidationError

class ApprovalCategoryApprover(models.Model):
    _inherit = 'approval.category.approver'

    is_limited_by_amount = fields.Boolean(string='Limitar por monto')
    is_high_payment_approver = fields.Boolean(string='Requeridos para pagos mayores')
