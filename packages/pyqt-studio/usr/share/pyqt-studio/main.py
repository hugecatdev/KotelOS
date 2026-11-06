# Код формы form.ui: setup(form) получает форму и подключает к ней действия.
# В pyqt-studio форма перезапускается после каждого сохранения (здесь или в Designer),
# отдельно - python3 main.py
import os

from PyQt5 import QtWidgets, uic


def setup(form):
    def hello():
        name = form.name.text().strip() or "мир"
        form.greeting.setText(f"Привет, {name}!")
        print("привет:", name)

    form.hello.clicked.connect(hello)
    form.name.returnPressed.connect(hello)
    form.slider.valueChanged.connect(form.progress.setValue)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    form = uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)), "form.ui"))
    setup(form)
    form.show()
    app.exec_()
