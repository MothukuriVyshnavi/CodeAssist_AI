
const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");

let timer = null;
let writing = false;

const outputDirectory = path.join(
    os.tmpdir(),
    "CodeAssistCaptures"
);

const snapshotPath = path.join(
    outputDirectory,
    "cursor_editor.json"
);

function writeSnapshot() {
    if (writing) return;

    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        console.log("[CodeAssist Bridge] No active editor yet.");
        return;
    }

    writing = true;

    try {
        fs.mkdirSync(outputDirectory, { recursive: true });

        const document = editor.document;

        const snapshot = {
            timestamp_ms: Date.now(),
            language_id: document.languageId,
            document_uri: document.uri.toString(),
            file_name: path.basename(
                document.fileName || "untitled"
            ),
            text: document.getText()
        };

        const temporaryPath = snapshotPath + ".tmp";

        fs.writeFileSync(
            temporaryPath,
            JSON.stringify(snapshot),
            "utf8"
        );

        fs.renameSync(temporaryPath, snapshotPath);

        console.log(
            `[CodeAssist Bridge] Snapshot written: ${snapshot.file_name}, ` +
            `${snapshot.text.length} characters, language=${snapshot.language_id}`
        );
    } catch (error) {
        console.error(
            "[CodeAssist Bridge] Snapshot write failed:",
            error
        );
    } finally {
        writing = false;
    }
}

function activate(context) {
    console.log("[CodeAssist Bridge] Activated.");

    // Try immediately and whenever the active editor changes.
    writeSnapshot();

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(() => {
            writeSnapshot();
        }),

        vscode.workspace.onDidChangeTextDocument((event) => {
            const editor = vscode.window.activeTextEditor;

            if (editor && event.document === editor.document) {
                writeSnapshot();
            }
        })
    );

    // Retry periodically in case an editor opens after activation.
    timer = setInterval(writeSnapshot, 1000);

    context.subscriptions.push({
        dispose: () => {
            if (timer !== null) {
                clearInterval(timer);
                timer = null;
            }
        }
    });
}

function deactivate() {
    if (timer !== null) {
        clearInterval(timer);
        timer = null;
    }
}

module.exports = {
    activate,
    deactivate
};
