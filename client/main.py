
print("Starting CodeAssist AI...", flush=True)

import sys
from PySide6.QtWidgets import QApplication
from client.main_window import MainWindow


def main():
    print("Creating desktop application...", flush=True)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    print("Window displayed. Waiting for events...", flush=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()