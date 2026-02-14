import * as vscode from 'vscode';
import { SentinelClient, IncidentRecord } from '../api/client';
import { IncidentTreeProvider, IncidentTreeItem } from '../views/incidentTreeProvider';
import { IncidentDetailPanel } from '../views/incidentDetailPanel';

export class SentinelCommands {
  constructor(
    private context: vscode.ExtensionContext,
    private client: SentinelClient,
    private treeProvider: IncidentTreeProvider
  ) { }

  register() {
    this.registerCommand('sentinel.triggerSynthetic', this.triggerSynthetic);
    this.registerCommand('sentinel.refresh', this.refresh);
    this.registerCommand('sentinel.viewIncident', this.viewIncident);
    this.registerCommand('sentinel.approveIncident', this.approveIncident);
    this.registerCommand('sentinel.rejectIncident', this.rejectIncident);
    this.registerCommand('sentinel.retryIncident', this.retryIncident);
    this.registerCommand('sentinel.openDiff', this.openDiff);
  }

  private registerCommand(command: string, callback: (...args: any[]) => any) {
    this.context.subscriptions.push(vscode.commands.registerCommand(command, callback.bind(this)));
  }

  private async triggerSynthetic() {
    try {
      const result = await this.client.triggerSynthetic();
      vscode.window.showInformationMessage(`Synthetic incident triggered: ${result.incident_id}`);
      this.treeProvider.refresh();
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to trigger synthetic incident: ${error}`);
    }
  }

  private refresh() {
    this.treeProvider.refresh();
  }

  private viewIncident(itemOrIncident: IncidentTreeItem | IncidentRecord) {
    let incident: IncidentRecord;
    if (itemOrIncident instanceof IncidentTreeItem) {
      incident = itemOrIncident.incident;
    } else {
      incident = itemOrIncident;
    }
    IncidentDetailPanel.createOrShow(this.context.extensionUri, this.client, incident);
  }

  private async approveIncident(item: IncidentTreeItem | undefined) {
    if (!item) return;
    const note = await vscode.window.showInputBox({ prompt: 'Approval Note' });
    try {
      await this.client.approveIncident(item.incident.incident.incident_id, {
        approved_by: 'vscode-user',
        decision: 'approve',
        notes: note || 'Approved via Sidebar',
      });
      vscode.window.showInformationMessage(`Incident ${item.incident.incident.incident_id} approved.`);
      this.treeProvider.refresh();
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to approve: ${error}`);
    }
  }

  private async rejectIncident(item: IncidentTreeItem | undefined) {
    if (!item) return;
    const note = await vscode.window.showInputBox({ prompt: 'Rejection Reason (Required)' });
    if (!note) return;

    try {
      await this.client.approveIncident(item.incident.incident.incident_id, {
        approved_by: 'vscode-user',
        decision: 'reject',
        notes: note,
      });
      vscode.window.showInformationMessage(`Incident ${item.incident.incident.incident_id} rejected.`);
      this.treeProvider.refresh();
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to reject: ${error}`);
    }
  }

  private async retryIncident(item: IncidentTreeItem | undefined) {
    // If called from palette without item, show picker? For now assume context menu
    let incidentId = item?.incident.incident.incident_id;
    if (!incidentId) {
      const incidents = await this.client.listIncidents();
      const picked = await vscode.window.showQuickPick(incidents.map(i => ({ label: i.incident.incident_id, detail: i.incident.service, incident: i })));
      if (!picked) return;
      incidentId = picked.incident.incident.incident_id;
    }

    const stages = ['triage', 'investigation', 'patch', 'verification'];
    const stage = await vscode.window.showQuickPick(stages, { placeHolder: 'Select stage to retry from' });
    if (!stage) return;

    try {
      await this.client.retryIncident(incidentId, stage);
      vscode.window.showInformationMessage(`Retrying ${incidentId} from ${stage}...`);
      this.treeProvider.refresh();
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to retry: ${error}`);
    }
  }

  private async openDiff(incident: IncidentRecord) {
    if (!incident.patch) {
      vscode.window.showErrorMessage('No patch available for this incident.');
      return;
    }

    // We want to show a diff check.
    // Left side: Original file (simulated or empty if new)
    // Right side: Patched file

    // Since we are mocking the repo interaction in MVP, we can't easily get the "original" content from disk
    // unless we actually check out the code.
    // For the hackathon demo, we can show the "patch_text" or "diff_summary" in a readonly document.
    // BETTER: Create two untitled documents with content and show diff.

    // Assuming we have the patch text, let's try to simulate a diff.
    // patch.patch_text usually contains the whole diff.
    // If we want a side-by-side diff, we need before/after content. 
    // The MVP PatchProposal model has `patch_text` which is likely a unified diff.
    // Inspecting models.py -> `patch_text: str`.

    // Let's just open the unified diff in a text editor for now, tailored as a "Patch View"
    // VS Code handles .diff files with syntax highlighting.

    const doc = await vscode.workspace.openTextDocument({
      content: incident.patch.patch_text,
      language: 'diff'
    });
    await vscode.window.showTextDocument(doc);
  }
}
