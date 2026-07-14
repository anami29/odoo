import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

export class SlaTrafficLightWidget extends Component {
    static template = "helpdesk_sla_traffic_light.SlaTrafficLightWidget";
    static props = {
        ...standardFieldProps,
    };

    get status() {
        return this.props.record.data.sla_status;
    }

    get deadline() {
        return this.props.record.data.sla_deadline;
    }

    get tooltipText() {
        let deadline = this.deadline;
        const status = this.status;
        if (status === 'no_sla' || !deadline) {
            return _t("No SLA");
        }
        
        if (typeof deadline === 'string') {
            let parsed = luxon.DateTime.fromISO(deadline);
            if (!parsed.isValid) {
                parsed = luxon.DateTime.fromSQL(deadline);
            }
            deadline = parsed;
        }

        if (!deadline || !deadline.isValid) {
            return _t("No SLA");
        }

        const now = luxon.DateTime.now();
        const formattedDeadline = deadline.toFormat("yyyy-MM-dd HH:mm:ss");

        if (deadline < now) {
            const diff = now.diff(deadline, ["hours", "minutes"]);
            const hours = Math.floor(diff.hours);
            const minutes = Math.floor(diff.minutes);
            return `${_t("Deadline:")} ${formattedDeadline} (${_t("expired")} ${hours}h ${minutes}m ${_t("ago")})`;
        } else {
            const diff = deadline.diff(now, ["hours", "minutes"]);
            const hours = Math.floor(diff.hours);
            const minutes = Math.floor(diff.minutes);
            return `${_t("Deadline:")} ${formattedDeadline} (${_t("remaining:")} ${hours}h ${minutes}m)`;
        }
    }
}

registry.category("fields").add("sla_traffic_light", {
    component: SlaTrafficLightWidget,
    supportedTypes: ["selection"],
});
