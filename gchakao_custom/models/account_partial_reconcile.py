from odoo import models, api, fields, _
from datetime import datetime, timedelta

class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def unlink(self):
        for record in self:
            user = self.env.user
            payment_info = '/'
            if record.credit_move_id.payment_id:
                payment_info = record.credit_move_id.payment_id.name
            elif record.debit_move_id.payment_id:
                payment_info = record.debit_move_id.payment_id.name
            elif record.debit_move_id and not record.debit_move_id.payment_id:
                payment_info = record.debit_move_id.move_id.name
            elif record.credit_move_id and not record.credit_move_id.payment_id:
                payment_info = record.credit_move_id.move_id.name
            date = datetime.now()
            new_date = date - timedelta(hours=4)
            formatted_date = new_date.strftime('%d-%m-%Y %H:%M')
            message = _(
                'El documento %(payment_info)s ha sido desconciliado por %(user_name)s '
                'el %(date)s.',
                payment_info=payment_info,
                user_name=user.name,
                date=formatted_date
            )
            record.debit_move_id.move_id.message_post(body=message)
        return super(AccountPartialReconcile, self).unlink()