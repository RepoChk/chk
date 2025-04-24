# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError


class AccountDebitNoteInherit(models.TransientModel):
    _inherit = 'account.debit.note'

    invoice_number = fields.Char(
        string='Número de Factura',
        compute='_compute_invoice_number_seq')


    @api.depends('journal_id')
    def _compute_invoice_number_seq(self):
        for rec in self:
            next_number = ''
            if rec.journal_id:
                sequence = rec.journal_id.invoice_seq_id
                prefix = sequence.prefix if sequence.prefix else ''
                if sequence and rec.move_type == 'out_invoice':
                    next_number = f'{prefix}{str(sequence.number_next_actual).zfill(sequence.padding)}'
            rec.invoice_number = next_number


    def _prepare_default_values(self, move):
        res = super()._prepare_default_values(move)
        res.update({
            'invoice_number': '',
            'nro_ctrl': '',
            'invoice_user_id': move.invoice_user_id.id,
            'team_id': move.team_id.id,
            'branch_id': move.branch_id.id,
        })
        return res