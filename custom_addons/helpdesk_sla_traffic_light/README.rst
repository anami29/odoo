==================================================
Helpdesk SLA Traffic Lights & AHT Reports
==================================================

This module extends OCA Helpdesk Management and Helpdesk SLA modules to provide:
1. SLA Traffic Lights (visual indicators) in Ticket lists, Kanban cards, and Form header.
2. Average Handling Time (AHT) reports with pivot, graph, list views, and a dedicated menu.

Features
========

* **Visual Indicators (Traffic Lights)**:
  * **Red**: SLA expired or breached.
  * **Green**: SLA active and on time.
  * **Amber**: SLA active but deadline is within the warning threshold (configurable, default 4 hours).
  * **Grey**: No SLA configured for this team, or all SLA lines already completed.
* **Average Handling Time Reports**:
  * Calculates resolution times and assignment times.
  * Accessible under Helpdesk -> Reporting -> Handling Time.
  * Restricts views to manager group.

Limitations
===========

* Handling time reporting is currently based on wall-clock time, not working hours calendar.
