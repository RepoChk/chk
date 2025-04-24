from datetime import datetime, timedelta

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import logging
import os
import io
from io import BytesIO
from PIL import Image
import tempfile
import xlsxwriter
import shutil
import base64
import csv
import xlwt
_logger = logging.getLogger(__name__)

class TomaFisica(models.TransientModel):
    _name = "physical.stocktaking.wizard"
    _description = "physical stocktaking wizard"

    
    date_now = fields.Datetime(string='Date Now', default=lambda *a:(datetime.now() - timedelta(hours=4)))
    warehouse_ids = fields.Many2many('stock.location', string='Almacen')
    category_id = fields.Many2many(comodel_name='product.category', string='Categoría')
    user_id = fields.Many2one(comodel_name='res.users', string='Usuario Activo', default=lambda x: x.env.uid)
    company_ids = fields.Many2many(comodel_name='res.company', string='Compañía', default=lambda self: self.env.companies.ids)
    
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],default='choose')
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)
    name = fields.Char('File Name', size=60)
    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.company.id)

    show_qty_av = fields.Boolean(string='¿Mostrar cantidad en existencia en el reporte?')
    show_filter = fields.Selection(string='Productos a mostrar', selection=[('todos', 'Todos los productos'), ('mayor_0', 'Existencia mayor que cero'),('igual_0', 'Sin existencia')], default='todos')
    show_filler = fields.Boolean(string='¿Mostrar filler en el reporte?')
    show_count = fields.Boolean(string='¿Mostrar conteo físico en el reporte?', default=True)

    @api.onchange('user_id')
    def _onchange_user_id(self):
        companies = self.env['res.users'].search([('id', '=', self.user_id.id)]).company_ids.ids
        return {'domain': {'company_ids': [('id', 'in', companies)]}}

    @api.onchange('company_ids')
    def onchange_location(self):
        return {'domain': {
            'warehouse_ids': [('company_id', 'in', self.company_ids.ids), ('usage', '=', 'internal')]
            }}

    def print_inventario(self):
        return {'type': 'ir.actions.report','report_name': 'gchakao_custom.physical_stocktaking_report','report_type':"qweb-pdf"}

    ##### Categorías #####
    def get_categ(self, category):
        categ = []
        temp = []
        if category.ids == []:
            category = self.env['product.category'].search([])

        for item in category:
            if item.parent_id:
                temp.append(item.id)
            else:
                xfind = self.env['product.category'].search([('parent_id', '=', item.id)])
                if xfind:
                    for line in xfind:
                        temp.append(line.id)
                else:
                    temp.append(item.id)
        temp = set(temp)
        for item in temp:
            categ.append(item)
        
        xfind = self.env['product.category'].search([('id', 'in', categ)])
        return xfind
    
    ##### Productos #####
    def _get_products(self, category):
        if self.show_filter == 'todos':
            xfind = self.env['product.product'].search([
                ('type', '=', 'product'),
                ('categ_id', '=', category.id),
            ])
            return xfind
        elif self.show_filter == 'mayor_0':
            xfind = self.env['product.product'].search([
                ('type', '=', 'product'),
                ('categ_id', '=', category.id),
                ('qty_available', '>', 0),
            ])

            result = []
            for item in xfind:
                cantidad = self.get_qty(item)
                if cantidad > 0:
                    result += item         

            return result
        else:
            xfind = self.env['product.product'].search([
                ('type', '=', 'product'),
                ('categ_id', '=', category.id),
                ('qty_available', '=', 0),
            ])
            return xfind

    ##### Cantidad en existencia #####
    def get_qty(self, producto):
        if self.warehouse_ids:
            if len(self.company_ids) > 0:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto.id),
                    ('location_id', 'in', self.warehouse_ids.ids),
                    ('quantity', '>', 0),
                    ('company_id', 'in', self.company_ids.ids)
                ])
            else:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto.id),
                    ('location_id', 'in', self.warehouse_ids.ids),
                    ('quantity', '>', 0)
                ])
        else:
            if len(self.company_ids) > 0:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto.id),
                    ('quantity', '>', 0),
                    ('company_id', 'in', self.company_ids.ids)
                ])
            else:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto.id),
                    ('quantity', '>', 0)
                ])
                 
        cantidad = 0
        for item in stock_q:
            cantidad += item.quantity

        return cantidad

    ##### Pedido del cliente #####
    def _get_orders(self, producto):
        if self.warehouse_ids:
            if len(self.company_ids) > 0:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto),
                    ('location_id', 'in', self.warehouse_ids.ids),
                    ('quantity', '>', 0),
                    ('company_id', 'in', self.company_ids.ids)
                ])
            else:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto),
                    ('location_id', 'in', self.warehouse_ids.ids),
                    ('quantity', '>', 0)
                ])
        else:
            if len(self.company_ids) > 0:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto),
                    ('quantity', '>', 0),
                    ('company_id', 'in', self.company_ids.ids)
                ])
            else:
                stock_q = self.env['stock.quant'].search([
                    ('product_id', '=', producto),
                    ('quantity', '>', 0)
                ])
        cantidad = 0
        for item in stock_q:
            cantidad += item.reserved_quantity

        return cantidad

    def get_rin(self, rin):
        if rin % 1 != 0:
            return rin
        else:
            txt = str(rin).split('.')
            return txt[0]

    # *******************  REPORTE EN EXCEL ****************************
    def generate_xls_report(self):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Toma Física')

        # Definiciones de estilo
        header_content_format = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter'})
        sub_header_format = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True})
        sub_header_center_format = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        sub_header_right_format = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'border': 1, 'align': 'right', 'valign': 'vcenter'})
        sub_header_content_format = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'valign': 'vcenter'})
        line_content_format = workbook.add_format({'font_name': 'Arial', 'valign': 'vcenter'})
        row = 0
        col = 0
        col_two = 0
        col_stock_final = 0
        # Cargar la imagen desde los datos binarios
        binaryData = self.env.company.logo

        worksheet.set_row(row, 25)
        worksheet.merge_range(row, 2, row, 6, "Toma Física de Inventario", header_content_format)

        xdate = self.date_now.strftime('%d/%m/%Y %I:%M:%S %p')
        xdate = datetime.strptime(xdate, '%d/%m/%Y %I:%M:%S %p')  # - timedelta(hours=4)
        worksheet.merge_range(row, 7, row, 9, xdate.strftime('%d/%m/%Y %I:%M:%S %p'), header_content_format)

        if self.show_qty_av:
            row += 1
            worksheet.merge_range(row, 2, row, 6, "Con cantidades en existencia", header_content_format)

        if self.show_filter == 'todos':
            row += 1
            worksheet.merge_range(row, 2, row, 6, "Todos los productos", header_content_format)
        elif self.show_filter == 'mayor_0':
            row += 1
            worksheet.merge_range(row, 2, row, 6, "Existencia mayor que cero", header_content_format)
        else:
            row += 1
            worksheet.merge_range(row, 2, row, 6, "Sin existencia", header_content_format)

        if self.show_filler:
            row += 1
            worksheet.merge_range(row, 2, row, 6, "Con filler", header_content_format)

        if self.show_count:
            row += 1
            worksheet.merge_range(row, 2, row, 6, "Con conteo físico", header_content_format)

        row += 2
        categorias = False
        if len(self.category_id) > 0:
            categorias = self.category_id
        else:
            categorias = self.env['product.category'].sudo().search([])

        warehouse_ids = False
        if len(categorias) == 0:
            raise UserError('No se consiguieron Categorías')
        if len(self.warehouse_ids) > 0:
            warehouse_ids = self.warehouse_ids
        else:
            warehouse_ids = self.env['stock.location'].sudo().search([('usage', '=', 'internal')])
        if len(warehouse_ids) == 0:
            raise UserError('No se consiguieron Ubicaciones')
        worksheet.write(row, 3, "Deposito: ", sub_header_right_format)
        worksheet.set_column(3, 3, int((len('Deposito: ') + 8) * 2))
        worksheet.merge_range(row, 4, row, 6, str(warehouse_ids.mapped('display_name')).replace('[','').replace(']',''), sub_header_content_format)
        row += 2
        productos = False
        total_categoria = subtotal_categoria = 0 
        center = right = False
        #CABECERA DE LA TABLA 
        productos_totales = self.env['product.product'].search([
                ('type', '=', 'product'),
                ('categ_id', 'in', categorias.ids),
            ])
        if len(productos_totales) == 0:
            raise UserError('No se consiguieron productos')
        for category in categorias:
            subtotal_categoria = 0 
            productos = self._get_products(category)
            if len(productos) > 0:
                worksheet.write(row, col+0, "Categoría", sub_header_center_format)
                worksheet.set_column(col+0, col+0, int((len('Categoría')+12) * 2))
                worksheet.write(row, col+1, "Código", sub_header_center_format)
                worksheet.set_column(col+1, col+1, int((len('Código')) * 2))
                worksheet.write(row, col+2, "Descripción", sub_header_center_format)
                worksheet.set_column(col+2, col+2, int((len('Descripción')+24) * 2))
                worksheet.write(row, col+3, "Modelo", sub_header_center_format)
                worksheet.set_column(col+3, col+3, int((len('Modelo')+12) * 2))
                worksheet.write(row, col+4, "Marca", sub_header_center_format)
                worksheet.write(row, col+5, "Lonas", sub_header_center_format)
                worksheet.set_column(col+5, col+5, int((len('Lonas')+2) * 2))
                worksheet.write(row, col+6, "Unidad de Medida", sub_header_center_format)
                worksheet.set_column(col+6, col+6, int((len('Unidad de Medida')+2) * 2))
                col_two = col + 6
                if self.show_filler:
                    col_two += 1
                    worksheet.write(row, col_two, "FillerT", sub_header_center_format)
                    worksheet.set_column(col_two, col_two, len('FillerT') * 2)
                col_two += 1
                worksheet.write(row, col_two, "MERC. APARTADA", sub_header_center_format)
                worksheet.set_column(col_two, col_two, len('MERC. APARTADA') * 2)
                if self.show_qty_av:
                    col_two += 1
                    worksheet.write(row, col_two, "Stock Final", sub_header_center_format)
                    worksheet.set_column(col_two, col_two, len('Stock Final') * 3)
                if self.show_count:
                    col_two += 1
                    worksheet.write(row, col_two, "Conteo Físico", sub_header_center_format)
                    worksheet.set_column(col_two, col_two, len('Conteo Físico') * 2)
                center = workbook.add_format({'align': 'center'})
                right = workbook.add_format({'align': 'right'})
                for product in productos:
                    row += 1
                    # Code
                    if product.categ_id:
                        worksheet.write(row, col+0, product.categ_id.name, center)
                    else:
                        worksheet.write(row, col+0, '', center)
                    # Code
                    if product.default_code:
                        worksheet.write(row, col+1, product.default_code, center)
                    else:
                        worksheet.write(row, col+1, '', center)
                    # Description
                    if product.name:
                        worksheet.write(row, col+2, product.name, center)
                    else:
                        worksheet.write(row, col+2, product.name, center)
                    # Model
                    if product.product_tmpl_id.model:
                        worksheet.write(row, col+3, product.product_tmpl_id.model, center)
                    else:
                        worksheet.write(row, col+3, '', center)
                    # Brand
                    if product.product_tmpl_id.brand_id:
                        worksheet.write(row, col+4, product.product_tmpl_id.brand_id.name, center)
                    else:
                        worksheet.write(row, col+4, '', center)
                    # Tarps
                    if product.product_tmpl_id.tarps == 0:
                        worksheet.write(row, col+5, 'N/A', center)
                    else:
                        worksheet.write(row, col+5, product.product_tmpl_id.tarps, center)
                    # Unidad de Medida
                    worksheet.write(row, col+6, product.uom_id.name, center)
                    # FillerT
                    col_two = col + 6
                    if self.show_filler:
                        col_two += 1
                        worksheet.write(row, col_two, round(product.filler, 3), center)
                    # Client Order
                    col_two += 1
                    worksheet.write(row, col_two, self._get_orders(product.id), center)
                    # Final Stock
                    if self.show_qty_av:
                        col_two += 1
                        cantidad_producto = self.get_qty(product)
                        worksheet.write(row, col_two, cantidad_producto, center)
                        col_stock_final = col_two - 1
                        subtotal_categoria += cantidad_producto
                        total_categoria += cantidad_producto
                    # Physical Count
                    if self.show_count:
                        col_two += 1
                        worksheet.write(row, col_two, '', center)
                if self.show_qty_av:
                    row += 1
                    worksheet.merge_range(row, 0, row, col_stock_final, "SubTotal Categoría", sub_header_right_format)
                    col_two += 1
                    worksheet.write(row, col_stock_final+1, subtotal_categoria, center)
                row += 2
        if self.show_qty_av:
            worksheet.merge_range(row, 0, row, col_stock_final, "Total Inventario", sub_header_right_format)
            worksheet.write(row, col_stock_final+1, total_categoria, header_content_format)
            row += 2

        workbook.close()

        # Convertir y codificar el contenido del libro de trabajo
        out = base64.encodebytes(output.getvalue()).decode('utf-8')
        fecha = datetime.now().strftime('%d/%m/%Y')
        self.write({'state': 'get', 'report': out, 'name': 'Toma física de inventario ' + fecha + '.xlsx'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'physical.stocktaking.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
