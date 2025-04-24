# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, time, timedelta
import pytz
import calendar
import re
import json
import io
from io import BytesIO
import xlsxwriter
import shutil
import base64
import csv
import xlwt

class MerchTransitWizard(models.TransientModel):
    _name = 'merch.transit.wizard'

    name = fields.Char('Nombre del archivo',size=32)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],default='choose')
    report = fields.Binary('Descargar Reporte', filters='.xls', readonly=True)

    landed_cost_id = fields.Many2one(
        'stock.landed.cost', 
        string='Gastos de Envío',
        required=True,
        
    )

    def generate_xls_report(self):
        active_id = self.landed_cost_id   
        purchase = self.env['purchase.order'].search([('invoice_ids.id', '=',self.landed_cost_id.vendor_bill_id.id)])
        wb1 = xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('Resumen')
        fp = BytesIO()

        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'

        number_format = xlwt.XFStyle()
        number_format.num_format_str = '#,##0.00'

        header_content_style = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170;")
        header_content_style_c = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170; align: horiz center")
        sub_header_style = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin;")
        sub_header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz center")
        sub_header_style_r = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz right")

        header_style = xlwt.easyxf("font: name Helvetica size 10 px, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz center")
        header_style_diarios = xlwt.easyxf("font: name Helvetica size 10 px, height 170; borders: left thin, right thin, top thin, bottom thin;")
        header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz center")
        header_style_r = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz right")

        sub_header_content_style = xlwt.easyxf("font: name Helvetica size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Helvetica, height 170;")
        row = 0
        col = 0
        ws1.row(row).height = 500

        ################ Variables #######################
        acumulador_qty = 0
        acumulador_total_fob = 0
        acumulador_total_ddp = 0
        costo_imp = 0
        factor_imp = 0

        ############### Cabecera #########################
    
        # ws1.write_merge(row,row, 0, 0, "AGENTE",header_style)
        # if purchase.reference:
        #     ws1.write_merge(row,row, 1, 1, purchase.reference,header_style)
        # else:    
        #     ws1.write_merge(row,row, 1, 1, " ",header_style)
        # row += 1
        ws1.write_merge(row,row, 0, 0, "PUERTO",header_style)
        if active_id.vendor_bill_id.destination_port:
            ws1.write_merge(row,row, 1, 1, active_id.vendor_bill_id.destination_port,header_style)
        else:    
            ws1.write_merge(row,row, 1, 1, " ",header_style)
        row += 1
        ws1.write_merge(row,row, 0, 0, "IMPORTADORA",header_style)
        if purchase.sub_provider_id:
            ws1.write_merge(row,row, 1, 1, purchase.sub_provider_id.name,header_style)
        else:
            ws1.write_merge(row,row, 1, 1, " ",header_style)
        row += 1
        # ws1.write_merge(row,row, 0, 0, "NAVIERA",header_style)
        # if purchase.vessel_name:
        #     ws1.write_merge(row,row, 1, 1, purchase.vessel_name,header_style)
        # else:
        #     ws1.write_merge(row,row, 1, 1, " ",header_style)
        # row += 1
        ws1.write_merge(row,row, 0, 0, "PROVEEDOR",header_style)
        if purchase.partner_id:
            ws1.write_merge(row,row, 1, 1, purchase.partner_id.name,header_style)
        else:
            ws1.write_merge(row,row, 1, 1, " ",header_style)
        row += 1
        ws1.write_merge(row,row, 0, 0, "NRO FACTURA",header_style)
        if active_id.vendor_bill_id.supplier_invoice_number:
            ws1.write_merge(row,row, 1, 1, active_id.vendor_bill_id.supplier_invoice_number,header_style)
        else:
            ws1.write_merge(row,row, 1, 1, " ",header_style)
        row += 1
        ws1.write_merge(row,row, 0, 0, "CANT",header_style)
        ws1.write_merge(row,row, 1, 1, "DESCRIPCION",header_style)
        ws1.write_merge(row,row, 2, 2, "MODELO",header_style)
        ws1.write_merge(row,row, 3, 3, "MARCA",header_style)
        ws1.write_merge(row,row, 4, 4, "FOB",header_style)
        ws1.write_merge(row,row, 5, 5, "TOTAL FOB",header_style)
        ws1.write_merge(row,row, 6, 7, "DDP IMP 100%",header_style)

        cost_imp = active_id.amount_total_usd 

        ################ Cuerpo del excel ################
        for data in purchase:
            price_cost = 0
            factor_imp = active_id.amount_total_usd / data.amount_total + 1
            for line in data.order_line:
                row += 1
                ws1.write_merge(row,row, 0, 0, line.product_qty,header_style_c)
                acumulador_qty += line.product_qty
                ws1.write_merge(row,row, 1, 1, line.product_id.name,header_style_c)
                ws1.write_merge(row,row, 2, 2, line.product_id.model,header_style_c)
                ws1.write_merge(row,row, 3, 3, line.product_id.brand_id.name,header_style_c)
                ws1.write_merge(row,row, 4, 4, line.price_unit,header_style_c)
                ws1.write_merge(row,row, 5, 5, line.price_unit * line.product_qty,number_format)
                acumulador_total_fob += line.price_unit * line.product_qty

                ws1.write_merge(row,row, 6, 6, line.price_unit * factor_imp,number_format)
                price_cost = line.price_unit * factor_imp
                ws1.write_merge(row,row, 7, 7, price_cost * line.product_qty,number_format)
                acumulador_total_ddp += (factor_imp * line.price_unit) * line.product_qty

                

        row += 1        
        ws1.write_merge(row,row, 0, 0, acumulador_qty,number_format)
        ws1.write_merge(row,row, 4, 4, "FOB",header_style)
        ws1.write_merge(row,row, 5, 5, acumulador_total_fob,number_format)
        ws1.write_merge(row,row, 6, 6, "DDP 100%",header_style)
        ws1.write_merge(row,row, 7, 7, acumulador_total_ddp,number_format)
        row += 1 
        ws1.write_merge(row,row, 6, 6, "COSTO IMP 100%",header_style)
        ws1.write_merge(row,row, 7, 7, active_id.amount_total_usd,number_format)
        row += 1 
        ws1.write_merge(row,row, 6, 6, "FACTOR IMP 100%",header_style)
        ws1.write_merge(row,row, 7, 7, active_id.amount_total_usd / acumulador_total_fob + 1)
        row += 1 

        wb1.save(fp)
        out = base64.b64encode(fp.getvalue())
        fecha  = datetime.now().strftime('%d/%m/%Y')
        self.write({'state': 'get', 'report': out, 'name':'Mercancia_en_Transito.xls'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'merch.transit.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }