import mintapi
import pandas
import dateutil.relativedelta
import datetime
import pickle
import csv
import argparse
import urwid


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

# Get new transactions from Mint and put them in a pickle.
def get_new_transactions(pickle_name):
    with open('no_checkin.txt') as f:
        user = f.readline().strip()
        psw = f.readline().strip()
    mint = mintapi.Mint(user, psw)
    transactions = mint.get_transactions()
    transactions.to_pickle(pickle_name)

# Format a transaction in a consistent manner.
def format_transaction(row):
    return '{}, {:30}, {:>10.2f}'.format(row.date.date(), row.description, row.amount)

def get_well_known_transactions():
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
def get_data_frames(df):
    joint_df = pandas.DataFrame()
    personal_df = pandas.DataFrame()
    unknown_df = pandas.DataFrame()

    for index, row in df.iterrows():
        desc = row['description']
        print("index", index, "description =", desc)
        # Check if an item matching this description is known to be
        # joint reimbursable or a personal expense.
        if desc in joint_set:
            joint_df = joint_df.append(row, ignore_index = True)
        elif desc in personal_set:
            personal_df = personal_df.append(row, ignore_index = True)
        else:
            unknown_df = unknown_df.append(row, ignore_index = True)
    return joint_df, personal_df, unknown_df

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

month = processing_date.strftime('%B')
year = processing_date.strftime('%Y')
year_month = processing_date.strftime('%Y-%m')

joint_set, personal_set = get_well_known_transactions()

# Get new transactions from Mint as command line indicates
if args.get_new:
    get_new_transactions("transactions.pkl")

# Possible new transactions are already in the pickle
transactions = pandas.read_pickle("transactions.pkl")

# Index transactions by date.
transactions.set_index(['date'], drop=False, inplace=True)

# Get transactions from the months we're processing.
df = transactions.loc[year_month]

# Get transactions sorted into joint, personal, unknown
joint_df, personal_df, unknown_df = get_data_frames(df)

for index, row in df.iterrows():
    desc = row['description']
    print("index", index, "description =", desc)
    # Check if an item matching this description is known to be
    # joint reimbursable or a personal expense.
    if desc in joint_set:
        joint_df = joint_df.append(row, ignore_index = True)
    elif desc in personal_set:
        personal_df = personal_df.append(row, ignore_index = True)
    else:
        unknown_df = unknown_df.append(row, ignore_index = True)

joint_choices = []
for index, row in joint_df.iterrows():
    joint_choices.append(format_transaction(row))

unknown_choices = []
for index, row in unknown_df.iterrows():
    unknown_choices.append(format_transaction(row))

personal_choices = []
for index, row in personal_df.iterrows():
    personal_choices.append(format_transaction(row))

def item_chosen(button):
    response = urwid.Text([u'You chose ', button.label, u'\n'])
    done = menu_button(u'Ok', exit_program)
    top.open_box(urwid.Filler(urwid.Pile([response, done])))

def unknown_state_change(cb, new_state):
    text = cb.get_label()
    if new_state:
        cb.set_label([('checked', text)])
    else:
        cb.set_label([('normal', text)])


def exit_program(button):
    raise urwid.ExitMainLoop()

def create_csv(dummy):
    for index, row in joint_df.iterrows():
        print("{}", format_transaction(row))

# Create the submenu for personal expense items.
personal_submenu = []
for c in personal_choices:
    cb = urwid.CheckBox(c)
    personal_submenu.append(cb)

# Create the submenu for personal expense items.
joint_submenu = []
for c in joint_choices:
    cb = urwid.CheckBox(c)
    joint_submenu.append(cb)

# Create the submenu for unknown expense items.
unknown_submenu = []
for c in unknown_choices:
    cb = urwid.CheckBox(c,on_state_change=unknown_state_change)
    map = urwid.AttrMap(cb, 'default', focus_map='infocus')
    unknown_submenu.append(map)

menu_top = menu(u'Main Menu', [
    sub_menu(u'Personal', personal_submenu),
    sub_menu(u'Joint Reimbursable', joint_submenu),
    sub_menu(u'Unknown Transactions.  Select items that are joint reimbursable.', unknown_submenu),
    urwid.Button(u'Create .csv.', create_csv)
])

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

palette = [
    ('normal', 'white', 'dark gray', '', 'white', 'g19'),
    ('infocus', 'white', 'dark gray', '', 'white', 'g19'),
    ('checked', 'light blue', 'dark gray', '', 'light blue', 'g19'),
    ('bg', 'black', 'dark gray', '', 'black', 'g19'),]

top = CascadingBoxes(menu_top)
urwid.MainLoop(top, palette=palette).run()