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
  Dimensions,
  Modal,
  Animated,
  useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  listDirectory,
  readFile,
  writeFile,
  runSystemCommand,
  copilotEdit,
  askAI,
  getCurrentWorkingDirectory,
  getAIProviders,
  runIDEAgentAction,
  FileInfo,
  CopilotEditResponse,
} from '@/lib/api';
import configManager from '@/lib/config';

// VS Code Dark Theme Colors
const VSColors = {
  bg: '#1e1e1e',
  sidebar: '#252526',
  activityBar: '#333333',
  editor: '#1e1e1e',
  terminal: '#1e1e1e',
  border: '#3c3c3c',
  text: '#cccccc',
  textMuted: '#808080',
  accent: '#007acc',
  accentLight: '#1177bb',
  success: '#4ec9b0',
  error: '#f14c4c',
  warning: '#cca700',
  lineNumber: '#858585',
  selection: '#264f78',
  hover: '#2a2d2e',
  inputBg: '#3c3c3c',
  white: '#ffffff',
};

interface OpenTab {
  path: string;
  name: string;
  content: string;
  language: string;
  modified: boolean;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isError?: boolean;
  diff?: string;
  filePath?: string;
}

// Responsive breakpoints
const MOBILE_BREAKPOINT = 768;
const TABLET_BREAKPOINT = 1024;

export default function IDEScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ openPath?: string }>();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();

  // Responsive helpers
  const isMobile = windowWidth < MOBILE_BREAKPOINT;
  const isTablet = windowWidth >= MOBILE_BREAKPOINT && windowWidth < TABLET_BREAKPOINT;

  // State
  const [currentPath, setCurrentPath] = useState(params.openPath || '.');
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [showHidden, setShowHidden] = useState(false);

  // Terminal state
  const [terminalOutput, setTerminalOutput] = useState('$ Welcome to JARVIS Terminal\n');
  const [terminalCommand, setTerminalCommand] = useState('');
  const [runningCommand, setRunningCommand] = useState(false);

  // Copilot Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content:
        'AI assistant ready.\n\n' +
        '• Chat: ask anything (works without a file open)\n' +
        '• Agent mode: "add, commit and push to main" runs git on your paired laptop\n' +
        '• Code edit: open a file, then say "edit …" or "fix …"\n\n' +
        'Configure AI in Settings (GitHub token, OpenAI, or Ollama).',
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [loadingChat, setLoadingChat] = useState(false);
  const [pendingEdit, setPendingEdit] = useState<CopilotEditResponse | null>(null);
  const [agentMode, setAgentMode] = useState(true);
  const [aiProviderLabel, setAiProviderLabel] = useState('');

  // UI state - responsive
  const [sidebarCollapsed, setSidebarCollapsed] = useState(isMobile);
  const [showCopilotPanel, setShowCopilotPanel] = useState(!isMobile);
  const [showTerminal, setShowTerminal] = useState(!isMobile);
  const [activeBottomPanel, setActiveBottomPanel] = useState<'terminal' | 'copilot' | null>(isMobile ? null : 'terminal');
  const [sidebarWidth] = useState(new Animated.Value(isMobile ? 0 : 180));
  const [showOpenFolder, setShowOpenFolder] = useState(false);
  const [folderInput, setFolderInput] = useState(currentPath);
  const [activePanel, setActivePanel] = useState<'files' | 'search' | 'git'>('files');

  const terminalScrollRef = useRef<ScrollView>(null);
  const chatScrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    void (async () => {
      try {
        await configManager.init();
        const p = await getAIProviders();
        const cur = p.providers?.[p.current];
        setAiProviderLabel(
          cur?.available
            ? `${p.current} ✓`
            : `${p.current} (fallback)`
        );
      } catch {
        setAiProviderLabel('');
      }
    })();
  }, []);

  // Initialize current path dynamically
  useEffect(() => {
    const initializePath = async () => {
      if (!params.openPath) {
        try {
          const workingDir = await getCurrentWorkingDirectory();
          setCurrentPath(workingDir);
          setFolderInput(workingDir);
          loadDirectory(workingDir);
        } catch (error) {
          console.warn('Failed to get working directory, using fallback');
          loadDirectory('.');
        }
      } else {
        loadDirectory(params.openPath);
      }
    };

    initializePath();
  }, []);

  // Toggle sidebar with animation
  const toggleSidebar = useCallback(() => {
    const newCollapsed = !sidebarCollapsed;
    setSidebarCollapsed(newCollapsed);
    Animated.timing(sidebarWidth, {
      toValue: newCollapsed ? 0 : (isMobile ? windowWidth * 0.7 : 180),
      duration: 200,
      useNativeDriver: false,
    }).start();
  }, [sidebarCollapsed, isMobile, windowWidth, sidebarWidth]);

  // Toggle mobile bottom panels
  const toggleBottomPanel = useCallback((panel: 'terminal' | 'copilot') => {
    if (isMobile) {
      setActiveBottomPanel(prev => prev === panel ? null : panel);
    } else {
      if (panel === 'terminal') setShowTerminal(prev => !prev);
      if (panel === 'copilot') setShowCopilotPanel(prev => !prev);
    }
  }, [isMobile]);

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
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoadingFiles(false);
    }
  }, [showHidden]);

  useEffect(() => {
    if (params.openPath) {
      setCurrentPath(params.openPath);
      setFolderInput(params.openPath);
      loadDirectory(params.openPath);
    }
  }, [params.openPath]);

  // Open file in tab
  const openFile = async (file: FileInfo) => {
    if (file.is_dir) {
      loadDirectory(file.path);
      return;
    }

    // Check if already open
    const existing = openTabs.find(t => t.path === file.path);
    if (existing) {
      setActiveTab(file.path);
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
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to open file');
    } finally {
      setLoadingContent(false);
    }
  };

  // Close tab
  const closeTab = (path: string) => {
    const tab = openTabs.find(t => t.path === path);
    if (tab?.modified) {
      Alert.alert('Unsaved Changes', 'Save before closing?', [
        { text: 'Discard', style: 'destructive', onPress: () => removeTab(path) },
        { text: 'Cancel', style: 'cancel' },
        { text: 'Save', onPress: async () => { await saveFile(path); removeTab(path); } },
      ]);
    } else {
      removeTab(path);
    }
  };

  const removeTab = (path: string) => {
    setOpenTabs(prev => prev.filter(t => t.path !== path));
    if (activeTab === path) {
      const remaining = openTabs.filter(t => t.path !== path);
      setActiveTab(remaining.length > 0 ? remaining[remaining.length - 1].path : null);
    }
  };

  // Save file
  const saveFile = async (path: string) => {
    const tab = openTabs.find(t => t.path === path);
    if (!tab) return;

    try {
      const result = await writeFile(path, tab.content);
      if (result.success) {
        setOpenTabs(prev => prev.map(t => t.path === path ? { ...t, modified: false } : t));
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to save');
    }
  };

  // Update file content
  const updateContent = (path: string, content: string) => {
    setOpenTabs(prev => prev.map(t => t.path === path ? { ...t, content, modified: true } : t));
  };

  // Run terminal command
  const runCommand = async () => {
    if (!terminalCommand.trim() || runningCommand) return;

    const cmd = terminalCommand.trim();
    setTerminalOutput(prev => `${prev}$ ${cmd}\n`);
    setTerminalCommand('');
    setRunningCommand(true);

    try {
      const result = await runSystemCommand(cmd);
      let output = '';
      if (result.stdout) output += result.stdout;
      if (result.stderr) output += result.stderr;
      setTerminalOutput(prev => `${prev}${output}\n`);
    } catch (err) {
      setTerminalOutput(prev => `${prev}Error: ${err instanceof Error ? err.message : 'Unknown'}\n`);
    } finally {
      setRunningCommand(false);
      terminalScrollRef.current?.scrollToEnd({ animated: true });
    }
  };

  // Send Copilot / Agent message
  const sendCopilotMessage = async () => {
    if (!chatInput.trim() || loadingChat) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: chatInput,
    };
    setChatMessages(prev => [...prev, userMsg]);
    const currentInput = chatInput;
    setChatInput('');
    setLoadingChat(true);

    try {
      if (agentMode) {
        await configManager.init();
        if (!configManager.pairingCode) {
          setChatMessages(prev => [
            ...prev,
            {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content:
                'Agent mode needs a paired laptop. Open Settings, enter your pairing code, and keep the PC agent running.',
              isError: true,
            },
          ]);
          return;
        }
        const agentResult = await runIDEAgentAction(currentInput, currentPath);
        if (agentResult.handled) {
          setChatMessages(prev => [
            ...prev,
            {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: agentResult.message,
              isError: !agentResult.success,
            },
          ]);
          return;
        }
      }

      const isEditRequest =
        /\b(edit|change|modify|update|fix|refactor|rewrite)\b/i.test(currentInput) && activeTab;

      if (isEditRequest && activeTab) {
        // Use Copilot editing for code modifications
        const result = await copilotEdit(activeTab, currentInput, false);

        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: result.success
            ? 'Here are my suggested changes. You can apply them if they look good.'
            : result.message,
          isError: !result.success,
          diff: result.success ? result.diff : undefined,
          filePath: activeTab,
        };

        setChatMessages(prev => [...prev, assistantMsg]);

        // If successful, show the pending edit
        if (result.success) {
          setPendingEdit(result);
        }
      } else {
        // Use general AI chat for questions, explanations, etc.
        const fileContent = activeTab ? (await readFile(activeTab)).content : undefined;
        const fileLanguage = activeTab ? activeTab.split('.').pop() : undefined;

        const aiResponse = await askAI(
          currentInput,
          fileContent,
          activeTab ?? undefined,
          fileLanguage
        );

        const assistantMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: aiResponse.status === 'success'
            ? aiResponse.response
            : aiResponse.error || 'AI is not available. Check your AI provider settings.',
          isError: aiResponse.status !== 'success',
        };

        setChatMessages(prev => [...prev, assistantMsg]);
      }
    } catch (err) {
      setChatMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to get AI response. Check your connection and AI provider settings.'}`,
        isError: true,
      }]);
    } finally {
      setLoadingChat(false);
      chatScrollRef.current?.scrollToEnd({ animated: true });
    }
  };

  // Apply Copilot edit
  const applyEdit = () => {
    if (!pendingEdit || !activeTab) return;

    setOpenTabs(prev => prev.map(t =>
      t.path === activeTab ? { ...t, content: pendingEdit.suggested_content, modified: true } : t
    ));

    setChatMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: 'Changes applied! Review and save when ready.',
    }]);

    setPendingEdit(null);
  };

  // Helper function to get path separator
  const getPathSeparator = (path: string) => {
    return path.includes('\\') ? '\\' : '/';
  };

  // Go to parent
  const goUp = () => {
    const separator = getPathSeparator(currentPath);
    const parent = currentPath.substring(0, currentPath.lastIndexOf(separator));
    if (parent && parent !== currentPath) {
      loadDirectory(parent);
    }
  };

  // Get file icon
  const getIcon = (file: FileInfo): keyof typeof Ionicons.glyphMap => {
    if (file.is_dir) return 'folder';
    const ext = file.extension.toLowerCase();
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
    };
    return icons[ext] || 'document';
  };

  const activeFile = openTabs.find(t => t.path === activeTab);

  // Responsive sidebar width
  const getSidebarStyle = () => {
    if (isMobile) {
      return sidebarCollapsed ? { width: 0, display: 'none' as const } : {
        position: 'absolute' as const,
        left: 48,
        top: 0,
        bottom: 0,
        width: windowWidth * 0.7,
        zIndex: 100,
      };
    }
    return { width: sidebarCollapsed ? 0 : 180 };
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {/* Activity Bar */}
      <View style={[styles.activityBar, isMobile && styles.activityBarMobile]}>
        {/* Sidebar Toggle */}
        <TouchableOpacity
          style={styles.activityIcon}
          onPress={toggleSidebar}
        >
          <Ionicons
            name={sidebarCollapsed ? "menu" : "close"}
            size={24}
            color={VSColors.white}
          />
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.activityIcon, activePanel === 'files' && styles.activityIconActive]}
          onPress={() => { setActivePanel('files'); if (sidebarCollapsed) toggleSidebar(); }}
        >
          <Ionicons name="documents" size={24} color={activePanel === 'files' ? VSColors.white : VSColors.textMuted} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.activityIcon, activePanel === 'search' && styles.activityIconActive]}
          onPress={() => { setActivePanel('search'); if (sidebarCollapsed) toggleSidebar(); }}
        >
          <Ionicons name="search" size={24} color={activePanel === 'search' ? VSColors.white : VSColors.textMuted} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.activityIcon, activePanel === 'git' && styles.activityIconActive]}
          onPress={() => { setActivePanel('git'); if (sidebarCollapsed) toggleSidebar(); }}
        >
          <Ionicons name="git-branch" size={24} color={activePanel === 'git' ? VSColors.white : VSColors.textMuted} />
        </TouchableOpacity>

        <View style={{ flex: 1 }} />

        {/* Bottom Actions */}
        <TouchableOpacity
          style={[styles.activityIcon, activeBottomPanel === 'terminal' && styles.activityIconActive]}
          onPress={() => toggleBottomPanel('terminal')}
        >
          <Ionicons name="terminal" size={24} color={activeBottomPanel === 'terminal' || showTerminal ? VSColors.accent : VSColors.textMuted} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.activityIcon, activeBottomPanel === 'copilot' && styles.activityIconActive]}
          onPress={() => toggleBottomPanel('copilot')}
        >
          <Ionicons name="sparkles" size={24} color={activeBottomPanel === 'copilot' || showCopilotPanel ? VSColors.accent : VSColors.textMuted} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.activityIcon} onPress={() => setShowOpenFolder(true)}>
          <Ionicons name="folder-open" size={24} color={VSColors.textMuted} />
        </TouchableOpacity>
      </View>

      {/* Sidebar Overlay for Mobile */}
      {isMobile && !sidebarCollapsed && (
        <TouchableOpacity
          style={styles.sidebarOverlay}
          onPress={toggleSidebar}
          activeOpacity={1}
        />
      )}

      {/* Sidebar */}
      <Animated.View style={[styles.sidebar, getSidebarStyle()]}>
        <View style={styles.sidebarHeader}>
          <Text style={styles.sidebarTitle}>EXPLORER</Text>
          <TouchableOpacity onPress={() => loadDirectory(currentPath)}>
            <Ionicons name="refresh" size={16} color={VSColors.textMuted} />
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.folderHeader} onPress={goUp}>
          <Ionicons name="chevron-up" size={14} color={VSColors.textMuted} />
          <Text style={styles.folderName} numberOfLines={1}>
            {currentPath.split(/[/\\]/).pop() || 'Root'}
          </Text>
        </TouchableOpacity>

        {loadingFiles ? (
          <ActivityIndicator size="small" color={VSColors.accent} style={{ marginTop: 20 }} />
        ) : (
          <FlatList
            data={files}
            keyExtractor={item => item.path}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={[styles.fileRow, activeTab === item.path && styles.fileRowActive]}
                onPress={() => { openFile(item); if (isMobile) setSidebarCollapsed(true); }}
              >
                <Ionicons
                  name={getIcon(item)}
                  size={16}
                  color={item.is_dir ? VSColors.warning : VSColors.textMuted}
                />
                <Text style={styles.fileName} numberOfLines={1}>{item.name}</Text>
              </TouchableOpacity>
            )}
          />
        )}
      </Animated.View>

      {/* Main Area */}
      <View style={styles.main}>
        {/* Tabs */}
        <View style={styles.tabBar}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
            {openTabs.map(tab => (
              <TouchableOpacity
                key={tab.path}
                style={[styles.tab, activeTab === tab.path && styles.tabActive]}
                onPress={() => setActiveTab(tab.path)}
              >
                <Text style={[styles.tabText, activeTab === tab.path && styles.tabTextActive]} numberOfLines={1}>
                  {tab.modified ? '● ' : ''}{tab.name}
                </Text>
                <TouchableOpacity onPress={() => closeTab(tab.path)} style={styles.tabClose}>
                  <Ionicons name="close" size={14} color={VSColors.textMuted} />
                </TouchableOpacity>
              </TouchableOpacity>
            ))}
          </ScrollView>
          {activeTab && (
            <TouchableOpacity style={styles.saveBtn} onPress={() => saveFile(activeTab)}>
              <Ionicons name="save" size={18} color={VSColors.accent} />
            </TouchableOpacity>
          )}
        </View>

        {/* Editor */}
        <View style={styles.editorContainer}>
          {activeFile ? (
            <ScrollView style={styles.editor}>
              <TextInput
                style={styles.codeInput}
                value={activeFile.content}
                onChangeText={(text) => updateContent(activeFile.path, text)}
                multiline
                autoCapitalize="none"
                autoCorrect={false}
                spellCheck={false}
              />
            </ScrollView>
          ) : (
            <View style={styles.noFile}>
              <Ionicons name="code-slash" size={48} color={VSColors.textMuted} />
              <Text style={styles.noFileText}>Open a file to start editing</Text>
              <TouchableOpacity style={styles.openFolderBtn} onPress={() => setShowOpenFolder(true)}>
                <Text style={styles.openFolderBtnText}>Open Folder</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Terminal - Desktop or when active on mobile */}
        {(showTerminal || (isMobile && activeBottomPanel === 'terminal')) && (
          <View style={[styles.terminal, isMobile && styles.terminalMobile]}>
            <View style={styles.terminalHeader}>
              <Text style={styles.terminalTitle}>TERMINAL</Text>
              {isMobile && (
                <TouchableOpacity onPress={() => setActiveBottomPanel(null)} style={styles.panelCloseBtn}>
                  <Ionicons name="chevron-down" size={18} color={VSColors.textMuted} />
                </TouchableOpacity>
              )}
            </View>
            <ScrollView
              ref={terminalScrollRef}
              style={styles.terminalOutput}
              onContentSizeChange={() => terminalScrollRef.current?.scrollToEnd({ animated: true })}
            >
              <Text style={styles.terminalText}>{terminalOutput}</Text>
            </ScrollView>
            <View style={styles.terminalInputRow}>
              <Text style={styles.terminalPrompt}>$</Text>
              <TextInput
                style={styles.terminalInput}
                value={terminalCommand}
                onChangeText={setTerminalCommand}
                onSubmitEditing={runCommand}
                placeholder="Enter command..."
                placeholderTextColor={VSColors.textMuted}
                editable={!runningCommand}
              />
              <TouchableOpacity onPress={runCommand} disabled={runningCommand} style={styles.terminalSendBtn}>
                {runningCommand ? (
                  <ActivityIndicator size="small" color={VSColors.accent} />
                ) : (
                  <Ionicons name="send" size={18} color={VSColors.accent} />
                )}
              </TouchableOpacity>
            </View>
          </View>
        )}
      </View>

      {/* Copilot Panel - Desktop sidebar or Mobile bottom sheet */}
      {(showCopilotPanel || (isMobile && activeBottomPanel === 'copilot')) && (
        <View style={[
          styles.copilotPanel,
          isMobile && styles.copilotPanelMobile,
          isTablet && styles.copilotPanelTablet,
        ]}>
          <View style={styles.copilotHeader}>
            <Ionicons name="sparkles" size={16} color={VSColors.accent} />
            <Text style={styles.copilotTitle}>{agentMode ? 'AI AGENT' : 'AI CHAT'}</Text>
            {aiProviderLabel ? (
              <Text style={styles.providerBadge}>{aiProviderLabel}</Text>
            ) : null}
            <TouchableOpacity
              style={[styles.agentToggle, agentMode && styles.agentToggleOn]}
              onPress={() => setAgentMode((v) => !v)}
            >
              <Text style={styles.agentToggleText}>{agentMode ? 'Agent' : 'Chat'}</Text>
            </TouchableOpacity>
            <View style={{ flex: 1 }} />
            {isMobile && (
              <TouchableOpacity onPress={() => setActiveBottomPanel(null)} style={styles.panelCloseBtn}>
                <Ionicons name="chevron-down" size={18} color={VSColors.textMuted} />
              </TouchableOpacity>
            )}
          </View>

          <ScrollView
            ref={chatScrollRef}
            style={styles.chatMessages}
            onContentSizeChange={() => chatScrollRef.current?.scrollToEnd({ animated: true })}
            keyboardShouldPersistTaps="handled"
          >
            {chatMessages.map(msg => (
              <View key={msg.id} style={[styles.chatBubble, msg.role === 'user' ? styles.userBubble : styles.aiBubble]}>
                <Text style={[styles.chatText, msg.isError && styles.chatError]}>{msg.content}</Text>
                {msg.diff && (
                  <View style={styles.diffBox}>
                    <Text style={styles.diffText}>{msg.diff.substring(0, 500)}</Text>
                    {pendingEdit && (
                      <TouchableOpacity style={styles.applyBtn} onPress={applyEdit}>
                        <Text style={styles.applyBtnText}>Apply Changes</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                )}
              </View>
            ))}
            {loadingChat && <ActivityIndicator size="small" color={VSColors.accent} style={{ marginTop: 8 }} />}
          </ScrollView>

          {/* Copilot Input - Always visible with send button */}
          <View style={[styles.chatInputRow, isMobile && styles.chatInputRowMobile]}>
            <TextInput
              style={[styles.chatInput, isMobile && styles.chatInputMobile]}
              value={chatInput}
              onChangeText={setChatInput}
              placeholder={
                agentMode
                  ? 'e.g. add, commit and push to main'
                  : activeTab
                    ? 'Ask or request code edits…'
                    : 'Ask AI (open a file to edit code)…'
              }
              placeholderTextColor={VSColors.textMuted}
              multiline
              maxLength={500}
              onSubmitEditing={sendCopilotMessage}
              blurOnSubmit={false}
            />
            <TouchableOpacity
              style={[styles.sendBtn, (!chatInput.trim() || loadingChat) && styles.sendBtnDisabled]}
              onPress={sendCopilotMessage}
              disabled={loadingChat || !chatInput.trim()}
            >
              <Ionicons name="send" size={20} color={loadingChat || !chatInput.trim() ? VSColors.textMuted : VSColors.white} />
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Mobile Bottom Navigation Bar */}
      {isMobile && !activeBottomPanel && (
        <View style={styles.mobileBottomBar}>
          <TouchableOpacity
            style={styles.mobileBottomBtn}
            onPress={() => setActiveBottomPanel('terminal')}
          >
            <Ionicons name="terminal" size={22} color={VSColors.textMuted} />
            <Text style={styles.mobileBottomBtnText}>Terminal</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.mobileBottomBtn}
            onPress={() => setActiveBottomPanel('copilot')}
          >
            <Ionicons name="sparkles" size={22} color={VSColors.accent} />
            <Text style={[styles.mobileBottomBtnText, { color: VSColors.accent }]}>Copilot</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.mobileBottomBtn}
            onPress={() => activeTab && saveFile(activeTab)}
            disabled={!activeTab}
          >
            <Ionicons name="save" size={22} color={activeTab ? VSColors.success : VSColors.textMuted} />
            <Text style={styles.mobileBottomBtnText}>Save</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Open Folder Modal */}
      <Modal visible={showOpenFolder} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>Open Folder</Text>
            <TextInput
              style={styles.modalInput}
              value={folderInput}
              onChangeText={setFolderInput}
              placeholder="C:\path\to\folder"
              placeholderTextColor={VSColors.textMuted}
              autoCapitalize="none"
            />
            <View style={styles.modalBtns}>
              <TouchableOpacity style={styles.modalBtnCancel} onPress={() => setShowOpenFolder(false)}>
                <Text style={styles.modalBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalBtnOpen}
                onPress={() => {
                  loadDirectory(folderInput);
                  setShowOpenFolder(false);
                }}
              >
                <Text style={[styles.modalBtnText, { color: VSColors.white }]}>Open</Text>
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
    flexDirection: 'row',
    backgroundColor: VSColors.bg,
  },
  activityBar: {
    width: 48,
    backgroundColor: VSColors.activityBar,
    paddingTop: 8,
    alignItems: 'center',
  },
  activityBarMobile: {
    paddingBottom: 8,
  },
  activityIcon: {
    width: 48,
    height: 48,
    justifyContent: 'center',
    alignItems: 'center',
    borderLeftWidth: 2,
    borderLeftColor: 'transparent',
  },
  activityIconActive: {
    borderLeftColor: VSColors.accent,
  },
  sidebarOverlay: {
    position: 'absolute',
    left: 48,
    top: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    zIndex: 99,
  },
  sidebar: {
    width: 180,
    backgroundColor: VSColors.sidebar,
    borderRightWidth: 1,
    borderRightColor: VSColors.border,
    overflow: 'hidden',
  },
  sidebarHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  sidebarTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: VSColors.textMuted,
    letterSpacing: 0.5,
  },
  folderHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 6,
    backgroundColor: VSColors.hover,
  },
  folderName: {
    fontSize: 13,
    fontWeight: '600',
    color: VSColors.text,
    marginLeft: 4,
    flex: 1,
  },
  fileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  fileRowActive: {
    backgroundColor: VSColors.selection,
  },
  fileName: {
    fontSize: 13,
    color: VSColors.text,
    marginLeft: 6,
    flex: 1,
  },
  main: {
    flex: 1,
    borderRightWidth: 1,
    borderRightColor: VSColors.border,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: VSColors.sidebar,
    borderBottomWidth: 1,
    borderBottomColor: VSColors.border,
    height: 35,
    alignItems: 'center',
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRightWidth: 1,
    borderRightColor: VSColors.border,
    height: '100%',
    maxWidth: 150,
  },
  tabActive: {
    backgroundColor: VSColors.editor,
    borderBottomWidth: 1,
    borderBottomColor: VSColors.accent,
  },
  tabText: {
    fontSize: 12,
    color: VSColors.textMuted,
    flex: 1,
  },
  tabTextActive: {
    color: VSColors.white,
  },
  tabClose: {
    marginLeft: 8,
    padding: 2,
  },
  saveBtn: {
    paddingHorizontal: 12,
  },
  editorContainer: {
    flex: 2,
    backgroundColor: VSColors.editor,
  },
  editor: {
    flex: 1,
    padding: 8,
  },
  codeInput: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 13,
    color: VSColors.text,
    lineHeight: 20,
    textAlignVertical: 'top',
    minHeight: 300,
  },
  noFile: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  noFileText: {
    color: VSColors.textMuted,
    fontSize: 14,
    marginTop: 12,
  },
  openFolderBtn: {
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: VSColors.accent,
    borderRadius: 4,
  },
  openFolderBtnText: {
    color: VSColors.white,
    fontWeight: '600',
  },
  terminal: {
    flex: 1,
    backgroundColor: VSColors.terminal,
    borderTopWidth: 1,
    borderTopColor: VSColors.border,
    maxHeight: 200,
  },
  terminalMobile: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 250,
    maxHeight: 250,
    zIndex: 50,
  },
  terminalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: VSColors.border,
  },
  terminalTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: VSColors.textMuted,
    letterSpacing: 0.5,
  },
  terminalOutput: {
    flex: 1,
    padding: 8,
  },
  terminalText: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    color: VSColors.text,
    lineHeight: 18,
  },
  terminalInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: VSColors.border,
    gap: 8,
  },
  terminalPrompt: {
    color: VSColors.success,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
  },
  terminalInput: {
    flex: 1,
    color: VSColors.text,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    padding: 0,
  },
  terminalSendBtn: {
    padding: 8,
    backgroundColor: VSColors.inputBg,
    borderRadius: 4,
  },
  panelCloseBtn: {
    padding: 4,
  },
  copilotPanel: {
    width: 220,
    backgroundColor: VSColors.sidebar,
  },
  copilotPanelMobile: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    width: '100%',
    height: 350,
    borderTopWidth: 1,
    borderTopColor: VSColors.border,
    zIndex: 50,
  },
  copilotPanelTablet: {
    width: 280,
  },
  copilotHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: VSColors.border,
  },
  copilotTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: VSColors.textMuted,
    letterSpacing: 0.5,
    marginLeft: 6,
    marginRight: 6,
  },
  providerBadge: {
    fontSize: 10,
    color: VSColors.success,
    marginRight: 6,
  },
  agentToggle: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: VSColors.border,
    backgroundColor: VSColors.inputBg,
  },
  agentToggleOn: {
    borderColor: VSColors.accent,
    backgroundColor: VSColors.accent + '33',
  },
  agentToggleText: {
    fontSize: 10,
    color: VSColors.text,
    fontWeight: '600',
  },
  chatMessages: {
    flex: 1,
    padding: 8,
  },
  chatBubble: {
    marginBottom: 8,
    padding: 8,
    borderRadius: 6,
    maxWidth: '100%',
  },
  userBubble: {
    backgroundColor: VSColors.accent,
    alignSelf: 'flex-end',
  },
  aiBubble: {
    backgroundColor: VSColors.inputBg,
    alignSelf: 'flex-start',
  },
  chatText: {
    fontSize: 12,
    color: VSColors.text,
    lineHeight: 18,
  },
  chatError: {
    color: VSColors.error,
  },
  diffBox: {
    marginTop: 8,
    padding: 8,
    backgroundColor: VSColors.bg,
    borderRadius: 4,
  },
  diffText: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 10,
    color: VSColors.text,
  },
  applyBtn: {
    marginTop: 8,
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: VSColors.success,
    borderRadius: 4,
    alignSelf: 'flex-start',
  },
  applyBtnText: {
    color: VSColors.bg,
    fontSize: 12,
    fontWeight: '600',
  },
  chatInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 8,
    borderTopWidth: 1,
    borderTopColor: VSColors.border,
    gap: 8,
  },
  chatInputRowMobile: {
    paddingBottom: 12,
  },
  chatInput: {
    flex: 1,
    backgroundColor: VSColors.inputBg,
    color: VSColors.text,
    fontSize: 12,
    borderRadius: 4,
    paddingHorizontal: 10,
    paddingVertical: 8,
    maxHeight: 80,
  },
  chatInputMobile: {
    fontSize: 14,
    paddingVertical: 10,
    maxHeight: 100,
  },
  sendBtn: {
    backgroundColor: VSColors.accent,
    padding: 10,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: VSColors.inputBg,
  },
  mobileBottomBar: {
    position: 'absolute',
    left: 48,
    right: 0,
    bottom: 0,
    height: 56,
    flexDirection: 'row',
    backgroundColor: VSColors.sidebar,
    borderTopWidth: 1,
    borderTopColor: VSColors.border,
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  mobileBottomBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  mobileBottomBtnText: {
    fontSize: 10,
    color: VSColors.textMuted,
    marginTop: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modal: {
    backgroundColor: VSColors.sidebar,
    borderRadius: 8,
    padding: 20,
    width: '80%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: VSColors.text,
    marginBottom: 16,
  },
  modalInput: {
    backgroundColor: VSColors.inputBg,
    color: VSColors.text,
    fontSize: 14,
    borderRadius: 4,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 16,
  },
  modalBtns: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
  },
  modalBtnCancel: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  modalBtnOpen: {
    backgroundColor: VSColors.accent,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 4,
  },
  modalBtnText: {
    color: VSColors.text,
    fontWeight: '600',
  },
});
