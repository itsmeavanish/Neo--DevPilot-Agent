import { useState, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, FontSize, BorderRadius } from '@/lib/theme';
import { runSystemCommand, runGitCommand, type CommandResponse } from '@/lib/api';

interface Task {
  id: string;
  name: string;
  command: string;
  commandType: 'system' | 'git';
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: string;
}

const PRESET_TASKS = [
  { name: 'Node Version', command: 'node -v', commandType: 'system' as const },
  { name: 'Git Status', command: 'git status', commandType: 'git' as const },
  { name: 'List Files', command: 'dir', commandType: 'system' as const },
  { name: 'Python Version', command: 'python --version', commandType: 'system' as const },
  { name: 'Git Log', command: 'git log --oneline -5', commandType: 'git' as const },
  { name: 'NPM Version', command: 'npm -v', commandType: 'system' as const },
];

function StatusIcon({ status }: { status: Task['status'] }) {
  switch (status) {
    case 'completed':
      return <Ionicons name="checkmark-circle" size={18} color={Colors.green} />;
    case 'running':
      return <ActivityIndicator size="small" color={Colors.amber} />;
    case 'failed':
      return <Ionicons name="alert-circle" size={18} color={Colors.red} />;
    default:
      return <Ionicons name="time" size={18} color={Colors.blue} />;
  }
}

function StatusBadge({ status }: { status: Task['status'] }) {
  const colors = {
    completed: { bg: Colors.greenBg, text: Colors.greenLight, border: Colors.greenBorder },
    running: { bg: Colors.amberBg, text: Colors.amberLight, border: Colors.amberBorder },
    failed: { bg: Colors.redBg, text: Colors.redLight, border: Colors.redBorder },
    pending: { bg: Colors.blueBg, text: Colors.blueLight, border: Colors.blueBorder },
  };
  const c = colors[status];
  return (
    <View style={[styles.badge, { backgroundColor: c.bg, borderColor: c.border }]}>
      <Text style={[styles.badgeText, { color: c.text }]}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Text>
    </View>
  );
}

export default function TasksScreen() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [customCommand, setCustomCommand] = useState('');

  const runTask = useCallback(async (name: string, command: string, commandType: 'system' | 'git') => {
    const id = Date.now().toString() + Math.random();
    const task: Task = { id, name, command, commandType, status: 'running' };
    setTasks((prev) => [task, ...prev]);

    try {
      let res: CommandResponse;
      if (commandType === 'git') {
        res = await runGitCommand(command);
      } else {
        res = await runSystemCommand(command);
      }
      const output = res.stdout || res.stderr || res.message || 'No output';
      setTasks((prev) =>
        prev.map((t) =>
          t.id === id
            ? { ...t, status: res.status === 'success' ? 'completed' : 'failed', output: output.trim() }
            : t
        )
      );
    } catch (err) {
      setTasks((prev) =>
        prev.map((t) =>
          t.id === id ? { ...t, status: 'failed', output: err instanceof Error ? err.message : 'Failed' } : t
        )
      );
    }
  }, []);

  const handleCustomRun = () => {
    const cmd = customCommand.trim();
    if (!cmd) return;
    setCustomCommand('');
    const isGit = cmd.toLowerCase().startsWith('git ');
    runTask(cmd.slice(0, 30), cmd, isGit ? 'git' : 'system');
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.iconContainer}>
          <Ionicons name="flash" size={18} color={Colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Task Runner</Text>
          <Text style={styles.subtitle}>Run and track command tasks</Text>
        </View>
        <TouchableOpacity onPress={() => setTasks([])} style={styles.clearBtn}>
          <Text style={styles.clearText}>Clear All</Text>
        </TouchableOpacity>
      </View>

      {/* Quick Tasks */}
      <Text style={styles.sectionTitle}>QUICK TASKS</Text>
      <View style={styles.quickTasksGrid}>
        {PRESET_TASKS.map((preset) => (
          <TouchableOpacity
            key={preset.name}
            style={styles.quickTask}
            onPress={() => runTask(preset.name, preset.command, preset.commandType)}
          >
            <Text style={styles.quickTaskName}>{preset.name}</Text>
            <Text style={styles.quickTaskCmd}>{preset.command}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Custom Task */}
      <Text style={styles.sectionTitle}>CUSTOM TASK</Text>
      <View style={styles.customInputRow}>
        <TextInput
          style={styles.customInput}
          value={customCommand}
          onChangeText={setCustomCommand}
          placeholder="Enter any command..."
          placeholderTextColor={Colors.mutedDark}
          onSubmitEditing={handleCustomRun}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.runBtn, !customCommand.trim() && styles.runBtnDisabled]}
          onPress={handleCustomRun}
          disabled={!customCommand.trim()}
        >
          <Ionicons name="play" size={16} color={Colors.foreground} />
          <Text style={styles.runBtnText}>Run</Text>
        </TouchableOpacity>
      </View>

      {/* Results */}
      <Text style={styles.sectionTitle}>RESULTS ({tasks.length})</Text>
      {tasks.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="flash-outline" size={40} color={Colors.mutedDark} />
          <Text style={styles.emptyText}>No tasks run yet</Text>
        </View>
      ) : (
        tasks.map((task) => (
          <View key={task.id} style={styles.taskCard}>
            <View style={styles.taskHeader}>
              <StatusIcon status={task.status} />
              <View style={styles.taskInfo}>
                <Text style={styles.taskName}>{task.name}</Text>
                <Text style={styles.taskCommand}>{task.command}</Text>
              </View>
              <StatusBadge status={task.status} />
            </View>
            {task.output && (
              <View style={styles.outputContainer}>
                <Text style={styles.outputText}>{task.output}</Text>
              </View>
            )}
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: Spacing.lg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.xl,
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
  clearText: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  sectionTitle: {
    fontSize: FontSize.xs,
    fontWeight: 'bold',
    color: Colors.muted,
    letterSpacing: 1,
    marginBottom: Spacing.md,
    marginTop: Spacing.lg,
  },
  quickTasksGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  quickTask: {
    width: '48%',
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
  },
  quickTaskName: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.foreground,
  },
  quickTaskCmd: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 4,
  },
  customInputRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  customInput: {
    flex: 1,
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: FontSize.sm,
    color: Colors.foreground,
  },
  runBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.md,
  },
  runBtnDisabled: {
    opacity: 0.5,
  },
  runBtnText: {
    color: Colors.foreground,
    fontSize: FontSize.sm,
    fontWeight: '600',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: Spacing.xxl * 2,
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  emptyText: {
    color: Colors.muted,
    fontSize: FontSize.sm,
    marginTop: Spacing.md,
  },
  taskCard: {
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  taskHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  taskInfo: {
    flex: 1,
  },
  taskName: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.foreground,
  },
  taskCommand: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  badge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: FontSize.xs,
    fontWeight: '600',
  },
  outputContainer: {
    backgroundColor: Colors.codeBg,
    borderRadius: BorderRadius.sm,
    padding: Spacing.md,
    marginTop: Spacing.md,
    maxHeight: 120,
  },
  outputText: {
    fontSize: FontSize.xs,
    color: Colors.greenLight,
    fontFamily: 'monospace',
  },
});
