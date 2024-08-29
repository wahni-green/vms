# Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from pypika import CustomFunction


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

	@frappe.whitelist()
	def get_order_items(self):
		# routes = [d.route for d in self.routes]
		# territories = [d.territory for d in self.territories]
		routes = []
		territories = []

		draft_allocations = (
			frappe.db.get_all("Vehicle Allocation", filters={"docstatus": 0}, pluck="name") or []
		)
		draft_allocations.append(self.name)
		exclude = []
		if draft_allocations:
			exclude = frappe.db.get_all(
				"Vehicle Allocation Order",
				filters={"parent": ["in", draft_allocations]},
				pluck="sales_order_detail",
			)

		so = frappe.qb.DocType("Sales Order")
		soi = frappe.qb.DocType("Sales Order Item")

		DateFormat = CustomFunction("DATE_FORMAT", ["date", "format"])
		orders = []
		company_list = frappe.db.get_all("Company", pluck="name", order_by="name desc")
		for company in company_list:
			result = (
				frappe.qb.from_(so)
				.inner_join(soi)
				.on(soi.parent == so.name)
				.select(
					so.name.as_("sales_order"),
					so.customer,
					DateFormat(so.transaction_date, "%d-%m-%Y").as_("date"),
					so.company,
					so.transaction_date,
					so.route,
					soi.name.as_("sales_order_detail"),
					soi.item_code.as_("item"),
					# (soi.qty - soi.allocated_qty).as_("qty"),
					soi.qty,
					soi.rate,
					soi.uom,
					soi.stock_qty,
					(soi.weight_per_unit * (soi.qty)).as_("weight"),
				)
				.where(so.docstatus == 1)
				.where(so.company == company)
				.where(so.status != "Closed")
				# .where(soi.allocated_qty < soi.qty)
				.orderby(so.transaction_date)
			)
			if exclude:
				result = result.where(soi.name.notin(exclude))
			if territories:
				result = result.where(so.territory.isin(territories))
			if routes:
				result = result.where(so.route.isin(routes))

			orders += result.run(as_dict=True) or []

		order_dict = {}
		order_details = {}
		for order in orders:
			order_dict.setdefault(
				order.get("sales_order"),
				{
					"sales_order": order.get("sales_order"),
					"customer": order.get("customer"),
					"date": order.get("date"),
					"company": order.get("company"),
					"transaction_date": order.get("transaction_date"),
					"route": order.get("route"),
				},
			)
			order_details.setdefault(order.get("sales_order"), [])
			order_details[order.get("sales_order")].append(
				{
					"sales_order_detail": order.get("sales_order_detail"),
					"item": order.get("item"),
					"qty": order.get("qty"),
					"rate": order.get("rate"),
					"uom": order.get("uom"),
					"stock_qty": order.get("stock_qty"),
					"weight": order.get("weight"),
					"sales_order": order.get("sales_order"),
					"customer": order.get("customer"),
					"date": order.get("date"),
					"company": order.get("company"),
					"transaction_date": order.get("transaction_date"),
					"route": order.get("route"),
				}
			)

		return {"orders": list(order_dict.values()), "items": order_details}
