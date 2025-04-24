# -*- coding: utf-8 -*-

from odoo import models, _, fields, api
from odoo.exceptions import UserError


class AccountMoveReversalInherit(models.TransientModel):
    _inherit = 'account.move.reversal'

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario',
        required=True,
        check_company=True,
    )

    nro_ctrl = fields.Char(
        'Número de Control', size=32,
        help="Número utilizado para gestionar facturas preimpresas, por ley "
             "Necesito poner aquí este número para poder declarar"
             "Informes fiscales correctamente.", store=True, readonly=False)

    invoice_number = fields.Char(
        string='Número de Factura',
        compute='_compute_invoice_number_seq')

    motive = fields.Selection(
        string='Motivo de la Nota',
        selection=[
            ('d', 'Devolución'), 
            ('dr', 'Devolución por refacturación'), 
            ('dreu', 'Devolución por reubicación'), 
            ('de', 'Descuento'),
            ('dp', 'Descuento por pronto'),
            ('dg', 'Descuento por garantía'),
            ('dc', 'Descuento por compensación 4%'),
            ('dcc', 'Descuento por compensación 2%'),
            ('ap', 'Ajuste de precio'),
        ]
    ) 

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

    @api.depends('journal_id')
    def _compute_journal_seq(self):
        for rec in self:
            next_serial_number = ''
            if rec.journal_id:
                sequence = rec.journal_id.invoice_ctrl_seq_id
                refix = sequence.prefix if sequence.prefix else ''
                if sequence and rec.move_type == 'out_invoice':
                    next_serial_number = f'{refix}{str(sequence.number_next_actual).zfill(sequence.padding)}'
            rec.nro_ctrl = next_serial_number

    # def reverse_moves(self, is_modify=False):
    #     for rec in self:
    #         if rec.journal_id.invoice_seq_id and rec.move_type == 'out_invoice':
    #             name_seq = rec.journal_id.invoice_seq_id.code
    #             self.env['ir.sequence'].next_by_code(name_seq)

    #         if rec.journal_id.invoice_ctrl_seq_id and rec.move_type == 'out_invoice':
    #             name_seq = rec.journal_id.invoice_ctrl_seq_id.code
    #             self.env['ir.sequence'].next_by_code(name_seq)
    #     return super().reverse_moves(is_modify)

    def _prepare_default_reversal(self, move):
        res = super()._prepare_default_reversal(move)
        for rec in self:
            res.update({
                'invoice_number': '',
                'nro_ctrl': '',
                'motive': rec.motive,
            })
        return res