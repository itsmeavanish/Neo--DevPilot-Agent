import { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../lib/theme';
import configManager from '../../lib/config';
import {
  getMissionDevice,
  autonomousExecute,
  approveAutonomousRun,
  MissionDevice,
  AutonomousExecuteResult,
} from '../../lib/api';

type PendingApproval = {
  taskId: string;
  plan: Record<string, unknown> | null;
  steps: Record<string, unknown>[];
};

function formatApprovalSummary(p: PendingApproval): string {
  const lines: string[] = [];
  if (p.plan?.reasoning) lines.push(String(p.plan.reasoning));
  const steps = p.steps.length ? p.steps : ((p.plan?.steps as unknown[]) ?? []);
  for (const s of steps) {
    const step = s as Record<string, unknown>;
    lines.push(
      `• ${String(step.description || step.tool_name || 'step')} [${String(step.tool_name || '')}]`
    );
  }
  return lines.join('\n') || '(no step details)';
}

const INTENT_CHIPS: { label: string; intent: string }[] = [
  { label: 'Git status', intent: 'git status' },
  { label: 'List home folder', intent: 'list %USERPROFILE%' },
  { label: 'Python version', intent: 'run python --version' },
  { label: 'Disk free space', intent: 'run powershell -NoProfile -Command "Get-PSDrive -PSProvider FileSystem | Format-Table -AutoSize"' },
  { label: 'Network ping', intent: 'run ping -n 1 127.0.0.1' },
];

export default function MissionScreen() {
  const [ready, setReady] = useState(false);
  const [mission, setMission] = useState<MissionDevice | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [intent, setIntent] = useState('');
  const [runBusy, setRunBusy] = useState(false);
  const [approvalModal, setApprovalModal] = useState(false);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [workspaceRoot, setWorkspaceRoot] = useState('');

  const load = useCallback(async () => {
    await configManager.init();
    setWorkspaceRoot(configManager.workspaceRoot);
    setReady(true);
    const code = configManager.pairingCode;
    if (!code) {
      setMission(null);
      setLoading(false);
      return;
    }
    try {
      const m = await getMissionDevice(code);
      setMission(m);
    } catch {
      setMission(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    void load();
  };

  const showRunResult = (res: AutonomousExecuteResult) => {
    const lines = [
      `Status: ${res.status}`,
      res.message,
      res.error ? `Error: ${res.error}` : '',
      res.step_results?.length
        ? `Steps: ${res.step_results.map((s) => JSON.stringify(s)).join('\n')}`
        : '',
    ]
      .filter(Boolean)
      .join('\n');
    Alert.alert('Autonomous run', lines.slice(0, 3500) || '(no output)');
  };

  const runAutonomous = async (text: string) => {
    const t = text.trim();
    if (!t) return;
    if (!configManager.pairingCode) {
      Alert.alert('Not paired', 'Add your pairing code in Settings.');
      return;
    }
    setRunBusy(true);
    try {
      const res: AutonomousExecuteResult = await autonomousExecute(t, {
        approval_mode: 'confirm',
        defer_approval: true,
        use_multi_agent: true,
      });
      if (res.status === 'awaiting_approval' && res.task_id) {
        setPendingApproval({
          taskId: res.task_id,
          plan: res.plan ?? null,
          steps: res.steps_for_approval ?? [],
        });
        setApprovalModal(true);
        return;
      }
      showRunResult(res);
      void load();
    } catch (e) {
      Alert.alert('Run failed', e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setRunBusy(false);
    }
  };

  const submitApproval = async (approved: boolean) => {
    if (!pendingApproval) return;
    const snap = pendingApproval;
    const tid = snap.taskId;
    setApprovalModal(false);
    setRunBusy(true);
    try {
      const res = await approveAutonomousRun(tid, approved);
      setPendingApproval(null);
      showRunResult(res);
      void load();
    } catch (e) {
      Alert.alert('Approval failed', e instanceof Error ? e.message : 'Unknown error');
      setPendingApproval({ taskId: tid, plan: snap.plan, steps: snap.steps });
      setApprovalModal(true);
    } finally {
      setRunBusy(false);
    }
  };

  if (!ready || loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.muted}>Loading mission control…</Text>
      </View>
    );
  }

  if (!configManager.pairingCode) {
    return (
      <View style={styles.centered}>
        <Ionicons name="link-outline" size={48} color={Colors.muted} />
        <Text style={styles.title}>Pair your laptop</Text>
        <Text style={styles.muted}>Settings → pairing code → then return here.</Text>
      </View>
    );
  }

  const tel = mission?.telemetry;

  return (
    <>
    <Modal
      visible={approvalModal}
      animationType="fade"
      transparent
      onRequestClose={() => {
        setApprovalModal(false);
        setPendingApproval(null);
      }}
    >
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Approve this run?</Text>
          <Text style={styles.modalSub}>
            These commands will run on your paired laptop. Review and confirm.
          </Text>
          <ScrollView style={styles.modalScroll} nestedScrollEnabled>
            <Text style={styles.modalBody}>
              {pendingApproval ? formatApprovalSummary(pendingApproval) : ''}
            </Text>
          </ScrollView>
          <View style={styles.modalActions}>
            <TouchableOpacity
              style={[styles.modalBtn, styles.rejectBtn]}
              onPress={() => void submitApproval(false)}
            >
              <Text style={styles.modalBtnText}>Reject</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modalBtn, styles.approveBtn]}
              onPress={() => void submitApproval(true)}
            >
              <Text style={styles.modalBtnText}>Approve & run</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>

    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />
      }
    >
      <Text style={styles.headline}>Mission control</Text>
      <Text style={styles.sub}>Live telemetry and intent-driven runs on your paired PC.</Text>
      {workspaceRoot ? (
        <Text style={styles.workspaceLine} numberOfLines={2}>
          Project: {workspaceRoot}
        </Text>
      ) : (
        <Text style={styles.mutedSmall}>
          Set a project folder in Files (folder icon) so the agent can edit multiple files safely.
        </Text>
      )}

      <View style={styles.card}>
        <View style={styles.row}>
          <Ionicons
            name={mission?.online ? 'radio-button-on' : 'radio-button-off'}
            size={22}
            color={mission?.online ? Colors.green : Colors.red}
          />
          <Text style={styles.cardTitle}>
            {mission?.online ? 'Agent online' : 'Agent offline'}
          </Text>
        </View>
        {mission?.hostname ? (
          <Text style={styles.meta}>{mission.hostname} · {mission.platform || '?'}</Text>
        ) : null}
      </View>

      {tel ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>System pulse</Text>
          <Text style={styles.metric}>CPU {tel.cpu_percent?.toFixed(0) ?? '—'}%</Text>
          <Text style={styles.metric}>Memory {tel.memory_percent?.toFixed(0) ?? '—'}%</Text>
          <Text style={styles.metric}>Disk (home) {tel.disk_percent?.toFixed(0) ?? '—'}%</Text>
          {tel.top_processes && tel.top_processes.length > 0 ? (
            <>
              <Text style={styles.sectionLabel}>Top processes</Text>
              {tel.top_processes.map((p, i) => (
                <Text key={i} style={styles.proc}>
                  {p.name} · {p.cpu_percent}%
                </Text>
              ))}
            </>
          ) : null}
        </View>
      ) : mission?.online ? (
        <View style={styles.card}>
          <Text style={styles.muted}>Telemetry unavailable (update laptop agent script).</Text>
        </View>
      ) : null}

      {mission?.predictive_hints && mission.predictive_hints.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Predictive hints</Text>
          {mission.predictive_hints.map((h, i) => (
            <Text key={i} style={styles.hint}>
              • {h}
            </Text>
          ))}
        </View>
      ) : null}

      <Text style={styles.sectionLabel}>Quick intents</Text>
      <View style={styles.chips}>
        {INTENT_CHIPS.map((c) => (
          <TouchableOpacity
            key={c.label}
            style={styles.chip}
            onPress={() => runAutonomous(c.intent)}
            disabled={runBusy}
          >
            <Text style={styles.chipText}>{c.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.sectionLabel}>Autonomous mode</Text>
      <Text style={styles.mutedSmall}>
        Describe what you want done on the laptop (multi-step planner + remote shell).
      </Text>
      <TextInput
        style={styles.input}
        placeholder="e.g. git status then run python --version"
        placeholderTextColor={Colors.muted}
        value={intent}
        onChangeText={setIntent}
        multiline
      />
      <TouchableOpacity
        style={[styles.runBtn, runBusy && styles.runBtnDisabled]}
        onPress={() => runAutonomous(intent)}
        disabled={runBusy}
      >
        {runBusy ? (
          <ActivityIndicator color={Colors.foreground} />
        ) : (
          <>
            <Ionicons name="flash" size={20} color={Colors.foreground} />
            <Text style={styles.runBtnText}>Run on laptop</Text>
          </>
        )}
      </TouchableOpacity>
    </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background, padding: 16 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.background, padding: 24 },
  headline: { fontSize: 22, fontWeight: '700', color: Colors.foreground },
  sub: { color: Colors.muted, marginTop: 6, marginBottom: 16 },
  title: { fontSize: 18, fontWeight: '600', color: Colors.foreground, marginTop: 12 },
  muted: { color: Colors.muted, textAlign: 'center', marginTop: 8 },
  mutedSmall: { color: Colors.muted, fontSize: 12, marginBottom: 8 },
  workspaceLine: {
    color: Colors.primary,
    fontSize: 12,
    fontFamily: 'monospace',
    marginBottom: 12,
  },
  card: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: Colors.foreground },
  meta: { color: Colors.muted, marginTop: 4, fontSize: 13 },
  metric: { color: Colors.foreground, fontFamily: 'monospace', marginTop: 4 },
  sectionLabel: { color: Colors.primary, fontWeight: '600', marginTop: 8, marginBottom: 8 },
  proc: { color: Colors.muted, fontSize: 12, fontFamily: 'monospace' },
  hint: { color: Colors.yellow, marginTop: 4, fontSize: 13 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  chip: {
    backgroundColor: Colors.cardLight,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  chipText: { color: Colors.foreground, fontSize: 13 },
  input: {
    backgroundColor: Colors.card,
    borderRadius: 10,
    padding: 12,
    color: Colors.foreground,
    minHeight: 80,
    textAlignVertical: 'top',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  runBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.primary,
    padding: 14,
    borderRadius: 10,
    marginTop: 12,
    marginBottom: 32,
  },
  runBtnDisabled: { opacity: 0.6 },
  runBtnText: { color: Colors.foreground, fontWeight: '700', fontSize: 16 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'center',
    padding: 20,
  },
  modalCard: {
    backgroundColor: Colors.card,
    borderRadius: 14,
    padding: 16,
    maxHeight: '80%',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: Colors.foreground },
  modalSub: { color: Colors.muted, marginTop: 8, marginBottom: 12, fontSize: 13 },
  modalScroll: { maxHeight: 280, marginBottom: 12 },
  modalBody: { color: Colors.foreground, fontSize: 13, fontFamily: 'monospace', lineHeight: 20 },
  modalActions: { flexDirection: 'row', gap: 10, justifyContent: 'flex-end' },
  modalBtn: { paddingVertical: 12, paddingHorizontal: 16, borderRadius: 10, minWidth: 110, alignItems: 'center' },
  rejectBtn: { backgroundColor: Colors.cardLight, borderWidth: 1, borderColor: Colors.border },
  approveBtn: { backgroundColor: Colors.primary },
  modalBtnText: { color: Colors.foreground, fontWeight: '600', fontSize: 14 },
});
