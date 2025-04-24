# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    analytic_distribution_char = fields.Char(
        string='Distribución Analitica GC',
        compute='_compute_analytic_distribution_char',
        readonly=False,
        store=True,
    )

    @api.depends('analytic_distribution')
    def _compute_analytic_distribution_char(self):
        for rec in self:
            rec.analytic_distribution_char = ''
            if rec.analytic_distribution:
                if isinstance(rec.analytic_distribution, str):
                    analytic_distribution_list = json.loads(rec.analytic_distribution)
                else:
                    analytic_distribution_list = rec.analytic_distribution

                names = []
                for distribution in analytic_distribution_list:
                    account = self.env['account.analytic.account'].browse(int(distribution))
                    if account.exists():
                        names.append(f'[{account[0].code}] {account[0].name}')
                
                rec.analytic_distribution_char = ', '.join(names)