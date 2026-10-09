
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
)

from server.orchestrator import process_command


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CodeAssist AI")
        self.resize(850, 600)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        title = QLabel("CodeAssist AI")
        title.setStyleSheet("font-size: 26px; font-weight: bold;")

        description = QLabel(
            "Your voice-controlled programming assistant"
        )

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "Enter a programming command..."
        )

        self.submit_button = QPushButton("Submit Command")
        self.submit_button.clicked.connect(self.handle_command)

        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText(
            "Agent responses will appear here."
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.command_input)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.results)

        self.setCentralWidget(central_widget)

    def handle_command(self):
        command = self.command_input.text().strip()

        if not command:
            self.results.append("Please enter a command.")
            return

        self.results.append(f"\nYou: {command}")

        response = process_command(command)
        self.results.append(f"CodeAssist AI: {response}")

        self.command_input.clear()