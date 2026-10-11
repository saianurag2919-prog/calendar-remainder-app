"""
Calendar and Reminder App
=========================
A desktop application built with Python and Tkinter (standard library only).

Features
--------
* Monthly calendar with previous / next month and a "Today" button
* Add reminders (title, date, optional time, category, notes)
* View reminders for the selected day or all reminders at once
* Delete reminders (with confirmation)
* Mark reminders as done / not done
* A pop-up alert when a reminder's time arrives while the app is open
* Reminders are saved automatically to reminders.json next to this file

Run:
    python calendar_reminder_app.py
    python calendar_reminder_app.py --demo     (loads sample reminders on first run)

Requires Python 3.8+ with Tkinter (included in the standard Python installer).
"""

import calendar
import json
import sys
import tkinter as tk
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

DATA_FILE = Path(__file__).resolve().with_name("reminders.json")
CATEGORIES = ["Work", "Study", "Personal", "Health"]
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Colour palette
BG = "#EEF3F0"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F6F9F7"
TEXT = "#14241C"
MUTED = "#5E6F66"
LINE = "#D4DDD7"
PRIMARY = "#2E7D5B"
PRIMARY_DARK = "#235F45"
SELECTED_BG = "#E0F1E8"
DANGER = "#B3261E"
FONT = "Helvetica"


def clickable(widget, command):
    """Makes a label behave like a button (works the same on Windows, macOS and Linux)."""
    widget.bind("<Button-1>", lambda e: command())
    return widget


# --------------------------------------------------------------------------
# Data layer
# --------------------------------------------------------------------------
class ReminderStore:
    """Keeps reminders in memory and saves them to a JSON file."""

    def __init__(self, path=DATA_FILE):
        self.path = Path(path)
        self.items = []
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.items = []

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.items, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save reminders:\n{exc}")

    def add(self, title, day, time="", category="Personal", notes=""):
        reminder = {
            "id": uuid.uuid4().hex,
            "title": title,
            "date": day.isoformat(),
            "time": time,
            "category": category,
            "notes": notes,
            "done": False,
        }
        self.items.append(reminder)
        self.save()
        return reminder

    def delete(self, reminder_id):
        before = len(self.items)
        self.items = [r for r in self.items if r["id"] != reminder_id]
        self.save()
        return len(self.items) < before

    def toggle_done(self, reminder_id):
        for r in self.items:
            if r["id"] == reminder_id:
                r["done"] = not r["done"]
                self.save()
                return r["done"]
        return None

    @staticmethod
    def _sort_key(r):
        return (r["date"], r["time"] or "00:00", r["title"].lower())

    def on(self, day):
        iso = day.isoformat()
        return sorted((r for r in self.items if r["date"] == iso), key=self._sort_key)

    def all_sorted(self):
        return sorted(self.items, key=self._sort_key)

    def get(self, reminder_id):
        return next((r for r in self.items if r["id"] == reminder_id), None)


# --------------------------------------------------------------------------
# User interface
# --------------------------------------------------------------------------
class CalendarApp(tk.Tk):
    def __init__(self, store=None):
        super().__init__()
        self.title("Calendar and Reminder App")
        self.geometry("1040x660")
        self.minsize(940, 620)
        self.configure(bg=BG)

        self.store = store or ReminderStore()
        self.cal = calendar.Calendar(firstweekday=6)  # weeks start on Sunday
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today
        self.notified = set()
        self._mark_past_as_notified()

        self._setup_styles()
        self._build_header()
        self._build_body()
        self._build_status_bar()

        self.refresh_all()
        self.after(20000, self.check_due)

    # ----- setup ----------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 6), font=(FONT, 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", PRIMARY_DARK)])
        style.configure("Treeview", rowheight=28, font=(FONT, 10), background=SURFACE,
                        fieldbackground=SURFACE, foreground=TEXT, bordercolor=LINE)
        style.configure("Treeview.Heading", font=(FONT, 10, "bold"), background=SURFACE_ALT, foreground=MUTED)
        style.map("Treeview", background=[("selected", SELECTED_BG)], foreground=[("selected", TEXT)])
        style.configure("TCombobox", padding=4)

    def _build_header(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(header, text="Calendar and Reminder App", bg=BG, fg=TEXT,
                 font=(FONT, 20, "bold")).pack(side="left")
        self.today_label = tk.Label(header, text="", bg=BG, fg=MUTED, font=(FONT, 11))
        self.today_label.pack(side="right")

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 6))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # ---- left: calendar ----
        left = tk.Frame(body, bg=SURFACE, highlightthickness=1, highlightbackground=LINE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        nav = tk.Frame(left, bg=SURFACE)
        nav.pack(fill="x", padx=12, pady=12)
        self.month_label = tk.Label(nav, text="", bg=SURFACE, fg=TEXT, font=(FONT, 17, "bold"))
        self.month_label.pack(side="left")
        self._nav_button(nav, "Next >", lambda: self.change_month(1)).pack(side="right", padx=(6, 0))
        self._nav_button(nav, "Today", self.go_today, primary=True).pack(side="right", padx=(6, 0))
        self._nav_button(nav, "< Prev", lambda: self.change_month(-1)).pack(side="right")

        self.grid_frame = tk.Frame(left, bg=SURFACE)
        self.grid_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # ---- right: reminders + form ----
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        day_tab = tk.Frame(self.notebook, bg=SURFACE)
        all_tab = tk.Frame(self.notebook, bg=SURFACE)
        self.notebook.add(day_tab, text="Selected day")
        self.notebook.add(all_tab, text="All reminders")

        self.day_heading = tk.Label(day_tab, text="", bg=SURFACE, fg=TEXT, font=(FONT, 12, "bold"), anchor="w")
        self.day_heading.pack(fill="x", padx=10, pady=(10, 4))
        self.day_tree = self._make_tree(day_tab, ("time", "title", "category", "status"),
                                        ("Time", "Title", "Category", "Status"), (70, 150, 80, 70))
        self.all_tree = self._make_tree(all_tab, ("date", "time", "title", "category", "status"),
                                        ("Date", "Time", "Title", "Category", "Status"), (88, 56, 120, 74, 62))

        self.details = tk.Label(right, text="Select a reminder to see its notes.", bg=BG, fg=MUTED,
                                font=(FONT, 10), anchor="w", justify="left", wraplength=360)
        self.details.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        actions = tk.Frame(right, bg=BG)
        actions.grid(row=2, column=0, sticky="ew", pady=(6, 8))
        self._action_button(actions, "Mark done / undone", self.toggle_selected).pack(side="left")
        self._action_button(actions, "Delete selected", self.delete_selected, danger=True).pack(side="left", padx=8)

        self._build_form(right).grid(row=3, column=0, sticky="ew")

        for tree in (self.day_tree, self.all_tree):
            tree.bind("<<TreeviewSelect>>", self.show_details)
            tree.bind("<Delete>", lambda e: self.delete_selected())

    def _build_form(self, parent):
        form = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=LINE)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        tk.Label(form, text="Add a reminder", bg=SURFACE, fg=TEXT, font=(FONT, 12, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 6))

        self.var_title = tk.StringVar()
        self.var_date = tk.StringVar()
        self.var_time = tk.StringVar()
        self.var_cat = tk.StringVar(value=CATEGORIES[0])
        self.var_notes = tk.StringVar()

        def label(text, r, c):
            tk.Label(form, text=text, bg=SURFACE, fg=MUTED, font=(FONT, 9, "bold")).grid(
                row=r, column=c, sticky="w", padx=(10, 4), pady=3)

        label("Title", 1, 0)
        self.title_entry = ttk.Entry(form, textvariable=self.var_title)
        self.title_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=3)
        label("Date", 2, 0)
        ttk.Entry(form, textvariable=self.var_date, width=12).grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=3)
        label("Time", 2, 2)
        ttk.Entry(form, textvariable=self.var_time, width=8).grid(row=2, column=3, sticky="ew", padx=(0, 10), pady=3)
        label("Category", 3, 0)
        ttk.Combobox(form, textvariable=self.var_cat, values=CATEGORIES, state="readonly", width=10).grid(
            row=3, column=1, sticky="ew", padx=(0, 8), pady=3)
        tk.Label(form, text="Date: YYYY-MM-DD   Time: HH:MM (24h, optional)", bg=SURFACE, fg=MUTED,
                 font=(FONT, 8)).grid(row=3, column=2, columnspan=2, sticky="w", pady=3)
        label("Notes", 4, 0)
        ttk.Entry(form, textvariable=self.var_notes).grid(row=4, column=1, columnspan=3, sticky="ew",
                                                          padx=(0, 10), pady=3)
        add_btn = self._action_button(form, "Add reminder", self.add_reminder, primary=True)
        add_btn.grid(row=5, column=0, columnspan=4, sticky="ew", padx=10, pady=(6, 10))
        self.title_entry.bind("<Return>", lambda e: self.add_reminder())
        return form

    def _build_status_bar(self):
        self.status = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 10), anchor="w").pack(
            fill="x", padx=18, pady=(0, 10))

    # ----- small widget helpers ------------------------------------------
    def _nav_button(self, parent, text, command, primary=False):
        return clickable(tk.Label(parent, text=text, bg=PRIMARY if primary else SURFACE_ALT,
                        fg="white" if primary else TEXT, font=(FONT, 10, "bold"), padx=12, pady=6,
                        highlightthickness=1, highlightbackground=PRIMARY if primary else LINE,
                        cursor="hand2"), command)

    def _action_button(self, parent, text, command, primary=False, danger=False):
        bg = PRIMARY if primary else (SURFACE if not danger else SURFACE)
        fg = "white" if primary else (DANGER if danger else TEXT)
        border = PRIMARY if primary else (DANGER if danger else LINE)
        return clickable(tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, 10, "bold"), padx=12, pady=7,
                        highlightthickness=1, highlightbackground=border, cursor="hand2"), command)

    def _make_tree(self, parent, columns, headings, widths):
        wrap = tk.Frame(parent, bg=SURFACE)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="browse")
        for col, head, width in zip(columns, headings, widths):
            tree.heading(col, text=head)
            tree.column(col, width=width, anchor="w", stretch=(col == "title"))
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.tag_configure("overdue", foreground=DANGER)
        tree.tag_configure("done", foreground=MUTED)
        return tree

    # ----- calendar -------------------------------------------------------
    def refresh_all(self):
        self.today_label.config(text=date.today().strftime("Today: %A, %d %B %Y"))
        self.refresh_calendar()
        self.refresh_lists()

    def refresh_calendar(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.month_label.config(text=f"{calendar.month_name[self.month]} {self.year}")
        for c, name in enumerate(WEEKDAYS):
            tk.Label(self.grid_frame, text=name.upper(), bg=SURFACE, fg=MUTED, font=(FONT, 9, "bold")).grid(
                row=0, column=c, sticky="nsew", pady=(0, 4))
            self.grid_frame.columnconfigure(c, weight=1, uniform="day")
        weeks = self.cal.monthdatescalendar(self.year, self.month)
        for r, week in enumerate(weeks, start=1):
            self.grid_frame.rowconfigure(r, weight=1, uniform="week")
            for c, day in enumerate(week):
                self._make_day_cell(r, c, day)

    def _make_day_cell(self, row, col, day):
        in_month = day.month == self.month
        is_today = day == date.today()
        is_selected = day == self.selected
        bg = SELECTED_BG if is_selected else (SURFACE if in_month else SURFACE_ALT)
        cell = tk.Frame(self.grid_frame, bg=bg, highlightthickness=2, cursor="hand2", width=84, height=64,
                        highlightbackground=PRIMARY if is_selected else LINE,
                        highlightcolor=PRIMARY if is_selected else LINE)
        cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
        cell.pack_propagate(False)

        number = tk.Label(cell, text=str(day.day), bg=PRIMARY if is_today else bg,
                          fg="white" if is_today else (TEXT if in_month else "#9AA8A0"),
                          font=(FONT, 11, "bold"), width=3)
        number.pack(anchor="nw", padx=4, pady=(4, 0))
        widgets = [cell, number]

        reminders = self.store.on(day)
        if reminders:
            pending = sum(1 for r in reminders if not r["done"])
            text = f"● {len(reminders)} reminder" + ("s" if len(reminders) > 1 else "")
            badge = tk.Label(cell, text=text, bg=bg, fg=PRIMARY_DARK if pending else MUTED, font=(FONT, 9, "bold"))
            badge.pack(anchor="sw", padx=6, pady=(2, 0))
            first = tk.Label(cell, text=reminders[0]["title"][:14], bg=bg, fg=MUTED, font=(FONT, 8))
            first.pack(anchor="sw", padx=6)
            widgets += [badge, first]

        for w in widgets:
            w.bind("<Button-1>", lambda e, d=day: self.select_date(d))

    def change_month(self, step):
        month = self.month - 1 + step
        self.year += month // 12
        self.month = month % 12 + 1
        self.refresh_calendar()

    def go_today(self):
        self.select_date(date.today())

    def select_date(self, day):
        self.selected = day
        self.year, self.month = day.year, day.month
        self.var_date.set(day.isoformat())
        self.notebook.select(0)
        self.refresh_all()
        self.status.set(f"Selected {day.strftime('%A, %d %B %Y')}")

    # ----- reminder lists -------------------------------------------------
    def _row_values(self, r, with_date):
        time_text = r["time"] or "All day"
        status = "Done" if r["done"] else ("Overdue" if r["date"] < date.today().isoformat() else "Pending")
        values = [time_text, r["title"], r["category"], status]
        if with_date:
            values.insert(0, datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b %Y"))
        return values, status

    def refresh_lists(self):
        self.var_date.set(self.var_date.get() or self.selected.isoformat())
        self.day_heading.config(text=self.selected.strftime("%A, %d %B %Y"))
        for tree, items, with_date in ((self.day_tree, self.store.on(self.selected), False),
                                       (self.all_tree, self.store.all_sorted(), True)):
            tree.delete(*tree.get_children())
            for r in items:
                values, status = self._row_values(r, with_date)
                tag = "done" if status == "Done" else ("overdue" if status == "Overdue" else "")
                tree.insert("", "end", iid=r["id"], values=values, tags=(tag,))
        if not self.store.on(self.selected):
            self.details.config(text="No reminders on this day. Add one using the form below.")
        else:
            self.details.config(text="Select a reminder to see its notes.")

    def _active_tree(self):
        return self.day_tree if self.notebook.index(self.notebook.select()) == 0 else self.all_tree

    def _selected_id(self):
        selection = self._active_tree().selection()
        return selection[0] if selection else None

    def show_details(self, _event=None):
        rid = self._selected_id()
        r = self.store.get(rid) if rid else None
        if r:
            notes = r["notes"] or "No notes"
            self.details.config(text=f"{r['title']}  |  {notes}")

    # ----- actions --------------------------------------------------------
    def add_reminder(self):
        title = self.var_title.get().strip()
        if not title:
            messagebox.showwarning("Missing title", "Please enter a title for the reminder.")
            self.title_entry.focus_set()
            return
        try:
            day = datetime.strptime(self.var_date.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showwarning("Invalid date", "Enter the date as YYYY-MM-DD, for example 2026-10-14.")
            return
        time_text = self.var_time.get().strip()
        if time_text:
            try:
                time_text = datetime.strptime(time_text, "%H:%M").strftime("%H:%M")
            except ValueError:
                messagebox.showwarning("Invalid time", "Enter the time as HH:MM in 24-hour format, for example 17:30.")
                return
        reminder = self.store.add(title, day, time_text, self.var_cat.get(), self.var_notes.get().strip())
        if self._already_passed(reminder):
            self.notified.add(reminder["id"])
        self.var_title.set("")
        self.var_time.set("")
        self.var_notes.set("")
        self.select_date(day)
        self.status.set(f"Reminder added for {day.strftime('%d %B %Y')}")

    def delete_selected(self):
        rid = self._selected_id()
        if not rid:
            messagebox.showinfo("Delete reminder", "Select a reminder from the list first.")
            return
        r = self.store.get(rid)
        if messagebox.askyesno("Delete reminder", f"Delete \"{r['title']}\"?"):
            self.store.delete(rid)
            self.refresh_all()
            self.status.set("Reminder deleted")

    def toggle_selected(self):
        rid = self._selected_id()
        if not rid:
            messagebox.showinfo("Mark reminder", "Select a reminder from the list first.")
            return
        done = self.store.toggle_done(rid)
        self.refresh_all()
        self.status.set("Marked as done" if done else "Marked as not done")

    # ----- alerts ---------------------------------------------------------
    @staticmethod
    def _already_passed(r):
        if r["date"] < date.today().isoformat():
            return True
        return r["date"] == date.today().isoformat() and bool(r["time"]) and r["time"] <= datetime.now().strftime("%H:%M")

    def _mark_past_as_notified(self):
        for r in self.store.items:
            if self._already_passed(r):
                self.notified.add(r["id"])

    def check_due(self):
        now = datetime.now()
        for r in list(self.store.items):
            if r["done"] or not r["time"] or r["id"] in self.notified:
                continue
            if r["date"] == now.date().isoformat() and r["time"] <= now.strftime("%H:%M"):
                self.notified.add(r["id"])
                messagebox.showinfo("Reminder", f"{r['title']}\n\n{r['time']}  |  {r['category']}"
                                    + (f"\n{r['notes']}" if r["notes"] else ""))
        self.after(20000, self.check_due)


def load_demo(store):
    """Adds sample reminders when the store is empty (python app.py --demo)."""
    if store.items:
        return
    today = date.today()
    store.add("Team stand-up call", today, "10:00", "Work", "Share progress on the project")
    store.add("Gym session", today, "18:30", "Health")
    store.add("Submit assignment", today + timedelta(days=2), "17:00", "Study", "Upload code and video")
    store.add("Dentist appointment", today + timedelta(days=5), "11:15", "Health", "Carry old reports")
    store.add("Friend's birthday", today + timedelta(days=9), "", "Personal", "Order a gift")
    store.add("Pay electricity bill", today - timedelta(days=1), "", "Personal")


if __name__ == "__main__":
    data_store = ReminderStore()
    if "--demo" in sys.argv:
        load_demo(data_store)
    CalendarApp(data_store).mainloop()