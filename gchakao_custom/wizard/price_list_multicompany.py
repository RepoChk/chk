from datetime import datetime, timedelta
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import logging

import io
from io import BytesIO


_logger = logging.getLogger(__name__)

class PriceListMulticompany(models.TransientModel):
    _name = "price.list.multicompany"
    _description = "Price List Multi-company"

    product_pricelist_ids = fields.Many2many('product.pricelist', string='Tarifa', required=True,)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    category_ids = fields.Many2many('product.category', string='Categoría', required=True, domain=[('parent_id','=',False), ])
    product_ids = fields.Many2many('product.product', string='Producto', domain="[('type','=','product')]")
    user_id = fields.Many2one('res.users', string='Usuario Activo', default=lambda self: self.env.user)
    is_qty_total = fields.Boolean(string='Cant. Total',)
    is_qty_available = fields.Boolean(string='Cant. Disponible', default=True)

    @api.onchange('category_ids')
    def onchange_category_ids(self):
        for rec in self:
            domain = dict()
            if len(rec.category_ids) > 0:
                domain = {'domain': {
                    'product_ids' :[
                        ('product_tmpl_id.categ_id.id','child_of',rec.category_ids.ids)
                        ]
                    }
                }
            else:
                domain = {'domain': {
                    'product_ids' :[
                        ('type','=','product')
                        ]
                    }
                }
            return domain

    def price_list_print(self):
        for rec in self:
            data = {
                'ids': 0,
                'form': {
                    'product_pricelist_ids': self.product_pricelist_ids.ids if self.product_pricelist_ids else [],
                    'category_ids': self.category_ids.ids if self.category_ids else [],
                    'product_ids': self.product_ids.ids if self.product_ids else [],
                    'company_id': self.company_id.id,
                    'is_qty_total': self.is_qty_total,
                    'is_qty_available': self.is_qty_available,
                }
            }
            return self.env.ref('gchakao_custom.action_prices_list_multicompany_report_template').report_action(self, data=data)

class PriceListMulticompanyReport(models.AbstractModel):
    _name = 'report.gchakao_custom.price_list_multicompany_report'

    @api.model
    def _get_companies(self):
        companias = """
            SELECT DISTINCT rc.id 
                FROM stock_warehouse AS sw 
                JOIN res_company rc ON sw.company_id = rc.id 
                JOIN res_users_stock_warehouse_rel AS wr ON wr.stock_warehouse_id = sw.id 
                WHERE wr.res_users_id = %s 
                AND rc.parent_id IS NULL 
                ORDER BY rc.id;
        """
        params = [self.env.user.id]
        self.env.cr.execute(companias, params)
        results = self.env.cr.fetchall()
        return [result[0] for result in results]

    @api.model
    def _get_locations(self):
        ubicaciones = """
            SELECT sl.id from stock_location sl where warehouse_id IN (
                SELECT sw.id from stock_warehouse AS sw
                JOIN res_company rc ON sw.company_id=rc.id
                JOIN res_users_stock_warehouse_rel AS wr ON wr.stock_warehouse_id=sw.id
                where wr.res_users_id = %s
            ) AND sl.usage = 'internal' 
        """
        params = [self.env.user.id]
        self.env.cr.execute(ubicaciones, params)
        results = self.env.cr.fetchall()
        return [result[0] for result in results]

    def get_report_data(self, product_pricelist_ids=None, category_ids=None, product_product_ids=None):
        if not category_ids:
            category_ids = self.env['product.category'].search([('parent_id', '=', False)]).ids
        if not product_product_ids:
            product_product_ids = self.env['product.product'].search([('type', '=', 'product')]).ids

        all_categories = set(category_ids)

        for parent in category_ids:
            child_categories = self.env['product.category'].search([('parent_id', '=', parent)]).ids
            all_categories.update(child_categories)
        all_categories = list(all_categories)

        location_ids = self._get_locations()
        company_ids = self._get_companies()

        if not company_ids:
            raise UserError('No tiene almacenes asignados')

        query = """
            WITH max_tax AS (
                SELECT ptr.prod_id, MAX(ata.amount) AS max_amount 
                FROM account_tax ata JOIN product_taxes_rel ptr ON ata.id = ptr.tax_id 
                WHERE ata.active = true AND ata.type_tax_use = 'sale' AND ata.company_id IN (SELECT id FROM res_company WHERE id IN %s) 
                GROUP BY ptr.prod_id 
            )
            SELECT 
                pt.measure AS medidas, pt.model, pb.name AS brand_id, SUM(sq.quantity) AS qty, SUM(sq.reserved_quantity) AS qty_reserved, pt.load_speed, 
                pt.tarps, pt.id AS product_tmpl_id, pp.id AS product_id, pc.name AS category, pt.construction_type, pt.rin, pc.parent_id AS category_father,
                COALESCE(mt.max_amount, 0) AS amount, rc.id AS company_id, rc.name AS company_name
            FROM 
                product_template AS pt 
                JOIN product_product AS pp ON pt.id = pp.product_tmpl_id 
                JOIN stock_quant AS sq ON sq.product_id = pp.id 
                JOIN stock_location AS sl ON sq.location_id = sl.id 
                JOIN product_brand AS pb ON pb.id = pt.brand_id 
                JOIN product_category AS pc ON pc.id = pt.categ_id 
                JOIN res_company AS rc ON sl.company_id = rc.id
                LEFT JOIN max_tax mt ON mt.prod_id = pt.id 
            WHERE sl.company_id IN %s AND sl.id IN %s and pp.id IN %s AND pc.id IN %s AND sl.usage = 'internal' 
                AND EXISTS (
                    SELECT 1 
                    FROM product_pricelist_item ppi 
                    WHERE ppi.product_tmpl_id = pt.id 
                    AND ppi.pricelist_id IN (SELECT id FROM product_pricelist WHERE id IN %s)
                )
            GROUP BY pt.measure, pt.model, pb.name, pt.load_speed, pt.tarps, pt.id, pp.id, 
                pc.name, pt.construction_type, pt.rin, mt.max_amount, pc.parent_id, sl.company_id, rc.id, rc.name
            ORDER BY pc.parent_id, pb.name;
        """
        params = (tuple(company_ids), tuple(company_ids), tuple(location_ids), tuple(product_product_ids), tuple(all_categories), tuple(product_pricelist_ids))
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()
        return results

    def _get_report_values(self, docids, data=None):
        company_id = self.env['res.company'].browse(data['form']['company_id'])
        company_ids = self._get_companies()
        data_list = []
        category_ids = []
        product_pricelist_ids = []
        product_ids = []

        if data['form']['product_pricelist_ids']:
            product_pricelist_ids = data['form']['product_pricelist_ids']
        if data['form']['category_ids']:
            category_ids = data['form']['category_ids']
        if data['form']['product_ids']:
            product_ids = data['form']['product_ids']

        all_categories = set(category_ids)

        for parent in category_ids:
            child_categories = self.env['product.category'].search([('parent_id', '=', parent)]).ids
            all_categories.update(child_categories)

        all_categories = list(all_categories)
        is_qty_total = data['form']['is_qty_total']
        is_qty_available = data['form']['is_qty_available']

        price_list_ids = self.env['product.pricelist'].browse(product_pricelist_ids)
        company_list_ids = self.env['res.company'].browse(company_ids)
        products = self.get_report_data(product_pricelist_ids, all_categories, product_ids)

        if not products:
            raise UserError('No hay registros para imprimir')

        def sort_key(p):
            if p['category_father'] is None or p['category_father'] == '':
                return (0, p['category'])
            return (1, p['category_father'], p['category'])

        products = sorted(products, key=sort_key)
        category_names = []
        product_info = {}

        for p in products:
            if p['category'] not in category_names:
                category_names.append(p['category'])
            
            medidas = p['medidas']
            if p['construction_type'] == 'r':
                medidas += 'R'
            elif p['construction_type'] == 'c':
                medidas += '-'
            rin = p.get('rin')
            if rin is not None and rin != 0:
                if isinstance(rin, (int, float)) and rin.is_integer():
                    medidas += str(int(rin))
                else:
                    medidas += str(rin)
            
            product_key = (p['product_tmpl_id'], p['product_id'], medidas)
            if product_key not in product_info:
                product_info[product_key] = {
                    'category': p['category'], 
                    'measure': medidas,
                    'model': p['model'],
                    'brand_id': p['brand_id'],
                    'construction_type': p['construction_type'],
                    'load_speed': p['load_speed'],
                    'tarps': p['tarps'],
                    'product_tmpl_id': p['product_tmpl_id'],
                    'product_id': p['product_id'],
                    'amount': p['amount'],
                    'aliquot': 'G' if int(p['amount']) > 0 else 'E',
                    'pricelist_ids': [],
                    'qty_by_company': {company.id: {'company_name': company.name, 'company_id': company.id, 'qty': 0, 'qty_reserved': 0, 'qty_available': 0} for company in company_list_ids},
                    'processed_pricelist_ids': set()  # aca rastreo los ids de las listas de precios procesadas
                }
            
            product_info[product_key]['qty_by_company'][p['company_id']] = {
                'company_name': p['company_name'],
                'company_id': p['company_id'],
                'qty': (p['qty'] or 0),
                'qty_reserved': p['qty_reserved'],
                'qty_available' : (p['qty'] or 0) - (p['qty_reserved'] or 0)
            }

            for price in price_list_ids:
                if price.id not in product_info[product_key]['processed_pricelist_ids']:
                    price_list = {}
                    exist = False
                    for item in price.item_ids:
                        price_amount = 0
                        price_amount_total = 0
                        if item.product_tmpl_id.id == product_info[product_key]['product_tmpl_id'] and item.pricelist_id.id == price.id:
                            exist = True
                            price_amount = item.fixed_price + (item.fixed_price * product_info[product_key]['amount']) / 100 if int(product_info[product_key]['amount']) > 0 else item.fixed_price
                            price_amount_total = price_amount * product_info[product_key]['qty_by_company'][p['company_id']]['qty']
                            price_list = {
                                'list_id': price.id,
                                'list_name': price.name,
                                'item_id': item.id,
                                'price': price_amount,
                                'price_total': price_amount_total,
                                'product_tmpl_id': item.product_tmpl_id.id,
                            }
                        if not exist:
                            price_list = {
                                'list_id': price.id,
                                'list_name': price.name,
                                'item_id': False,
                                'price': price_amount,
                                'price_total': price_amount_total,
                                'product_tmpl_id': item.product_tmpl_id.id,
                            }
                    product_info[product_key]['pricelist_ids'].append(price_list)
                    product_info[product_key]['processed_pricelist_ids'].add(price.id)  # aqui marco la lista de precios como procesada
        
        # Aqui elimino los ids procesados antes de devolver los datos
        for product_key, values in product_info.items():
            del values['processed_pricelist_ids']
            data_list.append(values)

        return {
            'companies': company_list_ids,
            'pricelist_ids': price_list_ids,
            'company': company_id,
            'data': data_list,
            'category_names': category_names,
            'is_qty_total': is_qty_total,
            'is_qty_available': is_qty_available,
        }
