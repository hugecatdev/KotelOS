# Окно для демо встраивания (examples/embed): обычный tkinter, идёт и в MicroPython, и в CPython
import tkinter as tk

root = tk.Tk()
root.title("tkinter на сайте")


def note():
    w = tk.Toplevel(root)
    w.title("Заметка")
    t = tk.Text(w, width=30, height=6)
    t.insert("1.0", "Второе окно той же программы.\nЕго можно таскать, как и первое.")
    t.pack(padx=8, pady=8)


bar = tk.Menu(root)
menu = tk.Menu(bar, tearoff=0)
menu.add_command(label="Заметка", command=note)
menu.add_separator()
menu.add_command(label="Выход", command=root.destroy)
bar.add_cascade(label="Файл", menu=menu)
root.config(menu=bar)

tk.Label(root, text="Это окно рисует страница машины,\nа программа идёт в эмуляторе x86.").pack(padx=12, pady=(10, 6))

name = tk.StringVar()
row = tk.Frame(root)
row.pack(padx=12, pady=4, fill="x")
entry = tk.Entry(row, textvariable=name)
entry.pack(side="left", fill="x", expand=True)
said = tk.Label(root, text="")


def hello(*_):
    said.config(text="Привет, %s!" % (name.get() or "мир"))


tk.Button(row, text="Привет", command=hello).pack(side="left", padx=(6, 0))
entry.bind("<Return>", hello)
said.pack(pady=4)

cv = tk.Canvas(root, width=300, height=110, bg="black", highlightthickness=0)
cv.pack(padx=12, pady=(4, 12))
cv.create_text(150, 14, text="шарик можно таскать", fill="gray")
ball = cv.create_oval(130, 40, 170, 80, fill="orange", outline="")
at = [0, 0]


def grab(e):
    at[0], at[1] = e.x, e.y


def drag(e):
    cv.move(ball, e.x - at[0], e.y - at[1])
    at[0], at[1] = e.x, e.y


cv.tag_bind(ball, "<Button-1>", grab)
cv.tag_bind(ball, "<B1-Motion>", drag)

root.mainloop()
