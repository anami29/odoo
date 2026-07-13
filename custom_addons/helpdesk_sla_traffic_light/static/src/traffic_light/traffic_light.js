import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";
import { formatDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;

export class SlaTrafficLightField extends Component {
    static template = "helpdesk_sla_traffic_light.SlaTrafficLightField";
    static props = {
        ...standardFieldProps,
    };

    get status() {
        return this.props.record.data[this.props.name];
    }

    get deadline() {
        return this.props.record.data.sla_deadline;
    }

    get tooltipText() {
        const status = this.status;
        const deadline = this.deadline;

        if (status === "no_sla") {
            return _t("No SLA");
        }

        if (!deadline) {
            if (status === "expired") {
                return _t("SLA Breached");
            }
            return _t("SLA Active");
        }

        // Format deadline
        const formattedDeadline = formatDateTime(deadline, { format: localization.dateFormat + " HH:mm:ss" });

        // Calculate remaining time
        const now = DateTime.local();
        const diff = deadline.diff(now, ["days", "hours", "minutes"]);
        
        if (diff.as("milliseconds") <= 0) {
            return _t("SLA Breached (Deadline: %s)", formattedDeadline);
        }

        // Format remaining string
        let remainingStr = "";
        const days = Math.floor(diff.days);
        const hours = Math.floor(diff.hours);
        const minutes = Math.floor(diff.minutes);

        if (days > 0) {
            remainingStr += _t("%s days ", days);
        }
        if (hours > 0 || days > 0) {
            remainingStr += _t("%s hours ", hours);
        }
        remainingStr += _t("%s minutes", minutes);

        return _t("Deadline: %s (Remaining: %s)", formattedDeadline, remainingStr);
    }

    get dotClass() {
        const status = this.status;
        switch (status) {
            case "expired":
                return "bg-danger o_sla_dot_red";
            case "warning":
                return "bg-warning o_sla_dot_amber";
            case "on_time":
                return "bg-success o_sla_dot_green";
            case "no_sla":
            default:
                return "bg-secondary o_sla_dot_grey";
        }
    }
}

export const slaTrafficLightField = {
    component: SlaTrafficLightField,
    supportedTypes: ["selection"],
};

registry.category("fields").add("sla_traffic_light", slaTrafficLightField);
