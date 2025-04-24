# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def js_assign_outstanding_line(self, line_id):
        # verifica si el asiento es un anticipo
        account_invoice = self.line_ids.filtered(
            lambda x: x.account_id.account_type in ('asset_receivable', 'liability_payable'))
        line = self.env['account.move.line'].browse(line_id)
        if account_invoice.account_id == line.account_id:
            lines = super(AccountMove, self).js_assign_outstanding_line(line_id)
            line_ids = self.env['account.move.line'].browse(line_id)
            line_ids._compute_amount_residual_usd()
            return lines

        residual_line = line.amount_residual
        resudual_line_usd = line.amount_residual_usd
        residual_invoice = account_invoice.amount_residual
        residual_invoice_usd = self.amount_residual_usd

        residual = 0
        residual_usd = 0

        # buscar cual es monto menor en usd
        if abs(resudual_line_usd) < abs(residual_invoice_usd):
            residual_usd = resudual_line_usd
        else:
            residual_usd = residual_invoice_usd

        # buscar cual es monto menor en moneda local
        if abs(residual_line) < abs(residual_invoice):
            residual = residual_line
        else:
            residual = residual_invoice



        # crear un asiento contable con las mismas cuentas del pago
        # y el monto residual
        if residual_usd != 0 and residual != 0:
            lines = [(0, 0, {
                'name': line.name,
                'account_id': line.account_id.id,
                'debit': abs(residual) if line.credit > 0 else 0,
                'credit': abs(residual) if line.debit > 0 else 0,
                'debit_usd': abs(residual_usd) if line.credit > 0 else 0,
                'credit_usd': abs(residual_usd) if line.debit > 0 else 0,
                'amount_currency': (-1 * abs(residual_usd)) if line.credit > 0 else abs(residual_usd),
                'currency_id': line.currency_id.id,
                'date_maturity': line.date_maturity,
                'partner_id': line.partner_id.id,
                'tax_today': line.move_id.tax_today,
            }), (0, 0, {
                'name': line.name,
                'account_id': account_invoice.account_id.id,
                'debit': abs(residual) if line.debit > 0 else 0,
                'credit': abs(residual) if line.credit > 0 else 0,
                'debit_usd': abs(residual_usd) if line.debit > 0 else 0,
                'credit_usd': abs(residual_usd) if line.credit > 0 else 0,
                'amount_currency': (-1 * abs(residual_usd)) if line.credit > 0 else abs(residual_usd),
                'currency_id': line.currency_id.id,
                'date_maturity': line.date_maturity,
                'partner_id': line.partner_id.id,
                'tax_today': line.move_id.tax_today,
            })]
            move_vals = {
                'journal_id': line.journal_id.id,
                'line_ids': lines,
                'date': fields.Date.today(),
                'tax_today': line.move_id.tax_today,
                'ref': line.ref,
            }
            move = self.env['account.move'].create(move_vals)
            move._post(soft=False)
            line_id = move.line_ids.filtered(lambda x: x.account_id == account_invoice.account_id).id
            line_anticipo_id = move.line_ids.filtered(lambda x: x.account_id == line.account_id)
            (line_anticipo_id + line).reconcile()

        lines = super(AccountMove, self).js_assign_outstanding_line(line_id)
        line_ids = self.env['account.move.line'].browse(line_id)
        line_ids._compute_amount_residual_usd()
        return lines

    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', '|', ('amount_residual', '!=', 0.0), ('amount_residual_usd', '!=', 0.0),
                ('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            lines = self.env['account.move.line'].search(domain)
            # buscar si hay anticipos
            anticipos = False
            if move.is_inbound():
                anticipos = self.env['account.move.line'].search([
                    ('account_id', '=', move.partner_id.cuenta_anticipo_clientes_id.id),
                    ('parent_state', '=', 'posted'),
                    ('partner_id', '=', move.partner_id.id),
                    ('reconciled', '=', False)
                ])
            else:
                anticipos = self.env['account.move.line'].search([
                    ('account_id', '=', move.partner_id.cuenta_anticipo_proveedores_id.id),
                    ('parent_state', '=', 'posted'),
                    ('partner_id', '=', move.partner_id.id),
                    ('reconciled', '=', False),
                ])

            if anticipos:
                lines += anticipos

            for line in lines:
                line._compute_amount_residual_usd()
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_usd) > 0:
                        payments_widget_vals['content'].append({
                            'journal_name': '%s (%s)' % (line.ref or line.move_id.name, line.currency_id.name),
                            'amount': 0,
                            'amount_usd': abs(line.amount_residual_usd),
                            'currency_id': move.company_id.currency_id.id,
                            'currency_id_dif': move.currency_id_dif.id,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'date': fields.Date.to_string(line.date),
                            'account_payment_id': line.payment_id.id,
                        })
                        continue
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual)
                    amount_usd = abs(line.amount_residual_usd)
                else:
                    # Different foreign currencies.
                    # amount = line.company_currency_id._convert(
                    #     abs(line.amount_residual),
                    #     move.currency_id,
                    #     move.company_id,
                    #     line.date,
                    # )
                    amount = abs(line.amount_residual)
                    amount_usd = abs(line.amount_residual_usd)

                if move.currency_id.is_zero(amount) and amount_usd == 0:
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': '%s (%s)' % (line.ref or line.move_id.name, line.currency_id.name),
                    'amount': amount,
                    'amount_usd': amount_usd,
                    'currency_id': move.company_id.currency_id.id,
                    'currency_id_dif': move.currency_id_dif.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue
            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True
