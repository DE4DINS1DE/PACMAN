"""
Library Management System (Tkinter + SQLite + Google Books API)
"""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
import json
from io import BytesIO



DB_FILE = "library.db"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"

# ---------- database ----------
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Drop existing tables if they have wrong structure
    c.execute("DROP TABLE IF EXISTS books")
    c.execute("DROP TABLE IF EXISTS members")
    c.execute("DROP TABLE IF EXISTS transactions")

    # Recreate tables with correct structure
    c.execute("""CREATE TABLE books(
        book_id INTEGER PRIMARY KEY AUTOINCREMENT,
        isbn TEXT UNIQUE, 
        title TEXT, 
        author TEXT, 
        publisher TEXT,
        publication_year INTEGER, 
        category TEXT, 
        description TEXT,
        cover_url TEXT, 
        total_copies INTEGER, 
        available_copies INTEGER
    )""")

    c.execute("""CREATE TABLE members(
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        membership_number TEXT UNIQUE,
        first_name TEXT, 
        last_name TEXT, 
        email TEXT, 
        phone TEXT,
        address TEXT, 
        join_date TEXT, 
        status TEXT
    )""")

    c.execute("""CREATE TABLE transactions(
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, 
        book_id INTEGER,
        issue_date TEXT, 
        due_date TEXT, 
        return_date TEXT,
        fine_amount REAL, 
        status TEXT
    )""")

    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# Initialize database before running the app
init_db()

# ---------- Google Books lookup ----------
def lookup_book(isbn):
    """Alternative lookup without requests module"""
    try:
        url = f"{GOOGLE_BOOKS_URL}?q=isbn:{isbn}"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})

        with urlopen(req) as response:
            data = json.loads(response.read().decode())

        items = data.get("items")
        if not items:
            return None

        vol = items[0]["volumeInfo"]
        return {
            "title": vol.get("title", ""),
            "author": ", ".join(vol.get("authors", [])),
            "publisher": vol.get("publisher", ""),
            "publication_year": vol.get("publishedDate", "")[:4],
            "category": ", ".join(vol.get("categories", [])),
            "description": vol.get("description", ""),
            "cover_url": vol.get("imageLinks", {}).get("thumbnail")
        }
    except URLError as e:
        print("Lookup error:", e)
        return None
    except Exception as e:
        print("Error:", e)
        return None

# ---------- main app ----------
class LibraryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Library Management System")
        self.geometry("1100x650")

        # Initialize instance attributes
        self.book_tab = None
        self.member_tab = None
        self.trans_tab = None
        self.isbn_var = None
        self.book_tree = None
        self.book_vars = {}
        self.desc_txt = None
        self.cover_label = None
        self.cover_url = None
        self.selected_book = None
        self.mem_tree = None
        self.mem_vars = {}
        self.selected_member = None
        self.tr_tree = None

        self.create_widgets()
        self.refresh_books()
        self.refresh_members()
        self.refresh_transactions()

    # ----- notebook -----
    def create_widgets(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        self.book_tab = ttk.Frame(nb)
        self.member_tab = ttk.Frame(nb)
        self.trans_tab = ttk.Frame(nb)

        nb.add(self.book_tab, text="Books")
        nb.add(self.member_tab, text="Members")
        nb.add(self.trans_tab, text="Transactions")

        self.build_books_tab()
        self.build_members_tab()
        self.build_transactions_tab()

    # ---------- BOOKS ----------
    def build_books_tab(self):
        frm = self.book_tab
        top = ttk.Frame(frm)
        top.pack(fill=tk.X, pady=5)

        ttk.Label(top, text="ISBN:").pack(side=tk.LEFT)
        self.isbn_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.isbn_var, width=20).pack(side=tk.LEFT)
        ttk.Button(top, text="Lookup", command=self.lookup_and_fill).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Add Book", command=self.add_book).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Delete Book", command=self.delete_book).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh_books).pack(side=tk.LEFT, padx=4)

        cols = ("id", "isbn", "title", "author", "year", "avail")
        self.book_tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c, h in zip(cols, ["ID", "ISBN", "Title", "Author", "Year", "Available"]):
            self.book_tree.heading(c, text=h)
            self.book_tree.column(c, width=150, anchor=tk.CENTER)
        self.book_tree.pack(fill=tk.BOTH, expand=True)
        self.book_tree.bind("<<TreeviewSelect>>", self.on_book_select)

        form = ttk.Frame(frm)
        form.pack(fill=tk.X, pady=5)
        self.book_vars = {}

        for i, (lab, w) in enumerate([("Title", 50), ("Author", 30), ("Publisher", 30),
                                    ("Year", 6), ("Category", 20), ("Total Copies", 5)]):
            ttk.Label(form, text=lab).grid(row=i//2, column=(i%2)*2, sticky=tk.W)
            v = tk.StringVar()
            self.book_vars[lab] = v
            ttk.Entry(form, textvariable=v, width=w).grid(row=i//2, column=(i%2)*2+1, sticky=tk.W)

        ttk.Label(form, text="Description").grid(row=3, column=0, sticky=tk.W)
        self.desc_txt = tk.Text(form, width=60, height=4)
        self.desc_txt.grid(row=3, column=1)

        self.cover_label = ttk.Label(form, text="No cover")
        self.cover_label.grid(row=0, column=3, rowspan=4, padx=20)

    def lookup_and_fill(self):
        isbn = self.isbn_var.get().strip()
        if not isbn:
            return

        data = lookup_book(isbn)
        if not data:
            messagebox.showinfo("Not found", "No data for that ISBN")
            return

        for k in ["Title", "Author", "Publisher", "Year", "Category"]:
            if k == "Title":
                self.book_vars[k].set(data.get("title", ""))
            elif k == "Author":
                self.book_vars[k].set(data.get("author", ""))
            elif k == "Publisher":
                self.book_vars[k].set(data.get("publisher", ""))
            elif k == "Year":
                self.book_vars[k].set(data.get("publication_year", ""))
            elif k == "Category":
                self.book_vars[k].set(data.get("category", ""))

        self.desc_txt.delete("1.0", "end")
        self.desc_txt.insert("end", data.get("description", ""))

        self.cover_label.config(text="Cover lookup disabled")

    def add_book(self):
        vals = {k: v.get().strip() for k, v in self.book_vars.items()}
        if not vals["Title"]:
            messagebox.showwarning("Validation", "Title required")
            return

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("""INSERT INTO books(isbn, title, author, publisher, publication_year, category, description, cover_url,
                        total_copies, available_copies)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                      (self.isbn_var.get() or None, vals["Title"], vals["Author"], vals["Publisher"], vals["Year"],
                       vals["Category"], self.desc_txt.get("1.0", "end").strip(), getattr(self, "cover_url", None),
                       int(vals.get("Total Copies") or 1), int(vals.get("Total Copies") or 1)))
            conn.commit()
            messagebox.showinfo("Success", "Book added")
            self.refresh_books()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Duplicate ISBN")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            conn.close()

    def refresh_books(self):
        # Clear existing items
        for item in self.book_tree.get_children():
            self.book_tree.delete(item)

        conn = get_conn()
        c = conn.cursor()
        try:
            # Verify table structure
            c.execute("PRAGMA table_info(books)")
            columns = [row[1] for row in c.fetchall()]
            print("Books table columns:", columns)

            # Fetch and display books
            c.execute("SELECT * FROM books ORDER BY book_id DESC")
            books = c.fetchall()

            for book in books:
                self.book_tree.insert("", tk.END, values=(
                    book["book_id"],
                    book["isbn"] or "",
                    book["title"],
                    book["author"],
                    book["publication_year"],
                    f"{book['available_copies']}/{book['total_copies']}"
                ))

        except Exception as e:
            print("Error refreshing books:", e)
            messagebox.showerror("Database Error", f"Error loading books: {str(e)}")
        finally:
            conn.close()

    def on_book_select(self, event):
        sel = self.book_tree.selection()
        if not sel:
            return
        self.selected_book = self.book_tree.item(sel[0])["values"][0]

    def delete_book(self):
        sel = self.book_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a book to delete")
            return

        book_id = self.book_tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("Confirm", "Delete this book? This cannot be undone."):
            return

        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM transactions WHERE book_id=? AND status='issued'", (book_id,))
            if cur.fetchone()[0] > 0:
                messagebox.showwarning("Blocked", "Cannot delete a book that is currently issued.")
            else:
                cur.execute("DELETE FROM books WHERE book_id=?", (book_id,))
                conn.commit()
                messagebox.showinfo("Deleted", "Book deleted")
                self.refresh_books()
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting book: {str(e)}")
        finally:
            conn.close()

    # ---------- MEMBERS ----------
    def build_members_tab(self):
        frm = self.member_tab
        top = ttk.Frame(frm)
        top.pack(fill=tk.X, pady=5)

        ttk.Button(top, text="Add Member", command=self.add_member).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Delete Member", command=self.delete_member).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh_members).pack(side=tk.LEFT, padx=4)

        cols = ("id", "num", "name", "email", "phone", "status")
        self.mem_tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c, h in zip(cols, ["ID", "Membership#", "Name", "Email", "Phone", "Status"]):
            self.mem_tree.heading(c, text=h)
            self.mem_tree.column(c, width=150)
        self.mem_tree.pack(fill=tk.BOTH, expand=True)
        self.mem_tree.bind("<<TreeviewSelect>>", self.on_member_select)

        form = ttk.Frame(frm)
        form.pack(fill=tk.X, pady=6)
        self.mem_vars = {}

        for i, lab in enumerate(["Membership #", "First Name", "Last Name", "Email", "Phone", "Address"]):
            ttk.Label(form, text=lab).grid(row=i, column=0, sticky=tk.W)
            v = tk.StringVar()
            self.mem_vars[lab] = v
            ttk.Entry(form, textvariable=v, width=40).grid(row=i, column=1)

    def add_member(self):
        vals = {k: v.get().strip() for k, v in self.mem_vars.items()}
        if not vals["First Name"]:
            messagebox.showwarning("Validation", "Name required")
            return

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("""INSERT INTO members(membership_number, first_name, last_name, email, phone, address, join_date, status)
                     VALUES(?,?,?,?,?,?,?,?)""",
                  (vals["Membership #"] or None, vals["First Name"], vals["Last Name"],
                   vals["Email"], vals["Phone"], vals["Address"], str(date.today()), "active"))
            conn.commit()
            messagebox.showinfo("Success", "Member added")
            self.refresh_members()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            conn.close()

    def refresh_members(self):
        for item in self.mem_tree.get_children():
            self.mem_tree.delete(item)

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM members ORDER BY member_id DESC")
            members = c.fetchall()

            for member in members:
                name = f"{member['first_name']} {member['last_name']}"
                self.mem_tree.insert("", tk.END, values=(
                    member['member_id'],
                    member['membership_number'] or "",
                    name,
                    member['email'],
                    member['phone'],
                    member['status']
                ))
        except Exception as e:
            print("Error refreshing members:", e)
        finally:
            conn.close()

    def on_member_select(self, event):
        sel = self.mem_tree.selection()
        if not sel:
            return
        self.selected_member = self.mem_tree.item(sel[0])["values"][0]

    def delete_member(self):
        sel = self.mem_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a member to delete")
            return

        member_id = self.mem_tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("Confirm", "Delete this member?"):
            return

        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) AS cnt FROM transactions WHERE member_id=? AND status='issued'", (member_id,))
            if cur.fetchone()[0] > 0:
                messagebox.showwarning("Blocked", "Cannot delete a member who still has issued books.")
            else:
                cur.execute("DELETE FROM members WHERE member_id=?", (member_id,))
                conn.commit()
                messagebox.showinfo("Deleted", "Member deleted")
                self.refresh_members()
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting member: {str(e)}")
        finally:
            conn.close()

    # ---------- TRANSACTIONS ----------
    def build_transactions_tab(self):
        frm = self.trans_tab
        top = ttk.Frame(frm)
        top.pack(fill=tk.X, pady=5)

        ttk.Button(top, text="Issue Book", command=self.issue_book).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Return Book", command=self.return_book).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Delete Transaction", command=self.delete_transaction).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh_transactions).pack(side=tk.LEFT, padx=4)

        cols = ("id", "member", "book", "issue", "due", "return", "status")
        self.tr_tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c, h in zip(cols, ["ID", "Member", "Book", "Issue", "Due", "Return", "Status"]):
            self.tr_tree.heading(c, text=h)
            self.tr_tree.column(c, width=120)
        self.tr_tree.pack(fill=tk.BOTH, expand=True)

    def issue_book(self):
        if not hasattr(self, "selected_book") or not hasattr(self, "selected_member"):
            messagebox.showinfo("Select", "Select a member and a book")
            return

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT available_copies FROM books WHERE book_id=?", (self.selected_book,))
            row = c.fetchone()
            if not row or row["available_copies"] <= 0:
                messagebox.showinfo("Unavailable", "No copies left")
                return

            issue = str(date.today())
            due = str(date.today() + timedelta(days=14))

            c.execute("""INSERT INTO transactions(member_id, book_id, issue_date, due_date, status)
                         VALUES(?,?,?,?,?)""",
                      (self.selected_member, self.selected_book, issue, due, "issued"))
            c.execute("UPDATE books SET available_copies=available_copies-1 WHERE book_id=?", (self.selected_book,))
            conn.commit()

            messagebox.showinfo("Issued", f"Book issued until {due}")
            self.refresh_books()
            self.refresh_transactions()
        except Exception as e:
            messagebox.showerror("Error", f"Error issuing book: {str(e)}")
        finally:
            conn.close()

    def return_book(self):
        sel = self.tr_tree.selection()
        if not sel:
            return

        tid = self.tr_tree.item(sel[0])["values"][0]
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM transactions WHERE transaction_id=?", (tid,))
            t = c.fetchone()

            if not t or t["status"] != "issued":
                messagebox.showinfo("Info", "Already returned")
                return

            c.execute("UPDATE transactions SET status='returned', return_date=? WHERE transaction_id=?",
                      (str(date.today()), tid))
            c.execute("UPDATE books SET available_copies=available_copies+1 WHERE book_id=?", (t["book_id"],))
            conn.commit()

            messagebox.showinfo("Returned", "Book returned")
            self.refresh_books()
            self.refresh_transactions()
        except Exception as e:
            messagebox.showerror("Error", f"Error returning book: {str(e)}")
        finally:
            conn.close()

    def delete_transaction(self):
        sel = self.tr_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a transaction to delete")
            return

        tid = self.tr_tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("Confirm", "Delete this transaction?"):
            return

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("SELECT * FROM transactions WHERE transaction_id=?", (tid,))
            t = c.fetchone()

            if t and t["status"] == "issued":
                # restore availability
                c.execute("UPDATE books SET available_copies=available_copies+1 WHERE book_id=?", (t["book_id"],))

            c.execute("DELETE FROM transactions WHERE transaction_id=?", (tid,))
            conn.commit()

            messagebox.showinfo("Deleted", "Transaction deleted")
            self.refresh_books()
            self.refresh_transactions()
        except Exception as e:
            messagebox.showerror("Error", f"Error deleting transaction: {str(e)}")
        finally:
            conn.close()

    def refresh_transactions(self):
        for item in self.tr_tree.get_children():
            self.tr_tree.delete(item)

        conn = get_conn()
        c = conn.cursor()
        try:
            q = """SELECT t.transaction_id, m.first_name||' '||m.last_name AS member,
                 b.title AS book, t.issue_date, t.due_date, t.return_date, t.status
                 FROM transactions t
                 JOIN members m ON t.member_id=m.member_id
                 JOIN books b ON t.book_id=b.book_id
                 ORDER BY t.transaction_id DESC"""

            for r in c.execute(q):
                self.tr_tree.insert("", tk.END, values=(
                    r["transaction_id"],
                    r["member"],
                    r["book"],
                    r["issue_date"],
                    r["due_date"],
                    r["return_date"] or "",
                    r["status"]
                ))
        except Exception as e:
            print("Error refreshing transactions:", e)
        finally:
            conn.close()

# ---------- run ----------
if __name__ == "__main__":
    app = LibraryApp()
    app.mainloop()