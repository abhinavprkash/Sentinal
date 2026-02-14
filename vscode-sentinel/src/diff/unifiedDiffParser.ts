export interface ParsedDiffFile {
  filePath: string;
  beforeContent: string;
  afterContent: string;
}

export function parseUnifiedDiff(diffText: string): ParsedDiffFile[] {
  const lines = diffText.split(/\r?\n/);
  const files: ParsedDiffFile[] = [];
  let currentPath = "";
  let beforeLines: string[] = [];
  let afterLines: string[] = [];
  let inHunk = false;

  const pushCurrent = (): void => {
    if (!currentPath) {
      return;
    }
    files.push({
      filePath: currentPath,
      beforeContent: beforeLines.length > 0 ? beforeLines.join("\n") : "// No previous content in patch context.",
      afterContent: afterLines.length > 0 ? afterLines.join("\n") : "// No resulting content in patch context."
    });
    currentPath = "";
    beforeLines = [];
    afterLines = [];
    inHunk = false;
  };

  for (const line of lines) {
    if (line.startsWith("--- ")) {
      pushCurrent();
      continue;
    }
    if (line.startsWith("+++ ")) {
      currentPath = normalizeFilePath(line.slice(4).trim());
      continue;
    }
    if (line.startsWith("@@")) {
      inHunk = true;
      continue;
    }
    if (!inHunk || !currentPath) {
      continue;
    }
    if (line.startsWith("+")) {
      afterLines.push(line.slice(1));
      continue;
    }
    if (line.startsWith("-")) {
      beforeLines.push(line.slice(1));
      continue;
    }
    if (line.startsWith(" ")) {
      const content = line.slice(1);
      beforeLines.push(content);
      afterLines.push(content);
    }
  }

  pushCurrent();
  return files;
}

function normalizeFilePath(pathValue: string): string {
  return pathValue.replace(/^a\//, "").replace(/^b\//, "").trim();
}
