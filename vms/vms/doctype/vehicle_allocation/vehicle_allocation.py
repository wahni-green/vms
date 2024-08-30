# Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.party import get_party_account
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.item.item import get_item_defaults
from frappe import _
from frappe.contacts.doctype.address.address import get_company_address
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.utils import cint, flt
from pypika import CustomFunction


class VehicleAllocation(Document):
	def validate(self):
		self.check_availability()
		self.calculate_allocated_qty()

	def on_submit(self):
		if not self.orders:
			frappe.throw(_("Cannot submit without any items."))
		self.update_allocated_qty()
		self.generate_invoice()

	def on_cancel(self):
		self.update_allocated_qty()

	def update_allocated_qty(self):
		if self.docstatus == 1:
			for row in self.orders:
				allocated_qty = row.order_qty - row.pending_qty
				allocated_qty += row.allocated_qty
				frappe.db.set_value(
					"Sales Order Item", row.sales_order_detail, "allocated_qty", allocated_qty
				)
		elif self.docstatus == 2:
			for row in self.orders:
				allocated_qty = frappe.db.get_value(
					"Sales Order Item", row.sales_order_detail, "allocated_qty"
				)
				allocated_qty -= row.allocated_qty
				frappe.db.set_value(
					"Sales Order Item", row.sales_order_detail, "allocated_qty", allocated_qty
				)

	@frappe.whitelist()
	def generate_invoice(self):
		sales_order_map = {}
		row_qty_map = {}
		for row in self.orders:
			sales_order_map.setdefault(row.sales_order, []).append(row.sales_order_detail)
			row_qty_map[row.sales_order_detail] = row.allocated_qty

		for order, rows in sales_order_map.items():
			try:
				target_doc = self.make_sales_invoice(order, rows, row_qty_map)
			except Exception as e:
				frappe.log_error(
					title="Vehicle Allocation Invoice Error", message=str(frappe.get_traceback())
				)
				frappe.throw(_("Could not invoice order {0}. Error: {1}").format(order, e))

			if target_doc and target_doc.items:
				# target_doc.save()
				target_doc.submit()

		frappe.publish_realtime("invoice_generation")

	def make_sales_invoice(self, order, rows, row_qty_map):
		# reason why this is put here is to let people extend this method to override
		def postprocess(source, target):
			set_missing_values(source, target)
			# Get the advance paid Journal Entries in Sales Invoice Advance
			if target.get("allocate_advances_automatically"):
				target.set_advances()

		def set_missing_values(source, target):
			target.flags.ignore_permissions = True
			target.run_method("set_missing_values")
			target.run_method("set_po_nos")
			target.run_method("calculate_taxes_and_totals")
			target.run_method("set_use_serial_batch_fields")

			if source.company_address:
				target.update({"company_address": source.company_address})
			else:
				# set company address
				target.update(get_company_address(target.company))

			if target.company_address:
				target.update(get_fetch_values("Sales Invoice", "company_address", target.company_address))

			# set the redeem loyalty points if provided via shopping cart
			if source.loyalty_points and source.order_type == "Shopping Cart":
				target.redeem_loyalty_points = 1

			target.debit_to = get_party_account("Customer", source.customer, source.company)
			target.vehicle_allocation = self.name

		def update_item(source, target, source_parent):
			target.amount = flt(source.amount) - flt(source.billed_amt)
			target.base_amount = target.amount * flt(source_parent.conversion_rate)
			target.qty = (
				target.amount / flt(source.rate)
				if (source.rate and source.billed_amt)
				else source.qty - source.returned_qty
			)

			if source_parent.project:
				target.cost_center = frappe.db.get_value("Project", source_parent.project, "cost_center")
			if target.item_code:
				item = get_item_defaults(target.item_code, source_parent.company)
				item_group = get_item_group_defaults(target.item_code, source_parent.company)
				cost_center = item.get("selling_cost_center") or item_group.get("selling_cost_center")

				if cost_center:
					target.cost_center = cost_center

		doclist = get_mapped_doc(
			"Sales Order",
			order,
			{
				"Sales Order": {
					"doctype": "Sales Invoice",
					"field_map": {
						"party_account_currency": "party_account_currency",
						"payment_terms_template": "payment_terms_template",
					},
					"field_no_map": ["payment_terms_template"],
					"validation": {"docstatus": ["=", 1]},
				},
				"Sales Order Item": {
					"doctype": "Sales Invoice Item",
					"field_map": {
						"name": "so_detail",
						"parent": "sales_order",
					},
					"postprocess": update_item,
					"condition": (
						lambda doc: (
							doc.qty
							and (doc.base_amount == 0 or abs(doc.billed_amt) < abs(doc.amount))
							and doc.name in rows
						)
					),
				},
				"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "add_if_empty": True},
				"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
			},
			None,
			postprocess,
			ignore_permissions=False,
		)

		automatically_fetch_payment_terms = cint(
			frappe.db.get_single_value("Accounts Settings", "automatically_fetch_payment_terms")
		)
		if automatically_fetch_payment_terms:
			doclist.set_payment_schedule()

		return doclist

	def calculate_allocated_qty(self):
		self.allocated_qty = 0
		self.allocated_weight = 0
		for order in self.orders:
			self.allocated_qty += order.allocated_qty
			self.allocated_weight += order.allocated_weight

		if self.allocated_qty > self.qty_capacity:
			frappe.msgprint(_("Allocated quantity is more than vehicle capacity."))

		if self.allocated_weight > self.weight_capacity:
			frappe.msgprint(_("Allocated weight is more than vehicle capacity."))

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
		routes = [d.route for d in self.routes]
		territories = [d.territory for d in self.territories]

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
					(soi.qty - soi.allocated_qty).as_("qty"),
					soi.qty.as_("order_qty"),
					soi.rate,
					soi.uom,
					soi.stock_qty,
					(soi.weight_per_unit * (soi.qty)).as_("weight"),
				)
				.where(so.docstatus == 1)
				.where(so.company == company)
				.where(so.status != "Closed")
				.where(soi.allocated_qty < soi.qty)
				.where(soi.delivered_qty < soi.qty)
				.where((soi.billed_amt) < (soi.amount))
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
					"route": order.get("route", ""),
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
					"route": order.get("route", ""),
					"order_qty": order.get("order_qty"),
				}
			)

		return {"orders": list(order_dict.values()), "items": order_details}
