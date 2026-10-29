
const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");

let snapshotPath;
let timer;

function writeSnapshot() {
    try {
        const editor = vscode.window.activeTextEditor;
        const document = editor ? editor.document : null;

        const snapshot = {
            timestamp_ms: Date.now(),
            window_focused: vscode.window.state.focused,
            language_id: document ? document.languageId : "",
            document_uri: document ? document.uri.toString() : "",
            file_name: document ? path.basename(document.fileName) : "",
            text: document ? document.getText() : ""
        };

        const tempPath = snapshotPath + ".tmp";

        fs.writeFileSync(
            tempPath,
            JSON.stringify(snapshot, null, 2),
            "utf8"
        );

        try {
            fs.renameSync(tempPath, snapshotPath);
        } catch (error) {
            if (fs.existsSync(snapshotPath)) {
                fs.unlinkSync(snapshotPath);
            }
            fs.renameSync(tempPath, snapshotPath);
        }
    } catch (error) {
        console.error("[CodeAssist VS Code]", error);
    }
}

function activate(context) {
    const directory = path.join(
        os.tmpdir(),
        "CodeAssistCaptures"
    );

    fs.mkdirSync(directory, { recursive: true });

    snapshotPath = path.join(
        directory,
        "vscode_editor.json"
    );

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(writeSnapshot),
        vscode.workspace.onDidChangeTextDocument(writeSnapshot),
        vscode.window.onDidChangeWindowState(writeSnapshot)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand(
            "codeassist-vscode-bridge.captureNow",
            () => {
                writeSnapshot();
                vscode.window.showInformationMessage(
                    "CodeAssist: Editor code snapshot updated."
                );
            }
        )
    );

    timer = setInterval(writeSnapshot, 1000);

    context.subscriptions.push({
        dispose: () => clearInterval(timer)
    });

    writeSnapshot();

    console.log(
        "[CodeAssist VS Code] Snapshot path:",
        snapshotPath
    );
}

function deactivate() {
    if (timer) {
        clearInterval(timer);
    }
}

module.exports = {
    activate,
    deactivate
};
