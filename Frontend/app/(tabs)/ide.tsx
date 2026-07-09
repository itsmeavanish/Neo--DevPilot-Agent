import { useState, useRef, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams } from 'expo-router';
import {
  listDirectory,
  readFile,
  writeFile,
  runSystemCommand,
  ideAgentStream,
  claudeCodeStream,
  runJulesAgent,
  getCurrentWorkingDirectory,
  FileInfo,
} from '@/lib/api';
import configManager from '@/lib/config';
import { Colors, Spacing, FontSize, BorderRadius } from '@/lib/theme';

let _idCounter = 0;
const uid = (prefix: string) => `${prefix}-${Date.now()}-${++_idCounter}`;

// Types
interface OpenTab {
  path: string;
  name: string;
  content: string;
  language: string;
  modified: boolean;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  isError?: boolean;
  isThinking?: boolean;
  isToolCall?: boolean;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  toolResult?: Record<string, unknown>;
  durationMs?: number;
  step?: number;
  expanded?: boolean;
}

interface TerminalLine {
  id: string;
  type: 'command' | 'output' | 'error';
  content: string;
}

type AgentType = 'freellm' | 'claude_code' | 'jules';

// Formatted response renderer for Claude Code messages
function FormattedResponse({ content }: { content: string }) {
  const blocks = parseResponseBlocks(content);
  return (
    <View style={fmtStyles.container}>
      {blocks.map((block, i) => {
        switch (block.type) {
          case 'heading':
            return (
              <Text key={i} style={[fmtStyles.heading, block.level === 1 && fmtStyles.h1, block.level === 2 && fmtStyles.h2]}>
                {block.text}
              </Text>
            );
          case 'code':
            return (
              <View key={i} style={fmtStyles.codeBlock}>
                {block.lang ? <Text style={fmtStyles.codeLang}>{block.lang}</Text> : null}
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <Text style={fmtStyles.codeText} selectable>{block.text}</Text>
                </ScrollView>
              </View>
            );
          case 'list':
            return (
              <View key={i} style={fmtStyles.listItem}>
                <Text style={fmtStyles.bullet}>{block.ordered ? `${block.index}.` : '•'}</Text>
                <Text style={fmtStyles.listText}>{block.text}</Text>
              </View>
            );
          case 'separator':
            return <View key={i} style={fmtStyles.separator} />;
          default:
            return block.text.trim() ? (
              <Text key={i} style={fmtStyles.paragraph} selectable>{block.text}</Text>
            ) : null;
        }
      })}
    </View>
  );
}

type Block = { type: 'text' | 'heading' | 'code' | 'list' | 'separator'; text: string; level?: number; lang?: string; ordered?: boolean; index?: number };

function parseResponseBlocks(content: string): Block[] {
  const lines = content.split('\n');
  const blocks: Block[] = [];
  let inCode = false;
  let codeBuffer = '';
  let codeLang = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (!inCode) {
        inCode = true;
        codeLang = line.slice(3).trim();
        codeBuffer = '';
      } else {
        blocks.push({ type: 'code', text: codeBuffer, lang: codeLang });
        inCode = false;
        codeBuffer = '';
        codeLang = '';
      }
      continue;
    }

    if (inCode) {
      codeBuffer += (codeBuffer ? '\n' : '') + line;
      continue;
    }

    if (line.startsWith('### ')) {
      blocks.push({ type: 'heading', text: line.slice(4), level: 3 });
    } else if (line.startsWith('## ')) {
      blocks.push({ type: 'heading', text: line.slice(3), level: 2 });
    } else if (line.startsWith('# ')) {
      blocks.push({ type: 'heading', text: line.slice(2), level: 1 });
    } else if (/^[-*] /.test(line)) {
      blocks.push({ type: 'list', text: line.slice(2), ordered: false, index: 0 });
    } else if (/^\d+\. /.test(line)) {
      const match = line.match(/^(\d+)\. (.*)$/);
      blocks.push({ type: 'list', text: match?.[2] || line, ordered: true, index: parseInt(match?.[1] || '1') });
    } else if (line.match(/^---+$|^===+$/)) {
      blocks.push({ type: 'separator', text: '' });
    } else {
      const last = blocks[blocks.length - 1];
      if (last && last.type === 'text' && line.trim()) {
        last.text += '\n' + line;
      } else if (line.trim()) {
        blocks.push({ type: 'text', text: line });
      }
    }
  }

  if (inCode && codeBuffer) {
    blocks.push({ type: 'code', text: codeBuffer, lang: codeLang });
  }

  return blocks;
}

const fmtStyles = StyleSheet.create({
  container: { gap: 8 },
  heading: { fontWeight: '700', color: Colors.foreground, marginTop: 4 },
  h1: { fontSize: 16 },
  h2: { fontSize: 14 },
  paragraph: { fontSize: 13, color: Colors.foreground, lineHeight: 20 },
  codeBlock: {
    backgroundColor: Colors.background,
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  codeLang: { fontSize: 10, color: Colors.muted, marginBottom: 4, textTransform: 'uppercase' },
  codeText: { fontSize: 12, color: Colors.cyan, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  listItem: { flexDirection: 'row', gap: 6, paddingLeft: 4 },
  bullet: { fontSize: 13, color: Colors.primary, width: 16 },
  listText: { fontSize: 13, color: Colors.foreground, lineHeight: 20, flex: 1 },
  separator: { height: 1, backgroundColor: Colors.border, marginVertical: 6 },
});

export default function IDEScreen() {
  const params = useLocalSearchParams<{ openPath?: string }>();

  // File explorer state
  const [currentPath, setCurrentPath] = useState(params.openPath || '.');
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [showHidden, setShowHidden] = useState(false);

  // Editor state
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);

  // Terminal state
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([
    { id: '0', type: 'output', content: 'Welcome to JARVIS Terminal' },
  ]);
  const [terminalCommand, setTerminalCommand] = useState('');
  const [runningCommand, setRunningCommand] = useState(false);

  // AI Agent state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content:
        '👋 AI Agent ready. I have full access to your workspace.\n\n' +
        '• Read, write, and create files\n' +
        '• Run terminal commands and git operations\n' +
        '• Refactor, fix bugs, and implement features\n\n' +
        'Open a folder and ask me anything.',
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [loadingChat, setLoadingChat] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentType>('freellm');
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const [agentSessionId, setAgentSessionId] = useState<string | undefined>();
  const abortAgentRef = useRef<(() => void) | null>(null);
  const [thinkingSteps, setThinkingSteps] = useState<ChatMessage[]>([]);
  const [showThinkingDetails, setShowThinkingDetails] = useState(true);

  // Drawer state (replaces panel state)
  const [showFilesDrawer, setShowFilesDrawer] = useState(false);
  const [showEditorDrawer, setShowEditorDrawer] = useState(false);
  const [showTerminalDrawer, setShowTerminalDrawer] = useState(false);
  const [showOpenFolderModal, setShowOpenFolderModal] = useState(false);
  const [folderInput, setFolderInput] = useState(currentPath);

  // Refs
  const terminalScrollRef = useRef<ScrollView>(null);
  const chatScrollRef = useRef<ScrollView>(null);
  const claudeSessionStarted = useRef(false);

  // Initialize workspace
  useEffect(() => {
    const init = async () => {
      try {
        await configManager.init();
        if (!params.openPath) {
          const workingDir = await getCurrentWorkingDirectory();
          setCurrentPath(workingDir);
          setFolderInput(workingDir);
          await loadDirectory(workingDir);
        } else {
          await loadDirectory(params.openPath);
        }
      } catch (error) {
        console.warn('Failed to initialize workspace:', error);
        await loadDirectory('.');
      }
    };
    init();
  }, [params.openPath]);

  // Drawer handlers
  const openFilesDrawer = useCallback(() => {
    setShowFilesDrawer(true);
  }, []);

  const openEditorDrawer = useCallback(() => {
    setShowEditorDrawer(true);
  }, []);

  const openTerminalDrawer = useCallback(() => {
    setShowTerminalDrawer(true);
  }, []);

  const closeFilesDrawer = useCallback(() => {
    setShowFilesDrawer(false);
  }, []);

  const closeEditorDrawer = useCallback(() => {
    setShowEditorDrawer(false);
  }, []);

  const closeTerminalDrawer = useCallback(() => {
    setShowTerminalDrawer(false);
  }, []);

  // Start a new chat session (resets context)
  const startNewSession = useCallback(() => {
    setChatMessages([]);
    setThinkingSteps([]);
    claudeSessionStarted.current = false;
  }, []);

  // Load directory
  const loadDirectory = useCallback(async (path: string) => {
    setLoadingFiles(true);
    try {
      const result = await listDirectory(path, showHidden);
      if (result.error) {
        Alert.alert('Error', result.error);
      } else {
        setFiles(result.files);
        setCurrentPath(result.path);
        setFolderInput(result.path);
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to load directory');
    } finally {
      setLoadingFiles(false);
    }
  }, [showHidden]);

  // Navigate up
  const goUp = useCallback(() => {
    const separator = currentPath.includes('\\') ? '\\' : '/';
    const parent = currentPath.substring(0, currentPath.lastIndexOf(separator));
    if (parent && parent !== currentPath) {
      loadDirectory(parent);
    }
  }, [currentPath, loadDirectory]);

  // Open file
  const openFile = useCallback(async (file: FileInfo) => {
    if (file.is_dir) {
      await loadDirectory(file.path);
      return;
    }

    const existing = openTabs.find(t => t.path === file.path);
    if (existing) {
      setActiveTab(file.path);
      closeFilesDrawer();
      return;
    }

    setLoadingContent(true);
    try {
      const result = await readFile(file.path, 1000);
      if (result.error) {
        Alert.alert('Error', result.error);
        return;
      }

      const newTab: OpenTab = {
        path: file.path,
        name: file.name,
        content: result.content,
        language: result.language,
        modified: false,
      };

      setOpenTabs(prev => [...prev, newTab]);
      setActiveTab(file.path);
      closeFilesDrawer();
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to open file');
    } finally {
      setLoadingContent(false);
    }
  }, [openTabs, closeFilesDrawer, loadDirectory]);

  // Close tab
  const closeTab = useCallback((path: string) => {
    const tab = openTabs.find(t => t.path === path);
    if (tab?.modified) {
      Alert.alert('Unsaved Changes', 'Save before closing?', [
        { text: 'Discard', style: 'destructive', onPress: () => {
          setOpenTabs(prev => prev.filter(t => t.path !== path));
          if (activeTab === path) {
            const remaining = openTabs.filter(t => t.path !== path);
            setActiveTab(remaining.length > 0 ? remaining[remaining.length - 1].path : null);
          }
        }},
        { text: 'Cancel', style: 'cancel' },
        { text: 'Save', onPress: async () => {
          await saveFile(path);
          setOpenTabs(prev => prev.filter(t => t.path !== path));
          if (activeTab === path) {
            const remaining = openTabs.filter(t => t.path !== path);
            setActiveTab(remaining.length > 0 ? remaining[remaining.length - 1].path : null);
          }
        }},
      ]);
    } else {
      setOpenTabs(prev => prev.filter(t => t.path !== path));
      if (activeTab === path) {
        const remaining = openTabs.filter(t => t.path !== path);
        setActiveTab(remaining.length > 0 ? remaining[remaining.length - 1].path : null);
      }
    }
  }, [openTabs, activeTab]);

  // Save file
  const saveFile = useCallback(async (path: string) => {
    const tab = openTabs.find(t => t.path === path);
    if (!tab) return;

    try {
      const result = await writeFile(path, tab.content);
      if (result.success) {
        setOpenTabs(prev => prev.map(t => t.path === path ? { ...t, modified: false } : t));
        Alert.alert('Success', 'File saved successfully');
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to save file');
    }
  }, [openTabs]);

  // Update content
  const updateContent = useCallback((path: string, content: string) => {
    setOpenTabs(prev => prev.map(t => t.path === path ? { ...t, content, modified: true } : t));
  }, []);

  // Run terminal command
  const runCommand = useCallback(async () => {
    if (!terminalCommand.trim() || runningCommand) return;

    const cmd = terminalCommand.trim();
    setTerminalLines(prev => [...prev, { id: uid('msg'), type: 'command', content: cmd }]);
    setTerminalCommand('');
    setRunningCommand(true);

    try {
      const result = await runSystemCommand(cmd);
      const output = (result.stdout || '') + (result.stderr || '');
      if (output) {
        setTerminalLines(prev => [...prev, {
          id: uid('msg'),
          type: result.stderr ? 'error' : 'output',
          content: output,
        }]);
      }
    } catch (err) {
      setTerminalLines(prev => [...prev, {
        id: uid('msg'),
        type: 'error',
        content: err instanceof Error ? err.message : 'Unknown error',
      }]);
    } finally {
      setRunningCommand(false);
      setTimeout(() => terminalScrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [terminalCommand, runningCommand]);

  // Handle "open folder X in VS Code" intent
  const handleOpenFolderIntent = useCallback(async (input: string): Promise<boolean> => {
    const match = input.match(/open\s+(?:folder\s+|project\s+)?(.+?)\s+(?:in\s+)?(?:vs\s*code|vscode)/i)
      || input.match(/open\s+(.+?)\s+(?:folder|project)\s+(?:in\s+)?(?:vs\s*code|vscode)/i)
      || input.match(/(?:vs\s*code|vscode)\s+(?:open|me)\s+(.+)/i);
    if (!match) return false;

    const folderName = match[1].trim().replace(/['"]/g, '');
    if (!folderName) return false;

    setChatMessages(prev => [...prev, {
      id: uid('system'),
      role: 'system',
      content: `Searching for "${folderName}" on your laptop...`,
    }]);

    try {
      let folderPath = '';

      // Strategy: check common parent directories directly (fast, no recursion)
      const checkCmd = `if exist "%USERPROFILE%\\Desktop\\${folderName}" (echo %USERPROFILE%\\Desktop\\${folderName}) else if exist "%USERPROFILE%\\Documents\\${folderName}" (echo %USERPROFILE%\\Documents\\${folderName}) else if exist "%USERPROFILE%\\Projects\\${folderName}" (echo %USERPROFILE%\\Projects\\${folderName}) else if exist "%USERPROFILE%\\source\\repos\\${folderName}" (echo %USERPROFILE%\\source\\repos\\${folderName}) else if exist "%USERPROFILE%\\${folderName}" (echo %USERPROFILE%\\${folderName}) else (echo __NOT_FOUND__)`;
      const checkResult = await runSystemCommand(checkCmd);

      if (checkResult.stdout?.trim() && !checkResult.stdout.includes('__NOT_FOUND__')) {
        folderPath = checkResult.stdout.trim().split('\n')[0].trim();
      }

      // Fallback: shallow search in Desktop and Documents (depth 1 only — fast)
      if (!folderPath) {
        const fallbackCmd = `dir /b /ad "%USERPROFILE%\\Desktop\\${folderName}" 2>nul && echo %USERPROFILE%\\Desktop\\${folderName}`;
        const fallback = await runSystemCommand(fallbackCmd);
        if (fallback.stdout?.trim() && fallback.exit_code === 0) {
          const lines = fallback.stdout.trim().split('\n');
          const pathLine = lines.find(l => l.includes('\\'));
          if (pathLine) folderPath = pathLine.trim();
        }
      }

      if (!folderPath) {
        setChatMessages(prev => [...prev, {
          id: uid('err'),
          role: 'assistant',
          content: `Could not find folder "${folderName}" on your laptop. Try providing the full path like: open folder C:\\Users\\...\\${folderName} in VS Code`,
          isError: true,
        }]);
        return true;
      }

      await runSystemCommand(`code "${folderPath}"`);

      await loadDirectory(folderPath);

      setChatMessages(prev => [...prev, {
        id: uid('opened'),
        role: 'assistant',
        content: `Opened "${folderName}" in VS Code and set IDE workspace.\n\nPath: ${folderPath}`,
      }]);

    } catch (err) {
      setChatMessages(prev => [...prev, {
        id: uid('err'),
        role: 'assistant',
        content: `Failed to open folder: ${err instanceof Error ? err.message : 'Unknown error'}`,
        isError: true,
      }]);
    }
    return true;
  }, [loadDirectory]);

  // Send agent message
  const sendCopilotMessage = useCallback(async () => {
    if (!chatInput.trim() || loadingChat) return;

    const userMsg: ChatMessage = {
      id: uid('msg'),
      role: 'user',
      content: chatInput,
    };
    setChatMessages(prev => [...prev, userMsg]);
    const currentInput = chatInput;
    setChatInput('');
    setLoadingChat(true);
    setThinkingSteps([]);

    try {
      // Check for "open folder X in VS Code" intent
      const handled = await handleOpenFolderIntent(currentInput);
      if (handled) {
        setLoadingChat(false);
        setTimeout(() => chatScrollRef.current?.scrollToEnd({ animated: true }), 100);
        return;
      }

      let contextMessage = currentInput;
      if (activeTab) {
        const activeFileData = openTabs.find(t => t.path === activeTab);
        if (activeFileData) {
          if (selectedAgent === 'claude_code') {
            // Claude Code uses --cwd for full workspace access.
            // Just pass the user's request directly — Claude Code reads files itself.
            // Only mention the current file if one is open so it knows what to focus on.
            contextMessage = activeTab
              ? `I'm currently looking at ${activeFileData.name}. ${currentInput}`
              : currentInput;
          } else {
            contextMessage = `[Currently editing: ${activeTab}]\n\n${currentInput}`;
          }
        }
      }

      // Jules agent
      if (selectedAgent === 'jules') {
        const thinkingId = uid('jules-thinking');
        setChatMessages(prev => [...prev, {
          id: thinkingId,
          role: 'system',
          content: '🚀 Dispatching task to Jules...',
          isThinking: true,
        }]);

        try {
          const result = await runJulesAgent(currentInput, currentPath);
          setChatMessages(prev => {
            const without = prev.filter(m => m.id !== thinkingId);
            return [...without, {
              id: uid('jules'),
              role: 'assistant',
              content: result.success
                ? `✓ Task dispatched to Jules.\n\n${result.issue_url ? `Issue: ${result.issue_url}` : result.message}`
                : `✗ Failed: ${result.message}`,
              isError: !result.success,
            }];
          });
        } catch (err) {
          setChatMessages(prev => {
            const without = prev.filter(m => m.id !== thinkingId);
            return [...without, {
              id: uid('jules-err'),
              role: 'assistant',
              content: err instanceof Error ? err.message : 'Jules dispatch failed',
              isError: true,
            }];
          });
        }
        setLoadingChat(false);
        setTimeout(() => chatScrollRef.current?.scrollToEnd({ animated: true }), 100);
        return;
      }

      // Streaming agent (FreeLLM or Claude Code)
      const thinkingId = uid('thinking');
      let currentStepNumber = 0;
      let tokenBuffer = '';

      const agentCallbacks = {
        onSessionId: (sid: string) => {
          setAgentSessionId(sid);
        },
        onThinking: (content: string, step?: number) => {
          if (step !== undefined && step !== currentStepNumber) {
            currentStepNumber = step;
          }
          const thinkingMsg: ChatMessage = {
            id: `${thinkingId}-${step || 0}`,
            role: 'system',
            content: content || 'Reasoning...',
            isThinking: true,
            step: step || currentStepNumber,
          };
          setThinkingSteps(prev => {
            const existing = prev.findIndex(m => m.step === (step || currentStepNumber));
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = thinkingMsg;
              return updated;
            }
            return [...prev, thinkingMsg];
          });
        },
        onToolCall: (tool: string, args: Record<string, unknown>, step?: number) => {
          const toolMsg: ChatMessage = {
            id: uid(`tool-${step || 0}`),
            role: 'system',
            content: `Using ${tool}`,
            isToolCall: true,
            toolName: tool,
            toolArgs: args,
            step: step || currentStepNumber,
          };
          setThinkingSteps(prev => [...prev, toolMsg]);
        },
        onToolResult: (tool: string, result: Record<string, unknown>, durationMs?: number, step?: number) => {
          setThinkingSteps(prev => {
            const lastToolIdx = prev.findLastIndex(m => m.isToolCall && m.toolName === tool);
            if (lastToolIdx >= 0) {
              const updated = [...prev];
              updated[lastToolIdx] = {
                ...updated[lastToolIdx],
                toolResult: result,
                durationMs,
                content: `${tool} ${result?.status === 'success' ? '✓' : '✗'}`,
              };
              return updated;
            }
            return prev;
          });
        },
        onToken: (chunk: string) => {
          tokenBuffer += chunk;
        },
        onDone: (fullText: string) => {
          const finalText = fullText || tokenBuffer;
          setChatMessages(prev => [...prev, {
            id: uid('answer'),
            role: 'assistant',
            content: finalText || 'Done.',
          }]);
          setLoadingChat(false);
          setThinkingSteps([]);

          // Refresh current directory and active file
          loadDirectory(currentPath);
          if (activeTab) {
            readFile(activeTab, 1000).then(result => {
              if (!result.error) {
                setOpenTabs(prev => prev.map(t =>
                  t.path === activeTab ? { ...t, content: result.content, modified: false } : t
                ));
              }
            }).catch(() => {});
          }
          setTimeout(() => chatScrollRef.current?.scrollToEnd({ animated: true }), 100);
        },
        onError: (error: string) => {
          setChatMessages(prev => [...prev, {
            id: uid('error'),
            role: 'assistant',
            content: error,
            isError: true,
          }]);
          setLoadingChat(false);
          setThinkingSteps([]);
          setTimeout(() => chatScrollRef.current?.scrollToEnd({ animated: true }), 100);
        },
        onPipelineStart: (content: string) => {
          setThinkingSteps(prev => [...prev, {
            id: uid('pipeline'),
            role: 'system',
            content,
            isThinking: true,
          }]);
        },
        onPhaseStart: (phase: string, content: string) => {
          setThinkingSteps(prev => [...prev, {
            id: uid('phase'),
            role: 'system',
            content: `Phase: ${phase}`,
            isThinking: true,
          }]);
        },
        onPhaseResult: (phase: string, content: string) => {
          setThinkingSteps(prev => [...prev, {
            id: uid('phase-result'),
            role: 'system',
            content: `${phase}: ${content}`,
            isThinking: true,
          }]);
        },
      };

      let abort: () => void;
      if (selectedAgent === 'claude_code') {
        const shouldContinue = claudeSessionStarted.current;
        abort = claudeCodeStream(contextMessage, currentPath, agentCallbacks, shouldContinue);
        claudeSessionStarted.current = true;
      } else {
        abort = ideAgentStream(contextMessage, currentPath, agentCallbacks, { sessionId: agentSessionId });
      }
      abortAgentRef.current = abort;

    } catch (err) {
      setChatMessages(prev => [...prev, {
        id: uid('msg'),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to get AI response'}`,
        isError: true,
      }]);
      setLoadingChat(false);
      setThinkingSteps([]);
      setTimeout(() => chatScrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [chatInput, loadingChat, activeTab, openTabs, selectedAgent, currentPath, agentSessionId, loadDirectory]);

  // Stop agent
  const stopAgent = useCallback(() => {
    if (abortAgentRef.current) {
      abortAgentRef.current();
      abortAgentRef.current = null;
    }
    setLoadingChat(false);
    setThinkingSteps([]);
    setChatMessages(prev => [...prev, {
      id: uid('stopped'),
      role: 'system',
      content: 'Agent stopped by user.',
    }]);
  }, []);

  // Get file icon
  const getIcon = (file: FileInfo): keyof typeof Ionicons.glyphMap => {
    if (file.is_dir) return 'folder';
    const ext = file.extension?.toLowerCase() || '';
    const icons: Record<string, keyof typeof Ionicons.glyphMap> = {
      '.py': 'logo-python',
      '.js': 'logo-javascript',
      '.ts': 'document-text',
      '.tsx': 'logo-react',
      '.jsx': 'logo-react',
      '.json': 'code-slash',
      '.md': 'document-text',
      '.html': 'logo-html5',
      '.css': 'logo-css3',
      '.go': 'code-working',
      '.java': 'code-working',
      '.cpp': 'code-working',
      '.c': 'code-working',
      '.rs': 'code-working',
    };
    return icons[ext] || 'document';
  };

  // Get agent label
  const getAgentLabel = () => {
    switch (selectedAgent) {
      case 'freellm': return 'FreeLLM';
      case 'claude_code': return 'Claude Code';
      case 'jules': return 'Jules';
    }
  };

  const activeFile = openTabs.find(t => t.path === activeTab);
  const folderName = currentPath.split(/[/\\]/).filter(Boolean).pop() || 'No folder open';

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {/* Top Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.agentSelector}
          onPress={() => setShowAgentPicker(!showAgentPicker)}
        >
          <Text style={styles.agentSelectorText}>{getAgentLabel()}</Text>
          <Ionicons name={showAgentPicker ? 'chevron-up' : 'chevron-down'} size={10} color={Colors.primary} />
        </TouchableOpacity>

        {loadingChat && (
          <TouchableOpacity style={styles.stopButton} onPress={stopAgent}>
            <Ionicons name="stop-circle" size={20} color={Colors.red} />
          </TouchableOpacity>
        )}

        <TouchableOpacity style={styles.headerIcon} onPress={startNewSession}>
          <Ionicons name="add-circle-outline" size={20} color={Colors.primary} />
        </TouchableOpacity>

        <View style={{ flex: 1 }} />

        <TouchableOpacity style={styles.headerIcon} onPress={openFilesDrawer}>
          <Ionicons name="documents-outline" size={20} color={Colors.foreground} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.headerIcon} onPress={openEditorDrawer}>
          <Ionicons name="code-slash-outline" size={20} color={Colors.foreground} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.headerIcon} onPress={openTerminalDrawer}>
          <Ionicons name="terminal-outline" size={20} color={Colors.foreground} />
        </TouchableOpacity>
      </View>

      {/* Agent Picker Dropdown */}
      {showAgentPicker && (
        <View style={styles.agentPickerMenu}>
          <TouchableOpacity
            style={[styles.agentPickerItem, selectedAgent === 'freellm' && styles.agentPickerItemActive]}
            onPress={() => { setSelectedAgent('freellm'); setShowAgentPicker(false); }}
          >
            <Ionicons name="infinite" size={18} color={selectedAgent === 'freellm' ? Colors.primary : Colors.foreground} />
            <View style={{ flex: 1, marginLeft: Spacing.md }}>
              <Text style={[styles.agentPickerName, selectedAgent === 'freellm' && styles.agentPickerNameActive]}>FreeLLM</Text>
              <Text style={styles.agentPickerDesc}>Free AI agent with full workspace access</Text>
            </View>
            {selectedAgent === 'freellm' && <Ionicons name="checkmark-circle" size={18} color={Colors.primary} />}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.agentPickerItem, selectedAgent === 'claude_code' && styles.agentPickerItemActive]}
            onPress={() => { setSelectedAgent('claude_code'); setShowAgentPicker(false); }}
          >
            <Ionicons name="terminal" size={18} color={selectedAgent === 'claude_code' ? Colors.primary : Colors.foreground} />
            <View style={{ flex: 1, marginLeft: Spacing.md }}>
              <Text style={[styles.agentPickerName, selectedAgent === 'claude_code' && styles.agentPickerNameActive]}>Claude Code</Text>
              <Text style={styles.agentPickerDesc}>Anthropic's CLI agent on your laptop</Text>
            </View>
            {selectedAgent === 'claude_code' && <Ionicons name="checkmark-circle" size={18} color={Colors.primary} />}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.agentPickerItem, selectedAgent === 'jules' && styles.agentPickerItemActive]}
            onPress={() => { setSelectedAgent('jules'); setShowAgentPicker(false); }}
          >
            <Ionicons name="git-branch" size={18} color={selectedAgent === 'jules' ? Colors.primary : Colors.foreground} />
            <View style={{ flex: 1, marginLeft: Spacing.md }}>
              <Text style={[styles.agentPickerName, selectedAgent === 'jules' && styles.agentPickerNameActive]}>Jules</Text>
              <Text style={styles.agentPickerDesc}>GitHub's async coding agent via issues</Text>
            </View>
            {selectedAgent === 'jules' && <Ionicons name="checkmark-circle" size={18} color={Colors.primary} />}
          </TouchableOpacity>
        </View>
      )}

      {/* Chat Messages (Main Content) */}
      <ScrollView
        ref={chatScrollRef}
        style={styles.chatMessages}
        contentContainerStyle={styles.chatMessagesContent}
        onContentSizeChange={() => chatScrollRef.current?.scrollToEnd({ animated: true })}
      >
        {chatMessages.map(msg => {
          if (msg.role === 'assistant' && !msg.isError && msg.content.length > 120) {
            const isExpanded = msg.expanded ?? false;
            const preview = msg.content.slice(0, 100).replace(/\n/g, ' ') + '...';
            return (
              <TouchableOpacity
                key={msg.id}
                activeOpacity={0.8}
                onPress={() => {
                  setChatMessages(prev => prev.map(m =>
                    m.id === msg.id ? { ...m, expanded: !m.expanded } : m
                  ));
                }}
                style={[styles.chatMessage, styles.chatMessageAssistant]}
              >
                {!isExpanded ? (
                  <View style={styles.collapsedResponse}>
                    <View style={styles.collapsedHeader}>
                      <Ionicons name="sparkles" size={14} color={Colors.primary} />
                      <Text style={styles.collapsedLabel}>Claude Code</Text>
                      <Ionicons name="chevron-down" size={14} color={Colors.muted} />
                    </View>
                    <Text style={styles.collapsedPreview} numberOfLines={2}>{preview}</Text>
                  </View>
                ) : (
                  <View style={styles.expandedResponse}>
                    <View style={styles.expandedHeader}>
                      <Ionicons name="sparkles" size={14} color={Colors.primary} />
                      <Text style={styles.collapsedLabel}>Claude Code</Text>
                      <Ionicons name="chevron-up" size={14} color={Colors.muted} />
                    </View>
                    <FormattedResponse content={msg.content} />
                  </View>
                )}
              </TouchableOpacity>
            );
          }
          return (
            <View key={msg.id} style={[
              styles.chatMessage,
              msg.role === 'user' && styles.chatMessageUser,
              msg.role === 'assistant' && styles.chatMessageAssistant,
              msg.role === 'system' && styles.chatMessageSystem,
            ]}>
              <Text style={[styles.chatMessageText, msg.isError && styles.chatMessageError]}>
                {msg.content}
              </Text>
            </View>
          );
        })}

        {/* Thinking steps */}
        {thinkingSteps.length > 0 && (
          <View style={styles.thinkingContainer}>
            <TouchableOpacity
              style={styles.thinkingHeader}
              onPress={() => setShowThinkingDetails(!showThinkingDetails)}
            >
              <View style={styles.thinkingPulse}>
                <ActivityIndicator size="small" color={Colors.primary} />
              </View>
              <Text style={styles.thinkingHeaderText}>{loadingChat ? 'Processing...' : `${thinkingSteps.length} steps`}</Text>
              <Ionicons name={showThinkingDetails ? 'chevron-up' : 'chevron-down'} size={16} color={Colors.primary} />
            </TouchableOpacity>

            {showThinkingDetails && thinkingSteps.map(step => {
              if (step.isThinking) {
                return (
                  <View key={step.id} style={styles.thinkingStep}>
                    <Ionicons name="bulb-outline" size={12} color={Colors.yellow} />
                    <Text style={styles.thinkingStepText}>{step.content}</Text>
                  </View>
                );
              }
              if (step.isToolCall) {
                return (
                  <View key={step.id} style={styles.toolCallCard}>
                    <View style={styles.toolCallHeader}>
                      <Ionicons name="construct-outline" size={14} color={Colors.cyan} />
                      <Text style={styles.toolCallName}>{step.toolName}</Text>
                      {step.toolResult && (
                        <View style={styles.toolCallStatus}>
                          <Ionicons
                            name={step.toolResult.status === 'success' ? 'checkmark-circle' : 'close-circle'}
                            size={12}
                            color={step.toolResult.status === 'success' ? Colors.green : Colors.red}
                          />
                          {step.durationMs && (
                            <Text style={styles.toolCallDuration}>{step.durationMs}ms</Text>
                          )}
                        </View>
                      )}
                    </View>
                    {step.toolArgs && Object.keys(step.toolArgs).length > 0 && (
                      <Text style={styles.toolCallArgs} numberOfLines={2}>
                        {Object.entries(step.toolArgs)
                          .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
                          .join(', ')}
                      </Text>
                    )}
                  </View>
                );
              }
              return null;
            })}
          </View>
        )}
      </ScrollView>

      {/* Chat Input */}
      <View style={styles.chatInputContainer}>
        <TextInput
          style={styles.chatInput}
          value={chatInput}
          onChangeText={setChatInput}
          placeholder="Ask me anything about this codebase..."
          placeholderTextColor={Colors.mutedDark}
          multiline
          maxLength={2000}
          editable={!loadingChat}
        />
        <TouchableOpacity
          style={[styles.chatSendButton, (!chatInput.trim() || loadingChat) && styles.chatSendButtonDisabled]}
          onPress={sendCopilotMessage}
          disabled={!chatInput.trim() || loadingChat}
        >
          <Ionicons name="send" size={18} color={Colors.foreground} />
        </TouchableOpacity>
      </View>


      {/* Files Drawer Modal */}
      <Modal visible={showFilesDrawer} animationType="slide" transparent>
        <TouchableOpacity style={styles.drawerBackdrop} activeOpacity={1} onPress={closeFilesDrawer} />
        <View style={styles.drawerContainer}>
          <View style={styles.drawerHandle} />
          <View style={styles.drawerHeader}>
            <Text style={styles.drawerTitle}>EXPLORER</Text>
            <View style={{ flexDirection: 'row', gap: Spacing.md }}>
              <TouchableOpacity onPress={() => setShowOpenFolderModal(true)}>
                <Ionicons name="folder-open-outline" size={18} color={Colors.primary} />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => loadDirectory(currentPath)}>
                <Ionicons name="refresh" size={18} color={Colors.muted} />
              </TouchableOpacity>
              <TouchableOpacity onPress={closeFilesDrawer}>
                <Ionicons name="close" size={20} color={Colors.muted} />
              </TouchableOpacity>
            </View>
          </View>

          <TouchableOpacity style={styles.breadcrumb} onPress={goUp}>
            <Ionicons name="chevron-up" size={14} color={Colors.muted} />
            <Text style={styles.breadcrumbText} numberOfLines={1}>{folderName}</Text>
          </TouchableOpacity>

          {loadingFiles ? (
            <View style={styles.centerLoader}>
              <ActivityIndicator size="small" color={Colors.primary} />
            </View>
          ) : (
            <FlatList
              data={files}
              keyExtractor={item => item.path}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.fileItem, activeTab === item.path && styles.fileItemActive]}
                  onPress={() => openFile(item)}
                >
                  <Ionicons
                    name={getIcon(item)}
                    size={16}
                    color={item.is_dir ? Colors.yellow : Colors.primary}
                    style={{ marginRight: Spacing.sm }}
                  />
                  <Text style={styles.fileItemText} numberOfLines={1}>{item.name}</Text>
                </TouchableOpacity>
              )}
            />
          )}
        </View>
      </Modal>

      {/* Editor Drawer Modal */}
      <Modal visible={showEditorDrawer} animationType="slide" transparent>
        <TouchableOpacity style={styles.drawerBackdrop} activeOpacity={1} onPress={closeEditorDrawer} />
        <View style={styles.drawerContainer}>
          <View style={styles.drawerHandle} />
          <View style={styles.drawerHeader}>
            <Text style={styles.drawerTitle}>EDITOR</Text>
            <TouchableOpacity onPress={closeEditorDrawer}>
              <Ionicons name="close" size={20} color={Colors.muted} />
            </TouchableOpacity>
          </View>

          {/* Tab Bar */}
          <View style={styles.tabBar}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
              {openTabs.map(tab => (
                <View key={tab.path} style={[styles.tab, activeTab === tab.path && styles.tabActive]}>
                  <TouchableOpacity
                    style={styles.tabButton}
                    onPress={() => setActiveTab(tab.path)}
                  >
                    <Text style={[styles.tabText, activeTab === tab.path && styles.tabTextActive]} numberOfLines={1}>
                      {tab.modified && <Text style={styles.modifiedDot}>● </Text>}
                      {tab.name}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.tabClose} onPress={() => closeTab(tab.path)}>
                    <Ionicons name="close" size={14} color={Colors.muted} />
                  </TouchableOpacity>
                </View>
              ))}
            </ScrollView>
            {activeTab && (
              <TouchableOpacity style={styles.saveButton} onPress={() => saveFile(activeTab)}>
                <Ionicons name="save-outline" size={18} color={Colors.primary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Editor */}
          <View style={styles.editorContainer}>
            {activeFile ? (
              <ScrollView style={styles.editor}>
                <View style={styles.codeWrapper}>
                  <View style={styles.lineNumbers}>
                    {activeFile.content.split('\n').map((_, idx) => (
                      <Text key={idx} style={styles.lineNumber}>{idx + 1}</Text>
                    ))}
                  </View>
                  <TextInput
                    style={styles.codeInput}
                    value={activeFile.content}
                    onChangeText={(text) => updateContent(activeFile.path, text)}
                    multiline
                    autoCapitalize="none"
                    autoCorrect={false}
                    spellCheck={false}
                    scrollEnabled={false}
                  />
                </View>
              </ScrollView>
            ) : (
              <View style={styles.emptyEditor}>
                <Ionicons name="code-slash-outline" size={64} color={Colors.mutedDark} />
                <Text style={styles.emptyText}>No file open</Text>
              </View>
            )}
          </View>
        </View>
      </Modal>

      {/* Terminal Drawer Modal */}
      <Modal visible={showTerminalDrawer} animationType="slide" transparent>
        <TouchableOpacity style={styles.drawerBackdrop} activeOpacity={1} onPress={closeTerminalDrawer} />
        <View style={styles.drawerContainer}>
          <View style={styles.drawerHandle} />
          <View style={styles.drawerHeader}>
            <Ionicons name="terminal" size={16} color={Colors.green} style={{ marginRight: Spacing.xs }} />
            <Text style={styles.drawerTitle}>TERMINAL</Text>
            <View style={{ flex: 1 }} />
            <TouchableOpacity onPress={() => setTerminalLines([{ id: '0', type: 'output', content: 'Terminal cleared' }])}>
              <Ionicons name="trash-outline" size={16} color={Colors.muted} />
            </TouchableOpacity>
            <TouchableOpacity onPress={closeTerminalDrawer} style={{ marginLeft: Spacing.md }}>
              <Ionicons name="close" size={20} color={Colors.muted} />
            </TouchableOpacity>
          </View>

          <ScrollView
            ref={terminalScrollRef}
            style={styles.terminalOutput}
            onContentSizeChange={() => terminalScrollRef.current?.scrollToEnd({ animated: true })}
          >
            {terminalLines.map(line => (
              <View key={line.id} style={styles.terminalLine}>
                {line.type === 'command' && <Text style={styles.terminalPrompt}>$ </Text>}
                <Text style={[
                  styles.terminalText,
                  line.type === 'command' && styles.terminalTextCommand,
                  line.type === 'error' && styles.terminalTextError,
                ]}>{line.content}</Text>
              </View>
            ))}
          </ScrollView>

          <View style={styles.terminalInput}>
            <Text style={styles.terminalPrompt}>$</Text>
            <TextInput
              style={styles.terminalTextInput}
              value={terminalCommand}
              onChangeText={setTerminalCommand}
              onSubmitEditing={runCommand}
              placeholder="Enter command..."
              placeholderTextColor={Colors.mutedDark}
              editable={!runningCommand}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity onPress={runCommand} disabled={runningCommand} style={styles.terminalSendBtn}>
              {runningCommand ? (
                <ActivityIndicator size="small" color={Colors.primary} />
              ) : (
                <Ionicons name="send" size={16} color={Colors.primary} />
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Open Folder Modal */}
      <Modal visible={showOpenFolderModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>Open Folder</Text>
            <TextInput
              style={styles.modalInput}
              value={folderInput}
              onChangeText={setFolderInput}
              placeholder="Enter folder path..."
              placeholderTextColor={Colors.mutedDark}
              autoCapitalize="none"
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalButtonSecondary]}
                onPress={() => setShowOpenFolderModal(false)}
              >
                <Text style={styles.modalButtonTextSecondary}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalButtonPrimary]}
                onPress={() => {
                  loadDirectory(folderInput);
                  setShowOpenFolderModal(false);
                }}
              >
                <Text style={styles.modalButtonText}>Open</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'column',
    backgroundColor: Colors.background,
  },

  // Top Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: Spacing.md,
  },
  headerIcon: {
    padding: Spacing.xs,
  },


  // Drawer Modal
  drawerBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  drawerContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: '80%',
    backgroundColor: Colors.surface,
    borderTopLeftRadius: BorderRadius.lg,
    borderTopRightRadius: BorderRadius.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 10,
  },
  drawerHandle: {
    width: 40,
    height: 4,
    backgroundColor: Colors.border,
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  drawerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  drawerTitle: {
    fontSize: FontSize.sm,
    fontWeight: '700',
    color: Colors.foreground,
    letterSpacing: 0.5,
    flex: 1,
  },

  // Files
  breadcrumb: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  breadcrumbText: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.foreground,
    marginLeft: Spacing.xs,
    flex: 1,
  },
  fileItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  fileItemActive: {
    backgroundColor: Colors.primaryBg,
    borderLeftWidth: 2,
    borderLeftColor: Colors.primary,
  },
  fileItemText: {
    fontSize: FontSize.sm,
    color: Colors.foreground,
    flex: 1,
  },
  // Editor Tab Bar
  tabBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    height: 36,
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    height: '100%',
    borderRightWidth: 1,
    borderRightColor: Colors.border,
    maxWidth: 180,
  },
  tabActive: {
    backgroundColor: Colors.background,
    borderBottomWidth: 2,
    borderBottomColor: Colors.primary,
  },
  tabButton: {
    flex: 1,
  },
  tabText: {
    fontSize: FontSize.sm,
    color: Colors.muted,
  },
  tabTextActive: {
    color: Colors.foreground,
    fontWeight: '500',
  },
  modifiedDot: {
    color: Colors.primary,
  },
  tabClose: {
    marginLeft: Spacing.sm,
    padding: 2,
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    gap: Spacing.xs,
  },
  saveButtonText: {
    fontSize: FontSize.xs,
    color: Colors.primary,
    fontWeight: '600',
  },

  // Editor
  editorContainer: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  editor: {
    flex: 1,
  },
  codeWrapper: {
    flexDirection: 'row',
    padding: Spacing.md,
  },
  lineNumbers: {
    paddingRight: Spacing.md,
    paddingTop: 2,
  },
  lineNumber: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.sm,
    color: Colors.mutedDark,
    lineHeight: 20,
    textAlign: 'right',
    minWidth: 32,
  },
  codeInput: {
    flex: 1,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.sm,
    color: Colors.foreground,
    lineHeight: 20,
    textAlignVertical: 'top',
    minHeight: 300,
  },
  emptyEditor: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
  },
  emptyText: {
    fontSize: FontSize.md,
    color: Colors.muted,
    marginTop: Spacing.lg,
  },
  primaryButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  primaryButtonText: {
    color: Colors.foreground,
    fontSize: FontSize.md,
    fontWeight: '600',
  },

  // Terminal
  terminalPanel: {
    flex: 1,
  },
  terminalOutput: {
    flex: 1,
    padding: Spacing.md,
  },
  terminalLine: {
    flexDirection: 'row',
    marginBottom: 2,
  },
  terminalPrompt: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.sm,
    color: Colors.green,
    marginRight: Spacing.xs,
  },
  terminalText: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.sm,
    color: Colors.foreground,
    flex: 1,
  },
  terminalTextCommand: {
    color: Colors.greenLight,
    fontWeight: '500',
  },
  terminalTextError: {
    color: Colors.red,
  },
  terminalInput: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    gap: Spacing.sm,
  },
  terminalTextInput: {
    flex: 1,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.sm,
    color: Colors.foreground,
  },
  terminalSendBtn: {
    padding: Spacing.sm,
  },

  // Agent Selector
  agentSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.primaryBg,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    borderColor: Colors.primary + '40',
    gap: Spacing.xs,
  },
  agentSelectorText: {
    fontSize: FontSize.sm,
    color: Colors.primary,
    fontWeight: '600',
  },
  stopButton: {
    padding: Spacing.xs,
  },
  agentPickerMenu: {
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    overflow: 'hidden',
  },
  agentPickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  agentPickerItemActive: {
    backgroundColor: Colors.primaryBg,
  },
  agentPickerName: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.foreground,
  },
  agentPickerNameActive: {
    color: Colors.primary,
  },
  agentPickerDesc: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 2,
  },

  // Chat Messages
  chatMessages: {
    flex: 1,
  },
  chatMessagesContent: {
    padding: Spacing.md,
  },
  chatMessage: {
    marginBottom: Spacing.md,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    maxWidth: '95%',
  },
  chatMessageUser: {
    backgroundColor: Colors.primaryBg,
    alignSelf: 'flex-end',
    borderWidth: 1,
    borderColor: Colors.primary + '40',
  },
  chatMessageAssistant: {
    backgroundColor: Colors.card,
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  chatMessageSystem: {
    backgroundColor: Colors.surface,
    alignSelf: 'center',
    borderWidth: 1,
    borderColor: Colors.borderLight,
  },
  chatMessageText: {
    fontSize: FontSize.sm,
    color: Colors.foreground,
    lineHeight: 20,
  },
  chatMessageError: {
    color: Colors.red,
  },
  collapsedResponse: {
    gap: 6,
  },
  collapsedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  collapsedLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.primary,
    flex: 1,
  },
  collapsedPreview: {
    fontSize: 12,
    color: Colors.muted,
    lineHeight: 18,
  },
  expandedResponse: {
    gap: 8,
  },
  expandedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderLight,
  },

  // Thinking
  thinkingContainer: {
    marginBottom: Spacing.md,
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.borderLight,
    overflow: 'hidden',
  },
  thinkingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  thinkingPulse: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primaryBg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  thinkingHeaderText: {
    fontSize: FontSize.sm,
    color: Colors.primary,
    fontWeight: '600',
    flex: 1,
  },
  thinkingStep: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.md,
    paddingTop: Spacing.sm,
    gap: Spacing.sm,
  },
  thinkingStepText: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    fontStyle: 'italic',
    flex: 1,
  },
  toolCallCard: {
    padding: Spacing.md,
    paddingTop: Spacing.sm,
    backgroundColor: Colors.codeBg,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  toolCallHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  toolCallName: {
    fontSize: FontSize.xs,
    fontWeight: '700',
    color: Colors.cyan,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    flex: 1,
  },
  toolCallStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  toolCallDuration: {
    fontSize: FontSize.xs,
    color: Colors.mutedDark,
  },
  toolCallArgs: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: Spacing.xs,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },

  // Chat Input
  chatInputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    gap: Spacing.sm,
  },
  chatInput: {
    flex: 1,
    backgroundColor: Colors.input,
    color: Colors.foreground,
    fontSize: FontSize.sm,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    maxHeight: 100,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  chatSendButton: {
    backgroundColor: Colors.primary,
    width: 40,
    height: 40,
    borderRadius: BorderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatSendButtonDisabled: {
    backgroundColor: Colors.mutedDark,
    opacity: 0.5,
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.xl,
  },
  modal: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.xl,
    width: '100%',
    maxWidth: 400,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalTitle: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    color: Colors.foreground,
    marginBottom: Spacing.lg,
  },
  modalInput: {
    backgroundColor: Colors.input,
    color: Colors.foreground,
    fontSize: FontSize.md,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    marginBottom: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: Spacing.md,
  },
  modalButton: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  modalButtonPrimary: {
    backgroundColor: Colors.primary,
  },
  modalButtonSecondary: {
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalButtonText: {
    color: Colors.foreground,
    fontWeight: '600',
    fontSize: FontSize.md,
  },
  modalButtonTextSecondary: {
    color: Colors.muted,
    fontWeight: '600',
    fontSize: FontSize.md,
  },

  // Utility
  centerLoader: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: Spacing.xxl,
  },
});
