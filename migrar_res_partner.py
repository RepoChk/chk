import odoorpc

odoo_13 = odoorpc.ODOO('148.113.175.159', port=8069)
odoo_13.login('odoo13_prd_chakao', 'Anderson Rodriguez', '*gA241ghk*')
print('conectado a odoo 13')

#instancia de prueba odoo 17
odoo_17 = odoorpc.ODOO('qa.grupochakao.com', port=80)
odoo_17.login('qa.grupochakao.com', 'ajrodriguez@grupochakao.com', '123456')
print('conectado a odoo 17')

#consultar el modelo res.partner en odoo 13
partner_ids = odoo_13.env['res.partner'].search([])
print('cantidad de partners en odoo 13: ', len(partner_ids))

#ordena la lista de partner_ids
partner_ids = sorted(partner_ids)

estados_ids = odoo_17.env['res.country.state'].search([('country_id', '=', 238)])
estados_ids = odoo_17.env['res.country.state'].browse(estados_ids)

estados_map = []
#por cada estado en estados_ids agregar a la variable estamos_map el código y el id
for e in estados_ids:
    estados_map.append({
        'name': e.name.replace(' (VE) ', ''),
        'id': e.id
    })
print('estados_map: ', estados_map)
municipios_ids = odoo_17.env['res.country.state.municipality'].search([])
municipios_ids = odoo_17.env['res.country.state.municipality'].browse(municipios_ids)

muninicipios_map = []
#por cada municipio en municipios_ids agregar a la variable municipios_map el código y el id
for m in municipios_ids:
    muninicipios_map.append({
        'name': m.name.rstrip(),
        'id': m.id
    })

parroquias_ids = odoo_17.env['res.country.state.municipality.parish'].search([])
parroquias_ids = odoo_17.env['res.country.state.municipality.parish'].browse(parroquias_ids)

parroquias_map = []
#por cada parroquia en parroquias_ids agregar a la variable parroquias_map el código y el id
for p in parroquias_ids:
    parroquias_map.append({
        'name': p.name.rstrip(),
        'id': p.id
    })

i = -1
#crear un ciclo para buscar cada partner en odoo 13 e incluir en odoo 17
for partner in partner_ids:
    i += 1
    if i >= 0:
        partner_data = odoo_13.env['res.partner'].read(partner, ['name', 'street', 'street2', 'city', 'zip', 'state_id', 'country_id', 'municipality_id', 'parish_id', 'phone', 'mobile', 'email', 'vat', 'company_id', 'company_type', 'doc_type'])
        partner_data = partner_data[0]
        print('partner_data: ', partner_data)
        doc_type = partner_data['doc_type'].upper() if partner_data['doc_type'] else 'V'
        vat = partner_data['vat'].replace('-', '') if partner_data['vat'] else False
        state_id = False
        if partner_data['state_id']:
            state_name = partner_data['state_id'][1].replace(' (VE)', '')
            for e in estados_map:
                if e['name'] == state_name:
                    state_id = e['id']
        municipality_id = False
        if partner_data['municipality_id']:
            for m in muninicipios_map:
                if m['name'] == partner_data['municipality_id'][1].rstrip():
                    municipality_id = m['id']

        parroquias_id = False
        if partner_data['parish_id']:
            for p in parroquias_map:
                if p['name'] == partner_data['parish_id'][1].rstrip().replace('Capital ', ''):
                    parroquias_id = p['id']

        print('inicializando data_to_create')
        data_to_create = {
            'name': partner_data['name'],
            'street': partner_data['street'],
            'street2': partner_data['street2'],
            'city': partner_data['city'],
            'zip': partner_data['zip'],
            'state_id': state_id,
            'country_id': 238,
            'municipality_id': municipality_id,
            'parish_id': parroquias_id,
            'phone': partner_data['phone'],
            'mobile': partner_data['mobile'],
            'email': partner_data['email'],
            'vat': (doc_type + '-' + vat[:-1] + '-' + vat[-1]) if vat else False,
            'rif': (doc_type + '-' + vat[:-1] + '-' + vat[-1]) if vat else False,
            'company_type': partner_data['company_type'],
            'people_type_individual':'pnre',
            'people_type_company':'pjdo',
        }
        print('creando: ', data_to_create)
        #incluir en odoo 17
        try:
            odoo_17.env['res.partner'].create(data_to_create)
        except Exception as e:
            print('error: ', e)
        print('creado: ', partner_data['name'])
        print('i = ', i)
