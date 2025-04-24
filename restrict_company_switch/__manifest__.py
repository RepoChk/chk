{
    "name": "Restricción Cambio de Compañías",
    "summary": "Restringe la selección de múltiples compañías en el Switch de Compañías basado en un grupo",
    "depends": ["base", "web"],
    "data": [
        "security/security_groups.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "restrict_company_switch/static/src/js/restrict_company_switch.js",
        ],
    },
    "installable": True,
    "application": False,
}