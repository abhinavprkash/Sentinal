import * as vscode from 'vscode';
import { SentinelClient } from './api/client';
import { IncidentTreeProvider } from './views/incidentTreeProvider';
import { SentinelCommands } from './commands/commands';
import { SentinelStatusBar } from './statusBar';

export function activate(context: vscode.ExtensionContext) {
  console.log('Sentinel extension is now active!');

  // 1. Create API Client
  const client = new SentinelClient();

  // 2. Create Tree View Provider
  const treeProvider = new IncidentTreeProvider(client);
  const treeView = vscode.window.createTreeView('sentinel-incidents', {
    treeDataProvider: treeProvider
  });
  context.subscriptions.push(treeView);

  // 3. Register Commands
  const commands = new SentinelCommands(context, client, treeProvider);
  commands.register();

  // 4. Create Status Bar Item
  const statusBar = new SentinelStatusBar(client);
  context.subscriptions.push(statusBar);

  // Check backend health on startup
  client.healthCheck().then(() => {
    console.log('Sentinel Backend is healthy');
  }).catch(err => {
    vscode.window.showWarningMessage(`Sentinel Backend not detected at ${client['baseUrl']}. Is it running?`);
  });
}

export function deactivate() { }
