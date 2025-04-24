from datetime import datetime, timedelta
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import logging

import io
from io import BytesIO


_logger = logging.getLogger(__name__)

class ProductPriceList(models.TransientModel):
    _name = "product.price.list"
    _description = "Product Price List"

    def _domain_company_ids(self):
        company_ids = self.env.user.company_ids.ids
        return [('id', 'in', company_ids)]

    product_pricelist_ids = fields.Many2many('product.pricelist', string='Tarifa', required=True,)
    company_ids = fields.Many2many('res.company', required=True, domain=_domain_company_ids,)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    category_ids = fields.Many2many('product.category', string='Categoría', required=True, domain=[('parent_id','=',False), ])
    product_ids = fields.Many2many('product.product', string='Producto', domain="[('type','=','product')]")
    user_id = fields.Many2one('res.users', string='Usuario Activo', default=lambda self: self.env.user)
    is_qty_total = fields.Boolean(string='Cant. Total',)
    is_qty_available = fields.Boolean(string='Cant. Disponible',default=True)

    @api.model
    def _get_location_domain(self):
        user_warehouses = self.env.user.warehouse_ids
        if user_warehouses:
            return [('id', 'in', user_warehouses.lot_stock_id.ids), ('usage', '=', 'internal')]
        return [('usage', '=', 'internal')]

    location_ids = fields.Many2many(
        'stock.location', 
        string='Ubicación', 
        domain=lambda self: self._get_location_domain()
    )

    @api.model
    def default_get(self, fields):
        res = super(ProductPriceList, self).default_get(fields)
        selected_company_ids = self.env.context.get('allowed_company_ids', [])
        res['company_ids'] = [(6, 0, selected_company_ids)]
        return res

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
                    'location_ids': self.location_ids.ids if self.location_ids else [],
                    'company_id': self.company_id.id,
                    'company_ids': self.company_ids.ids,
                    'is_qty_total': self.is_qty_total,
                    'is_qty_available': self.is_qty_available,
                }
            }
            return self.env.ref('gchakao_custom.action_product_prices_list_report_template').report_action(self, data=data)

class PriceListReport(models.AbstractModel):
    _name = 'report.gchakao_custom.product_price_list_report'

    @api.model
    def get_report_data(self, company_ids, product_pricelist_ids=None, category_ids=None, location_ids=None, product_product_ids=None):
        if not company_ids:
            user_company_ids = self.env.context.get('allowed_company_ids', [])
            company_ids = self.env['res.company'].search([('id', '=', user_company_ids)]).ids
        if not category_ids:
            category_ids = self.env['product.category'].search([('parent_id', '=', False)]).ids
        if not location_ids:
            location_ids = self.env['stock.location'].sudo().search([('usage', '=', 'internal'),('company_id', 'in', company_ids)]).ids
        if not product_product_ids:
            product_product_ids = self.env['product.product'].search([('type', '=', 'product')]).ids

        all_categories = set(category_ids)

        for parent in category_ids:
            child_categories = self.env['product.category'].search([('parent_id', '=', parent)]).ids
            all_categories.update(child_categories)
        all_categories = list(all_categories)

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
                COALESCE(mt.max_amount, 0) AS amount
            FROM 
                product_template AS pt 
                JOIN product_product AS pp ON pt.id = pp.product_tmpl_id 
                JOIN stock_quant AS sq ON sq.product_id = pp.id 
                JOIN stock_location AS sl ON sq.location_id = sl.id 
                JOIN product_brand AS pb ON pb.id = pt.brand_id 
                JOIN product_category AS pc ON pc.id = pt.categ_id 
                LEFT JOIN max_tax mt ON mt.prod_id = pt.id 
            WHERE sl.company_id IN %s AND sl.id IN %s and pp.id IN %s AND pc.id IN %s AND sl.usage = 'internal' 
                AND EXISTS (
                    SELECT 1 
                    FROM product_pricelist_item ppi 
                    WHERE ppi.product_tmpl_id = pt.id 
                    AND ppi.pricelist_id IN (SELECT id FROM product_pricelist WHERE id IN %s)
                )
            GROUP BY pt.measure, pt.model, pb.name, pt.load_speed, pt.tarps, pt.id, pp.id, pc.name, pt.construction_type, pt.rin, mt.max_amount, pc.parent_id
            ORDER BY pc.parent_id, pb.name;
        """
        params = [tuple(company_ids), tuple(company_ids), tuple(location_ids), tuple(product_product_ids), tuple(all_categories), tuple(product_pricelist_ids)]
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()
        return results

    def _get_report_values(self, docids, data=None):
        company_id = self.env['res.company'].browse(data['form']['company_id'])
        data_list = []
        category_ids = []
        product_pricelist_ids = []
        product_ids = []
        location_ids = []

        if data['form']['product_pricelist_ids']:
            product_pricelist_ids = data['form']['product_pricelist_ids']
        if data['form']['category_ids']:
            category_ids = data['form']['category_ids']
        if data['form']['product_ids']:
            product_ids = data['form']['product_ids']
        if data['form']['location_ids']:
            location_ids = data['form']['location_ids']
        if data['form']['company_ids']:
            company_ids = data['form']['company_ids']

        all_categories = set(category_ids)

        for parent in category_ids:
            child_categories = self.env['product.category'].search([('parent_id', '=', parent)]).ids
            all_categories.update(child_categories)

        all_categories = list(all_categories)
        is_qty_total = data['form']['is_qty_total']
        is_qty_available = data['form']['is_qty_available']

        price_list_ids = self.env['product.pricelist'].browse(product_pricelist_ids)
        products = self.get_report_data(company_ids, product_pricelist_ids, all_categories, location_ids, product_ids)

        if not products:
            raise UserError('No hay registros para imprimir')

        def sort_key(p):
            if p['category_father'] is None or p['category_father'] == '':
                return (0, p['category'])
            return (1, p['category_father'], p['category'])

        products = sorted(products, key=sort_key)
        category_names = []
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
            values = {
                'category': p['category'], 
                'measure': medidas,
                'model': p['model'],
                'brand_id': p['brand_id'],
                'rin': p['rin'],
                'construction_type': p['construction_type'],
                'qty': (p['qty'] or 0),
                'qty_reserved': p['qty_reserved'],
                'qty_available' : (p['qty'] or 0) - (p['qty_reserved'] or 0),
                'load_speed': p['load_speed'],
                'tarps': p['tarps'],
                'product_tmpl_id': p['product_tmpl_id'],
                'product_id': p['product_id'],
                'amount': p['amount'],
                'aliquot': 'G' if int(p['amount']) > 0 else 'E',
                'pricelist_ids': [],
            }
            for price in price_list_ids:
                price_list = {}
                exist = False
                for item in price.item_ids:
                    price_amount = 0
                    price_amount_total = 0
                    if item.product_tmpl_id.id == p['product_tmpl_id'] and item.pricelist_id.id == price.id:
                        exist = True
                        price_amount = item.fixed_price + (item.fixed_price * values['amount']) / 100 if int(values['amount']) > 0 else item.fixed_price
                        price_amount_total = price_amount * values['qty']
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
                values['pricelist_ids'].append(price_list)
            data_list.append(values)
        return {
            'pricelist_ids': price_list_ids,
            'company': company_id,
            'data':data_list,
            'category_names':category_names,
            'is_qty_total':is_qty_total,
            'is_qty_available':is_qty_available,
        }