import string
import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp
from datetime import timedelta, datetime, date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class AccountFiscalBook(models.Model):
    _inherit = 'account.fiscal.book'

    def get_t_type(self, doc_type=None, name=None, state=False):
        tt = ''
        if doc_type:
            #if doc_type == "N/DB" or doc_type == "N/CR":
            #validar, segun seniat las notas rectificativas deben aparecer como 01-REG y solo las NOtas de debitos como 02-COMP
            if doc_type == "N/DB":
                tt = '02-REG'
            elif doc_type == "N/CR":
                tt = '03-REG'
            elif doc_type == "FACT":
                tt = '01-REG'
        return tt  

    def get_doc_type(self, inv_id=None, iwdl_id=None, cf_id=None):
        """ Returns a string that indicates de document type. For withholding
        returns 'AJST' and for invoice docuemnts returns different values
        depending of the invoice type: Debit Note 'N/DB', Credit Note 'N/CR',
        Invoice 'FACT'.
        @param inv_id : invoice id
        @param iwdl_id: wh iva line id
        """

        res = False
        # if fb_id:
        #    obj_fb = self.env['account.fiscal.book']
        #    fb_brw = obj_fb.browse( fb_id)
        if inv_id:
            inv_obj = self.env['account.move']
            inv_brw = inv_obj.browse(inv_id)
            if inv_brw.move_type in ["in_invoice"]:
                if inv_brw.debit_origin_id:
                    res = "N/DB"
                else:
                    res = "FACT"
            elif inv_brw.move_type in ["out_invoice"]:
                if inv_brw.debit_origin_id or inv_brw.ref:
                    res = "N/DB"
                else:
                    res = "FACT"
            elif inv_brw.move_type in ["out_refund", "in_refund"]:
                res = "N/CR"

            assert res, str(inv_brw) + ": Error in the definition \
                of the document type. \n There is not type category definied for \
                your invoice."
        elif iwdl_id:
            res = 'AJST' if self.type == 'sale' else 'RET'
        # CONDICION RELACIONADO CON ELMODELO customs.form DEL MODULO l10n_ve_imex
        #        elif cf_id:
        #            res = 'F/IMP'

        return res

    def update_book_lines(self, fb_id):
        """ It updates the fiscal book lines values. Cretate, order and rank
        the book lines. Creates the book taxes too acorring to lines created.
        @param fb_id: fiscal book id
        """

        data = []
        data2= []
        iwdl_obj = self.env['account.wh.iva.line']
        fb_brw = self.browse(fb_id)
        rp_obj = self.env['res.partner']
        local_inv_affected = ''
        boll = False
        cliente = False
        proveedor = False
        inv_siva = []
        inv_iva = []
        fecha = ''
        for inv_brw in self.browse(fb_id).issue_invoice_ids:

            # if inv_brw.partner_id.people_type_company:
            #     if inv_brw.partner_id.people_type_company == 'pjnd':
            #         inv_iva += inv_brw
            #         continue
            if inv_brw.wh_iva_id.state in ['draft', 'cancel'] and (inv_brw.state == 'posted' or inv_brw.state == 'cancel') and inv_brw.sin_cred == False:
            #if inv_brw.wh_iva_id.state == 'draft' and (inv_brw.state == 'posted') and inv_brw.sin_cred == False:
                inv_siva += inv_brw
            elif inv_brw.wh_iva_id.state == 'done' and (inv_brw.state == 'posted') and inv_brw.sin_cred == False:
                inv_iva += inv_brw

            if not inv_brw.wh_iva_id and inv_brw.partner_id.wh_iva_agent == False and (inv_brw.state == 'posted' or inv_brw.state == 'cancel') and inv_brw.sin_cred == False:
                inv_siva += inv_brw
            elif not inv_brw.wh_iva_id and inv_brw.partner_id.wh_iva_agent == True and (inv_brw.state == 'posted' or inv_brw.state == 'cancel') and inv_brw.sin_cred == False:
                inv_siva += inv_brw

        #printer_fiscal = self.company_id.printer_fiscal
        busq = self.browse(fb_id)
  #       if printer_fiscal == True and busq.type == 'sale':
  #           tabla_report_z = self.env['datos.zeta.diario']
  #           date_from1 = ''
  #           date_to1 = ''
  #           local_period = self.get_time_period(self.time_period)
  #           date_from = local_period.get('dt_from')
  #           date_to = local_period.get('dt_to')
  #
  #           if len(str(date_from.month)) == 1:
  #               date_from1 = '0' + str(date_from.month)
  #           if len(str(date_to.month)) == 1:
  #               date_to1 = '0' + str(date_to.month)
  #           if len(str(date_from.month)) == 2:
  #               date_from1 = str(date_from.month)
  #           if len(str(date_to.month)) == 2:
  #               date_to1 = str(date_to.month)
  #           from_date1 = str(date_from.day) + '-' + date_from1 + '-' + str(date_from.year)
  #           to_date1 = str(date_to.day) + '-' + date_to1 + '-' + str(date_to.year)
  #
  #           domain = [
  #                     ('create_date', '>=', date_from),
  #                     ('create_date', '<=', date_to),
  #                     ('numero_ultimo_reporte_z', '>','0')
  #                    ]
  #           report_z_ids = tabla_report_z.search(domain, order='fecha_ultimo_reporte_z asc')
  # #          for iwdl_brw in iwdl_ids:
  #           for report_z in report_z_ids:
  #               # rp_brw = rp_obj._find_accounting_partner(iwdl_brw.retention_id.partner_id)
  #               # para obtener el tipo de transacción
  #               if float(report_z.ventas_exento) != 0 or float(report_z.base_imponible_ventas_iva_g) != 0  or \
  #                   float(report_z.base_imponible_ventas_iva_r) != 0 or float(report_z.base_imponible_ventas_iva_g)!= 0 or float(report_z.bi_iva_g_en_nota_de_credito)!= 0 or float(report_z.bi_iva_r_en_nota_de_credito)!= 0 or float(report_z.bi_iva_a_en_nota_de_credito)!= 0:
  #                   z_report = ''
  #                   people_type = 'N/A'
  #
  #                   t_type = fb_brw.type == 'sale' and 'tp' or 'do'
  #                   if len(report_z.numero_ultimo_reporte_z) == 1:
  #                       z_report = report_z.numero_ultimo_reporte_z
  #                   if len(report_z.numero_ultimo_reporte_z) == 2:
  #                       z_report = '00'+ str(report_z.numero_ultimo_reporte_z)
  #                   elif len(report_z.numero_ultimo_reporte_z) == 3:
  #                       z_report = '0' + str(report_z.numero_ultimo_reporte_z)
  #                   date_str = report_z.fecha_ultimo_reporte_z
  #                   date_time_obj = datetime.strptime(date_str, '%d-%m-%Y').date()
  #
  #                   values = {'report_z_id': report_z.id,
  #                             'accounting_date': date_time_obj or False,
  #                             'emission_date': date_time_obj  or False,
  #                             'type': t_type,
  #                             'doc_type':'Reporte Z',
  #                             'wh_number':  False,
  #                             'get_wh_vat':  0.0,
  #                             'partner_name': 'N/A',
  #                             'people_type': people_type,
  #                             'debit_affected': False,
  #                             'credit_affected':  False,
  #                             'partner_vat': 'N/A',
  #                             'affected_invoice':
  #                                 '',
  #                             'affected_invoice_date':
  #                                date_time_obj,
  #                             'wh_rate':'',
  #                             'invoice_number': "",
  #                             'ctrl_number': "",
  #                             'void_form': '',
  #                             'fiscal_printer': False,
  #                             'n_ultima_factZ': report_z.numero_ultima_factura,
  #                             'z_report': z_report or False,
  #                             }
  #                   data.append((0, 0, values))


        if inv_iva:

                orphan_iwdl_ids = self._get_orphan_iwdl_ids(fb_id)
                # no_match_dt_iwdl_ids = self._get_no_match_date_iwdl_ids(fb_id)
                iwdl_ids = orphan_iwdl_ids
                # for nm in no_match_dt_iwdl_ids:
                #     iwdl_ids += nm
                t_type = fb_brw.type == 'sale' and 'tp' or 'do'
                for iwdl_otro1 in inv_iva:
                  #  busq = self.env['account.move'].search([('id','=',)])
                  #   if iwdl_otro1 and iwdl_otro1.move_type == 'in_invoice' or iwdl_otro1.move_type == 'in_refund':
                  otro = iwdl_otro1.id
                  iwdl_ids += iwdl_obj.search([('invoice_id', '=', otro)])

                for iwdl_brw in iwdl_ids:
                    # if iwdl_brw.type == 'in_invoice':
                        rp_brw = rp_obj._find_accounting_partner(iwdl_brw.retention_id.partner_id)
                        #para obtener el tipo de transacción

                        people_type = 'N/A'
                        document_v = 'N/A'
                        if rp_brw:
                            if rp_brw.company_type == 'company':
                                people_type = rp_brw.people_type_company
                                if people_type == 'pjdo':
                                    document_v = rp_brw.rif
                                if people_type == 'pjnd':
                                    document_v = rp_brw.rif

                            elif rp_brw.company_type == 'person':
                                if rp_brw.rif:
                                    document_v = rp_brw.rif
                                    people_type = rp_brw.people_type_individual
                                else:
                                    document_v = ''
                                    # people_type = rp_brw.people_type_individual
                                    # if rp_brw.nationality == 'V' or rp_brw.nationality == 'E':
                                    #     document_v = str(rp_brw.nationality) + str(rp_brw.identification_id)
                                    # else:
                                    #     document_v = rp_brw.identification_id

                        doc_type = self.get_doc_type(inv_id=iwdl_brw.invoice_id.id)


                        if (doc_type == "N/DB" or doc_type == "N/CR"):
                            if fb_brw.type == 'sale':
                                if iwdl_brw.invoice_id.move_type == 'out_refund':
                                    cliente = True
                                    local_inv_affected = iwdl_brw.invoice_id.reversed_entry_id.invoice_number
                                    fecha = iwdl_brw.invoice_id.reversed_entry_id.date
                                elif iwdl_brw.invoice_id.move_type == 'out_invoice':
                                    cliente = True
                                    debit_account_id = self.env['account.move'].search(
                                        [('id', '=', iwdl_brw.invoice_id.debit_origin_id.id)])
                                    local_inv_affected = debit_account_id.invoice_number
                                    fecha = debit_account_id.date
                            elif  iwdl_brw.invoice_id.move_type == 'in_invoice' and doc_type == 'N/DB':
                                proveedor = True
                                debit_account_id = self.env['account.move'].search([('id', '=', iwdl_brw.invoice_id.debit_origin_id.id)])
                                local_inv_affected = debit_account_id.supplier_invoice_number
                                fecha = debit_account_id.invoice_date
                            elif iwdl_brw.invoice_id.move_type == 'in_refund' and doc_type == 'N/CR':
                                proveedor = True
                                local_inv_affected = iwdl_brw.invoice_id.invoice_reverse_purchase_id.supplier_invoice_number
                                fecha = iwdl_brw.invoice_id.invoice_reverse_purchase_id.invoice_date

                        if doc_type == 'N/CR':

                            sign = -1
                        else:
                            sign = 1

                        values = {'iwdl_id': iwdl_brw.id,
                                  'type': t_type,
                                  'accounting_date': iwdl_brw.date_ret or False,
                                  'emission_date': iwdl_brw.invoice_id.invoice_date or iwdl_brw.invoice_id.date or False,
                                  'doc_type': self.get_doc_type(inv_id=iwdl_brw.invoice_id.id, iwdl_id=iwdl_brw.id),
                                  'wh_number': iwdl_brw.retention_id.number or False,
                                  'get_wh_vat': iwdl_brw and (iwdl_brw.amount_tax_ret)* sign or 0.0,
                                  'partner_name': rp_brw.name or 'ANULADA',
                                  'people_type': people_type,
                                  'debit_affected': local_inv_affected if doc_type == 'N/DB' else False,
                                  'credit_affected': local_inv_affected if doc_type == 'N/CR' else False,
                                  'partner_vat': document_v,
                                  'affected_invoice':
                                      (doc_type == "N/DB" or doc_type == "N/CR") and local_inv_affected,
                                  'affected_invoice_date':
                                    fecha if fecha else False,
                                  'wh_rate': iwdl_brw.wh_iva_rate,
                                  'invoice_number': iwdl_brw.invoice_id.supplier_invoice_number if iwdl_brw.invoice_id.supplier_invoice_number and not doc_type == 'N/CR' else iwdl_brw.invoice_id.invoice_number, # se agrega el campo numero de factura para las facturas fuera de periodo
                                  'numero_debit_credit': iwdl_brw.invoice_id.supplier_invoice_number if iwdl_brw.invoice_id.supplier_invoice_number else iwdl_brw.invoice_id.invoice_number,
                                  'ctrl_number': iwdl_brw.invoice_id.nro_ctrl or "", # se agrega el campo numero de control para las facturas fuera de periodo
                                  'void_form': self.get_t_type(doc_type),
                                  'fiscal_printer': iwdl_brw.invoice_id.fiscal_printer or False,
                                  'z_report': False,
                                  }
                        data.append((0, 0, values))
                        fecha = False


        for inv_otro in inv_siva:
                #if not self.browse(fb_id).iwdl_ids and iwdl_id == False:
                #if inv_otro.type == 'in_invoice':
                local_inv_affected = ' '

                local_inv_nbr = ''
                people_type = 'N/A'

                doc_type = self.get_doc_type(inv_id=inv_otro.id)

                rp_brw = rp_obj._find_accounting_partner(inv_otro.partner_id)

                people_type = 'N/A'
                document_v = 'N/A'
                if rp_brw:
                    if rp_brw.company_type == 'company':
                        people_type = rp_brw.people_type_company
                        if people_type == 'pjdo':
                            document_v = rp_brw.rif
                        if people_type == 'pjnd':
                            document_v = rp_brw.rif

                    elif rp_brw.company_type == 'person':
                        people_type = rp_brw.people_type_individual
                        document_v = rp_brw.rif

                if (doc_type == "N/DB" or doc_type == "N/CR"):
                    if fb_brw.type == 'sale':
                        if inv_otro.move_type == 'out_refund':
                            cliente = True
                            local_inv_affected = inv_otro.reversed_entry_id.invoice_number
                            local_inv_nbr =inv_otro.invoice_number
                            fecha = inv_otro.date
                        elif inv_otro.move_type == 'out_invoice':
                            cliente = True
                            debit_account_id = self.env['account.move'].search(
                                [('id', '=', inv_otro.debit_origin_id.id)])
                            local_inv_affected = debit_account_id.invoice_number
                            local_inv_nbr = inv_otro.invoice_number
                            fecha = debit_account_id.date
                    elif inv_otro.move_type == 'in_invoice' and doc_type == 'N/DB':
                        proveedor = True
                        debit_account_id = self.env['account.move'].search([('id', '=', inv_otro.debit_origin_id.id)])
                        local_inv_affected = debit_account_id.supplier_invoice_number
                        local_inv_nbr =inv_otro.supplier_invoice_number
                        fecha = debit_account_id.invoice_date
                    elif inv_otro.move_type == 'in_refund' and doc_type == 'N/CR':
                        proveedor = True
                        local_inv_affected = inv_otro.invoice_reverse_purchase_id.supplier_invoice_number
                        local_inv_nbr = inv_otro.supplier_invoice_number
                        fecha = inv_otro.invoice_date

                if  doc_type == 'N/CR':

                    sign = -1
                else:
                    sign = 1
                if inv_otro.state == 'cancel':
                    values = {
                        'invoice_id': inv_otro.id,
                        'emission_date':
                            (inv_otro.invoice_date or inv_otro.date) or
                            False,
                        'accounting_date':
                            inv_otro.date or
                            False,

                        'type': self.get_transaction_type(
                            fb_id, inv_otro.id),

                        'debit_affected': local_inv_affected if doc_type == 'N/DB' else False,

                        'credit_affected': local_inv_affected if doc_type == 'N/CR' else False,
                        'ctrl_number':
                            not inv_otro.fiscal_printer and
                            (inv_otro.nro_ctrl if inv_otro.nro_ctrl != 'False' else ''),
                        'affected_invoice': local_inv_affected,
                        'affected_invoice_date': fecha if fecha else False,
                        'partner_name': rp_brw.name or 'ANULADA',
                        'people_type': people_type,
                        'partner_vat': document_v,
                        'invoice_number': inv_otro.supplier_invoice_number if inv_otro.supplier_invoice_number and not doc_type == 'N/CR' else inv_otro.invoice_number,
                        'numero_debit_credit': inv_otro.supplier_invoice_number if inv_otro.supplier_invoice_number else inv_otro.invoice_number,

                        'doc_type': doc_type,
                        # 'void_form':
                        #    inv_otro.name and (
                        #            inv_otro.name.find('PAPELANULADO') >= 0 and
                        #            '03-ANU' or
                        #            '01-REG') or
                        #    '01-REG',
                        'void_form': self.get_t_type(doc_type, local_inv_nbr, inv_otro.state),
                        'fiscal_printer': inv_otro.fiscal_printer or False,
                        'z_report': False,
                        #  'custom_statement': False,
                        # inv_otro.customs_form_id.name or False,# TODO VALOR RELACIONADO CON MODULO l10n_ve_imex (importaciones)
                        #     'iwdl_id': ' ',
                        # 'wh_number': ' ',
                        # 'get_wh_vat': iwdl_brw  and iwdl_brw.amount_tax_ret * sign or 0.0,
                        # 'wh_rate': iwdl_brw and iwdl_brw.wh_iva_rate or 0.0,
                    }
                else:
                    values = {
                        'invoice_id': inv_otro.id,
                        'emission_date':
                            (inv_otro.invoice_date or inv_otro.date) or
                            False,
                        'accounting_date':
                            inv_otro.date or
                            False,

                        'type': self.get_transaction_type(
                            fb_id, inv_otro.id),

                        'debit_affected': local_inv_affected if doc_type == 'N/DB' else False,

                        'credit_affected': local_inv_affected if doc_type == 'N/CR' else False,
                        'ctrl_number':
                            not inv_otro.fiscal_printer and
                            (inv_otro.nro_ctrl if inv_otro.nro_ctrl != 'False' else ''),
                        'affected_invoice': local_inv_affected,
                        'affected_invoice_date': fecha if fecha else False,
                        'partner_name': rp_brw.name or 'ANULADA',
                        'people_type': people_type,
                        'partner_vat': document_v,
                        'invoice_number': inv_otro.supplier_invoice_number if inv_otro.supplier_invoice_number and not doc_type == 'N/CR' else inv_otro.invoice_number,
                        'numero_debit_credit': inv_otro.supplier_invoice_number if inv_otro.supplier_invoice_number else inv_otro.invoice_number,
                        'doc_type': doc_type,
                        #'void_form':
                        #    inv_otro.name and (
                        #            inv_otro.name.find('PAPELANULADO') >= 0 and
                        #            '03-ANU' or
                        #            '01-REG') or
                        #    '01-REG',
                        'void_form': self.get_t_type(doc_type, local_inv_nbr, inv_otro.state),
                        'fiscal_printer': inv_otro.fiscal_printer or False,
                        'z_report': False,
                      #  'custom_statement': False,
                    # inv_otro.customs_form_id.name or False,# TODO VALOR RELACIONADO CON MODULO l10n_ve_imex (importaciones)
                    #     'iwdl_id': ' ',
                        # 'wh_number': ' ',
                        # 'get_wh_vat': iwdl_brw  and iwdl_brw.amount_tax_ret * sign or 0.0,
                        # 'wh_rate': iwdl_brw and iwdl_brw.wh_iva_rate or 0.0,
                    }

                data.append((0, 0, values))
                fecha = False


        if data:

            self.write({'fbl_ids': data})
            self.link_book_lines_and_taxes(fb_id)

        if fb_brw.article_number in ['77', '78']:
            self.update_book_ntp_lines(fb_brw.id)
        else:
            self.order_book_lines(fb_brw.id)

        return True



    def link_book_lines_and_taxes(self, fb_id):
        """ Updates the fiscal book taxes. Link the tax with the corresponding
        book line and update the fields of sum taxes in the book.
        @param fb_id: the id of the current fiscal book """

        #        fbl_obj = self.env['account.fiscal.book.line']
        ut_obj = self.env['account.ut']
        fbt_obj = self.env['account.fiscal.book.taxes']
        # write book taxes
        data = []
        tax_data = {}
        exento = 0.0
        base_exento = 0
        amount = 0
        name = ' '
        base = 0
        fiscal_book = self.browse(fb_id)
        for fbl in fiscal_book.fbl_ids:
            if fbl.iwdl_id.invoice_id:
                fiscal_taxes = self.env['account.fiscal.book.taxes']
                line_taxes = {'fb_id': fb_id, 'fbl_id': fbl.id, 'base_amount': 0.0, 'tax_amount': 0.0, 'name': ' ', }
                fiscal_book = self.browse(fb_id)
                f_xc = ut_obj.sxc(
                    fbl.iwdl_id.invoice_id.currency_id.id,
                    fbl.iwdl_id.invoice_id.company_id.currency_id.id,
                    fbl.iwdl_id.invoice_id.invoice_date)
                if fbl.doc_type == 'N/CR' :
                    sign = -1
                else:
                    sign = 1
                sum_base_imponible = 0
                amount_field_data = {'total_with_iva':
                                        0.0,
                                     'vat_sdcf': 0.0, 'vat_exempt': 0.0, 'vat_general_base': 0.0,}

                for ait in fbl.iwdl_id.tax_line:
                    busq = self.env['account.tax'].search([('id', '=', ait.id_tax)])
                    if busq:
                        if ait.amount == 0:
                            base = ait.base
                            name = ait.name
                            amount_field_data['vat_exempt'] += exento * sign
                            if fbl.iwdl_id.invoice_id.partner_id.people_type_company:
                                if fbl.iwdl_id.invoice_id.partner_id.people_type_company == 'pjnd':
                                    amount = 16
                        else:
                            base = ait.base
                            amount = ait.amount
                            name = ait.name
                        if (ait.amount + ait.base) > 0:
                            amount_field_data['total_with_iva'] += (ait.amount + ait.base)* sign
                            if busq.appl_type == 'sdcf':
                                    amount_field_data['vat_sdcf'] += base * sign
                            if busq.appl_type == 'exento':
                                amount_field_data['vat_exempt'] += base * sign
                            if busq.appl_type == 'general':
                                amount_field_data['vat_general_base'] += base * sign

                        tax_data.update({'fb_id': fb_id,
                                         'fbl_id': fbl.id,
                                        # 'ait_id': busq.id,
                                         'base_amount': amount_field_data['vat_general_base'],
                                         'tax_amount': ait.amount})

                        line_taxes.update({'fb_id': fb_id,
                                           'fbl_id': fbl.id,
                                           'base_amount':  base,
                                           'tax_amount': amount,
                                           'name': name,
                                           'type': fiscal_book.type

                                           })
                    fbl.write(amount_field_data)
                    if line_taxes:
                        fiscal_taxes.create(line_taxes)
                    else:
                        data.append((0, 0, {'fb_id': fb_id,
                                            'fbl_id': fbl.id,

                                            }))
                        self.write({'fbt_ids': data})


            if fbl.invoice_id and fbl.invoice_id.state != 'cancel':
                tasa = 1
                if not fbl.invoice_id.currency_id == fbl.invoice_id.company_id.currency_id:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        tasa = fbl.invoice_id.tax_today
                    else:
                        tasa = self.obtener_tasa(fbl.invoice_id)
                fiscal_book = self.browse(fb_id)
                fiscal_taxes = self.env['account.fiscal.book.taxes']
                line_taxes = {'fb_id': fb_id, 'fbl_id': fbl.id,'base_amount': 0.0 , 'tax_amount': 0.0, 'name': ' ',}
                f_xc = ut_obj.sxc(
                    fbl.invoice_id.currency_id.id,
                    fbl.invoice_id.company_id.currency_id.id,
                    fbl.invoice_id.invoice_date)
                busq = ' '
                if fbl.doc_type == 'N/CR':
                    sign = -1
                else:
                    sign = 1
                sum_base_imponible = 0
                amount_field_data = {'total_with_iva':
                                         0.0,
                                     'vat_sdcf': 0.0, 'vat_exempt': 0.0, 'vat_general_base': 0.0, }

                if fbl.invoice_id.partner_id.people_type_company == 'pjnd' and fbl.invoice_id.invoice_import_id:
                    base = (sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                    amount = sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit')) - (sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                    tax_data.update({'fb_id': fb_id,
                                     'fbl_id': fbl.id,
                                     #     'ait_id': fbl.id,
                                     'base_amount': base,
                                     'tax_amount': amount})
                    line_taxes.update({'fb_id': fb_id,
                                       'fbl_id': fbl.id,
                                       'base_amount': base,
                                       'tax_amount': amount,
                                       'name': 'IVA (16.0%) compras',
                                       'type': fiscal_book.type

                                       })
                    fiscal_taxes.create(line_taxes)
                    amount_field_data['vat_general_base'] = base * sign
                    amount_field_data['total_with_iva'] = (base + amount) * sign
                    fbl.write(amount_field_data)
                else:
                    for line in fbl.invoice_id.invoice_line_ids:
                        amount = 0
                        base = 0
                        busq =  ''
                        tax = ' '

                        for tax in line.tax_ids:
                            busq = tax.appl_type
                            name = tax.name
                        if busq:
                            if (line.price_total - line.price_subtotal) == 0:
                                base = line.price_subtotal * tasa
                                amount = 0
                                amount_field_data['vat_exempt'] += exento * sign
                                if fbl.invoice_id.partner_id.people_type_company:
                                    if fbl.invoice_id.partner_id.people_type_company == 'pjnd':
                                        amount = line.price_subtotal * tasa * 0.16
                            else:
                                base = (line.price_subtotal) * tasa
                                amount = (line.price_total - line.price_subtotal) * tasa

                            if ((line.price_total - line.price_subtotal) == 0 or (line.price_total - line.price_subtotal) > 0) and line.price_total > 0:
                                if fbl.invoice_id.partner_id.people_type_company:
                                    if fbl.invoice_id.partner_id.people_type_company == 'pjnd':
                                        amount_field_data['total_with_iva'] += (line.price_total * sign * tasa) #* 1.16
                                    else:
                                        amount_field_data['total_with_iva'] += line.price_total * sign * tasa
                                else:
                                    amount_field_data['total_with_iva'] += line.price_total * sign * tasa
                                if busq == 'sdcf':
                                    amount_field_data['vat_sdcf'] += base * sign
                                if busq == 'exento':
                                    amount_field_data['vat_exempt'] += base * sign
                                if busq == 'general':
                                    amount_field_data['vat_general_base'] += base * sign

                            tax_data.update({'fb_id': fb_id,
                                             'fbl_id': fbl.id,
                                        #     'ait_id': fbl.id,
                                             'base_amount': base,
                                             'tax_amount': amount})

                            line_taxes.update({'fb_id': fb_id,
                                               'fbl_id': fbl.id,
                                               'base_amount': base,
                                               'tax_amount':amount,
                                               'name': name,
                                               'type': fiscal_book.type

                            })

                        fbl.write(amount_field_data)
                        if line_taxes:
                            fiscal_taxes.create(line_taxes)
                        else:
                            data.append((0, 0, {'fb_id': fb_id,
                                                'fbl_id': fbl.id,

                                                }))
                            self.write({'fbt_ids': data})

            if fbl.invoice_id and fbl.invoice_id.state == 'cancel':
                amount_field_data = {'total_with_iva':
                                         0.0,
                                     'vat_sdcf': 0.0, 'vat_exempt': 0.0, 'vat_general_base': 0.0, }
                fbl.write(amount_field_data)

        self.update_book_taxes_summary()
        self.update_book_lines_taxes_fields()
        self.update_book_taxes_amount_fields()
        return True


    def update_book_lines_taxes_fields(self):
        """ Update taxes data for every line in the fiscal book given,
        extrating de data from the fiscal book taxes associated.
        @param fb_id: fiscal book line id.
        """
        tax_amount = 0
        fbl_obj = self.env['account.fiscal.book.line']
        field_names = ['vat_reduced_base', 'vat_reduced_tax',
                       'vat_general_base', 'vat_general_tax',
                       'vat_additional_base', 'vat_additional_tax']
        tax_type = {'reduced': 'reducido', 'general': 'general',
                    'additional': 'adicional'}
        for fbl_brw in self.fbl_ids:
            if fbl_brw.doc_type == 'N/CR':
                sign = -1
            else:
                sign = 1
            data = {}.fromkeys(field_names, 0.0)
            busq = ' '
            # if fbl_brw.report_z_id:
            #
            #     for field_name in field_names:
            #         field_tax, field_amount = field_name[4:].split('_')
            #
            #         if field_tax == 'general' and (field_amount == 'base' or field_amount == 'tax'):
            #             if float(fbl_brw.report_z_id.base_imponible_ventas_iva_g) != 0:
            #                 base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_g) - float(fbl_brw.report_z_id.bi_iva_g_en_nota_de_credito)
            #                 tax_amount = float(fbl_brw.report_z_id.impuesto_iva_g) - float(fbl_brw.report_z_id.impuesto_iva_g_en_nota_de_credito)
            #                 data[field_name] += field_amount == 'base' and base \
            #                                 or tax_amount
            #         if field_tax  == 'reduced' and (field_amount == 'base' or field_amount == 'tax'):
            #             if float(fbl_brw.report_z_id.base_imponible_ventas_iva_r) != 0:
            #                 base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_r) - float(fbl_brw.report_z_id.bi_iva_r_en_nota_de_credito)
            #                 tax_amount = float(fbl_brw.report_z_id.impuesto_iva_r) - float(fbl_brw.report_z_id.impuesto_iva_r_en_nota_de_credito)
            #                 data[field_name] += field_amount == 'base' and base \
            #                                     or tax_amount
            #         if field_tax == 'additional' and (field_amount == 'base' or field_amount == 'tax'):
            #             if float(fbl_brw.report_z_id.base_imponible_ventas_iva_a) != 0:
            #                 base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_a) - float(fbl_brw.report_z_id.bi_iva_a_en_nota_de_credito)
            #                 tax_amount = float(fbl_brw.report_z_id.impuesto_iva_a) - float(fbl_brw.report_z_id.impuesto_iva_a_en_nota_de_credito)
            #                 data[field_name] += field_amount == 'base' and base \
            #                                     or tax_amount
            #     fbl_brw.write(data)

            if fbl_brw.iwdl_id.invoice_id:

               for line in fbl_brw.iwdl_id.invoice_id.invoice_line_ids:
                   for tax in line.tax_ids:
                       busq = tax.appl_type
                   tasa = 1
                   if not line.currency_id == line.move_id.company_id.currency_id:
                       module_dual_currency = self.env['ir.module.module'].sudo().search(
                           [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                       if module_dual_currency:
                           tasa = line.move_id.tax_today
                       else:
                           tasa = self.obtener_tasa(line)
                   # if line.currency_id.name == "USD":
                   #     tasa = self.obtener_tasa(line)
                   for field_name in field_names:
                        field_tax, field_amount = field_name[4:].split('_')
                        base = line.price_subtotal * tasa
                        tax_amount = (line.price_total - line.price_subtotal) * tasa
                        if fbl_brw.iwdl_id.invoice_id.partner_id.people_type_company:
                            if fbl_brw.iwdl_id.invoice_id.partner_id.people_type_company == 'pjnd':
                                tax_amount = line.price_subtotal * tasa * 0.16
                        if busq:
                            if busq == tax_type[field_tax]:
                                    data[field_name] += field_amount == 'base' and base * sign \
                                                        or tax_amount * sign
               fbl_brw.write(data)

            if fbl_brw.invoice_id and fbl_brw.invoice_id.state != 'cancel':
                tasa = 1
                if not fbl_brw.invoice_id.currency_id == fbl_brw.invoice_id.company_id.currency_id:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        tasa = fbl_brw.invoice_id.tax_today
                    else:
                        tasa = self.obtener_tasa(fbl_brw.invoice_id)
                if fbl_brw.invoice_id.partner_id.people_type_company == 'pjnd' and fbl_brw.invoice_id.invoice_import_id:
                    #cargar datos de la factura importacion nuvo metodo
                    debito = sum(fbl_brw.invoice_id.invoice_import_id.line_ids.mapped('debit'))
                    data['vat_general_base'] = ((debito)/1.16)
                    data['vat_general_tax'] = debito - (debito/1.16)
                else:
                    tax_amount_acum = 0
                    for line in fbl_brw.invoice_id.invoice_line_ids:
                        for tax in line.tax_ids:
                            busq = tax.appl_type
                        for field_name in field_names:
                            field_tax, field_amount = field_name[4:].split('_')
                            # if field_name == 'vat_general_tax':
                            #     raise UserError(f' field_name {field_name} \n \
                            #     field_tax {field_tax} \n \
                            #     field_amount {field_amount} \n \
                            #     busq {busq} \n \
                            #     ')
                            base = line.price_subtotal * tasa
                            tax_amount = (line.price_total - line.price_subtotal) * tasa
                            tax_amount_acum += tax_amount
                            # if fbl_brw.invoice_id.partner_id.people_type_company:
                            #     if fbl_brw.invoice_id.partner_id.people_type_company == 'pjnd':
                            #         tax_amount = line.price_total * tasa * 0.16
                            if busq:
                                if busq == tax_type[field_tax]:  # account.tax
                                    # if not fbt_brw.fbl_id.iwdl_id.invoice_id.name: #facura de account.wh.iva.line
                                    #     data[field_name] += field_amount == 'base' and (
                                    #         fbt_brw.fbl_id.invoice_id.factura_id.amount_gravable if fbt_brw.base_amount == 0 else fbt_brw.base_amount) * sign \
                                    #                         or fbt_brw.tax_amount * sign
                                    # else:
                                    data[field_name] += field_amount == 'base' and base * sign \
                                                        or tax_amount * sign
                    # if fbl_brw.invoice_id.id == 10437:
                    #     raise UserError(f' tax_amount_acum {tax_amount_acum} \n \
                    #      tax_amount_acum {tax_amount_acum/1.16} \n \
                    #      data {data} \n \
                    #     ')
                # Raise error DATA
                # if fbl_brw.invoice_id.id == 10437:
                #     raise UserError(f' data {data}')
                fbl_brw.write(data)
        return True