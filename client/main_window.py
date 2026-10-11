
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit
)

from server.orchestrator import process_command


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CodeAssist AI")
        self.resize(900, 750)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        title = QLabel("CodeAssist AI")
        title.setStyleSheet("font-size: 26px; font-weight: bold;")

        description = QLabel(
            "Your AI programming assistant"
        )

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "Example: Find errors in my Python code"
        )

        code_label = QLabel("Paste your code here:")

        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText(
            "Paste your Python code here..."
        )
        self.code_input.setMinimumHeight(220)

        self.submit_button = QPushButton("Analyze Command")
        self.submit_button.clicked.connect(self.handle_command)

        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText(
            "Agent results will appear here..."
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.command_input)
        layout.addWidget(code_label)
        layout.addWidget(self.code_input)
        layout.addWidget(self.submit_button)
        layout.addWidget(QLabel("Results:"))
        layout.addWidget(self.results)

        self.setCentralWidget(central_widget)

    def handle_command(self):
        command = self.command_input.text().strip()
        code = self.code_input.toPlainText()

        if not command:
            self.results.setPlainText(
                "Please enter a programming command."
            )
            return

        self.submit_button.setEnabled(False)
        self.results.setPlainText(
            "CodeAssist AI is processing your request...\n"
            "Please wait."
        )

        try:
            result = process_command(command, code)
            self.results.setPlainText(result)
        except Exception as error:
            self.results.setPlainText(
                f"An error occurred:\n{error}"
            )
        finally:
            self.submit_button.setEnabled(True)