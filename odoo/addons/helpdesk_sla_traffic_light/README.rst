==========================
Helpdesk SLA Traffic Light
==========================

This module adds visual indicators for SLA status on helpdesk tickets and Average Handling Time reports.

Configuration
=============

To configure the warning threshold hours, modify the system parameter `helpdesk_sla_traffic_light.warning_hours` (default: 4).

Usage
=====

* Visual indicators are visible in My Tickets and All Tickets views (list, kanban, and form).
* Average Handling Time reporting is available under Helpdesk -> Reporting -> Handling Time.

Limitations
===========

* Working-calendar-aware handling time is not supported in this version. Handled time is computed based on wall-clock time.
