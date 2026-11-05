import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

root = tk.Tk()
root.title("tkinter в браузере")

menu = tk.Menu(root)
app = tk.Menu(menu, tearoff=0)
app.add_command(label="О программе", command=lambda: messagebox.showinfo("tkdemo", "Обычный tkinter, окна рисует страница"))
app.add_separator()
app.add_command(label="Выход", command=root.destroy)
menu.add_cascade(label="Файл", menu=app)
root.config(menu=menu)

tabs = ttk.Notebook(root)
tabs.pack(fill="both", expand=True, padx=8, pady=8)

form = ttk.Frame(tabs, padding=8)
tabs.add(form, text="Форма")
name = tk.StringVar(value="мир")
loud = tk.BooleanVar()
mood = tk.StringVar(value="🙂")
tk.Label(form, text="Имя").grid(row=0, column=0, sticky="w")
tk.Entry(form, textvariable=name).grid(row=0, column=1, columnspan=3, sticky="ew", padx=6)
tk.Checkbutton(form, text="громко", variable=loud).grid(row=1, column=0, sticky="w", pady=6)
for i, m in enumerate(["🙂", "😎", "🤖"]):
    tk.Radiobutton(form, text=m, value=m, variable=mood).grid(row=1, column=i + 1)
size = tk.Scale(form, from_=10, to=28, orient="horizontal", label="размер", length=220)
size.set(16)
size.grid(row=2, column=0, columnspan=4, sticky="ew")
hello = tk.Label(form, text="", height=2)
hello.grid(row=3, column=0, columnspan=4, sticky="ew")
form.columnconfigure(1, weight=1)


def greet(*_):
    bang = "!!!" if loud.get() else "!"
    hello.config(text="Привет, %s%s %s" % (name.get(), bang, mood.get()),
                 font=("TkDefaultFont", size.get() * 3 // 4, "bold" if loud.get() else "normal"))


for v in (name, loud, mood):
    v.trace_add("write", greet)
size.config(command=greet)


def ask():
    age = simpledialog.askinteger("Вопрос", "Сколько тебе лет?", minvalue=1, maxvalue=150)
    if age is not None and messagebox.askyesno("Вопрос", "Тебе правда %d?" % age):
        name.set("%s, %d" % (name.get().split(",")[0], age))


tk.Button(form, text="Спросить возраст", command=ask).grid(row=4, column=0, columnspan=4, pady=4)

draw = ttk.Frame(tabs, padding=8)
tabs.add(draw, text="Рисование")
canvas = tk.Canvas(draw, width=360, height=220, bg="#111")
canvas.pack()
last = [None]


def press(e):
    last[0] = (e.x, e.y)
    canvas.create_oval(e.x - 2, e.y - 2, e.x + 2, e.y + 2, fill="#eee", outline="")


def move(e):
    if last[0]:
        canvas.create_line(last[0][0], last[0][1], e.x, e.y, fill="#eee", width=3, capstyle="round")
    last[0] = (e.x, e.y)


canvas.bind("<Button-1>", press)
canvas.bind("<B1-Motion>", move)
canvas.create_text(180, 110, text="рисуй мышкой", fill="#555", tags="hint")
canvas.tag_bind("hint", "<Button-1>", lambda e: canvas.delete("hint"))
tk.Button(draw, text="Очистить", command=lambda: canvas.delete("all")).pack(pady=(6, 0))

todo = ttk.Frame(tabs, padding=8)
tabs.add(todo, text="Список")
items = tk.Listbox(todo, height=7)
items.pack(side="left", fill="both", expand=True)
side = tk.Frame(todo)
side.pack(side="right", fill="y", padx=(8, 0))
new = tk.Entry(side, width=14)
new.pack()


def add(*_):
    if new.get().strip():
        items.insert("end", new.get().strip())
        new.delete(0, "end")


def remove():
    for i in reversed(items.curselection()):
        items.delete(i)


new.bind("<Return>", add)
tk.Button(side, text="Добавить", command=add).pack(fill="x", pady=4)
tk.Button(side, text="Удалить", command=remove).pack(fill="x")
for t in ("купить молоко", "собрать бандл", "написать tkinter"):
    items.insert("end", t)

status = tk.Label(root, anchor="w", fg="#777")
status.pack(fill="x", padx=8, pady=(0, 6))


def tick():
    status.config(text="%02d:%02d:%02d" % tuple(time.localtime()[3:6]))
    root.after(1000, tick)


greet()
tick()
root.mainloop()
