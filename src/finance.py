import mintapi
import pandas
import dateutil.relativedelta
import datetime
import pickle
import csv
import argparse
import urwid

palette = [
    ('normal', 'white', 'dark gray', '', 'white', 'g19'),
    ('infocus', 'white', 'dark gray', '', 'white', 'g19'),
    ('checked', 'light blue', 'dark gray', '', 'light blue', 'g19'),
    ('bg', 'black', 'dark gray', '', 'black', 'g19'),]

class CascadingBoxes(urwid.WidgetPlaceholder):
    max_box_levels = 4

    def __init__(self, box):
        super(CascadingBoxes, self).__init__(urwid.SolidFill(u'\N{MEDIUM SHADE}'))
        self.box_level = 0
        self.open_box(box)

    def open_box(self, box):
        self.original_widget = urwid.Overlay(urwid.LineBox(box),
            self.original_widget,
            align='center', width=('relative', 80),
            valign='middle', height=('relative', 80),
            min_width=24, min_height=8,
            left=self.box_level * 3,
            right=(self.max_box_levels - self.box_level - 1) * 3,
            top=self.box_level * 2,
            bottom=(self.max_box_levels - self.box_level - 1) * 2)
        self.box_level += 1

    def keypress(self, size, key):
        if key == 'esc' and self.box_level > 1:
            self.original_widget = self.original_widget[0]
            self.box_level -= 1
        else:
            return super(CascadingBoxes, self).keypress(size, key)

def menu_button(caption, callback):
    button = urwid.Button(caption)
    urwid.connect_signal(button, 'click', callback)
    return urwid.AttrMap(button, None, focus_map='reversed')

def sub_menu(caption, choices):
    contents = menu(caption, choices)
    def open_menu(button):
        return top.open_box(contents)
    return menu_button([caption, u'...'], open_menu)

def menu(title, choices):
    body = [urwid.Text(title), urwid.Divider()]
    body.extend(choices)
    return urwid.ListBox(urwid.SimpleFocusListWalker(body))

class Transaction:
    def __init__(self, row, tag = None, pretagged = False):
        self.date = row.date
        self.desc = row.description
        self.amount = row.amount
        self.type = row.transaction_type
        self.account_name = row.account_name
        self.tag = tag
        self.pretagged = pretagged

    def __repr__(self):
        return '{}, {:30}, {:>10.2f}, {:8}, {}'.format(self.date.date(),
            self.desc,
            # self.amount if self.type == 'debit' else '-'+str(self.amount),
            self.amount,
            self.tag, self.pretagged)


# Get new transactions from Mint as a pandas dataframe.
# Put all transactions in a pickle. Accessing Mint is
# slow, so we reuse the pickle during development.
# The file no_checkin.txt must have the following:
# Line 1: Mint user id
# Line 2: Mint password
def update_pickle_from_mint(pickle_name):
    with open('no_checkin.txt') as f:
        user = f.readline().strip()
        psw = f.readline().strip()
    mint = mintapi.Mint(user, psw)
    df = mint.get_transactions()
    df.to_pickle(pickle_name)

# Format a transaction in a consistent manner.
def format_transaction(row):
    return '{}, {:30}, {:>10.2f}, {:8}, {}'.format(row.date.date(),
        row.description, row.amount, row.tag, row.pretagged)

# Read pretagged transactions from the tags file.
def get_pretagged_sets():
    joint_set = set()
    personal_set = set()
    with open('tags.csv') as tagsfile:
        tags = csv.reader(tagsfile)
        for row in tags:
            if row[0] == "joint":
                joint_set.add(row[1].strip())
            if row[0] == "personal":
                personal_set.add(row[1].strip())
    return joint_set, personal_set

# Takes a pandas dataframe and sorts the transactions
# into 3 new dataframes: joint, personal and unknown
def df_to_transaction(df):
    joint = []
    personal = []
    unknown = []

    for index, row in df.iterrows():
        desc = row['description']
        # Check if an item matching this description is known to be
        # joint reimbursable or a personal expense.
        if desc in joint_set:
            joint.append(Transaction(row, 'joint', True))
        elif desc in personal_set:
            personal.append(Transaction(row, 'personal', True))
        else:
            unknown.append(Transaction(row, 'unknown', False))
    return joint, personal, unknown


# Convert a dataframe into a list of checkboxes.  The userdata
# for each checkbox is the corresponding dataframe row
def get_checkbox_list(trans_list):
    cb_list = []
    for t in trans_list:
        cb = urwid.CheckBox(str(t))
        cb_list.append(cb)
    return cb_list

def exit_urwid(button):
    raise urwid.ExitMainLoop()

parser = argparse.ArgumentParser(description='Process monthly finances.')
parser.add_argument('--new', dest='get_new', action='store_true',
                       help='Download new transactions from Mint.com')

parser.add_argument('--current_month', dest='current_month', action='store_true',
                       help='Process current month instead of previous month.')

args = parser.parse_args()


# Unless the user wants to process the current month,
# # then process last month.  We only process one month.
processing_date = datetime.datetime.now()
if not args.current_month:
    processing_date = processing_date + dateutil.relativedelta.relativedelta(months=-1)

year_month = processing_date.strftime('%Y-%m')

joint_set, personal_set = get_pretagged_sets()

# Get new transactions from Mint as command line indicates
if args.get_new:
    update_pickle_from_mint("transactions.pkl")

# If the user asked for new transactions, they're already in the pickle.
all_df = pandas.read_pickle("transactions.pkl")

# Index the dataframe by date.
all_df.set_index(['date'], drop=False, inplace=True)

# Get transactions from the month we're processing.
month_df = all_df.loc[year_month]

# Separate the months transactions into joint, personal, unknown
joint_trans, personal_trans, unknown_trans = df_to_transaction(month_df)

# Create the submenus for each category
joint_cb_list = get_checkbox_list(joint_trans)
personal_cb_list = get_checkbox_list(personal_trans)
unknown_cb_list = get_checkbox_list(unknown_trans)

menu_top = menu(u'Main Menu', [
    sub_menu(u'Personal', personal_cb_list),
    sub_menu(u'Joint Reimbursable', joint_cb_list),
    sub_menu(u'Unknown Transactions.  Select items that are joint reimbursable.', unknown_cb_list),
    urwid.Button(u'Done', exit_urwid)
])

top = CascadingBoxes(menu_top)
urwid.MainLoop(top, palette=palette).run()

# Copy checked unknown transactions to joint
# This list(zip()) iterates both lists at once
for t, cb in list(zip(unknown_trans, unknown_cb_list)):
    assert(str(t) == cb.label)
    if cb.get_state() == True:
        t.tag = "joint"
        joint_trans.append(t)

total = 0
for t in joint_trans:
    print(str(t))
    total = total + t.amount

print("\nTotal, {:>10.2f}".format(total))
