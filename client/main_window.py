import re
import time
from typing import Any

from PySide6.QtCore import QThread, QTimer, Qt, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from server.orchestrator import process_command
from server.services.screen_service import capture_screen, extract_text_from_screen
from server.services.speech_service import speak
from server.services.voice_service import listen_once, load_whisper_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response_to_text(response: Any) -> str:
    """Convert the orchestrator response into readable text for the UI."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("result", "output", "response", "message", "text"):
            value = response.get(key)
            if value is not None:
                return str(value)
    return str(response)


def _extract_corrected_code(response_text: str) -> str:
    """Find code explicitly marked as corrected by the correction agent."""
    # Preferred format: CORRECTED_CODE: followed by a fenced code block.
    marker = re.search(r"CORRECTED_CODE\s*:?", response_text, re.IGNORECASE)
    if marker:
        following_text = response_text[marker.end():]
        fenced = re.search(r"```[^\n`]*\n(.*?)```", following_text, re.DOTALL)
        if fenced:
            return fenced.group(1).strip("\n")

    # Compatible with the earlier output format used by this project.
    section = re.search(r"CODE CORRECTION AGENT\s*:?(.*)", response_text, re.IGNORECASE | re.DOTALL)
    if section:
        fenced = re.search(r"```[^\n`]*\n(.*?)```", section.group(1), re.DOTALL)
        if fenced:
            return fenced.group(1).strip("\n")

    return ""


def _approval_decision(recognized_text: str) -> str:
    """Return 'apply', 'reject', or 'unclear' from the spoken response."""
    text = re.sub(r"[^a-z0-9\s]", " ", (recognized_text or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "unclear"

    text = text.replace("don t", "dont")
    reject_phrases = (
        "cancel", "reject", "do not apply", "dont apply", "no",
        "leave it", "keep original", "keep the original", "dont change",
    )
    apply_phrases = (
        "apply", "yes", "accept", "approved", "approve", "go ahead",
        "do it", "make the change", "use the correction",
    )

    def contains_phrase(phrase: str) -> bool:
        return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None

    # Check rejection first so a phrase such as "no, don't apply" cannot pass.
    if any(contains_phrase(phrase) for phrase in reject_phrases):
        return "reject"
    if any(contains_phrase(phrase) for phrase in apply_phrases):
        return "apply"
    return "unclear"


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class ScreenVoiceWorker(QThread):
    """Capture the desktop, read visible text, and record a spoken command."""

    screenshot_ready = Signal(str)
    completed = Signal(str, str, str, str)
    failed = Signal(str)

    def run(self) -> None:
        screenshot_path = ""
        extracted_text = ""
        command = ""
        issues = []

        try:
            print("[CodeAssist] Capturing screen...", flush=True)
            screenshot_path = str(capture_screen())
            self.screenshot_ready.emit(screenshot_path)
        except Exception as error:
            self.failed.emit(f"Screen capture failed: {error}")
            return

        try:
            extracted_text = extract_text_from_screen(screenshot_path) or ""
            print(
                f"[CodeAssist] OCR extracted {len(extracted_text)} characters.",
                flush=True,
            )
        except Exception as error:
            issues.append(f"OCR failed: {error}")
            print(f"[CodeAssist] OCR failed: {error}", flush=True)

        try:
            # Load the model before recording so model startup time does not
            # consume the user's speaking time.
            print("[CodeAssist] Loading Whisper model...", flush=True)
            load_whisper_model()
            speak(
                "Please say your programming command after this message. "
                "For example, find errors in this code."
            )
            time.sleep(0.35)
            print("[CodeAssist] Listening for up to 12 seconds...", flush=True)
            command = (listen_once(timeout_seconds=12) or "").strip()
            print(f"[CodeAssist] Recognized command: {command!r}", flush=True)
            if not command:
                issues.append("No command was recognized. Check the microphone and try again.")
        except Exception as error:
            issues.append(f"Voice recognition failed: {error}")
            print(f"[CodeAssist] Voice recognition failed: {error}", flush=True)

        self.completed.emit(command, extracted_text, screenshot_path, "\n".join(issues))


class AnalysisWorker(QThread):
    """Run the three-agent orchestrator without blocking the desktop UI."""

    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, command: str, code: str):
        super().__init__()
        self.command = command
        self.code = code

    def run(self) -> None:
        try:
            response = process_command(self.command, self.code)
            response_text = _response_to_text(response)
            corrected_code = _extract_corrected_code(response_text)
            self.completed.emit(response_text, corrected_code)
        except Exception as error:
            self.failed.emit(f"Analysis failed: {error}")


class ApprovalWorker(QThread):
    """Ask for explicit spoken approval before placing corrected code in the UI."""

    completed = Signal(str, str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            load_whisper_model()
            speak(
                "A code correction is ready. Say apply or yes to accept it, "
                "or say cancel or no to reject it."
            )
            time.sleep(0.35)
            recognized_text = (listen_once(timeout_seconds=8) or "").strip()
            self.completed.emit(_approval_decision(recognized_text), recognized_text)
        except Exception as error:
            self.failed.emit(str(error))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CodeAssist - Desktop Programming Assistant")
        self.resize(900, 760)
        self.setMinimumSize(700, 600)

        self._screen_worker = None
        self._analysis_worker = None
        self._approval_worker = None
        self._pending_corrected_code = ""
        self._original_code_for_approval = ""

        self._build_interface()
        self._build_floating_icon()

    # ------------------------------ Main UI ------------------------------

    def _build_interface(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)

        title = QLabel("CodeAssist")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "A desktop programming assistant for screen capture, voice commands, "
            "error detection, and code correction."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")

        command_label = QLabel("Command")
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "Example: Find syntax errors and explain how to fix them"
        )
        self.command_input.returnPressed.connect(lambda: self.start_analysis())

        code_label = QLabel("Code / OCR text")
        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText(
            "Paste code here, or click the floating microphone to capture the screen..."
        )
        self.code_input.setMinimumHeight(190)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.analyze_button = QPushButton("Analyze Command")
        self.analyze_button.clicked.connect(lambda: self.start_analysis())
        self.capture_button = QPushButton("Capture Screen + Voice")
        self.capture_button.clicked.connect(lambda: self.start_screen_voice())
        buttons.addWidget(self.analyze_button)
        buttons.addWidget(self.capture_button)

        self.status_label = QLabel("Ready. Click the floating microphone or enter a command.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        output_label = QLabel("Results")
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setPlaceholderText("Analysis results and detected issues will appear here.")
        self.output_box.setMinimumHeight(180)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(command_label)
        layout.addWidget(self.command_input)
        layout.addWidget(code_label)
        layout.addWidget(self.code_input, 2)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)
        layout.addWidget(output_label)
        layout.addWidget(self.output_box, 2)

        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #101321;
                color: #F4F6FF;
                font-size: 10pt;
            }
            QLabel#pageTitle {
                color: #FFFFFF;
                font-size: 24pt;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #B8BED6;
                padding-bottom: 5px;
            }
            QLineEdit, QTextEdit {
                background-color: #191E31;
                color: #F4F6FF;
                border: 1px solid #343B59;
                border-radius: 8px;
                padding: 9px;
                selection-background-color: #6856D9;
            }
            QPushButton {
                background-color: #6856D9;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #7969E5;
            }
            QPushButton:disabled {
                background-color: #41465C;
                color: #B2B5C5;
            }
            QLabel#statusLabel {
                color: #AEB8FF;
                padding: 4px 0;
            }
            """
        )

    # -------------------------- Floating microphone -----------------------

    def _build_floating_icon(self) -> None:
        # A parentless tool window remains visible when the main window is
        # hidden so CodeAssist can capture the IDE behind it.
        self.floating_button = QToolButton()
        self.floating_button.setWindowTitle("CodeAssist microphone")
        self.floating_button.setToolTip("CodeAssist: capture screen and speak a command")
        self.floating_button.setFixedSize(50, 50)
        self.floating_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.floating_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.floating_button.setText("")
        self.floating_button.setIcon(QIcon(self._create_mic_icon()))
        self.floating_button.setIconSize(QSize(30, 30))
        self.floating_button.setMask(
            QRegion(0, 0, 50, 50, QRegion.RegionType.Ellipse)
        )
        self.floating_button.setStyleSheet(
            """
            QToolButton {
                background-color: #6255DC;
                border: 2px solid #A5A0FF;
                border-radius: 25px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #786BFA;
                border: 2px solid #FFFFFF;
            }
            QToolButton:pressed {
                background-color: #493BB8;
            }
            """
        )

        shadow = QGraphicsDropShadowEffect(self.floating_button)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(100, 85, 255, 180))
        self.floating_button.setGraphicsEffect(shadow)

        self.floating_button.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.floating_button.clicked.connect(lambda: self.start_screen_voice())
        self.position_floating_button()
        self.floating_button.show()
        self.floating_button.raise_()

    def _create_mic_icon(self) -> QPixmap:
        """Draw a white microphone symbol for the round floating button."""
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        white = QColor("#FFFFFF")
        painter.setPen(QPen(white, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(white)

        # Microphone capsule
        painter.drawRoundedRect(17, 5, 14, 22, 7, 7)

        # U-shaped support, stem and base
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(11, 12, 26, 24, 0, -180 * 16)
        painter.drawLine(24, 35, 24, 40)
        painter.drawLine(17, 41, 31, 41)
        painter.end()
        return pixmap

    def position_floating_button(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        size = self.floating_button.width() if hasattr(self, "floating_button") else 50
        x = area.right() - size - 12 + 1
        # Place it around three-quarters of the way down the screen.
        y = area.top() + int((area.height() - size) * 0.72)
        self.floating_button.move(x, y)

    def show_floating_icon(self) -> None:
        self.position_floating_button()
        self.floating_button.show()
        self.floating_button.raise_()

    # --------------------------- Screen + voice ----------------------------

    def start_screen_voice(self) -> None:
        if self._worker_is_running(self._screen_worker):
            return
        if self._worker_is_running(self._analysis_worker):
            self.status_label.setText("Please wait for the current analysis to finish.")
            return
        if self._worker_is_running(self._approval_worker):
            self.status_label.setText("Waiting for your spoken approval. Say APPLY or CANCEL.")
            return

        self.status_label.setText("Capturing the screen, reading visible text, and listening...")
        self.output_box.setPlainText(
            "SCREEN CAPTURE + VOICE\n\n"
            "The main window will briefly hide so CodeAssist can capture the app behind it. "
            "The round microphone icon will remain visible.\n"
        )

        # Hide only the main window. The independent floating microphone stays
        # on screen; the short delay lets the IDE behind this window become visible.
        self.hide()
        QTimer.singleShot(350, self._launch_screen_voice_worker)

    def _launch_screen_voice_worker(self) -> None:
        self._screen_worker = ScreenVoiceWorker()
        self._screen_worker.screenshot_ready.connect(self.handle_screen_captured)
        self._screen_worker.completed.connect(self.handle_screen_voice_complete)
        self._screen_worker.failed.connect(self.handle_screen_voice_failed)
        self._screen_worker.start()

    def handle_screen_captured(self, screenshot_path: str) -> None:
        self.status_label.setText("Screenshot captured. Reading the screen and listening for your command...")
        # Restore the results window after the desktop screenshot has been taken.
        self.show()
        self.raise_()
        self.activateWindow()
        self.show_floating_icon()
        self.output_box.setPlainText(
            "SCREEN CAPTURE\n"
            f"Screenshot: {screenshot_path}\n\n"
            "VOICE COMMAND\nListening for your programming command...\n"
        )

    def handle_screen_voice_complete(
        self,
        command: str,
        extracted_text: str,
        screenshot_path: str,
        issues: str,
    ) -> None:
        command = (command or "").strip()
        extracted_text = (extracted_text or "").strip()
        existing_code = self.code_input.toPlainText().strip()

        if extracted_text:
            self.code_input.setPlainText(extracted_text)

        parts = [
            "SCREEN CAPTURE",
            f"Screenshot: {screenshot_path or 'Not available'}",
            "",
            "VOICE COMMAND",
            command if command else "No command was recognized.",
            "",
            "OCR RESULT",
            f"Extracted {len(extracted_text)} characters." if extracted_text else "No readable text was extracted.",
        ]
        if issues:
            parts.extend(["", "NOTES", issues])
        if extracted_text:
            parts.extend([
                "",
                "Review the extracted text in the code area and correct any OCR mistakes before analysis.",
            ])

        self.output_box.setPlainText("\n".join(parts))

        if command:
            self.command_input.setText(command)
            code_to_analyze = extracted_text or existing_code
            if code_to_analyze:
                self.status_label.setText("Voice command recognized. Starting analysis...")
                self.start_analysis(command=command, code=code_to_analyze)
                return
            self.status_label.setText("Command recognized, but no code was found. Paste code to analyze it.")
        else:
            self.status_label.setText("Screen capture finished. Enter a command manually if voice recognition failed.")

        self.set_controls_enabled(True)
        self.show()
        self.show_floating_icon()

    def handle_screen_voice_failed(self, error_message: str) -> None:
        self.output_box.append("\n\nERROR\n" + error_message)
        self.status_label.setText(error_message)
        self.set_controls_enabled(True)
        self.show()
        self.raise_()
        self.show_floating_icon()

    # ------------------------------- Analysis -----------------------------

    def start_analysis(self, command: str = None, code: str = None) -> None:
        if self._worker_is_running(self._analysis_worker):
            return
        if self._worker_is_running(self._approval_worker):
            self.status_label.setText("Please respond to the correction approval first.")
            return

        command_text = (command if command is not None else self.command_input.text()).strip()
        code_text = (code if code is not None else self.code_input.toPlainText()).strip()

        if not command_text:
            QMessageBox.information(self, "Command required", "Enter or say what you want CodeAssist to do.")
            return

        if code is not None:
            self.code_input.setPlainText(code_text)
        self.command_input.setText(command_text)

        self._pending_corrected_code = ""
        self._original_code_for_approval = code_text
        self.set_controls_enabled(False)
        self.status_label.setText("Analyzing with the CodeAssist agents...")
        self.output_box.append("\n\nANALYSIS\nProcessing your command. Please wait...")

        self._analysis_worker = AnalysisWorker(command_text, code_text)
        self._analysis_worker.completed.connect(self.handle_analysis_result)
        self._analysis_worker.failed.connect(self.handle_analysis_failed)
        self._analysis_worker.start()

    def handle_analysis_result(self, result_text: str, corrected_code: str) -> None:
        self.output_box.setPlainText(result_text or "The analysis returned no text.")
        self.set_controls_enabled(True)

        if corrected_code:
            self._pending_corrected_code = corrected_code
            self.status_label.setText("Correction found. Waiting for your spoken approval: say APPLY or CANCEL.")
            self.output_box.append(
                "\n\nSPOKEN APPROVAL REQUIRED\n"
                "CodeAssist will not change the code area unless you say APPLY or YES. "
                "Say CANCEL or NO to keep the original code.\n"
            )
            self._approval_worker = ApprovalWorker()
            self._approval_worker.completed.connect(self.handle_approval_result)
            self._approval_worker.failed.connect(self.handle_approval_failed)
            self._approval_worker.start()
        else:
            self.status_label.setText("Analysis complete. No explicitly marked corrected code was found.")

    def handle_analysis_failed(self, error_message: str) -> None:
        self.output_box.append("\n\n" + error_message)
        self.status_label.setText("Analysis failed. Check the server/agent output in the terminal.")
        self.set_controls_enabled(True)

    # --------------------------- Spoken approval --------------------------

    def handle_approval_result(self, decision: str, recognized_text: str) -> None:
        if decision == "apply" and self._pending_corrected_code:
            self.code_input.setPlainText(self._pending_corrected_code)
            self.output_box.append(
                "\nVOICE APPROVAL: ACCEPTED\n"
                f"Recognized: {recognized_text or '(not available)'}\n"
                "The corrected code has been loaded into the CodeAssist code area. "
                "It has NOT been automatically written to your IDE or another file."
            )
            self.status_label.setText("Correction accepted and loaded into the CodeAssist code area.")
        elif decision == "reject":
            self.output_box.append(
                "\nVOICE APPROVAL: REJECTED\n"
                f"Recognized: {recognized_text or '(not available)'}\n"
                "The original code was left unchanged."
            )
            self.status_label.setText("Correction rejected. Original code remains unchanged.")
        else:
            self.output_box.append(
                "\nVOICE APPROVAL: NOT RECOGNIZED\n"
                f"Recognized: {recognized_text or '(no speech recognized)'}\n"
                "For safety, the correction was NOT applied. Click Analyze Command again to retry."
            )
            self.status_label.setText("No clear approval was recognized. Original code remains unchanged.")

        self._pending_corrected_code = ""
        self.set_controls_enabled(True)
        self.show()
        self.raise_()
        self.show_floating_icon()

    def handle_approval_failed(self, error_message: str) -> None:
        self.output_box.append(
            "\nVOICE APPROVAL FAILED\n"
            f"{error_message}\n"
            "The correction was not applied; the original code remains unchanged."
        )
        self.status_label.setText("Approval recording failed. The original code remains unchanged.")
        self._pending_corrected_code = ""
        self.set_controls_enabled(True)

    # ------------------------------- Helpers ------------------------------

    @staticmethod
    def _worker_is_running(worker) -> bool:
        return worker is not None and worker.isRunning()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.analyze_button.setEnabled(enabled)
        self.capture_button.setEnabled(enabled)
        # Keep the floating microphone visible and clickable. The method
        # checks worker state and ignores duplicate requests while busy.
        self.floating_button.setEnabled(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(100, self.show_floating_icon)

    def closeEvent(self, event) -> None:
        running_workers = [
            worker
            for worker in (self._screen_worker, self._analysis_worker, self._approval_worker)
            if worker is not None and worker.isRunning()
        ]
        if running_workers:
            QMessageBox.warning(
                self,
                "CodeAssist is busy",
                "Please wait for the current screen capture, analysis, or voice approval to finish before closing CodeAssist.",
            )
            event.ignore()
            return

        self.floating_button.close()
        event.accept()
