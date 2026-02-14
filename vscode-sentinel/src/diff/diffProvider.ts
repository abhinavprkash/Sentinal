import * as vscode from "vscode";
import { IncidentRecord } from "../types";
import { ParsedDiffFile, parseUnifiedDiff } from "./unifiedDiffParser";

export class SentinelDiffProvider implements vscode.TextDocumentContentProvider, vscode.Disposable {
  private readonly onDidChangeEmitter = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this.onDidChangeEmitter.event;
  private readonly contents = new Map<string, string>();
  private readonly registration: vscode.Disposable;

  constructor() {
    this.registration = vscode.workspace.registerTextDocumentContentProvider("sentinel-diff", this);
  }

  dispose(): void {
    this.registration.dispose();
    this.onDidChangeEmitter.dispose();
    this.contents.clear();
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this.contents.get(uri.toString()) ?? "// Diff content not available.";
  }

  async openDiffForIncident(record: IncidentRecord): Promise<void> {
    const patchText = record.patch?.patch_text;
    if (!patchText) {
      throw new Error("No patch diff available for this incident.");
    }
    const files = parseUnifiedDiff(patchText);
    if (files.length === 0) {
      throw new Error("Unable to parse patch diff.");
    }

    const selected = await this.selectDiffFile(files);
    if (!selected) {
      return;
    }

    const nonce = Date.now().toString();
    const leftUri = vscode.Uri.parse(`sentinel-diff:${selected.filePath}?side=before&n=${nonce}`);
    const rightUri = vscode.Uri.parse(`sentinel-diff:${selected.filePath}?side=after&n=${nonce}`);

    this.contents.set(leftUri.toString(), selected.beforeContent);
    this.contents.set(rightUri.toString(), selected.afterContent);
    this.onDidChangeEmitter.fire(leftUri);
    this.onDidChangeEmitter.fire(rightUri);

    await vscode.commands.executeCommand(
      "vscode.diff",
      leftUri,
      rightUri,
      `Sentinel Patch Diff: ${selected.filePath}`,
      { preview: true }
    );
  }

  private async selectDiffFile(files: ParsedDiffFile[]): Promise<ParsedDiffFile | undefined> {
    if (files.length === 1) {
      return files[0];
    }
    const pick = await vscode.window.showQuickPick(
      files.map((file) => ({
        label: file.filePath,
        description: "Select file to open in diff viewer",
        file
      })),
      {
        placeHolder: "Select a changed file"
      }
    );
    return pick?.file;
  }
}
