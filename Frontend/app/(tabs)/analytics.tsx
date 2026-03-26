import { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, FontSize, BorderRadius } from '../lib/theme';
import { getSystemInfo, checkHealth, type SystemInfo } from '../lib/api';

function StatCard({
  icon,
  iconColor,
  iconBg,
  label,
  value,
  subtext,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  iconBg: string;
  label: string;
  value: string;
  subtext?: string;
}) {
  return (
    <View style={styles.statCard}>
      <View style={styles.statHeader}>
        <View style={[styles.statIcon, { backgroundColor: iconBg }]}>
          <Ionicons name={icon} size={22} color={iconColor} />
        </View>
        <Text style={styles.statLabel}>{label}</Text>
      </View>
      <Text style={styles.statValue}>{value}</Text>
      {subtext && <Text style={styles.statSubtext}>{subtext}</Text>}
    </View>
  );
}

function ProgressBar({ value, color }: { value: number; color: string }) {
  return (
    <View style={styles.progressBg}>
      <View style={[styles.progressFill, { width: `${Math.min(value, 100)}%`, backgroundColor: color }]} />
    </View>
  );
}

export default function AnalyticsScreen() {
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      await checkHealth();
      setIsConnected(true);
      const info = await getSystemInfo();
      setSystemInfo(info);
      setLastUpdated(new Date());
    } catch {
      setIsConnected(false);
      setSystemInfo(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.iconContainer}>
          <Ionicons name="stats-chart" size={18} color={Colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>System Analytics</Text>
          <Text style={styles.subtitle}>
            {lastUpdated ? `Updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading...'}
          </Text>
        </View>
        <TouchableOpacity onPress={fetchData} disabled={isLoading} style={styles.refreshBtn}>
          {isLoading ? (
            <ActivityIndicator size="small" color={Colors.muted} />
          ) : (
            <Ionicons name="refresh" size={20} color={Colors.muted} />
          )}
        </TouchableOpacity>
      </View>

      {/* Connection Status */}
      <View style={[styles.connectionCard, { borderColor: isConnected ? Colors.greenBorder : Colors.redBorder }]}>
        <Ionicons
          name={isConnected ? 'wifi' : 'wifi-outline'}
          size={22}
          color={isConnected ? Colors.green : Colors.red}
        />
        <View style={{ flex: 1 }}>
          <Text style={[styles.connectionTitle, { color: isConnected ? Colors.greenLight : Colors.redLight }]}>
            {isConnected ? 'Backend Connected' : 'Backend Disconnected'}
          </Text>
          <Text style={styles.connectionSubtitle}>
            {isConnected && systemInfo
              ? `${systemInfo.hostname} — ${systemInfo.platform}`
              : 'Cannot reach backend server'}
          </Text>
        </View>
      </View>

      {systemInfo && (
        <>
          {/* Stats Grid */}
          <View style={styles.statsGrid}>
            <StatCard
              icon="speedometer"
              iconColor={Colors.blueLight}
              iconBg={Colors.blueBg}
              label="CPU Usage"
              value={`${systemInfo.cpu_percent ?? '—'}%`}
              subtext="Current utilization"
            />
            <StatCard
              icon="hardware-chip"
              iconColor={Colors.purple}
              iconBg={Colors.purpleBg}
              label="Memory"
              value={`${systemInfo.memory_percent ?? '—'}%`}
              subtext={
                systemInfo.memory_used_gb ? `${systemInfo.memory_used_gb} / ${systemInfo.memory_total_gb} GB` : undefined
              }
            />
            <StatCard
              icon="server"
              iconColor={Colors.amberLight}
              iconBg={Colors.amberBg}
              label="Disk"
              value={`${systemInfo.disk_percent ?? '—'}%`}
              subtext={
                systemInfo.disk_used_gb ? `${systemInfo.disk_used_gb} / ${systemInfo.disk_total_gb} GB` : undefined
              }
            />
          </View>

          {/* Progress Bars */}
          <View style={styles.progressCard}>
            <Text style={styles.progressTitle}>Resource Utilization</Text>

            <View style={styles.progressRow}>
              <View style={styles.progressLabelRow}>
                <Text style={styles.progressLabel}>CPU</Text>
                <Text style={styles.progressValue}>{systemInfo.cpu_percent ?? 0}%</Text>
              </View>
              <ProgressBar value={systemInfo.cpu_percent ?? 0} color={Colors.blue} />
            </View>

            <View style={styles.progressRow}>
              <View style={styles.progressLabelRow}>
                <Text style={styles.progressLabel}>Memory</Text>
                <Text style={styles.progressValue}>{systemInfo.memory_percent ?? 0}%</Text>
              </View>
              <ProgressBar value={systemInfo.memory_percent ?? 0} color={Colors.purple} />
            </View>

            <View style={styles.progressRow}>
              <View style={styles.progressLabelRow}>
                <Text style={styles.progressLabel}>Disk</Text>
                <Text style={styles.progressValue}>{systemInfo.disk_percent ?? 0}%</Text>
              </View>
              <ProgressBar value={systemInfo.disk_percent ?? 0} color={Colors.amber} />
            </View>
          </View>
        </>
      )}

      {!isConnected && !isLoading && (
        <View style={styles.disconnectedCard}>
          <Ionicons name="cloud-offline" size={48} color={Colors.mutedDark} />
          <Text style={styles.disconnectedTitle}>Backend Not Available</Text>
          <Text style={styles.disconnectedText}>Start the DevPilot agent to see system analytics.</Text>
          <View style={styles.codeBlock}>
            <Text style={styles.codeText}>cd devpilot-agent && python -m app.main</Text>
          </View>
        </View>
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
  refreshBtn: {
    padding: Spacing.sm,
  },
  connectionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    marginBottom: Spacing.xl,
  },
  connectionTitle: {
    fontSize: FontSize.sm,
    fontWeight: '600',
  },
  connectionSubtitle: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 2,
  },
  statsGrid: {
    gap: Spacing.md,
    marginBottom: Spacing.xl,
  },
  statCard: {
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
  },
  statHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  statIcon: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statLabel: {
    fontSize: FontSize.sm,
    color: Colors.muted,
  },
  statValue: {
    fontSize: FontSize.xxl,
    fontWeight: 'bold',
    color: Colors.foreground,
  },
  statSubtext: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 4,
  },
  progressCard: {
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
  },
  progressTitle: {
    fontSize: FontSize.md,
    fontWeight: 'bold',
    color: Colors.foreground,
    marginBottom: Spacing.lg,
  },
  progressRow: {
    marginBottom: Spacing.lg,
  },
  progressLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  progressLabel: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  progressValue: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  progressBg: {
    height: 8,
    backgroundColor: Colors.cardLight,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  disconnectedCard: {
    alignItems: 'center',
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    padding: Spacing.xxl,
  },
  disconnectedTitle: {
    fontSize: FontSize.lg,
    fontWeight: '600',
    color: Colors.foreground,
    marginTop: Spacing.lg,
  },
  disconnectedText: {
    fontSize: FontSize.sm,
    color: Colors.muted,
    marginTop: Spacing.sm,
    textAlign: 'center',
  },
  codeBlock: {
    backgroundColor: Colors.codeBg,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.lg,
  },
  codeText: {
    fontSize: FontSize.xs,
    color: Colors.greenLight,
    fontFamily: 'monospace',
  },
});
