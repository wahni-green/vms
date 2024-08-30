# Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Sales Order Item": [
				{
					"fieldname": "allocated_qty",
					"label": "Allocated Qty",
					"fieldtype": "Float",
					"insert_after": "delivered_qty",
					"translatable": 0,
					"read_only": 1,
				},
			],
			"Sales Order": [
				{
					"fieldname": "route",
					"label": "Route",
					"fieldtype": "Link",
					"options": "Route",
					"insert_after": "territory",
				}
			],
			"Sales Invoice": [
				{
					"fieldname": "vehicle_allocation",
					"label": "Vehicle Allocation",
					"fieldtype": "Link",
					"options": "Vehicle Allocation",
					"insert_after": "customer",
					"read_only": 1,
				},
				{
					"fieldname": "route",
					"label": "Route",
					"fieldtype": "Link",
					"options": "Route",
					"insert_after": "territory",
				},
			],
			"Vehicle": [
				{
					"fieldname": "qty_capacity",
					"label": "Qty Capacity",
					"fieldtype": "Float",
					"insert_after": "location",
				},
				{
					"fieldname": "weight_capacity",
					"label": "Weight Capacity",
					"fieldtype": "Float",
					"insert_after": "employee",
				},
			],
		}
	)
