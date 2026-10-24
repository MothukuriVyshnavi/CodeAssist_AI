import { tool } from "@opencode-ai/plugin";
import { spawn } from "node:child_process";

const python = process.env.USERPROFILE
  + "\\OneDrive\\Desktop\\CodeAssist_AI\\.venv\\Scripts\\python.exe";

const adapter = process.env.USERPROFILE
  + "\\OneDrive\\Desktop\\CodeAssistAgentLab\\codeassist_adapter.py";

export const CodeAssistPlugin = async () => ({
  tool: {
    codeassist_analyze: tool({
      description:
        "Run the existing CodeAssist Python agent pipeline to analyze code, detect errors, explain code, or propose corrections. Returns a proposal only; never applies code changes.",
      args: {
        command: tool.schema.string().describe(
          "The user's requested coding task, such as find syntax errors, explain code, or correct code."
        ),
        code: tool.schema.string().describe(
          "The source code to analyze. Pass the complete code supplied by the user."
        ),
      },
      async execute(args) {
        return await new Promise((resolve) => {
          const child = spawn(python, [adapter], {
            cwd: process.env.USERPROFILE
              + "\\OneDrive\\Desktop\\CodeAssist_AI",
            windowsHide: true,
            stdio: ["pipe", "pipe", "pipe"],
          });

          let stdout = "";
          let stderr = "";
          child.stdout.setEncoding("utf8");
          child.stderr.setEncoding("utf8");
          child.stdout.on("data", (chunk) => stdout += chunk);
          child.stderr.on("data", (chunk) => stderr += chunk);

          child.on("error", (error) => {
            resolve("CodeAssist adapter launch failed: " + error.message);
          });

          child.on("close", (exitCode) => {
            if (exitCode !== 0) {
              resolve(
                "CodeAssist adapter failed (exit " + exitCode + ").\n"
                + (stderr || stdout || "No diagnostic output.")
              );
              return;
            }

            try {
              const result = JSON.parse(stdout);
              resolve(JSON.stringify(result, null, 2));
            } catch {
              resolve(
                "Adapter returned non-JSON output.\n"
                + stdout
                + (stderr ? "\nDiagnostics:\n" + stderr : "")
              );
            }
          });

          child.stdin.end(JSON.stringify(args));
        });
      },
    }),
  },
});

export default CodeAssistPlugin;
