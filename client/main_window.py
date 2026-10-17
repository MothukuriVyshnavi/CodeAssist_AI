
import re
import time

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
    QMessageBox,
)

from server.orchestrator import process_command
from server.services.screen_service import (
    capture_screen,
    extract_text_from_screen,
)
from server.services.voice_service import listen_once
from server.services.speech_service import speak


def extract_corrected_code(result: str) -> str:
    """Extract corrected code from the correction agent's response."""

    match = re.search(
        r"CORRECTED_CODE\s*:\s*```[^\r\n]*\r?\n(.*?)```",
        result,
        re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return ""

    return match.group(1).strip("\r\n")


def approval_was_granted(spoken_text: str) -> bool:
    """Accept only explicit spoken approval commands."""

    normalized = re.sub(
        r"[^a-z\s]",
        "",
        spoken_text.lower(),
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    approved_phrases = {
        "yes",
        "yes please",
        "apply",
        "apply it",
        "yes apply",
        "yes apply it",
        "approve",
        "approved",
        "confirm",
        "confirm it",
    }

    return normalized in approved_phrases


class ScreenVoiceWorker(QThread):
    """Capture the screen, extract text, and listen for a command."""

    screen_captured = Signal(str)
    completed = Signal(str, str, str, str)
    failed = Signal(str)

    def run(self):
        screenshot_path = ""
        extracted_text = ""
        issues = []

        try:
            print("[Worker] Starting screen capture...", flush=True)

            # The main window and icon are hidden before this worker starts.
            screenshot_path = capture_screen()

            # Notify the GUI as soon as the screenshot is saved.
            # The floating icon can now reappear while OCR and voice
            # recognition continue.
            self.screen_captured.emit(screenshot_path)
            time.sleep(0.25)

            try:
                extracted_text = extract_text_from_screen(
                    screenshot_path
                )
            except Exception as error:
                issues.append(f"OCR failed: {error}")
                print(f"[Worker] {issues[-1]}", flush=True)

            print("[Worker] Preparing voice input...", flush=True)

            # This prompt is spoken before recording begins.
            speak(
                "Please say your programming command now."
            )

            try:
                print(
                    "[Worker] Recording voice for up to 8 seconds...",
                    flush=True,
                )

                command = listen_once(timeout_seconds=8)

                print(
                    f"[Worker] Recognized command: {command}",
                    flush=True,
                )

            except Exception as error:
                command = ""
                issues.append(f"Voice recognition failed: {error}")
                print(f"[Worker] {issues[-1]}", flush=True)

            # Return OCR text even when voice recognition fails.
            self.completed.emit(
                command,
                extracted_text,
                screenshot_path,
                "\n".join(issues),
            )

        except Exception as error:
            print(
                f"[Worker] Screen capture failed: {error}",
                flush=True,
            )
            self.failed.emit(
                f"Screen capture failed: {error}\n"
                f"Screenshot: {screenshot_path or 'Not created'}"
            )


class AnalysisWorker(QThread):
    """Run the agents, validate proposed code, and request approval."""

    result_ready = Signal(str, str)
    approval_prompt = Signal(str)

    def __init__(self, command: str, code: str):
        super().__init__()
        self.command = command
        self.code = code

    def run(self):
        try:
            result = process_command(
                self.command,
                self.code,
            )

            proposed_code = extract_corrected_code(result)
            approved_code = ""

            if not proposed_code:
                # The request might not require a correction.
                # Display the existing agent output unchanged.
                self.result_ready.emit(result, "")
                return

            from server.services.language_detector import (
                detect_language,
            )
            from server.services.diagnostic_service import (
                diagnose_code,
            )

            language = detect_language(
                self.code,
                self.command,
            )

            validation = diagnose_code(
                proposed_code,
                language,
                self.command,
            )

            if not validation["available"]:
                result += (
                    "\n\nVALIDATION FAILED\n"
                    "The appropriate language diagnostic tool is "
                    "unavailable. The proposed correction was not "
                    "applied.\n"
                    f"Details: {validation['diagnostics']}"
                )

                self.result_ready.emit(result, "")
                return

            if validation["has_errors"]:
                result += (
                    "\n\nVALIDATION FAILED\n"
                    "The proposed code still has reported errors. "
                    "No changes have been applied.\n"
                    f"Details: {validation['diagnostics']}"
                )

                self.result_ready.emit(result, "")
                return

            result += (
                "\n\nPROPOSED CORRECTION VALIDATED\n"
                f"Language: {language}\n"
                f"Validator: {validation['tool']}\n"
                f"Result: {validation['diagnostics']}\n\n"
                "VOICE APPROVAL REQUIRED\n"
                "Say APPLY to place the correction in the "
                "CodeAssist code box, or say CANCEL to reject it."
            )

            # Display the proposed correction while this worker
            # waits for the user's approval.
            self.approval_prompt.emit(result)

            try:
                speak(
                    "A corrected version is ready. "
                    "Say apply to approve the correction, "
                    "or cancel to reject it. "
                    "This will only update the CodeAssist code box."
                )

                spoken_response = listen_once(
                    timeout_seconds=8
                )

                if approval_was_granted(spoken_response):
                    approved_code = proposed_code

                    result += (
                        "\n\nAPPROVAL GRANTED\n"
                        "The correction will be placed in the "
                        "CodeAssist code box."
                    )

                    speak(
                        "Approval received. Updating the "
                        "CodeAssist code box."
                    )
                else:
                    result += (
                        "\n\nAPPROVAL NOT GRANTED\n"
                        f"Recognized response: {spoken_response}\n"
                        "No code was changed."
                    )

                    speak(
                        "The correction was not applied. "
                        "Your original code remains unchanged."
                    )

            except Exception as error:
                result += (
                    "\n\nAPPROVAL FAILED\n"
                    f"{error}\n"
                    "No code was changed."
                )

            self.result_ready.emit(result, approved_code)

        except Exception as error:
            self.result_ready.emit(
                f"An error occurred during analysis:\n{error}",
                "",
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CodeAssist AI")
        self.resize(900, 750)

        self._screen_worker = None
        self._analysis_worker = None

        self._build_interface()
        self._build_floating_icon()

    def _build_interface(self):
        """Build the main desktop interface."""

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        title = QLabel("CodeAssist AI")
        title.setStyleSheet(
            "font-size: 26px; font-weight: bold;"
        )

        description = QLabel(
            "Your multi-agent desktop programming assistant"
        )

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "Example: Find errors in my Python code"
        )

        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText(
            "Paste your code here or use the floating CA icon."
        )
        self.code_input.setMinimumHeight(220)

        self.capture_button = QPushButton(
            "Capture Screen + Voice Command"
        )
        self.capture_button.clicked.connect(
            self.start_screen_voice
        )

        self.analyze_button = QPushButton("Analyze Command")
        self.analyze_button.clicked.connect(
            self.start_analysis
        )

        self.status_label = QLabel("Ready.")

        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText(
            "Agent results will appear here."
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(QLabel("Command:"))
        layout.addWidget(self.command_input)
        layout.addWidget(QLabel("Code:"))
        layout.addWidget(self.code_input)
        layout.addWidget(self.capture_button)
        layout.addWidget(self.analyze_button)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Results:"))
        layout.addWidget(self.results)

        self.setCentralWidget(central_widget)

    def _build_floating_icon(self):
        """Create the floating assistant icon."""

        self.floating_button = QToolButton()

        self.floating_button.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )

        self.floating_button.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.floating_button.setWindowTitle(
            "CodeAssist Floating Assistant"
        )
        self.floating_button.setText("CA")
        self.floating_button.setToolTip(
            "Click to capture the screen and use a voice command"
        )
        self.floating_button.setFixedSize(64, 64)
        self.floating_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.floating_button.setStyleSheet(
            """
            QToolButton {
                background-color: #2563eb;
                color: white;
                border: 2px solid white;
                border-radius: 32px;
                font-size: 19px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #1d4ed8;
            }
            QToolButton:disabled {
                background-color: #64748b;
            }
            """
        )

        self.floating_button.clicked.connect(
            self.start_screen_voice
        )

        self.position_floating_button()

    def position_floating_button(self):
        """Place the icon in the bottom-right of the primary screen."""

        screen = QApplication.primaryScreen()

        if screen is None:
            return

        geometry = screen.availableGeometry()

        x = geometry.x() + geometry.width() - 84
        y = geometry.y() + geometry.height() - 100

        self.floating_button.move(x, y)

    def showEvent(self, event):
        """Display the floating icon after the main window appears."""

        super().showEvent(event)

        QTimer.singleShot(200, self.show_floating_icon)

    def show_floating_icon(self):
        """Show and raise the floating assistant."""

        if not hasattr(self, "floating_button"):
            return

        self.position_floating_button()
        self.floating_button.show()
        self.floating_button.raise_()

    def set_controls_enabled(self, enabled: bool):
        self.capture_button.setEnabled(enabled)
        self.analyze_button.setEnabled(enabled)

        # Keep the floating icon visible and clickable.
        self.floating_button.setEnabled(True)

    def restore_window(self):
        """Restore CodeAssist after screen capture or voice input."""

        self.showNormal()
        self.raise_()
        self.activateWindow()

        self.position_floating_button()
        self.floating_button.show()
        self.floating_button.raise_()

    def start_screen_voice(self):
        """Begin screen capture and voice-command processing."""

        if (
            self._screen_worker is not None
            and self._screen_worker.isRunning()
        ):
            return

        if (
            self._analysis_worker is not None
            and self._analysis_worker.isRunning()
        ):
            self.status_label.setText(
                "Please wait for the current analysis to finish."
            )
            return

        self.set_controls_enabled(False)

        self.status_label.setText(
            "Preparing screen capture..."
        )
        self.results.setPlainText(
            "Capturing a screenshot. The floating icon will "
            "reappear immediately after the capture."
        )

        # Temporarily hide CodeAssist to avoid capturing itself.
        self.floating_button.hide()
        self.hide()

        # Start capture after the windows have had time to disappear.
        QTimer.singleShot(
            450,
            self._launch_screen_voice_worker,
        )

    def _launch_screen_voice_worker(self):
        """Start the worker after the capture delay."""

        self._screen_worker = ScreenVoiceWorker()

        self._screen_worker.screen_captured.connect(
            self.handle_screen_captured
        )
        self._screen_worker.completed.connect(
            self.handle_screen_voice_complete
        )
        self._screen_worker.failed.connect(
            self.handle_screen_voice_failed
        )

        self._screen_worker.start()

    def handle_screen_captured(self, screenshot_path: str):
        """Restore the floating icon as soon as the screenshot is saved."""

        print(
            f"[GUI] Screenshot captured: {screenshot_path}",
            flush=True,
        )

        self.position_floating_button()
        self.floating_button.setToolTip(
            "CodeAssist is reading the screen and listening "
            "for your command."
        )
        self.floating_button.setEnabled(True)
        self.floating_button.show()
        self.floating_button.raise_()

    def handle_screen_voice_complete(
        self,
        command: str,
        extracted_text: str,
        screenshot_path: str,
        issues: str,
    ):
        """Show extracted text and recognized voice command."""

        self.restore_window()
        self.set_controls_enabled(True)

        self.command_input.setText(command)
        self.code_input.setPlainText(extracted_text)

        result_lines = [
            "SCREEN CAPTURE",
            f"Screenshot: {screenshot_path}",
            "",
            "VOICE COMMAND",
            command or "No command was recognized.",
            "",
            "OCR RESULT",
            (
                f"Extracted {len(extracted_text)} characters."
                if extracted_text
                else "No text was extracted."
            ),
        ]

        if issues:
            result_lines.extend(["", "DIAGNOSTICS", issues])

        if extracted_text:
            result_lines.extend([
                "",
                "Review the extracted text in the code area.",
                "Correct any OCR mistakes before analysis.",
            ])
            self.status_label.setText(
                "Review the extracted code, then click Analyze Command."
            )
        else:
            result_lines.extend([
                "",
                "Paste your source code manually and enter a command.",
            ])
            self.status_label.setText(
                "No code was extracted. Manual input is available."
            )

        if not command:
            result_lines.extend([
                "",
                "Enter your command in the command field manually "
                "if voice recognition failed.",
            ])

        self.results.setPlainText("\n".join(result_lines))

        self.floating_button.setToolTip(
            "CodeAssist: click to capture the screen and speak"
        )
    
    def handle_screen_voice_failed(self, message: str):
        """Handle screen capture or voice recognition failures."""

        self.restore_window()
        self.set_controls_enabled(True)

        self.status_label.setText(
            "Screen capture or voice input failed."
        )
        self.results.setPlainText(message)

        QMessageBox.warning(
            self,
            "CodeAssist Screen/Voice Error",
            message,
        )

    def start_analysis(self):
        """Run the agent workflow in a background thread."""

        if (
            self._analysis_worker is not None
            and self._analysis_worker.isRunning()
        ):
            return

        command = self.command_input.text().strip()
        code = self.code_input.toPlainText()

        if not command:
            self.results.setPlainText(
                "Please enter a command or use the floating assistant."
            )
            return

        self.set_controls_enabled(False)

        self.status_label.setText(
            "Processing with the three agents..."
        )
        self.results.setPlainText(
            "CodeAssist is analyzing your request. Please wait."
        )

        self._analysis_worker = AnalysisWorker(command, code)

        self._analysis_worker.approval_prompt.connect(
            self.show_approval_prompt
        )
        self._analysis_worker.result_ready.connect(
            self.handle_analysis_result
        )

        self._analysis_worker.start()

    def show_approval_prompt(self, result: str):
        """Display the proposed correction while awaiting approval."""

        self.status_label.setText(
            "Waiting for spoken approval..."
        )
        self.results.setPlainText(result)

    def handle_analysis_result(
        self,
        result: str,
        approved_code: str,
    ):
        """Display final results and apply approved code to the text area."""

        self.results.setPlainText(result)

        if approved_code:
            self.code_input.setPlainText(approved_code)
            self.status_label.setText(
                "Approved correction placed in the CodeAssist code box."
            )
        else:
            self.status_label.setText(
                "Analysis finished. No code was changed."
            )

        self.set_controls_enabled(True)
