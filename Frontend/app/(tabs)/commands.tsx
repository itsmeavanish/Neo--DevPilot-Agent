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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, FontSize, BorderRadius } from '@/lib/theme';
import { runSystemCommand } from '@/lib/api';

interface TerminalLine {
  id: string;
  type: 'input' | 'output' | 'error';
  content: string;
}

export default function CommandsScreen() {
  const [input, setInput] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [lines, setLines] = useState<TerminalLine[]>([
    { id: '0', type: 'output', content: 'DevPilot Terminal — Connected.\nType any command to execute on the remote machine.\n' },
  ]);
  const [history, setHistory] = useState<string[]>([]);
  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [lines]);

  const addLine = (type: TerminalLine['type'], content: string) => {
    setLines((prev) => [...prev, { id: Date.now().toString() + Math.random(), type, content }]);
  };

  const handleRun = async () => {
    const cmd = input.trim();
    if (!cmd || isRunning) return;
    setInput('');
    setHistory((prev) => [cmd, ...prev.slice(0, 49)]);
    addLine('input', `$ ${cmd}`);
    setIsRunning(true);

    try {
      const res = await runSystemCommand(cmd);
      if (res.stdout) addLine('output', res.stdout.trim());
      if (res.stderr) addLine('error', res.stderr.trim());
      if (!res.stdout && !res.stderr && res.message) {
        addLine(res.status === 'success' ? 'output' : 'error', res.message);
      }
    } catch (err) {
      addLine('error', err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setIsRunning(false);
    }
  };

  const clearTerminal = () => setLines([]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.iconContainer}>
            <Ionicons name="terminal" size={18} color={Colors.primary} />
          </View>
          <View>
            <Text style={styles.title}>Remote Terminal</Text>
            <Text style={styles.subtitle}>Execute commands on backend</Text>
          </View>
        </View>
        <TouchableOpacity onPress={clearTerminal} style={styles.clearBtn}>
          <Ionicons name="trash-outline" size={18} color={Colors.muted} />
        </TouchableOpacity>
      </View>

      {/* Terminal Output */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.terminalContainer}
        contentContainerStyle={styles.terminalContent}
      >
        {lines.map((line) => (
          <Text
            key={line.id}
            style={[
              styles.terminalLine,
              line.type === 'input' && styles.inputLine,
              line.type === 'error' && styles.errorLine,
            ]}
          >
            {line.content}
          </Text>
        ))}
        {isRunning && (
          <View style={styles.runningRow}>
            <ActivityIndicator size="small" color={Colors.amber} />
            <Text style={styles.runningText}>Running...</Text>
          </View>
        )}
      </ScrollView>

      {/* Input */}
      <View style={styles.inputContainer}>
        <Text style={styles.prompt}>$</Text>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Enter command..."
          placeholderTextColor={Colors.mutedDark}
          onSubmitEditing={handleRun}
          editable={!isRunning}
          returnKeyType="send"
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TouchableOpacity
          style={[styles.runBtn, (!input.trim() || isRunning) && styles.runBtnDisabled]}
          onPress={handleRun}
          disabled={!input.trim() || isRunning}
        >
          {isRunning ? (
            <ActivityIndicator size="small" color={Colors.foreground} />
          ) : (
            <Ionicons name="play" size={18} color={Colors.foreground} />
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  iconContainer: {
    width: 36,
    height: 36,
    backgroundColor: Colors.primaryBg,
    borderRadius: BorderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: FontSize.md,
    fontWeight: 'bold',
    color: Colors.foreground,
  },
  subtitle: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  clearBtn: {
    padding: Spacing.sm,
  },
  terminalContainer: {
    flex: 1,
    backgroundColor: Colors.surface,
  },
  terminalContent: {
    padding: Spacing.lg,
  },
  terminalLine: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.sm,
    color: Colors.greenLight,
    lineHeight: 20,
    marginBottom: 2,
  },
  inputLine: {
    color: Colors.primary,
    fontWeight: '600',
  },
  errorLine: {
    color: Colors.redLight,
  },
  runningRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  runningText: {
    color: Colors.amber,
    fontSize: FontSize.sm,
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
  prompt: {
    color: Colors.primary,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: FontSize.md,
    fontWeight: 'bold',
  },
  input: {
    flex: 1,
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: FontSize.sm,
    color: Colors.foreground,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  runBtn: {
    backgroundColor: Colors.primary,
    width: 44,
    height: 44,
    borderRadius: BorderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  runBtnDisabled: {
    opacity: 0.5,
  },
});
