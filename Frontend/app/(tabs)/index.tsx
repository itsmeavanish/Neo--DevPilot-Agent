import { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useRouter } from 'expo-router';
import { Colors, Spacing, FontSize, BorderRadius } from '../lib/theme';
import { runSystemCommand, runGitCommand, openVSCode, openProject, runCopilot, askAI, readFile, getAIProviders } from '../lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isError?: boolean;
}

interface FileContext {
  path: string;
  content: string;
  language: string;
}

const QUICK_ACTIONS = [
  { icon: 'terminal', label: 'Shell', prefix: '!' },
  { icon: 'git-branch', label: 'Git', prefix: 'git ' },
  { icon: 'code-slash', label: 'VS Code', prefix: '/vscode' },
  { icon: 'sparkles', label: 'AI', prefix: '/ai ' },
];

export default function ChatScreen() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Hello! I'm JARVIS — your DevPilot automation assistant.\n\n• !command — run shell commands\n• git ... — run git commands\n• /vscode [path] — launch VS Code & open IDE\n• /ai prompt — ask AI assistant\n• /file path — load file as context\n\nWhat would you like to do?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [fileContext, setFileContext] = useState<FileContext | null>(null);
  const [showContextModal, setShowContextModal] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<string>('');
  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  useEffect(() => {
    // Load current AI provider
    const loadProvider = async () => {
      try {
        const providers = await getAIProviders();
        setCurrentProvider(providers.current);
      } catch {
        // Ignore
      }
    };
    loadProvider();
  }, []);

  const addMessage = (role: Message['role'], content: string, isError = false) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString() + Math.random(), role, content, timestamp: new Date(), isError },
    ]);
  };

  const loadFileContext = async (path: string) => {
    try {
      const file = await readFile(path);
      if (file.error) {
        addMessage('assistant', `Error loading file: ${file.error}`, true);
        return;
      }
      setFileContext({
        path: file.path,
        content: file.content,
        language: file.language,
      });
      addMessage('assistant', `Loaded file as context: ${file.path}\n${file.lines} lines | ${file.language}\n\nYou can now use /ai to ask questions about this code.`);
    } catch (err) {
      addMessage('assistant', `Error: ${err instanceof Error ? err.message : 'Failed to load file'}`, true);
    }
  };

  const handleSend = async () => {
    // Normalize input: trim and collapse multiple spaces
    const text = input.trim().replace(/\s+/g, ' ');
    if (!text || isLoading) return;
    setInput('');
    addMessage('user', text);
    setIsLoading(true);

    try {
      // Handle different command types (case-insensitive matching)
      const lowerText = text.toLowerCase();

      if (text.startsWith('!')) {
        // Shell command: !node -v
        const cmd = text.slice(1).trim();
        if (!cmd) {
          addMessage('assistant', 'Please provide a command after !', true);
        } else {
          const res = await runSystemCommand(cmd);
          const output = res.stdout || res.stderr || res.message || 'No output';
          addMessage('assistant', `$ ${cmd}\n\n${output}`, res.status !== 'success');
        }
      } else if (lowerText.startsWith('git ') || lowerText === 'git') {
        // Git command
        const res = await runGitCommand(text);
        const output = res.stdout || res.stderr || res.message || 'No output';
        addMessage('assistant', `$ ${text}\n\n${output}`, res.status !== 'success');
      } else if (lowerText === '/vscode' || lowerText === 'vscode' || lowerText === 'code') {
        // Open VS Code and redirect to IDE
        const res = await openVSCode();
        addMessage('assistant', res.message || 'VS Code launched. Redirecting to IDE...', res.status !== 'success');
        if (res.status === 'success') {
          setTimeout(() => router.push('/ide'), 500);
        }
      } else if (lowerText.startsWith('/vscode ') || lowerText.startsWith('vscode ') || lowerText.startsWith('code ')) {
        // Open project in VS Code and redirect to IDE
        const prefixLen = lowerText.startsWith('/vscode ') ? 8 : lowerText.startsWith('vscode ') ? 7 : 5;
        const path = text.slice(prefixLen).trim();
        if (!path) {
          addMessage('assistant', 'Please provide a path after /vscode', true);
        } else {
          const res = await openProject(path);
          addMessage('assistant', res.message || `Opened: ${path}. Redirecting to IDE...`, res.status !== 'success');
          if (res.status === 'success') {
            setTimeout(() => router.push({ pathname: '/ide', params: { openPath: path } }), 500);
          }
        }
      } else if (lowerText.startsWith('/file ')) {
        // Load file as context
        const path = text.slice(6).trim();
        if (!path) {
          addMessage('assistant', 'Please provide a file path after /file', true);
        } else {
          await loadFileContext(path);
        }
      } else if (lowerText === '/context') {
        // Show current context
        if (fileContext) {
          setShowContextModal(true);
        } else {
          addMessage('assistant', 'No file context loaded. Use /file <path> to load a file.');
        }
      } else if (lowerText === '/clearcontext') {
        // Clear context
        setFileContext(null);
        addMessage('assistant', 'File context cleared.');
      } else if (lowerText.startsWith('/ai ') || lowerText.startsWith('ai ')) {
        // AI assistant
        const prefixLen = lowerText.startsWith('/ai ') ? 4 : 3;
        const prompt = text.slice(prefixLen).trim();
        if (!prompt) {
          addMessage('assistant', 'Please provide a prompt after /ai', true);
        } else {
          const res = await askAI(
            prompt,
            fileContext?.content,
            fileContext?.path,
            fileContext?.language
          );
          if (res.error) {
            addMessage('assistant', `AI Error: ${res.error}`, true);
          } else {
            const providerLabel = currentProvider ? `[${currentProvider}] ` : '';
            addMessage('assistant', `${providerLabel}${res.response}`);
          }
        }
      } else if (lowerText.startsWith('/copilot ') || lowerText.startsWith('copilot ')) {
        // Copilot CLI (legacy)
        const prefixLen = lowerText.startsWith('/copilot ') ? 9 : 8;
        const prompt = text.slice(prefixLen).trim();
        if (!prompt) {
          addMessage('assistant', 'Please provide a prompt after /copilot', true);
        } else {
          const res = await runCopilot(prompt);
          const output = res.stdout || res.stderr || res.message || 'No output';
          addMessage('assistant', `Copilot CLI:\n\n${output}`, res.status !== 'success');
        }
      } else {
        // Default: treat as system command
        const res = await runSystemCommand(text);
        const output = res.stdout || res.stderr || res.message || 'No output';
        addMessage('assistant', `$ ${text}\n\n${output}`, res.status !== 'success');
      }
    } catch (err) {
      addMessage('assistant', `Error: ${err instanceof Error ? err.message : 'Connection failed. Is the backend running?'}`, true);
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    await Clipboard.setStringAsync(text);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      {/* File Context Indicator */}
      {fileContext && (
        <TouchableOpacity style={styles.contextBar} onPress={() => setShowContextModal(true)}>
          <Ionicons name="document-text" size={16} color={Colors.primary} />
          <Text style={styles.contextText} numberOfLines={1}>
            Context: {fileContext.path.split(/[/\\]/).pop()}
          </Text>
          <TouchableOpacity onPress={() => setFileContext(null)}>
            <Ionicons name="close-circle" size={18} color={Colors.muted} />
          </TouchableOpacity>
        </TouchableOpacity>
      )}

      {/* Messages */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messagesContainer}
        contentContainerStyle={styles.messagesContent}
        showsVerticalScrollIndicator={false}
      >
        {messages.map((msg) => (
          <View
            key={msg.id}
            style={[
              styles.messageBubble,
              msg.role === 'user' ? styles.userBubble : styles.assistantBubble,
              msg.isError && styles.errorBubble,
            ]}
          >
            <Text style={[styles.messageText, msg.isError && styles.errorText]}>{msg.content}</Text>
            <View style={styles.messageFooter}>
              <Text style={styles.timestamp}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Text>
              {msg.role === 'assistant' && (
                <TouchableOpacity onPress={() => copyToClipboard(msg.content)} style={styles.copyBtn}>
                  <Ionicons name="copy-outline" size={14} color={Colors.muted} />
                </TouchableOpacity>
              )}
            </View>
          </View>
        ))}
        {isLoading && (
          <View style={[styles.messageBubble, styles.assistantBubble]}>
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={Colors.primary} />
              <Text style={styles.loadingText}>Executing...</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Quick Actions */}
      <View style={styles.quickActions}>
        {QUICK_ACTIONS.map((action) => (
          <TouchableOpacity
            key={action.label}
            style={styles.quickAction}
            onPress={() => setInput(action.prefix)}
          >
            <Ionicons name={action.icon as any} size={14} color={Colors.muted} />
            <Text style={styles.quickActionText}>{action.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Input */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={fileContext ? "Ask about the code..." : "Type a command..."}
          placeholderTextColor={Colors.mutedDark}
          onSubmitEditing={handleSend}
          editable={!isLoading}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!input.trim() || isLoading) && styles.sendBtnDisabled]}
          onPress={handleSend}
          disabled={!input.trim() || isLoading}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color={Colors.foreground} />
          ) : (
            <Ionicons name="send" size={20} color={Colors.foreground} />
          )}
        </TouchableOpacity>
      </View>

      {/* Context Preview Modal */}
      <Modal
        visible={showContextModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowContextModal(false)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowContextModal(false)}>
              <Ionicons name="close" size={24} color={Colors.foreground} />
            </TouchableOpacity>
            <Text style={styles.modalTitle} numberOfLines={1}>
              {fileContext?.path.split(/[/\\]/).pop()}
            </Text>
            <View style={styles.modalBadge}>
              <Text style={styles.modalLanguage}>{fileContext?.language}</Text>
            </View>
          </View>
          <ScrollView style={styles.contextCodeContainer} horizontal>
            <ScrollView>
              <Text style={styles.contextCode}>{fileContext?.content}</Text>
            </ScrollView>
          </ScrollView>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  messagesContainer: {
    flex: 1,
  },
  messagesContent: {
    padding: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  messageBubble: {
    maxWidth: '85%',
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: Colors.primaryBg,
    borderWidth: 1,
    borderColor: Colors.primary + '40',
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  errorBubble: {
    backgroundColor: Colors.redBg,
    borderColor: Colors.redBorder,
  },
  messageText: {
    color: Colors.foreground,
    fontSize: FontSize.sm,
    lineHeight: 20,
  },
  errorText: {
    color: Colors.redLight,
  },
  messageFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.sm,
  },
  timestamp: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  copyBtn: {
    padding: 4,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  loadingText: {
    color: Colors.muted,
    fontSize: FontSize.sm,
  },
  quickActions: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    gap: Spacing.sm,
    flexWrap: 'wrap',
  },
  quickAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.card,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  quickActionText: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.lg,
    gap: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  input: {
    flex: 1,
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    fontSize: FontSize.sm,
    color: Colors.foreground,
  },
  sendBtn: {
    backgroundColor: Colors.primary,
    width: 48,
    height: 48,
    borderRadius: BorderRadius.lg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    opacity: 0.5,
  },
  contextBar: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    backgroundColor: Colors.primaryBg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.primary + '40',
    gap: Spacing.sm,
  },
  contextText: {
    flex: 1,
    color: Colors.primary,
    fontSize: FontSize.xs,
    fontWeight: '500',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.lg,
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: Spacing.md,
  },
  modalTitle: {
    flex: 1,
    color: Colors.foreground,
    fontSize: FontSize.md,
    fontWeight: '600',
  },
  modalBadge: {
    backgroundColor: Colors.primary + '30',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: 4,
  },
  modalLanguage: {
    color: Colors.primary,
    fontSize: FontSize.xs,
    fontWeight: '500',
  },
  contextCodeContainer: {
    flex: 1,
    backgroundColor: Colors.card,
  },
  contextCode: {
    color: Colors.foreground,
    fontSize: FontSize.sm,
    fontFamily: 'monospace',
    padding: Spacing.lg,
    lineHeight: 20,
  },
});
