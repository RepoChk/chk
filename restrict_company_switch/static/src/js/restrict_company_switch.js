/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SwitchCompanyItem } from "@web/webclient/switch_company_menu/switch_company_menu";

// Parchear el SwitchCompanyItem para restringir selección múltiple
patch(SwitchCompanyItem.prototype, {
    async toggleCompany() {
        const selectedCompanies = this.companySelector.selectedCompaniesIds;

        // Verificar si el usuario pertenece al grupo directamente en el cliente
        const userHasGroup = await this.env.services.user.hasGroup("restrict_company_switch.group_restrict_company_switch");
        console.log("User has group:", userHasGroup);
        console.log("groups:", this.env.services.user.hasGroup("restrict_company_switch.group_restrict_company_switch"));
        // Si no tiene el grupo, aplicar la restricción
        if (!userHasGroup && selectedCompanies.length >= 1 && !selectedCompanies.includes(this.props.company.id)) {
            this.env.services.notification.add(
                "No puedes seleccionar más de una compañía al mismo tiempo.",
                { type: "danger" }
            );
            return; // Cancelar la acción si intenta seleccionar múltiples compañías
        }

        // Continuar con el comportamiento normal si cumple las condiciones
        this.companySelector.switchCompany("toggle", this.props.company.id);
    },
});