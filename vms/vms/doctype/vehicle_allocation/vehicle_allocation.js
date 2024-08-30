// Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vehicle Allocation", {
	refresh(frm) {
		if (frm.doc.docstatus == 0) {
			frm.add_custom_button(
				__("Sales Order"),
				function () {
					// eslint-disable-next-line
					let OrderSelector = new vms.OrderSelector(frm);
					OrderSelector.init();
				},
				__("Get Items From")
			);
		}
	},
});
