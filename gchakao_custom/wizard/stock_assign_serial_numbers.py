# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import datetime


class StockAssignSerialNumbers(models.TransientModel):
    _inherit = 'stock.assign.serial'

    is_battery = fields.Boolean(related='product_id.is_battery')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    next_serial_number = fields.Char('Primer NS', required=True, compute='_compute_next_serial_number', store=True,)

    def _create_seq_if_not_exist(self):
        name_seq = 'stock.assign.serial.seq.company_'+str(self.company_id.id)
        IrSequence = self.env['ir.sequence'].with_company(self.company_id)

        if not IrSequence.search([('code', '=', name_seq)]):
            IrSequence.sudo().create({
                'prefix': f'%(year)s%(month)s%(day)s',
                'name': 'Batery sequence',
                'code': name_seq,
                'implementation': 'no_gap',
                'padding': 8,
                'number_increment': 1,
                'company_id': self.company_id.id, 
            })
        return True    

    @api.depends('is_battery')
    def _compute_next_serial_number(self):
        self._create_seq_if_not_exist()
        name_seq = 'stock.assign.serial.seq.company_'+str(self.company_id.id)
        sequence = self.env['ir.sequence'].search([('code', '=', name_seq)])
        date_now = datetime.datetime.now()
        next_serial_number = f'{date_now.year}{str(date_now.month).zfill(2)}{str(date_now.day).zfill(2)}{str(sequence.number_next_actual).zfill(sequence.padding)}'
        self.next_serial_number = next_serial_number

    def action_confirm_lot(self):
        name_seq = 'stock.assign.serial.seq.company_'+str(self.company_id.id)
        for i in range(0, self.next_serial_count):
            n = self.env['ir.sequence'].next_by_code(name_seq)
        return n

    def generate_serial_numbers(self):
        self.ensure_one()
        res = super().generate_serial_numbers()
        self.action_confirm_lot()
        return res