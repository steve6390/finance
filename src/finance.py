import mintapi
import pandas
import dateutil.relativedelta
import datetime
import pickle
import csv
import argparse
import urwid


parser = argparse.ArgumentParser(description='Process monthly finances.')
parser.add_argument('--new', dest='get_new', action='store_true',
                       help='Download new transactions from Mint.com')

parser.add_argument('--current_month', dest='current_month', action='store_true',
                       help='Process current month instead of previous month.')

args = parser.parse_args()

processing_date = datetime.datetime.now()
# By default, narrow the search to last month.
if not args.current_month:
    processing_date = processing_date + dateutil.relativedelta.relativedelta(months=-1)

month = processing_date.strftime('%B')
year = processing_date.strftime('%Y')
year_month = processing_date.strftime('%Y-%m')

print("Calculating finances for", month, year, '(' + year_month + ')')

print("Loading transaction tag file.")
joint_set = set()
personal_set = set()
with open('tags.csv') as tagsfile:
    tags = csv.reader(tagsfile)
    for row in tags:
        if row[0] == "joint":
            joint_set.add(row[1].strip())
        if row[0] == "personal":
            personal_set.add(row[1].strip())

if args.get_new:
    print("Retrieving login name a password.")
    with open('no_checkin.txt') as f:
        user = f.readline().strip()
        psw = f.readline().strip()
    print("Logging into Mint")
    mint = mintapi.Mint(user, psw)
    print("Retrieving transactions.")
    transactions = mint.get_transactions()
    transactions.to_pickle("transactions.pkl")

transactions = pandas.read_pickle("transactions.pkl")

print("Indexing transactions by date.")
transactions.set_index(['date'], drop=False, inplace=True)

print("Getting transactions from", year_month)
df = transactions.loc[year_month]

joint_df = pandas.DataFrame()
personal_df = pandas.DataFrame()
unknown_df = pandas.DataFrame()

print(joint_set)
for index, row in df.iterrows():
    desc = row['description']
    print("index", index, "description =", desc)
    # Check if an item matching this description is known to be
    # joint reimbursable or a personal expense.
    if desc in joint_set:
        #print(row['description'], "for", row['amount'], 'is Joint Reimbursable')
        joint_df = joint_df.append(row, ignore_index = True)
    elif desc in personal_set:
        #print(row['description'], "for", row['amount'], 'is Personal')
        personal_df = personal_df.append(row, ignore_index = True)
    else:
        unknown_df = unknown_df.append(row, ignore_index = True)


def format_transaction(row):
    return '{}, {:30}, {:>10.2f}'.format(row.date.date(), row.description, row.amount)

joint_choices = []
for index, row in joint_df.iterrows():
    joint_choices.append(format_transaction(row))

unknown_choices = []
for index, row in unknown_df.iterrows():
    unknown_choices.append(format_transaction(row))

personal_choices = []
for index, row in personal_df.iterrows():
    personal_choices.append(format_transaction(row))

# def menu(title, choices):
#     body = [urwid.Text(title), urwid.Divider()]
#     for c in choices:
#         button = urwid.Button(c)
#         urwid.connect_signal(button, 'click', item_chosen, c)
#         body.append(urwid.AttrMap(button, None, focus_map='reversed'))
#     return urwid.ListBox(urwid.SimpleFocusListWalker(body))

# def item_chosen(button, choice):
#     response = urwid.Text([u'You chose ', choice, u'\n'])
#     done = urwid.Button(u'Ok')
#     urwid.connect_signal(done, 'click', exit_program)
#     main.original_widget = urwid.Filler(urwid.Pile([response,
#         urwid.AttrMap(done, None, focus_map='reversed')]))

# def exit_program(button):
#     raise urwid.ExitMainLoop()

# main = urwid.Padding(menu(u'Pythons', joint_choices), left=2, right=2)
# top = urwid.Overlay(main, urwid.SolidFill(u'\N{MEDIUM SHADE}'),
#     align='center', width=('relative', 60),
#     valign='middle', height=('relative', 60),
#     min_width=20, min_height=9)
# urwid.MainLoop(top, palette=[('reversed', 'standout', '')]).run()

# cascaded

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

def item_chosen(button):
    response = urwid.Text([u'You chose ', button.label, u'\n'])
    done = menu_button(u'Ok', exit_program)
    top.open_box(urwid.Filler(urwid.Pile([response, done])))

def item_state_change(checkbox, new_state):
    label = checkbox.get_label()
    # if new_state:
    #     checkbox.set_label([('bold', label)])
    # else:
    #     checkbox.set_label([('default', label)])


def exit_program(button):
    raise urwid.ExitMainLoop()

# Create the submenu for personal expense items.
personal_submenu = []
for c in personal_choices:
    cb = urwid.CheckBox(c,on_state_change=item_state_change)
    personal_submenu.append(cb)

# Create the submenu for unknown expense items.
unknown_submenu = []
for c in unknown_choices:
    cb = urwid.CheckBox(c,on_state_change=item_state_change)
    map = urwid.AttrMap(cb, None, focus_map='infocus')
    unknown_submenu.append(map)

menu_top = menu(u'Main Menu', [
    sub_menu(u'Personal', personal_submenu),
    sub_menu(u'Joint Reimbursable', [
        sub_menu(u'Accessories', [
            menu_button(u'Text Editor', item_chosen),
            menu_button(u'Terminal', item_chosen),
        ]),
    ]),
    sub_menu(u'Unknown Transactions.  Select items that are joint reimbursable.', unknown_submenu)
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
    ('infocus', 'light blue', 'dark gray', '', 'light blue', 'g19'),
    ('bg', 'black', 'dark gray', '', 'black', 'g19'),]

top = CascadingBoxes(menu_top)
urwid.MainLoop(top, palette=palette).run()