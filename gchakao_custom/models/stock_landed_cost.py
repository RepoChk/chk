# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero
# from odoo.addons.queue_job.job import job

class LandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    def calculate_ddp_cost(self):
        
        for rec in self:
            
            if rec.vendor_bill_id:
                ddp_cost= 0
                total_imp = rec.amount_total_usd 
                purchase = self.env['purchase.order'].search([('invoice_ids.id', '=', rec.vendor_bill_id.id)])
                for data in purchase:
                    factor = total_imp / data.amount_total + 1

                    for line in data.order_line:
                        if line.price_unit:
                            ddp_cost = line.price_unit * factor
                        else:
                            raise UserError('Disculpe, no se ha establecido el precio de algunos de los productos en la lineas del pedido de compra.')
                            
                        line.product_id.with_context(force_company=rec.company_id.id).sudo().last_cost_usd = ddp_cost
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Actualización Exitosa'),
                        'message': _('El cálculo del Costo DDP se realizó correctamente.'),
                        'sticky': False,  # Si es True, la notificación no desaparece hasta que el usuario la cierre
                        'next': {
                            'type': 'ir.actions.act_window_close',
                        }
                    }
                }
            else:
                raise UserError(_("Disculpe, no hay una factura asociada al costo en destino."))

    def _check_sum(self):
        """ Check if each cost line its valuation lines sum to the correct amount
        and if the overall total amount is correct also """
        prec_digits = self.env.company.currency_id.decimal_places
        for landed_cost in self:
            total_amount = sum(landed_cost.valuation_adjustment_lines.mapped('additional_landed_cost'))
            difference = total_amount - landed_cost.amount_total
            
            if abs(difference) < 1:
                return True

            if not tools.float_is_zero(difference, precision_digits=prec_digits):
                return False

            val_to_cost_lines = defaultdict(lambda: 0.0)
            for val_line in landed_cost.valuation_adjustment_lines:
                val_to_cost_lines[val_line.cost_line_id] += val_line.additional_landed_cost
            if any(not tools.float_is_zero(cost_line.price_unit - val_amount, precision_digits=prec_digits)
                   for cost_line, val_amount in val_to_cost_lines.items()):
                return False
        return True



    # @job
    # def async_button_validate(self):
    #     self._check_can_validate()
    #     cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
    #     if cost_without_adjusment_lines:
    #         cost_without_adjusment_lines.compute_landed_cost()
    #     if not self._check_sum():
    #         raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

    #     for cost in self:
    #         cost = cost.with_company(cost.company_id)
    #         move = self.env['account.move']
    #         move_vals = {
    #             'journal_id': cost.account_journal_id.id,
    #             'date': cost.date,
    #             'ref': cost.name,
    #             'line_ids': [],
    #             'move_type': 'entry',
    #         }
    #         valuation_layer_ids = []
    #         cost_to_add_byproduct = defaultdict(lambda: 0.0)
    #         for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
    #             remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped('remaining_qty'))
    #             linked_layer = line.move_id.stock_valuation_layer_ids[:1]

    #             # Prorate the value at what's still in stock
    #             cost_to_add = (remaining_qty / line.move_id.quantity) * line.additional_landed_cost
    #             if not cost.company_id.currency_id.is_zero(cost_to_add):
    #                 valuation_layer = self.env['stock.valuation.layer'].create({
    #                     'value': cost_to_add,
    #                     'unit_cost': 0,
    #                     'quantity': 0,
    #                     'remaining_qty': 0,
    #                     'stock_valuation_layer_id': linked_layer.id,
    #                     'description': cost.name,
    #                     'stock_move_id': line.move_id.id,
    #                     'product_id': line.move_id.product_id.id,
    #                     'stock_landed_cost_id': cost.id,
    #                     'company_id': cost.company_id.id,
    #                 })
    #                 linked_layer.remaining_value += cost_to_add
    #                 valuation_layer_ids.append(valuation_layer.id)
    #             # Update the AVCO/FIFO
    #             product = line.move_id.product_id
    #             if product.cost_method in ['average', 'fifo']:
    #                 cost_to_add_byproduct[product] += cost_to_add
    #             # Products with manual inventory valuation are ignored because they do not need to create journal entries.
    #             if product.valuation != "real_time":
    #                 continue
    #             # remaining_qty is negative if the move is out and delivered products that were not
    #             # in stock.
    #             qty_out = 0
    #             if line.move_id._is_in():
    #                 qty_out = line.move_id.quantity - remaining_qty
    #             elif line.move_id._is_out():
    #                 qty_out = line.move_id.quantity
    #             move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)

    #         # batch standard price computation avoid recompute quantity_svl at each iteration
    #         products = self.env['product.product'].browse(p.id for p in cost_to_add_byproduct.keys())
    #         for product in products:  # iterate on recordset to prefetch efficiently quantity_svl
    #             if not float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
    #                 product.with_company(cost.company_id).sudo().with_context(disable_auto_svl=True).standard_price += cost_to_add_byproduct[product] / product.quantity_svl

    #         move_vals['stock_valuation_layer_ids'] = [(6, None, valuation_layer_ids)]
    #         # We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
    #         cost_vals = {'state': 'done'}
    #         if move_vals.get("line_ids"):
    #             move = move.create(move_vals)
    #             cost_vals.update({'account_move_id': move.id})
    #         cost.write(cost_vals)
    #         if cost.account_move_id:
    #             move._post()
    #         cost.reconcile_landed_cost()
    #     return True

    # def button_validate(self):
    #     # Call the async function
    #     self.with_delay().async_button_validate()