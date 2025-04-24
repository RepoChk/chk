from datetime import datetime, timedelta
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import logging

import os
from io import BytesIO
from PIL import Image
import tempfile
import base64
import xlwt

_logger = logging.getLogger(__name__)

class WizardForma1312(models.TransientModel):
    _name = 'wizard.forma.1312'
    _description = 'Forma 13 - 12'

    date_from = fields.Date(string='Date From', default=lambda *a:datetime.now().strftime('%Y-%m-%d'))
    date_to = fields.Date('Date To', default=lambda *a:(datetime.now() + timedelta(days=(1))).strftime('%Y-%m-%d'))
    date_now = fields.Date(string='Fecha', default=lambda *a:datetime.now())
    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency')
    analytic_id = fields.Many2many('account.analytic.account', string='Cuenta Analítica')

    company_id = fields.Many2one(comodel_name='res.company', string='Compañía',default=lambda self: self.env.company.id)
    user_id = fields.Many2one(comodel_name='res.users', string='Usuario Activo', default=lambda x: x.env.uid)
    
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')
    report = fields.Binary('Archivo listo', filters='.xls', readonly=True)
    name = fields.Char('Nombre del Archivo', size=60)

    # ******************* FORMATOS ****************************

    def float_format(self,valor):
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result

    def count_mondays_month(self, contract):
        current_date = self.date_now
        first_day_of_month = current_date.replace(day=1)
        last_day_of_month = (first_day_of_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)

        monday_count = 0
        # Obtenemos la fecha de retiro del empleado en caso de que exista
        date_end = contract.date_end

        if date_end and date_end < last_day_of_month:
            last_day_of_month = date_end

        for single_date in (first_day_of_month + timedelta(n) for n in range((last_day_of_month - first_day_of_month).days + 1)):
            if single_date.weekday() == 0:
                monday_count += 1

        return monday_count

    # *******************  REPORTE EN PDF ****************************

    # def print_pdf(self):
    #     data = self._prepare_data()
    #     return self.env.ref('gchakao_custom.action_analysis_ledger_report').report_action([], data=data)

    # *******************  BÚSQUEDA DE DATOS ****************************

    def _prepare_data(self):
        results = []
        domain = [('state', '=', 'open')]

        if self.company_id:
            domain.append(('company_id', '=', self.company_id.id))

        contract_ids = self.env['hr.contract'].sudo().search(domain)
        cont = 1
        salario = self.env.company.salario_minimo * 5
        for con in contract_ids.sorted(key=lambda x: x.employee_id.name):
            lunes = self.count_mondays_month(con)
            weekly_salary = (salario * 12) / 52
            employee_weekly_quote = (weekly_salary * 0.1) * lunes
            employer_weekly_contribution = (weekly_salary * 0.04) * lunes
            employee_weekly_quote_rpe = (weekly_salary * 0.02) * lunes
            employer_weekly_quote_rpe = (weekly_salary * 0.005) * lunes
            values = {
                'cont': cont,
                'analytic_id': con.analytic_account_id.name,
                'employee': con.employee_id.name,
                'nationality': con.employee_id.nationality,
                'identification_id': con.employee_id.identification_id,
                'birthday_year': con.employee_id.birthday.year if con.employee_id.birthday else '',
                'birthday_month': con.employee_id.birthday.month if con.employee_id.birthday else '',
                'birthday_days': con.employee_id.birthday.day if con.employee_id.birthday else '',
                'female': 'X' if con.employee_id.gender == 'female' else '',
                'male': 'X' if con.employee_id.gender == 'male' else '',
                'date_start_year': con.date_start.year if con.date_start else '',
                'date_start_month': con.date_start.month if con.date_start else '',
                'date_start_days': con.date_start.day if con.date_start else '',
                'date_end_year': con.date_end.year if con.date_end else '',
                'date_end_month': con.date_end.month if con.date_end else '',
                'date_end_days': con.date_end.day if con.date_end else '',
                'monthly_salary': salario,
                'weekly_salary': weekly_salary,
                'employee_weekly_quote': employee_weekly_quote,
                'employer_weekly_contribution': employer_weekly_contribution,
                'total_contribution_ivss':  employee_weekly_quote + employer_weekly_contribution,
                'employee_weekly_quote_rpe': employee_weekly_quote_rpe,
                'employer_weekly_quote_rpe': employer_weekly_quote_rpe,
                'total_contribution_rpe':  employee_weekly_quote_rpe + employer_weekly_quote_rpe,
                'job_name':  con.job_id.name,
                'amount':  employee_weekly_quote + employer_weekly_contribution + employee_weekly_quote_rpe + employer_weekly_quote_rpe,
                'registration_date_IVSS':  self.company_id.registration_date_IVSS,
                'regime':  self.company_id.regime,
                'risk':  self.company_id.risk,
            }
            results.append(values)
            cont += 1  # Incrementar el contador

        data = {
            'result': results,
        }
        return data


    # *******************  REPORTE EN EXCEL ****************************

    def generate_xls_report(self):
        wb1 = xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet(_('Forma 13-12'))
        fp = BytesIO()
        items = self._prepare_data()

        # Cargar el logo desde la ruta local del addon
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'IVSS.png')

        # Convertir la imagen a formato BMP con fondo blanco y tamaño 60x80 px
        bmp_logo_path = os.path.join(tempfile.gettempdir(), 'logo.bmp')  # Ruta temporal para el BMP
        with Image.open(logo_path) as img:
            # Redimensionar la imagen a 60x80 px
            img = img.resize((65, 80), Image.ANTIALIAS)

            # Crear una nueva imagen con fondo blanco
            new_img = Image.new("RGB", (65, 80), "white")
            new_img.paste(img, (0, 0), img.convert("RGBA"))  # Pegar la imagen sobre el fondo blanco

            # Guardar la imagen como BMP
            new_img.save(bmp_logo_path, 'BMP')

        # Insertar el logo en la celda (0, 0) por ejemplo
        ws1.insert_bitmap(bmp_logo_path, 0, 0)  # Cambia las coordenadas según sea necesario

        text_info = [
            "REPÚBLICA BOLIVARIANA DE VENEZUELA",
            "MINISTERIO DEL PODER POPULAR PARA EL PROCESO SOCIAL DE TRABAJO",
            "INSTITUTO VENEZOLANO DE LOS SEGUROS SOCIALES"
        ]
        
        text_style = xlwt.easyxf("font: name Helvetica size 12 px; align: horiz left;")

        for i, line in enumerate(text_info):
            ws1.write(i, 1, line, text_style)  # Cambia la columna según sea necesario

        header_tittle = xlwt.easyxf("font: name Helvetica size 30 px, bold 1, height 170; align: horiz center, vert centre;")
        header_tittle_style = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170; align: horiz center, vert centre;")
        style_normal = xlwt.easyxf("font: name Helvetica size 25 px, height 170; align: horiz center, vert centre;")
        header_content_style = xlwt.easyxf("font: name Helvetica size 16 px, bold 1, height 170; align: horiz center, vert centre;")
        lines_style_center = xlwt.easyxf("font: name Helvetica size 10 px, height 170;borders: top dashed, bottom dashed, left dashed, right dashed; align: horiz center, vert centre;")
        lines_style_left = xlwt.easyxf("font: name Helvetica size 10 px, height 170; borders: top dashed, bottom dashed, left dashed, right dashed; align: horiz left, vert centre;")
        lines_style_colored = xlwt.easyxf(
            "font: name Helvetica size 10 px, color white, bold 1; "
            "pattern: pattern solid, fore_color gray_ega; "
            "borders: bottom thin, left thin, right thin, top thin; "
            "align: horiz center, vert centre;"
        )
        number_style_right = xlwt.easyxf(
            "font: name Helvetica size 10 px; "
            "borders: top dashed, bottom dashed, left dashed, right dashed; "
            "align: horiz right, vert centre;"
        )
        number_style_right.num_format_str = '0.00'
        row = 5
        ws1.row(row).height = 500

        ws1.write_merge(1, 2, 12, 22, 'REGISTRO PATRONAL DE ASEGURADOS', header_tittle)
        # CABECERA DEL REPORTE
        ws1.write_merge(row, row, 0, 3, 'RAZÓN SOCIAL DE LA EMPRESA O NOMBRE DEL EMPLEADOR', header_tittle_style)
        ws1.write_merge(row, row, 4, 5, 'Nº DE R.I.F.', header_tittle_style)
        ws1.write_merge(row, row, 6, 10, 'DOMICILIO FISCAL DE LA EMPRESA U ORGANISMO PÚBLICO', header_tittle_style)
        ws1.write_merge(row, row, 11, 12, 'Nº PATRONAL', header_tittle_style)
        row += 1
        ws1.write_merge(row, row, 0, 3,  self.company_id.name.upper(), style_normal)
        ws1.write_merge(row, row, 4, 5,  self.company_id.partner_id.identification_id, style_normal)
        ws1.write_merge(row, row, 6, 10, self.company_id.street.upper(), style_normal)
        ws1.write_merge(row, row, 11, 12, self.company_id.numero_patronal or '', style_normal)
        row += 2
        ws1.write_merge(row, row, 0, 3, 'FECHA DE INSCRIPCIÓN', header_tittle_style)
        ws1.write_merge(row, row, 4, 5, 'RÉGIMEN', header_tittle_style)
        ws1.write_merge(row, row, 6, 7, 'RIESGO', header_tittle_style)
        row += 1
        ws1.write_merge(row, row, 0, 3, self.company_id.registration_date_IVSS, style_normal)
        ws1.write_merge(row, row, 4, 5, self.company_id.regime, style_normal)
        ws1.write_merge(row, row, 6, 7, self.company_id.risk, style_normal)
        row += 1
        ws1.write_merge(row, row, 12, 13, _('Forma 13-12'), header_tittle_style)
        row += 2
        ws1.write_merge(row, row, 2, 3, 'NACIONALIDAD', header_tittle_style)
        ws1.write_merge(row, row, 4, 6, 'FECHA DE NACIMIENTO', header_tittle_style)
        ws1.write_merge(row, row, 7, 8, 'SEXO', header_tittle_style)
        ws1.write_merge(row, row, 11, 13, 'FECHA DE INGRESO', header_tittle_style)
        ws1.write_merge(row, row, 14, 16, 'FECHA DE RETIRO', header_tittle_style)
        ws1.write_merge(row, row, 17, 18, 'SALARIO O SUELDO', header_tittle_style)
        row += 1
        # Encabezado de la tabla
        ws1.write(row, 0, _("N°"), lines_style_colored)
        ws1.write(row, 1, _("NOMBRES Y APELLIDOS"), lines_style_colored)
        ws1.write(row, 2, _("V"), lines_style_colored)
        ws1.write(row, 3, _("CEDULA DE IDENTIDAD"), lines_style_colored)
        ws1.write(row, 4, _("DÍA"), lines_style_colored)
        ws1.write(row, 5, _("MES"), lines_style_colored)
        ws1.write(row, 6, _("AÑO"), lines_style_colored)
        ws1.write(row, 7, _("F"), lines_style_colored)
        ws1.write(row, 8, _("M"), lines_style_colored)
        ws1.write(row, 9, _("DIRECCION DEL TRABAJADOR"), lines_style_colored)
        ws1.write(row, 10, _("Nº DE REGISTRO EN EL IVSS"), lines_style_colored)
        ws1.write(row, 11, _("DÍA"), lines_style_colored)
        ws1.write(row, 12, _("MES"), lines_style_colored)
        ws1.write(row, 13, _("AÑO"), lines_style_colored)
        ws1.write(row, 14, _("DÍA"), lines_style_colored)
        ws1.write(row, 15, _("MES"), lines_style_colored)
        ws1.write(row, 16, _("AÑO"), lines_style_colored)
        ws1.write(row, 17, _("SEMANAL"), lines_style_colored)
        ws1.write(row, 18, _("MENSUAL"), lines_style_colored)
        ws1.write(row, 19, _("COTIZACIÓN SEMANAL DEL TRABAJADOR (IVSS)"), lines_style_colored)
        ws1.write(row, 20, _("APORTE SEMANAL DEL EMPLEADOR (IVSS)"), lines_style_colored)
        ws1.write(row, 21, _("TOTALES APORTES AL IVSS"), lines_style_colored)
        ws1.write(row, 22, _("COTIZACIÓN SEMANAL DEL TRABAJADOR POR  R. P. E."), lines_style_colored)
        ws1.write(row, 23, _("APORTE SEMANAL DEL EMPLEADOR POR  R. P. E."), lines_style_colored)
        ws1.write(row, 24, _("TOTALES APORTES POR  R. P. E."), lines_style_colored)
        ws1.write(row, 25, _("OCUPACIÓN U OFICIO"), lines_style_colored)
        ws1.write(row, 26, _("MONTO "), lines_style_colored)
        ws1.write(row, 27, _("TIPO DE MOVIMIENTO "), lines_style_colored)
        row += 1

        # Ajustar el ancho de las columnas automáticamente
        column_widths = [0] * 27
        min_width = 6

        for c in items['result']:
            column_widths[0] = max(column_widths[0], len(str(c['cont'])))
            column_widths[1] = max(column_widths[1], len(str(c['employee']) if c['employee'] else ''))
            column_widths[2] = max(column_widths[2], len(str(c['nationality']) if c['nationality'] else ''))
            column_widths[3] = max(column_widths[3], len(str(c['identification_id']) if c['identification_id'] else ''))
            column_widths[4] = max(column_widths[4], len(str(c['birthday_days']) if c['birthday_days'] else ''))
            column_widths[5] = max(column_widths[5], len(str(c['birthday_month']) if c['birthday_month'] else ''))
            column_widths[6] = max(column_widths[6], len(str(c['birthday_year']) if c['birthday_year'] else ''))
            column_widths[11] = max(column_widths[11], len(str(c['date_start_days']) if c['date_start_days'] else ''))
            column_widths[12] = max(column_widths[12], len(str(c['date_start_month']) if c['date_start_month'] else ''))
            column_widths[13] = max(column_widths[13], len(str(c['date_start_year']) if c['date_start_year'] else ''))
            column_widths[14] = max(column_widths[14], len(str(c['date_end_days']) if c['date_end_days'] else ''))
            column_widths[15] = max(column_widths[15], len(str(c['date_end_month']) if c['date_end_month'] else ''))
            column_widths[16] = max(column_widths[16], len(str(c['date_end_year']) if c['date_end_year'] else ''))
            
            column_widths[17] = max(column_widths[17], len(str(c['monthly_salary']) if c['monthly_salary'] else ''))
            column_widths[18] = max(column_widths[18], len(str(c['weekly_salary']) if c['weekly_salary'] else ''))
            column_widths[19] = max(column_widths[19], len(str(c['employee_weekly_quote']) if c['employee_weekly_quote'] else ''))
            column_widths[20] = max(column_widths[20], len(str(c['employer_weekly_contribution']) if c['employer_weekly_contribution'] else ''))
            column_widths[21] = max(column_widths[21], len(str(c['total_contribution_ivss']) if c['total_contribution_ivss'] else ''))
            column_widths[22] = max(column_widths[22], len(str(c['employee_weekly_quote_rpe']) if c['employee_weekly_quote_rpe'] else ''))
            column_widths[23] = max(column_widths[23], len(str(c['employer_weekly_quote_rpe']) if c['employer_weekly_quote_rpe'] else ''))
            column_widths[24] = max(column_widths[24], len(str(c['total_contribution_rpe']) if c['total_contribution_rpe'] else ''))
            
            column_widths[25] = max(column_widths[25], len(str(c['job_name']) if c['job_name'] else ''))
            
            column_widths[26] = max(column_widths[26], len(str(c['amount']) if c['amount'] else ''))

        for i, width in enumerate(column_widths):
            ws1.col(i).width = 256 * max(width + 2, min_width)  # Ajustar el ancho de la columna con un mínimo

        # Mostrar datos de _prepare_data()
        for c in items['result']:
            nationality = ''
            if c['nationality']:
                nationality = c['nationality'].lower()
            ws1.write(row, 0, c['cont'], lines_style_center)
            ws1.write(row, 1, c['employee'], lines_style_left)
            ws1.write(row, 2, 'X' if nationality == 'v' else '', lines_style_center)
            ws1.write(row, 3, c['identification_id'], lines_style_left)
            ws1.write(row, 4, c['birthday_days'], lines_style_center)
            ws1.write(row, 5, c['birthday_month'], lines_style_center)
            ws1.write(row, 6, c['birthday_year'], lines_style_center)
            ws1.write(row, 7, c['female'], lines_style_center)
            ws1.write(row, 8, c['male'], lines_style_center)
            ws1.write(row, 9, '', lines_style_left)
            ws1.write(row, 10, '', lines_style_left)
            ws1.write(row, 11, c['date_start_days'], lines_style_center)
            ws1.write(row, 12, c['date_start_month'], lines_style_center)
            ws1.write(row, 13, c['date_start_year'], lines_style_center)
            ws1.write(row, 14, c['date_end_days'], lines_style_center)
            ws1.write(row, 15, c['date_end_month'], lines_style_center)
            ws1.write(row, 16, c['date_end_year'], lines_style_center)
            ws1.write(row, 17, c['weekly_salary'], number_style_right)
            ws1.write(row, 18, c['monthly_salary'], number_style_right)
            ws1.write(row, 19, c['employee_weekly_quote'], number_style_right)
            ws1.write(row, 20, c['employer_weekly_contribution'], number_style_right)
            ws1.write(row, 21, c['total_contribution_ivss'], number_style_right)
            ws1.write(row, 22, c['employee_weekly_quote_rpe'], number_style_right)
            ws1.write(row, 23, c['employer_weekly_quote_rpe'], number_style_right)
            ws1.write(row, 24, c['total_contribution_rpe'], number_style_right)
            ws1.write(row, 25, c['job_name'], lines_style_left)
            ws1.write(row, 26, c['amount'], number_style_right)
            ws1.write(row, 27, 'SIN MOVIMIENTO ', lines_style_left)
            row += 1

        # IMPRESIÓN
        wb1.save(fp)
        
        out = base64.encodebytes(fp.getvalue()).decode('utf-8')
        fecha  = self.date_now.strftime('%B')
        self.write({'state': 'get', 'report': out, 'name': _('Forma 13-12 ')+ fecha +'.xls'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.forma.1312',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }