# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError,UserError
import datetime

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    def create(self, vals):
        if isinstance(vals, list):
            for val in vals:
                company = self.env['res.company'].browse(val.get('company_id') or self.env.company.id)
                if 'stock_move_id' in val:
                    stock_move_id = self.env['stock.move'].search([('id', '=', val['stock_move_id'])])
                    if company.return_actual_cost:
                        #verificar si el tipo de operacion es de entrada y si posee en el picking_id el grupo se aprovisiona y si tiene dentro de ese grupo una orden de venta
                        if stock_move_id.picking_id.picking_type_id.code == 'incoming' and stock_move_id.picking_id.group_id and stock_move_id.picking_id.group_id.sale_id:
                            #reeemplazar los valores de value, unit_cost, remaining_value
                            product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                            if product_id.with_company(company.id).cost_method in ('average', 'fifo'):
                                val['value'] = product_id.with_company(company.id).standard_price * float(val['quantity'])
                                val['unit_cost'] = product_id.with_company(company.id).standard_price
                                val['remaining_value'] = product_id.with_company(company.id).standard_price * float(val['quantity'])
                                #reemplaza tambien los valores en dolares
                                val['value_usd'] = product_id.with_company(company.id).standard_price_usd * float(val['quantity'])
                                val['unit_cost_usd'] = product_id.with_company(company.id).standard_price_usd
                                val['remaining_value_usd'] = product_id.with_company(company.id).standard_price_usd * float(val['quantity'])
                                if val['unit_cost'] == 0 or val['unit_cost_usd'] == 0:
                                    raise ValidationError(_("The cost and dollar cost of the product cannot be 0"))
                                new_rate = val['unit_cost'] / val['unit_cost_usd']
                                val['tasa'] = new_rate
                    if not 'unit_cost_usd' in val:
                        #verificar si el tipo de operacion es de entrada y es una ubicacion de perdida de inventario
                        if stock_move_id.location_id.usage == 'inventory' and float(val['quantity']) > 0:
                                #reeemplazar los valores de value, unit_cost, remaining_value
                                product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                                if product_id.with_company(company.id).cost_method in ('average', 'fifo'):
                                    #reemplaza los valores en dolares
                                    val['value_usd'] = product_id.with_company(company.id).standard_price_usd * float(val['quantity'])
                                    val['unit_cost_usd'] = product_id.with_company(company.id).standard_price_usd
                                    val['remaining_value_usd'] = product_id.with_company(company.id).standard_price_usd * float(val['quantity'])
                                    if val['unit_cost'] == 0 or val['unit_cost_usd'] == 0:
                                        raise ValidationError(_("The cost and dollar cost of the product cannot be 0"))
                                    new_rate = val['unit_cost'] / val['unit_cost_usd']
                                    val['tasa'] = new_rate

                if not 'unit_cost_usd' in val and not 'value_usd' in val:
                    if val.get('quantity'):
                        if float(val['quantity']) != 0:
                            supplier = False
                            product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                            standard_price_usd = 0
                            new_rate = company.currency_id_dif.inverse_company_rate
                            if 'stock_move_id' in val:
                                stock_move_id = self.env['stock.move'].search([('id', '=', val['stock_move_id'])])
                                if stock_move_id:
                                    picking_id = stock_move_id.picking_id
                                    date = datetime.date.today()
                                    if picking_id:
                                        date = picking_id.date_of_transfer or picking_id.create_date
                                    new_rate_ids = company.currency_id_dif._get_rates(company,date)
                                    if new_rate_ids:
                                        new_rate = 1 / new_rate_ids[company.currency_id_dif.id]
                                if stock_move_id.location_id.usage in ['supplier','production']:
                                    supplier = True
                                else:
                                    if 'tasa' in val:
                                        new_rate = val['tasa']

                            if 'stock_move_id' in val:
                                standard_price_usd = float(val['unit_cost']) / new_rate
                            else:
                                standard_price_usd = product_id.with_company(company.id).standard_price_usd
                            val['unit_cost_usd'] = round(standard_price_usd,company.currency_id_dif.decimal_places)
                            val['value_usd'] = float(val['quantity']) * val['unit_cost_usd']
                            val['tasa'] = new_rate
                            if product_id.with_company(company.id).cost_method in ('average', 'fifo') and supplier:
                                val['remaining_value_usd'] = float(val['quantity']) * standard_price_usd
                            if 'stock_move_id' in val:
                                stock_move_id = self.env['stock.move'].search([('id', '=', val.get('stock_move_id'))])
                                if stock_move_id.location_id.usage in ['supplier','production']:
                                    product_id.with_company(company.id).standard_price_usd = standard_price_usd
                                    #product_id.standard_price = standard_price_usd * new_rate
                        else:
                            product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                            val['value_usd'] = product_id.qty_available * product_id.with_company(company.id).standard_price_usd
                else:
                    product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                    if val.get('stock_move_id'):
                        stock_move_id = self.env['stock.move'].search([('id', '=', val.get('stock_move_id'))])
                        if stock_move_id.location_id.usage in ['supplier','production']:
                            if product_id.with_company(company.id).cost_method == 'average':
                                if product_id.with_company(company.id).standard_price_usd == 0:
                                    product_id.with_company(company.id).standard_price_usd = val['unit_cost_usd']
        else:
            company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
            if 'stock_move_id' in vals and company.return_actual_cost:
                stock_move_id = self.env['stock.move'].search([('id', '=', vals['stock_move_id'])])
                #verificar si el tipo de operacion es de entrada y si posee en el picking_id el grupo se aprovisiona y si tiene dentro de ese grupo una orden de venta
                if stock_move_id.picking_id.picking_type_id.code == 'incoming' and stock_move_id.picking_id.group_id and stock_move_id.picking_id.group_id.sale_id:
                    #reeemplazar los valores de value, unit_cost, remaining_value
                    product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                    if product_id.with_company(company.id).cost_method in ('average', 'fifo'):
                        vals['value'] = product_id.with_company(company.id).standard_price * float(vals['quantity'])
                        vals['unit_cost'] = product_id.with_company(company.id).standard_price
                        vals['remaining_value'] = product_id.with_company(company.id).standard_price * float(vals['quantity'])
                        #reemplaza tambien los valores en dolares
                        vals['value_usd'] = product_id.with_company(company.id).standard_price_usd * float(vals['quantity'])
                        vals['unit_cost_usd'] = product_id.with_company(company.id).standard_price_usd
                        vals['remaining_value_usd'] = product_id.with_company(company.id).standard_price_usd * float(vals['quantity'])
                        if vals['unit_cost'] == 0 or vals['unit_cost_usd'] == 0:
                            raise ValidationError(_("The cost and dollar cost of the product cannot be 0"))
                        new_rate = vals['unit_cost'] / vals['unit_cost_usd']
                        vals['tasa'] = new_rate

            if not 'unit_cost_usd' in vals and not 'value_usd' in vals:
                if 'quantity' in vals:
                    if float(vals['quantity']) != 0:
                        supplier = False
                        product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                        standard_price_usd = 0
                        # tasa = self.env.company.currency_id_dif
                        new_rate = company.currency_id_dif.inverse_company_rate
                        if 'stock_move_id' in vals:
                            stock_move_id = self.env['stock.move'].search([('id', '=', vals['stock_move_id'])])
                            if stock_move_id:
                                picking_id = stock_move_id.picking_id
                                date = datetime.date.today()
                                if picking_id:
                                    date = picking_id.date_of_transfer or picking_id.create_date
                                new_rate_ids = company.currency_id_dif._get_rates(company,date)
                                if new_rate_ids:
                                    new_rate = 1 / new_rate_ids[company.currency_id_dif.id]
                            if stock_move_id.location_id.usage == 'supplier':
                                supplier = True
                            else:
                                if 'tasa' in vals:
                                    new_rate = vals['tasa']
                            standard_price_usd = float(vals['unit_cost']) / new_rate
                        else:
                            standard_price_usd = product_id.with_company(company.id).standard_price_usd
                        vals['unit_cost_usd'] = round(standard_price_usd,company.currency_id_dif.decimal_places)
                        vals['value_usd'] = float(vals['quantity']) * vals['unit_cost_usd']
                        vals['tasa'] = new_rate
                        if vals.get('stock_move_id'):
                            stock_move_id = self.env['stock.move'].search([('id', '=', vals.get('stock_move_id'))])
                            if stock_move_id.location_id.usage in ['supplier','production']:
                                supplier = True
                                product_id.with_company(company.id).standard_price_usd = standard_price_usd
                                # product_id.standard_price = standard_price_usd * new_rate
                        if product_id.with_company(company.id).cost_method in ('average', 'fifo') and supplier:
                            vals['remaining_value_usd'] = float(vals['quantity']) * standard_price_usd
                    else:
                        product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                        if float(vals['value']) < 0:
                            vals['value_usd'] = float(vals['value']) / (company.currency_id_dif.inverse_company_rate)
                            #vals['value_usd'] = product_id.with_company(company.id).qty_available * product_id.with_company(company.id).standard_price_usd
            else:
                product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                if vals.get('stock_move_id'):
                    stock_move_id = self.env['stock.move'].search([('id', '=', vals.get('stock_move_id'))])
                    if stock_move_id.location_id.usage in ['supplier','production']:
                        if product_id.with_company(company.id).cost_method == 'average':
                            if product_id.with_company(company.id).standard_price_usd == 0:
                                valoracion_antigua = self.env['stock.valuation.layer'].search([('product_id', '=', vals['product_id']),('stock_move_id', '=', stock_move_id.id)])
                                product_id.with_company(company.id).standard_price_usd = valoracion_antigua.unit_cost_usd or 0
        res = super(StockValuationLayer, self).create(vals)
        for sl in res:
            if sl.stock_move_id:
                if sl.stock_move_id.location_id.usage in ['supplier','production'] and not sl.stock_landed_cost_id:
                    if sl.product_id.with_company(company.id).cost_method == 'average':
                        sl.product_id.with_company(company.id).standard_price_usd = sl.product_id.value_usd_svl / sl.product_id.with_company(company.id).quantity_svl

        return res