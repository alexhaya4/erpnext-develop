# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
import unittest

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.accounts.doctype.accounting_dimension.test_accounting_dimension import (
	create_dimension,
	disable_dimension,
)
from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import (
	make_closing_entry_from_opening,
)
from erpnext.accounts.doctype.pos_invoice.test_pos_invoice import create_pos_invoice
from erpnext.accounts.doctype.pos_opening_entry.test_pos_opening_entry import create_opening_entry
from erpnext.accounts.doctype.pos_profile.test_pos_profile import make_pos_profile
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.selling.page.point_of_sale.point_of_sale import get_items
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.serial_and_batch_bundle.test_serial_and_batch_bundle import (
	get_batch_from_bundle,
)
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_stock_entry


class TestPOSClosingEntry(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		frappe.db.sql("delete from `tabPOS Opening Entry`")
		cls.enterClassContext(cls.change_settings("POS Settings", {"invoice_type": "POS Invoice"}))

	@classmethod
	def tearDownClass(cls):
		frappe.db.sql("delete from `tabPOS Opening Entry`")

	def setUp(self):
		# Make stock available for POS Sales
		frappe.db.sql("delete from `tabPOS Opening Entry`")
		make_stock_entry(target="_Test Warehouse - _TC", qty=2, basic_rate=100)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.sql("delete from `tabPOS Profile`")

	def test_pos_closing_entry(self):
		test_user, pos_profile = init_user_and_profile()
		opening_entry = create_opening_entry(pos_profile, test_user.name)

		pos_inv1 = create_pos_invoice(rate=3500, do_not_submit=1)
		pos_inv1.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3500})
		pos_inv1.save()
		pos_inv1.submit()

		pos_inv2 = create_pos_invoice(rate=3200, do_not_submit=1)
		pos_inv2.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3200})
		pos_inv2.save()
		pos_inv2.submit()

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		payment = pcv_doc.payment_reconciliation[0]

		self.assertEqual(payment.mode_of_payment, "Cash")

		for d in pcv_doc.payment_reconciliation:
			if d.mode_of_payment == "Cash":
				d.closing_amount = 6700

		pcv_doc.submit()

		self.assertEqual(pcv_doc.total_quantity, 2)
		self.assertEqual(pcv_doc.net_total, 6700)

	def test_pos_closing_without_item_code(self):
		"""
		Test if POS Closing Entry is created without item code
		"""
		test_user, pos_profile = init_user_and_profile()
		opening_entry = create_opening_entry(pos_profile, test_user.name)

		pos_inv = create_pos_invoice(rate=3500, do_not_submit=1, item_name="Test Item", without_item_code=1)
		pos_inv.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3500})
		pos_inv.save()
		pos_inv.submit()

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		pcv_doc.submit()

		self.assertTrue(pcv_doc.name)

	def test_pos_qty_for_item(self):
		"""
		Test if quantity is calculated correctly for an item in POS Closing Entry
		"""
		from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

		test_user, pos_profile = init_user_and_profile()
		opening_entry = create_opening_entry(pos_profile, test_user.name)

		test_item_qty = get_test_item_qty(pos_profile)

		pos_inv1 = create_pos_invoice(rate=3500, do_not_submit=1)
		pos_inv1.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3500})
		pos_inv1.save()
		pos_inv1.submit()

		pos_inv2 = create_pos_invoice(rate=3200, do_not_submit=1)
		pos_inv2.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3200})
		pos_inv2.save()
		pos_inv2.submit()

		# make return entry of pos_inv2
		pos_return = make_sales_return(pos_inv2.name)
		pos_return.paid_amount = pos_return.grand_total
		pos_return.save()
		pos_return.submit()

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		pcv_doc.submit()

		opening_entry = create_opening_entry(pos_profile, test_user.name)
		test_item_qty_after_sales = get_test_item_qty(pos_profile)
		self.assertEqual(test_item_qty_after_sales, test_item_qty - 1)

	def test_cancelling_of_pos_closing_entry(self):
		test_user, pos_profile = init_user_and_profile()
		opening_entry = create_opening_entry(pos_profile, test_user.name)

		pos_inv1 = create_pos_invoice(rate=3500, do_not_submit=1)
		pos_inv1.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3500})
		pos_inv1.save()
		pos_inv1.submit()

		pos_inv2 = create_pos_invoice(rate=3200, do_not_submit=1)
		pos_inv2.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3200})
		pos_inv2.save()
		pos_inv2.submit()

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		payment = pcv_doc.payment_reconciliation[0]

		self.assertEqual(payment.mode_of_payment, "Cash")

		for d in pcv_doc.payment_reconciliation:
			if d.mode_of_payment == "Cash":
				d.closing_amount = 6700

		pcv_doc.submit()

		pos_inv1.load_from_db()
		self.assertRaises(frappe.ValidationError, pos_inv1.cancel)

		si_doc = frappe.get_doc("Sales Invoice", pos_inv1.consolidated_invoice)
		self.assertRaises(frappe.ValidationError, si_doc.cancel)

		pcv_doc.load_from_db()
		pcv_doc.cancel()

		cancelled_invoice = frappe.db.get_value(
			"POS Invoice Merge Log", {"pos_closing_entry": pcv_doc.name}, "consolidated_invoice"
		)
		docstatus = frappe.db.get_value("Sales Invoice", cancelled_invoice, "docstatus")
		self.assertEqual(docstatus, 2)

		pos_inv1.load_from_db()
		self.assertEqual(pos_inv1.status, "Paid")

	def test_pos_closing_for_required_accounting_dimension_in_pos_profile(self):
		"""
		test case to check whether we can create POS Closing Entry without mandatory accounting dimension
		"""

		create_dimension()
		location = frappe.get_doc("Accounting Dimension", "Location")
		location.dimension_defaults[0].mandatory_for_bs = True
		location.save()

		pos_profile = make_pos_profile(do_not_insert=1, do_not_set_accounting_dimension=1)

		self.assertRaises(frappe.ValidationError, pos_profile.insert)

		pos_profile.location = "Block 1"
		pos_profile.insert()
		self.assertTrue(frappe.db.exists("POS Profile", pos_profile.name))

		test_user = init_user_and_profile(do_not_create_pos_profile=1)

		opening_entry = create_opening_entry(pos_profile, test_user.name)
		pos_inv1 = create_pos_invoice(rate=350, do_not_submit=1, pos_profile=pos_profile.name)
		pos_inv1.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 3500})
		pos_inv1.save()
		pos_inv1.submit()

		# if in between a mandatory accounting dimension is added to the POS Profile then
		accounting_dimension_department = frappe.get_doc("Accounting Dimension", {"name": "Department"})
		accounting_dimension_department.dimension_defaults[0].mandatory_for_bs = 1
		accounting_dimension_department.save()

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		# will assert coz the new mandatory accounting dimension bank is not set in POS Profile
		self.assertRaises(frappe.ValidationError, pcv_doc.submit)

		accounting_dimension_department = frappe.get_doc(
			"Accounting Dimension Detail", {"parent": "Department"}
		)
		accounting_dimension_department.mandatory_for_bs = 0
		accounting_dimension_department.save()
		disable_dimension()

	def test_merging_into_sales_invoice_for_batched_item(self):
		frappe.flags.print_message = False
		from erpnext.accounts.doctype.pos_closing_entry.test_pos_closing_entry import (
			init_user_and_profile,
		)
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		frappe.db.sql("delete from `tabPOS Invoice`")
		item_doc = make_item(
			"_Test Item With Batch FOR POS Merge Test",
			properties={
				"is_stock_item": 1,
				"has_batch_no": 1,
				"batch_number_series": "BATCH-PM-POS-MERGE-.####",
				"create_new_batch": 1,
			},
		)

		item_code = item_doc.name
		se = make_stock_entry(
			target="_Test Warehouse - _TC",
			item_code=item_code,
			qty=10,
			basic_rate=100,
			use_serial_batch_fields=0,
		)
		batch_no = get_batch_from_bundle(se.items[0].serial_and_batch_bundle)

		test_user, pos_profile = init_user_and_profile()
		opening_entry = create_opening_entry(pos_profile, test_user.name)

		pos_inv = create_pos_invoice(
			item_code=item_code,
			qty=5,
			rate=300,
			use_serial_batch_fields=1,
			batch_no=batch_no,
			do_not_submit=True,
		)
		pos_inv.payments[0].amount = pos_inv.grand_total
		pos_inv.save()
		pos_inv.submit()
		pos_inv2 = create_pos_invoice(
			item_code=item_code,
			qty=5,
			rate=300,
			use_serial_batch_fields=1,
			batch_no=batch_no,
			do_not_submit=True,
		)
		pos_inv2.payments[0].amount = pos_inv2.grand_total
		pos_inv2.save()
		pos_inv2.submit()

		batch_qty_with_pos = get_batch_qty(batch_no, "_Test Warehouse - _TC", item_code)
		self.assertEqual(batch_qty_with_pos, 0.0)

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		pcv_doc.submit()

		piv_merge = frappe.db.get_value("POS Invoice Merge Log", {"pos_closing_entry": pcv_doc.name}, "name")

		self.assertTrue(piv_merge)
		piv_merge_doc = frappe.get_doc("POS Invoice Merge Log", piv_merge)
		self.assertTrue(piv_merge_doc.pos_invoices[0].pos_invoice)
		self.assertTrue(piv_merge_doc.pos_invoices[1].pos_invoice)

		pos_inv.load_from_db()
		self.assertTrue(pos_inv.consolidated_invoice)
		pos_inv2.load_from_db()
		self.assertTrue(pos_inv2.consolidated_invoice)

		batch_qty = frappe.db.get_value("Batch", batch_no, "batch_qty")
		self.assertEqual(batch_qty, 0.0)

		batch_qty_with_pos = get_batch_qty(batch_no, "_Test Warehouse - _TC", item_code)
		self.assertEqual(batch_qty_with_pos, 0.0)

		frappe.flags.print_message = True

		pcv_doc.reload()
		pcv_doc.cancel()

		batch_qty_with_pos = get_batch_qty(batch_no, "_Test Warehouse - _TC", item_code)
		self.assertEqual(batch_qty_with_pos, 0.0)

		pos_inv.reload()
		pos_inv2.reload()

		pos_inv.cancel()
		pos_inv2.cancel()

		batch_qty_with_pos = get_batch_qty(batch_no, "_Test Warehouse - _TC", item_code)
		self.assertEqual(batch_qty_with_pos, 10.0)

	@IntegrationTestCase.change_settings("POS Settings", {"invoice_type": "Sales Invoice"})
	def test_closing_entries_with_sales_invoice(self):
		test_user, pos_profile = init_user_and_profile()
		opening_entry = create_opening_entry(pos_profile, test_user.name)

		pos_si = create_sales_invoice(
			qty=10, is_created_using_pos=1, pos_profile=pos_profile.name, do_not_save=1
		)
		pos_si.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 1000})
		pos_si.save()
		pos_si.submit()

		pos_si2 = create_sales_invoice(
			qty=5, is_created_using_pos=1, pos_profile=pos_profile.name, do_not_save=11
		)
		pos_si2.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 1000})
		pos_si2.save()
		pos_si2.submit()

		pcv_doc = make_closing_entry_from_opening(opening_entry)
		payment = pcv_doc.payment_reconciliation[0]

		self.assertEqual(payment.mode_of_payment, "Cash")

		for d in pcv_doc.payment_reconciliation:
			if d.mode_of_payment == "Cash":
				d.closing_amount = 1500

		pcv_doc.submit()

		self.assertEqual(pcv_doc.total_quantity, 15)
		self.assertEqual(pcv_doc.net_total, 1500)

		pos_si2.reload()
		self.assertEqual(pos_si2.pos_closing_entry, pcv_doc.name)

	def test_sales_invoice_in_pos_invoice_mode(self):
		"""
		Test Sales Invoice and Return Sales Invoice creation during POS Invoice mode.
		"""
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

		test_user, pos_profile = init_user_and_profile()

		with self.change_settings("POS Settings", {"invoice_type": "Sales Invoice"}):
			opening_entry1 = create_opening_entry(pos_profile, test_user.name)

			pos_si1, pos_si2 = create_multiple_sales_invoices(pos_profile)

			pos_inv = create_pos_invoice(rate=100, do_not_save=1)
			pos_inv.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 100})
			self.assertRaises(frappe.ValidationError, pos_inv.save)

			pcv_doc1 = make_closing_entry_from_opening(opening_entry1)
			for d in pcv_doc1.payment_reconciliation:
				if d.mode_of_payment == "Cash":
					d.closing_amount = 300

			pcv_doc1.submit()
			self.assertTrue(pcv_doc1.name)

			pos_si1.reload()
			pos_si2.reload()
			self.assertEqual(pos_si1.pos_closing_entry, pcv_doc1.name)
			self.assertEqual(pos_si2.pos_closing_entry, pcv_doc1.name)

		with self.change_settings("POS Settings", {"invoice_type": "POS Invoice"}):
			opening_entry2 = create_opening_entry(pos_profile, test_user.name)

			pos_inv1, pos_inv2 = create_multiple_pos_invoices(pos_profile)

			# Trying to create Sales Invoice when invoice_type is set to POS Invoice.
			pos_si3 = create_sales_invoice(
				qty=1, is_created_using_pos=1, pos_profile=pos_profile.name, do_not_save=1
			)
			pos_si3.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 100})
			self.assertRaises(frappe.ValidationError, pos_si3.save)

			# Trying to create Return Sales Invoice.
			pos_rsi1 = make_sales_return(pos_si1.name)
			pos_rsi1.save()
			pos_rsi1.submit()

			self.assertEqual(pos_rsi1.paid_amount, -100)

			pcv_doc2 = make_closing_entry_from_opening(opening_entry2)
			pcv_doc2.submit()

			self.assertTrue(pcv_doc2.name)

			pos_rsi1.reload()
			self.assertEqual(pos_rsi1.pos_closing_entry, pcv_doc2.name)

			self.assertIn(pos_inv1.name, [d.pos_invoice for d in pcv_doc2.pos_invoices])
			self.assertNotIn(pos_inv2.name, [d.sales_invoice for d in pcv_doc2.sales_invoices])
			self.assertIn(pos_rsi1.name, [d.sales_invoice for d in pcv_doc2.sales_invoices])
			self.assertEqual(pcv_doc2.grand_total, 200)

	def test_pos_invoice_in_sales_invoice_mode(self):
		"""
		Test POS Invoice and Return POS Invoice creation during Sales Invoice mode.
		"""
		from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

		test_user, pos_profile = init_user_and_profile()

		with self.change_settings("POS Settings", {"invoice_type": "POS Invoice"}):
			opening_entry1 = create_opening_entry(pos_profile, test_user.name)

			pos_inv1, pos_inv2 = create_multiple_pos_invoices(pos_profile)

			# Trying to create Sales Invoice when invoice_type is set to POS Invoice.
			pos_sinv = create_sales_invoice(
				qty=1, is_created_using_pos=1, pos_profile=pos_profile.name, do_not_save=1
			)
			pos_sinv.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 100})
			self.assertRaises(frappe.ValidationError, pos_sinv.save)

			pcv_doc1 = make_closing_entry_from_opening(opening_entry1)
			for d in pcv_doc1.payment_reconciliation:
				if d.mode_of_payment == "Cash":
					d.closing_amount = 300

			pcv_doc1.submit()

			self.assertTrue(pcv_doc1.name)

			self.assertIn(pos_inv1.name, [d.pos_invoice for d in pcv_doc1.pos_invoices])
			self.assertEqual(pcv_doc1.grand_total, 300)

		with self.change_settings("POS Settings", {"invoice_type": "Sales Invoice"}):
			opening_entry2 = create_opening_entry(pos_profile, test_user.name)

			pos_si1, pos_si2 = create_multiple_sales_invoices(pos_profile)

			pos_inv3 = create_pos_invoice(rate=100, do_not_save=1)
			pos_inv3.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 100})
			self.assertRaises(frappe.ValidationError, pos_inv3.save)

			# Creating Return POS Invoice
			pos_rinv2 = make_sales_return(pos_inv2.name)
			pos_rinv2.save()
			pos_rinv2.submit()

			pos_rinv2.reload()
			self.assertIsNotNone(pos_rinv2.consolidated_invoice)

			# Getting Sales Invoice created during POS Invoice submission.
			pos_rinv2_si = frappe.get_doc("Sales Invoice", pos_rinv2.consolidated_invoice)
			self.assertEqual(pos_rinv2_si.is_return, 1)
			self.assertEqual(pos_rinv2_si.paid_amount, -200)

			pcv_doc2 = make_closing_entry_from_opening(opening_entry2)
			for d in pcv_doc1.payment_reconciliation:
				if d.mode_of_payment == "Cash":
					d.closing_amount = 100

			pcv_doc2.submit()
			self.assertTrue(pcv_doc2.name)

			pos_si1.reload()
			pos_si2.reload()
			pos_rinv2_si.reload()
			self.assertEqual(pos_si2.pos_closing_entry, pcv_doc2.name)
			self.assertEqual(pos_rinv2_si.pos_closing_entry, pcv_doc2.name)


def init_user_and_profile(**args):
	user = "test@example.com"
	test_user = frappe.get_doc("User", user)

	roles = ("Accounts Manager", "Accounts User", "Sales Manager")
	test_user.add_roles(*roles)
	frappe.set_user(user)

	if args.get("do_not_create_pos_profile"):
		return test_user

	pos_profile = make_pos_profile(**args)
	pos_profile.append("applicable_for_users", {"default": 1, "user": user})

	pos_profile.save()

	return test_user, pos_profile


def get_test_item_qty(pos_profile):
	test_item_pos = get_items(
		start=0,
		page_length=5,
		price_list="Standard Selling",
		pos_profile=pos_profile.name,
		search_term="_Test Item",
		item_group="All Item Groups",
	)

	test_item_qty = next(item for item in test_item_pos["items"] if item["item_code"] == "_Test Item").get(
		"actual_qty"
	)
	return test_item_qty


def create_multiple_sales_invoices(pos_profile):
	pos_si1 = create_sales_invoice(qty=1, is_created_using_pos=1, pos_profile=pos_profile.name, do_not_save=1)
	pos_si1.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 100})
	pos_si1.save()
	pos_si1.submit()

	pos_si2 = create_sales_invoice(qty=2, is_created_using_pos=1, pos_profile=pos_profile.name, do_not_save=1)
	pos_si2.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 200})
	pos_si2.save()
	pos_si2.submit()

	return pos_si1, pos_si2


def create_multiple_pos_invoices(pos_profile):
	pos_inv1 = create_pos_invoice(pos_profile=pos_profile.name, rate=100, do_not_save=1)
	pos_inv1.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 100})
	pos_inv1.save()
	pos_inv1.submit()

	pos_inv2 = create_pos_invoice(pos_profile=pos_profile.name, qty=2, do_not_save=1)
	pos_inv2.append("payments", {"mode_of_payment": "Cash", "account": "Cash - _TC", "amount": 200})
	pos_inv2.save()
	pos_inv2.submit()

	return pos_inv1, pos_inv2
