
import logging

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError

#_logger = logging.getLogger(__name__)
class AccountPayment(models.Model):
    _inherit = 'account.payment.method'

    
