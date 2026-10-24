import { tool } from "@opencode-ai/plugin";
import { spawn } from "node:child_process";

export default tool({
  description:
    "Call the existing CodeAssist Python agents to analyze code, detect errors, explain code, or propose corrections. Never edits files or applies corrections.",
  args: {
    command: tool.schema.string().describe(
      "The requested task, such as detect errors, explain code, or correct code."
    ),
    code: tool.schema.string().describe(
      "The complete source code to analyze."
    ),
  },
  async execute(args) {
    const root = process.env.USERPROFILE
      + "\\OneDrive\\Desktop\\CodeAssist_AI";
    const python = root + "\\.venv\\Scripts\\python.exe";
    const adapter = process.env.USERPROFILE
      + "\\OneDrive\\Desktop\\CodeAssistAgentLab\\codeassist_adapter.py";

    return await new Promise((resolve) => {
      const child = spawn(python, [adapter], {
        cwd: root,
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";
      let settled = false;

      const finish = (message) => {
        if (settled) return;
        settled = true;
        resolve(message);
      };

      child.stdout.setEncoding("utf8");
      child.stderr.setEncoding("utf8");
      child.stdout.on("data", chunk => stdout += chunk);
      child.stderr.on("data", chunk => stderr += chunk);

      child.on("error", error => {
        finish("Adapter launch failed: " + error.message);
      });

      child.on("close", exitCode => {
        if (exitCode !== 0) {
          finish("Adapter failed (exit " + exitCode + "):\n"
            + (stderr || stdout || "No diagnostic output."));
          return;
        }

        try {
          finish(JSON.stringify(JSON.parse(stdout), null, 2));
        } catch {
          finish("Adapter returned non-JSON output:\n" + stdout
            + (stderr ? "\nDiagnostics:\n" + stderr : ""));
        }
      });

      child.stdin.end(JSON.stringify(args));
    });
  },
});
