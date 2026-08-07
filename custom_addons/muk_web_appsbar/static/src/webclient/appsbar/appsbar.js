import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';

import { Component, onWillUnmount } from '@odoo/owl';

export class AppsBar extends Component {
	static template = 'muk_web_appsbar.AppsBar';
    static props = {};
	setup() {
		this.companyService = useService('company');
        this.appMenuService = useService('app_menu');
    	if (this.companyService.currentCompany.has_appsbar_image) {
            this.sidebarImageUrl = url('/web/image', {
                model: 'res.company',
                field: 'appbar_image',
                id: this.companyService.currentCompany.id,
            });
    	}
    	const renderAfterMenuChange = () => {
            this.render();
        };
        this.env.bus.addEventListener(
        	'MENUS:APP-CHANGED', renderAfterMenuChange
        );
        onWillUnmount(() => {
            this.env.bus.removeEventListener(
            	'MENUS:APP-CHANGED', renderAfterMenuChange
            );
        });
    }
    _onAppClick(app) {
        return this.appMenuService.selectApp(app);
    }
    getAppIcon(app) {
        if (app.webIconData) {
            return app.webIconData;
        }
        if (app.webIcon) {
            const parts = app.webIcon.split(',');
            if (parts.length === 2) {
                return `/${parts[0].trim()}/${parts[1].trim()}`;
            }
        }
        const xmlid = (app.xmlid || '').toLowerCase();
        const label = (app.label || '').toLowerCase();
        if (xmlid.includes('discuss') || xmlid.includes('mail') || label.includes('discuss')) return '/mail/static/description/icon.png';
        if (xmlid.includes('todo') || label.includes('to-do') || label.includes('todo')) return '/project/static/description/icon.png';
        if (xmlid.includes('contacts') || label.includes('contacts')) return '/contacts/static/description/icon.png';
        if (xmlid.includes('hr') || xmlid.includes('employee') || label.includes('employee')) return '/hr/static/description/icon.png';
        if (xmlid.includes('sale') || label.includes('sales')) return '/sale/static/description/icon.png';
        if (xmlid.includes('purchase') || label.includes('purchase')) return '/purchase/static/description/icon.png';
        if (xmlid.includes('stock') || label.includes('inventory')) return '/stock/static/description/icon.png';
        if (xmlid.includes('mrp') || label.includes('manufacturing')) return '/mrp/static/description/icon.png';
        if (xmlid.includes('account') || label.includes('invoicing')) return '/account/static/description/icon.png';
        if (xmlid.includes('helpdesk') || label.includes('helpdesk')) return '/helpdesk_mgmt/static/description/icon.png';
        if (xmlid.includes('project') || label.includes('project')) return '/project/static/description/icon.png';
        if (xmlid.includes('dashboard') || label.includes('dashboard')) return '/spreadsheet_dashboard/static/description/icon.png';
        if (xmlid.includes('spreadsheet') || label.includes('spreadsheet')) return '/spreadsheet_dashboard/static/description/icon.png';
        if (xmlid.includes('settings') || label.includes('settings')) return '/base/static/description/settings.png';
        if (xmlid.includes('apps') || label.includes('apps')) return '/base/static/description/settings.png';
        return '/base/static/description/icon.png';
    }
}
