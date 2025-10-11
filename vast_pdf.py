#!/usr/bin/env python3

# vast_pdf: Library of functions to create PDF reports of various type.
# Currently only makes invoices.
import argparse
import datetime
import math
import time
import random
from decimal import Decimal

import typing
import PIL.Image

try:
    from borb.pdf.canvas.color.color import HexColor, X11Color
    from borb.pdf.canvas.layout.image.image import Image
    from borb.pdf.canvas.layout.layout_element import Alignment
    from borb.pdf.canvas.layout.page_layout.multi_column_layout import SingleColumnLayout
    from borb.pdf.canvas.layout.page_layout.page_layout import PageLayout
    from borb.pdf.canvas.layout.table.fixed_column_width_table import FixedColumnWidthTable
    from borb.pdf.canvas.layout.table.flexible_column_width_table import FlexibleColumnWidthTable
    from borb.pdf.canvas.layout.table.table import Table, TableCell
    from borb.pdf.canvas.layout.text.paragraph import Paragraph
    from borb.pdf.document.document import Document
    from borb.pdf.page.page import Page
    from borb.pdf.pdf import PDF
except ImportError:
    print("""\nERROR: This library depends on a Python package called Borb to make the PDF files. To install this 
    package do 'pip3 install borb'.\n""")

## Globals
num_rows_first_page: int = 18
num_rows_subsequents_pages: int = 30
invoice_total: float = 0
now = datetime.date.today()
invoice_number: int = now.year * 12 + now.month - 1
page_count: int = 0
no_table_borders = False
no_table_borders = True


# def Paragraph_wr(text: str, *args, **kwargs):
#     """This is just a wrapper for the Paragraph function that prevents the text from being the null string "".
#
#      :param str text: The text to be checked for null.
#      """
#     if text == "":
#         text = " "
#     return Paragraph(text, *args, **kwargs)


def build_2nd_block_table() -> FixedColumnWidthTable:
    """
    This function creates a Table containing invoice information.
    This information spans the page and is the second large block of
    text on the page.

    :rtype FixedColumnWidthTable: a Table containing information such as the company address, payment terms, date, and sum of charge_fields/payments.
    """
    global invoice_total, now

    table = FixedColumnWidthTable(number_of_rows=3, number_of_columns=3)

    table.add(Paragraph("Vast.ai Inc."))
    table.add(Paragraph("Date", font="Helvetica-Bold", horizontal_alignment=Alignment.RIGHT))
    table.add(Paragraph("%d/%d/%d" % (now.day, now.month, now.year), horizontal_alignment=Alignment.RIGHT))

    table.add(Paragraph("100 Van Ness Ave."))
    table.add(Paragraph("Payment Terms:", font="Helvetica-Bold", horizontal_alignment=Alignment.RIGHT))
    table.add(Paragraph("Charged - Do Not Pay", horizontal_alignment=Alignment.RIGHT))

    table.add(Paragraph("San Francisco CA 94102"))

    table.add(
        Paragraph("Total", font="Helvetica-Bold", font_size=Decimal(20), horizontal_alignment=Alignment.RIGHT))
    table.add(Paragraph(format_float_val_as_currency(invoice_total), font="Helvetica-Bold", font_size=Decimal(20),
                        horizontal_alignment=Alignment.RIGHT))

    table.set_padding_on_all_cells(Decimal(2), Decimal(2), Decimal(2), Decimal(2))
    if no_table_borders: table.no_borders()
    return table


def blank_row(table: Table, col_num: int, row_num: int = 1) -> None:
    """Just a set of blank rows to act as filler.

    :param table: The table we want to modify
    :param int col_num: How many columns in the table?
    :param int row_num: How many blank rows do we need?
    :rtype None:
    """
    for j in range(row_num):
        for i in range(col_num):
            table.add(Paragraph(" "))
    return None


def field_and_filler(user_blob: typing.Dict, table: Table, fieldname: str) -> None:
    """Adds a field to the table along with a filler cell to span the table.

    :param str fieldname:
    :param Dict user_blob: A dict containing the user's info.
    :param Table table: The table to be modified.
    :rtype None:
    """
    table.add(Paragraph(str(user_blob[fieldname])))
    # table.add(Paragraph(" "))
    return None


def build_billto_table(user_blob: dict) -> FixedColumnWidthTable:
    """
    This function builds a Table containing billing and shipping information
    It spans the page using a single wide column.

    :param Dict user_blob: A dict containing the user's info.
    :rtype Table:    a Table containing shipping and billing information
    """
    table = FixedColumnWidthTable(number_of_rows=5, number_of_columns=1)
    table.add(Paragraph("BILL TO", font="Helvetica-Bold"))
    # table.add(Paragraph(" ", font="Helvetica-Bold"))

    field_ids = ["fullname", "billaddress_line1", "billaddress_line2"]
    list(map(lambda fieldname: field_and_filler(user_blob, table, fieldname), field_ids))

    table.add(Paragraph("%s, %s" % (user_blob["billaddress_city"], user_blob["billaddress_zip"])))  # BILLING
    # table.add(Paragraph(" "))  # SHIPPING
    # table.add(Paragraph(" "))  # BILLING
    # table.add(Paragraph(" "))  # SHIPPING
    table.set_padding_on_all_cells(Decimal(2), Decimal(2), Decimal(2), Decimal(2))
    if no_table_borders: table.no_borders()
    return table


class Charge:
    """
    This class represents a charge line.
    """

    def __init__(self, name: str, quantity: float, rate: float,
                 amount: float, type: str, last4: str, timestamp: float):
        """
        Charge constructor. Basically just turns a row into a Charge object.

        :param str name:
        :param float quantity:
        :param float rate:
        :param float amount:
        :param str type:
        :param str last4:
        :param float timestamp:
        """
        self.name: str = name
        # assert quantity >= 0
        self.quantity: float = quantity
        # assert rate >= 0
        self.rate: float = rate
        # assert amount >= 0
        self.amount: float = amount
        self.type = type
        self.last4 = last4
        self.timestamp = timestamp


def format_float_val_as_currency(v) -> str:
    """
    Given a float value, format it as currency. Note that the sign is backwards due to the fact that the charge_fields in
    the data that comes back are positive numbers but are written as negative on the invoice. There's also the fact
    that in our format string, if the value is actually negative it will print as "$-x.xx" instead of the correct
    "-$x.xx". I don't know if this can be fixed with format strings so we rely on this hack.

    :param float v:
    :rtype str:
    """
    if v > 0:
        return "     -${:10.2f}".format(v)
    else:
        return "     ${:10.2f}".format(-v)


def build_charge_table(charges: typing.List[Charge], page_number: int)\
        -> FlexibleColumnWidthTable:
    """
    This function builds a Table containing itemized billing information

    :param  typing.List[Charge] charges: the rows on the invoice
    :param  int page_number: Current page number.
    :rtype  FlexibleColumnWidthTable: Borb Table containing the information.
    """
    global invoice_total
    num_rows = len(charges)
    table = FlexibleColumnWidthTable(number_of_rows=(num_rows + 3), number_of_columns=4)
    table_header_padding_top = 4
    table_header_padding_bottom = 5
    table_header_padding_left = 3
    table_header_padding_right = 3
    item_font_size = Decimal(11)

    for h in ["Item", "Quantity", "Rate", "Amount"]:
        table.add(
            TableCell(
                Paragraph(h, font_color=X11Color("White"),
                          padding_top=Decimal(table_header_padding_top),
                          padding_bottom=Decimal(table_header_padding_bottom),
                          padding_left=Decimal(table_header_padding_left),
                          padding_right=Decimal(table_header_padding_right),
                          vertical_alignment=Alignment.TOP),
                background_color=HexColor("0b3954")
            )
        )

    odd_color = HexColor("BBBBBB")
    even_color = HexColor("FFFFFF")
    for row_number, item in enumerate(charges):
        c = even_color if row_number % 2 == 0 else odd_color
        table.add(TableCell(Paragraph(item.name, font="Helvetica-Bold",
                                      font_size=item_font_size), background_color=c))
        if item.type == "payment":
            table.add(TableCell(Paragraph(" ", horizontal_alignment=Alignment.RIGHT,
                                          font_size=item_font_size),
                                background_color=c))
            table.add(TableCell(Paragraph(" ", horizontal_alignment=Alignment.RIGHT,
                                          font_size=item_font_size), background_color=c))
        else:
            table.add(TableCell(Paragraph("     {:10.2f}".format(item.quantity),
                                          horizontal_alignment=Alignment.RIGHT,
                                          font_size=item_font_size),
                                background_color=c))
            table.add(TableCell(Paragraph(format_float_val_as_currency(item.rate),
                                          horizontal_alignment=Alignment.RIGHT,
                                          font_size=item_font_size),
                                background_color=c))
        table.add(TableCell(
            Paragraph(format_float_val_as_currency(item.amount),
                      horizontal_alignment=Alignment.RIGHT,
                      font_size=item_font_size), background_color=c))

    if page_number == page_count:
        table.add(TableCell(
            Paragraph(" ", font="Helvetica-Bold", horizontal_alignment=Alignment.RIGHT)))
        table.add(TableCell(Paragraph(" ", horizontal_alignment=Alignment.RIGHT)))

        table.add(TableCell(
            Paragraph("Total", font="Helvetica-Bold", horizontal_alignment=Alignment.RIGHT)))
        table.add(TableCell(
            Paragraph(format_float_val_as_currency(invoice_total), horizontal_alignment=Alignment.RIGHT)))
    else:
        blank_row(table, 4, 2)
    table.set_padding_on_all_cells(Decimal(2), Decimal(5), Decimal(2), Decimal(5))
    if no_table_borders: table.no_borders()
    return table


def product_row(charge_fields) -> Charge:
    """Makes a single row with charge information in it.

    :param charge_fields:
    :rtype Charge:
    """

    type = charge_fields["type"]
    is_credit = charge_fields["is_credit"] if "is_credit" in charge_fields else False
    timestamp = charge_fields["timestamp"]
    last4 = charge_fields["last4"] if "last4" in charge_fields and charge_fields["last4"] is not None else " "

    def credit_or_auto_billing():
        if is_credit:
            return "Add Credit: *" + last4 + " : " + datetime.datetime.fromtimestamp(timestamp).strftime(
                '%Y-%m-%d %H:%M')
        return "Auto-Billing: *" + last4 + " : " + datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')

    description = charge_fields[
        "description"] if "description" in charge_fields else credit_or_auto_billing()  # "Add Credit: *" + last4 + ":" + str(timestamp)
    amount = float(charge_fields["amount"]) if "amount" in charge_fields else 0.0
    quantity = float(charge_fields["quantity"]) if "quantity" in charge_fields else 1.0
    rate = float(charge_fields["rate"]) if "rate" in charge_fields else amount
    return Charge(description, quantity, rate, amount, type, last4, timestamp)


def product_rows(rows_invoice) -> typing.List[Charge]:
    """
    Maps a list of invoice dicts to a list of Charge objects using product_row function.

    :param  rows_invoice:
    :rtype typing.List[Charge]:
    """
    if rows_invoice is None:
        rows_invoice = []
    return list(map(lambda charges: product_row(charges), rows_invoice))


def build_invoice_charges_table(rows_invoice: typing.List[typing.Dict],
                                charges_per_page: int, page_number: int) -> FlexibleColumnWidthTable:
    """
    This function creates a page of invoice charge_fields and depletes the list of charge_fields by the number it
    prints out. Essentially a pop function that removes multiple items at once.

    :param int page_number:
    :param typing.List[typing.Dict] rows_invoice: List of rows in the invoice
    :param int charges_per_page: How many rows of charge_fields we put on this page.
    :rtype FlexibleColumnWidthTable:
    """
    rows_invoice_chunk = rows_invoice[0:charges_per_page]
    # sums = {"amount": compute_column_sum(rows_invoice, "amount", True)}
    del rows_invoice[0:charges_per_page]
    return build_charge_table(product_rows(rows_invoice_chunk), page_number)


def compute_column_sum(rows_invoice: typing.List[typing.Dict],
                       column_name: str,
                       values_are_negative: bool = False) -> float:
    """Sum over one of the columns in the invoice.

    :param  typing.List[typing.Dict] rows_invoice: List of rows in the invoice
    :param  str column_name: Name of column to sum over.
    :param  bool values_are_negative: are we summing values that are actually negative?
    :rtype: float
    """
    s: float = 0
    for row in rows_invoice:
        v: float = math.floor(float(row[column_name]) * 100) / 100
        # v = round(float(row[column_name]) * 100) / 100
        if values_are_negative:
            s = s - v
        else:
            s = s + v
    return math.floor(s * 100) / 100
    # return round(s * 100) / 100


def generate_invoice_page(user_blob: typing.Dict,
                          rows_invoice: typing.List[typing.Dict],
                          page_number: int, date_header_text: str = "") -> Page:
    """Makes a single page of the invoice.

    :param str date_header_text:
    :param Dict user_blob: Dict of info about the user
    :param typing.List[typing.Dict] rows_invoice: List of rows in the invoice
    :param int page_number: The page number for this page.
    :rtype Page:
    """
    global invoice_number

    if page_number == 1:
        rows_per_page = num_rows_first_page
    else:
        rows_per_page = num_rows_subsequents_pages

    page: Page = Page()

    # set PageLayout
    page_layout: PageLayout = SingleColumnLayout(page)
    table_logo_and_invoice_num = build_logo_and_invoice_num_table(page, page_number)
    page_layout.add(table_logo_and_invoice_num)
    page_layout.add(Paragraph(" "))

    if page_number == 1:
        # Invoice information table
        page_layout.add(build_2nd_block_table())
        # Empty paragraph for spacing
        page_layout.add(Paragraph(" "))
        # Billing and shipping information table
        page_layout.add(build_billto_table(user_blob))
        page_layout.add(Paragraph(date_header_text + " "))

    if len(rows_invoice) == 0:
        # If we don't handle this case the client crashes with no output.
        page_layout.add(Paragraph("NO DATA"))
    else:
        table_invoice_rows = build_invoice_charges_table(rows_invoice, rows_per_page, page_number)
        page_layout.add(table_invoice_rows)
    return page
def build_logo_and_invoice_num_table(page: Page, page_number: int) -> FixedColumnWidthTable:
    """
    At the top of every page is a table with our logo, the invoice number, and little text reading "page X of Y".
    This function creates that table and returns it.

    :param page_number:
    :rtype FixedColumnWidthTable:
    """
    if page_number == 1:
        invoice_number_font_size = Decimal(20)
        invoice_word_font_size = Decimal(40)
        logo_img_filename: str = r'./vast.ai-logo.png'
        logo_img_width: int = 48
        logo_img_height: int = 70
    else:
        invoice_number_font_size = Decimal(14)
        invoice_word_font_size = Decimal(20)
        logo_img_filename: str = r'./vast.ai-logo-50pct.png'
        logo_img_width: int = 36
        logo_img_height: int = 53

    w = page.get_page_info().get_width()
    content_w = w * Decimal("0.80")

    # allocate relative widths across 3 columns
    col_w = [
        content_w * Decimal("0.25"),  # logo
        content_w * Decimal("0.30"),  # middle
        content_w * Decimal("0.45"),  # right (big "Invoice")
    ]

    logo_img = PIL.Image.open(logo_img_filename)

    # 2 rows, 3 columns
    table = FixedColumnWidthTable(
        number_of_rows=2,
        number_of_columns=3,
        column_widths=col_w,
    )

    # Logo spans both rows in the first column
    table.add(
        TableCell(
            Image(
                logo_img,
                width=Decimal(logo_img_width),
                height=Decimal(logo_img_height),
                horizontal_alignment=Alignment.LEFT,
            ),
            row_span=2,
        )
    )

    # Row 1: middle cell = page text; right cell = big "Invoice"
    table.add(
        Paragraph(
            f"Page {page_number} of {page_count}",
            font="Helvetica",
            horizontal_alignment=Alignment.RIGHT,
        )
    )
    table.add(
        Paragraph(
            "Invoice",
            font="Helvetica",
            font_size=invoice_word_font_size,
            horizontal_alignment=Alignment.RIGHT,
        )
    )

    # Row 2: middle cell blank; right cell = invoice number
    table.add(Paragraph(" "))
    table.add(
        Paragraph(
            f"# {invoice_number}",
            font="Helvetica",
            font_size=invoice_number_font_size,
            horizontal_alignment=Alignment.RIGHT,
        )
    )

    table.set_padding_on_all_cells(Decimal(1), Decimal(1), Decimal(1), Decimal(1))
    if no_table_borders:
        table.no_borders()
    return table


def compute_pages_needed(rows_invoice: typing.List[typing.Dict]) -> int:
    """Function to work out how many pages we need so that the page_count can be filled in at the top of every page.

    :param typing.List[typing.Dict] rows_invoice: The list of dicts we use elsewhere.
    :rtype int:
    """
    num_rows_invoice = len(rows_invoice)
    num_rows_invoice = num_rows_invoice - num_rows_first_page
    page_count: int = math.ceil(num_rows_invoice / num_rows_subsequents_pages) + 1
    return page_count





def generate_invoice(user_blob: typing.Dict,
                     rows_invoice: typing.List[typing.Dict], filter_data: typing.Dict) -> None:
    """
    This is the main function in this library. It calls everything else and makes the invoice page by page. The
    resulting invoice is written as a single PDF file.

    :param filter_data: Parameters for client side filter.
    :param user_blob: info about the user
    :param typing.List[typing.Dict] rows_invoice: The list of dicts we use elsewhere.
    :rtype None:
    """

    pdf: Document = Document()
    global page_count
    page_count = compute_pages_needed(rows_invoice)
    global invoice_total
    invoice_total = compute_column_sum(rows_invoice, "amount")
    page_number = 1

    if len(rows_invoice) == 0:
        page = generate_invoice_page(user_blob, rows_invoice, page_number, filter_data["header_text"])
        print("Adding Empty page ", str(page_number))
        pdf.add_page(page)
    else:
        while len(rows_invoice) > 0:
            page = generate_invoice_page(user_blob, rows_invoice, page_number, filter_data["header_text"])
            print("Adding page ", str(page_number))
            pdf.add_page(page)
            page_number += 1

    # We write out the latest PDF so that we can watch the file change with `evince` or similar viewer even though
    # parameters may differ from run to run.
    with open("latest-invoice.pdf", "wb") as debug_file_handle:
        PDF.dumps(debug_file_handle, pdf)
    debug_file_handle.close()

    with open(filter_data["pdf_filename"], "wb") as users_file_handle:
        PDF.dumps(users_file_handle, pdf)
    users_file_handle.close()
