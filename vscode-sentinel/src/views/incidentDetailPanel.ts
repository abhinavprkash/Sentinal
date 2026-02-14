import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { SentinelClient, IncidentRecord } from '../api/client';

export class IncidentDetailPanel {
  public static currentPanel: IncidentDetailPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private readonly _extensionUri: vscode.Uri;
  private _disposables: vscode.Disposable[] = [];
  private _client: SentinelClient;
  private _currentIncident: IncidentRecord | undefined;

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, client: SentinelClient) {
    this._panel = panel;
    this._extensionUri = extensionUri;
    this._client = client;

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      async message => {
        switch (message.command) {
          case 'approve':
            await this.handleApprove(message.incidentId);
            return;
          case 'reject':
            await this.handleReject(message.incidentId);
            return;
          case 'retry':
            await this.handleRetry(message.incidentId, message.stage);
            return;
          case 'openDiff':
            await this.handleOpenDiff();
            return;
        }
      },
      null,
      this._disposables
    );
  }

  public static createOrShow(extensionUri: vscode.Uri, client: SentinelClient, incident: IncidentRecord) {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    // If we already have a panel, show it.
    if (IncidentDetailPanel.currentPanel) {
      IncidentDetailPanel.currentPanel._panel.reveal(column);
      IncidentDetailPanel.currentPanel.update(incident);
      return;
    }

    // Otherwise, create a new panel.
    const panel = vscode.window.createWebviewPanel(
      'sentinelIncident',
      `Incident: ${incident.incident.incident_id}`,
      column || vscode.ViewColumn.One,
      {
        enableScripts: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
      }
    );

    IncidentDetailPanel.currentPanel = new IncidentDetailPanel(panel, extensionUri, client);
    IncidentDetailPanel.currentPanel.update(incident);
  }

  public update(incident: IncidentRecord) {
    this._currentIncident = incident;
    this._panel.title = `Incident: ${incident.incident.incident_id}`;
    this._panel.webview.html = this._getHtmlForWebview(this._panel.webview, incident);
  }

  private async handleApprove(incidentId: string) {
    try {
      const note = await vscode.window.showInputBox({
        title: 'Approval Note',
        placeHolder: 'Reason for approval (optional)'
      });
      await this._client.approveIncident(incidentId, {
        approved_by: 'vscode-user', // Should get from config or git config
        decision: 'approve',
        notes: note || 'Approved from VS Code'
      });
      vscode.window.showInformationMessage(`Incident ${incidentId} approved.`);
      // Refresh logic handled by polling in Sidebar
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to approve incident: ${error}`);
    }
  }

  private async handleReject(incidentId: string) {
    try {
      const note = await vscode.window.showInputBox({
        title: 'Rejection Reason',
        placeHolder: 'Reason for rejection (required)'
      });
      if (!note) return;

      await this._client.approveIncident(incidentId, {
        approved_by: 'vscode-user',
        decision: 'reject',
        notes: note
      });
      vscode.window.showInformationMessage(`Incident ${incidentId} rejected.`);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to reject incident: ${error}`);
    }
  }

  private async handleRetry(incidentId: string, stage: string) {
    try {
      await this._client.retryIncident(incidentId, stage);
      vscode.window.showInformationMessage(`Incident ${incidentId} retrying from ${stage}.`);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to retry incident: ${error}`);
    }
  }

  private async handleOpenDiff() {
    if (!this._currentIncident?.patch) {
      return;
    }
    // Command to show diff not fully implemented here, would need to create a temporary file or virtual document
    // Delegate to commands.ts via executeCommand if needed, or implement here.
    // For simplicity, we trigger the command
    vscode.commands.executeCommand('sentinel.openDiff', this._currentIncident);
  }

  public dispose() {
    IncidentDetailPanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const x = this._disposables.pop();
      if (x) {
        x.dispose();
      }
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview, incident: IncidentRecord): string {
    // Load HTML template from disk
    const htmlPath = vscode.Uri.joinPath(this._extensionUri, 'webview', 'incident.html');
    let htmlContent = fs.readFileSync(htmlPath.fsPath, 'utf-8');

    // Replace placeholders with data
    // For a hackathon, simple string replacement is faster than a template engine
    // Or we pass the data as a global JSON object and let the frontend script render it
    // Passing data as JSON is cleaner

    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'styles.css')); // reusing styles.css spot for now or logic

    // Replace placeholders
    htmlContent = htmlContent.replace('{{INCIDENT_DATA}}', JSON.stringify(incident));
    htmlContent = htmlContent.replace('{{STYLES_URI}}', scriptUri.toString());

    return htmlContent;
  }
}
