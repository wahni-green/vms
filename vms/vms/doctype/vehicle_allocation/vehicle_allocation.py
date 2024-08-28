# Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleAllocation(Document):
    def validate(self):
        self.check_availability()
        # self.calculate_allocated_qty()
        # self.validate_capacity()

    def check_availability(self):
        duplicate = frappe.db.get_all(
            self.doctype,
            filters={
                "docstatus": ["!=", 2],
                "delivery_date": self.delivery_date,
                "name": ["!=", self.name],
            },
            or_filters={"vehicle": self.vehicle, "driver": self.driver},
        )
        if duplicate:
            frappe.throw(_("Vehicle or driver already allocated for the given delivery date."))