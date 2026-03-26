import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Modal,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../lib/theme';
import configManager from '../lib/config';
import { getPairedLaptopStatus, executeCommand, LaptopStatus } from '../lib/api';

export default function DevicesScreen() {
  const [laptop, setLaptop] = useState<LaptopStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCommandModal, setShowCommandModal] = useState(false);
  const [command, setCommand] = useState('');
  const [commandResult, setCommandResult] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);

  const loadLaptopStatus = useCallback(async () => {
    try {
      const status = await getPairedLaptopStatus();
      setLaptop(status);
    } catch (error) {
      console.error('Failed to load laptop status:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadLaptopStatus();
    const interval = setInterval(loadLaptopStatus, 10000);
    return () => clearInterval(interval);
  }, [loadLaptopStatus]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadLaptopStatus();
  }, [loadLaptopStatus]);

  const handleExecuteCommand = async () => {
    if (!command.trim()) return;

    setExecuting(true);
    setCommandResult(null);

    try {
      const result = await executeCommand(command.trim());
      setCommandResult(
        result.success
          ? result.stdout || 'Command executed successfully'
          : result.error || result.stderr || 'Command failed'
      );
    } catch (error: any) {
      setCommandResult(`Error: ${error.message}`);
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Checking laptop status...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />
        }
      >
        <View style={styles.headerSection}>
          <Text style={styles.headerTitle}>My Laptop</Text>
          <Text style={styles.headerSubtitle}>
            Paired with code: {configManager.pairingCode}
          </Text>
        </View>

        {/* Laptop Card */}
        <View style={styles.laptopCard}>
          <View style={styles.laptopHeader}>
            <Ionicons name="laptop-outline" size={48} color={Colors.primary} />
            <View style={styles.laptopInfo}>
              <Text style={styles.laptopName}>{laptop?.hostname || 'My Laptop'}</Text>
              <Text style={styles.laptopPlatform}>{laptop?.platform || 'Windows'}</Text>
            </View>
            <View style={styles.statusBadge}>
              <View style={[styles.statusDot, { backgroundColor: laptop?.online ? Colors.green : Colors.red }]} />
              <Text style={[styles.statusText, { color: laptop?.online ? Colors.green : Colors.red }]}>
                {laptop?.online ? 'Online' : 'Offline'}
              </Text>
            </View>
          </View>

          {laptop?.online ? (
            <TouchableOpacity
              style={styles.commandButton}
              onPress={() => setShowCommandModal(true)}
            >
              <Ionicons name="terminal" size={20} color={Colors.foreground} />
              <Text style={styles.commandButtonText}>Run Command</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.offlineMessage}>
              <Ionicons name="warning-outline" size={20} color={Colors.yellow} />
              <Text style={styles.offlineText}>
                Start the JARVIS Agent on your laptop to connect
              </Text>
            </View>
          )}
        </View>

        {/* Quick Actions */}
        {laptop?.online && (
          <View style={styles.quickActions}>
            <Text style={styles.sectionTitle}>Quick Actions</Text>
            <View style={styles.actionGrid}>
              <TouchableOpacity
                style={styles.actionCard}
                onPress={() => {
                  setCommand('dir');
                  setShowCommandModal(true);
                }}
              >
                <Ionicons name="folder-outline" size={24} color={Colors.primary} />
                <Text style={styles.actionText}>List Files</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.actionCard}
                onPress={() => {
                  setCommand('ipconfig');
                  setShowCommandModal(true);
                }}
              >
                <Ionicons name="wifi-outline" size={24} color={Colors.primary} />
                <Text style={styles.actionText}>Network Info</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.actionCard}
                onPress={() => {
                  setCommand('tasklist');
                  setShowCommandModal(true);
                }}
              >
                <Ionicons name="list-outline" size={24} color={Colors.primary} />
                <Text style={styles.actionText}>Processes</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.actionCard}
                onPress={() => {
                  setCommand('systeminfo');
                  setShowCommandModal(true);
                }}
              >
                <Ionicons name="information-circle-outline" size={24} color={Colors.primary} />
                <Text style={styles.actionText}>System Info</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Command Modal */}
      <Modal visible={showCommandModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Run Command</Text>
              <TouchableOpacity onPress={() => {
                setShowCommandModal(false);
                setCommandResult(null);
              }}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>

            <TextInput
              style={styles.commandInput}
              placeholder="Enter command..."
              placeholderTextColor={Colors.muted}
              value={command}
              onChangeText={setCommand}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <TouchableOpacity
              style={[styles.executeButton, executing && styles.disabledButton]}
              onPress={handleExecuteCommand}
              disabled={executing}
            >
              {executing ? (
                <ActivityIndicator size="small" color={Colors.foreground} />
              ) : (
                <>
                  <Ionicons name="play" size={20} color={Colors.foreground} />
                  <Text style={styles.executeButtonText}>Execute</Text>
                </>
              )}
            </TouchableOpacity>

            {commandResult && (
              <View style={styles.resultBox}>
                <Text style={styles.resultLabel}>Output:</Text>
                <ScrollView style={styles.resultScroll}>
                  <Text style={styles.resultText}>{commandResult}</Text>
                </ScrollView>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scrollView: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.background },
  loadingText: { marginTop: 12, color: Colors.muted, fontSize: 14 },
  headerSection: { padding: 20, paddingBottom: 10 },
  headerTitle: { fontSize: 28, fontWeight: 'bold', color: Colors.foreground },
  headerSubtitle: { fontSize: 14, color: Colors.muted, marginTop: 4 },
  laptopCard: {
    backgroundColor: Colors.card,
    margin: 20,
    marginTop: 10,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  laptopHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  laptopInfo: { flex: 1, marginLeft: 16 },
  laptopName: { fontSize: 20, fontWeight: '600', color: Colors.foreground },
  laptopPlatform: { fontSize: 14, color: Colors.muted, marginTop: 2 },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 10, height: 10, borderRadius: 5 },
  statusText: { fontSize: 14, fontWeight: '500' },
  commandButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary,
    padding: 14,
    borderRadius: 10,
    gap: 8,
  },
  commandButtonText: { color: Colors.foreground, fontSize: 16, fontWeight: '600' },
  offlineMessage: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.cardLight,
    padding: 12,
    borderRadius: 8,
    gap: 10,
  },
  offlineText: { flex: 1, color: Colors.yellow, fontSize: 14 },
  quickActions: { paddingHorizontal: 20 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: Colors.foreground, marginBottom: 12 },
  actionGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  actionCard: {
    width: '47%',
    backgroundColor: Colors.card,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  actionText: { color: Colors.foreground, fontSize: 14, fontWeight: '500' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: Colors.card, borderRadius: 16, padding: 20, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 20, fontWeight: 'bold', color: Colors.foreground },
  commandInput: {
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    padding: 14,
    fontSize: 16,
    color: Colors.foreground,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 12,
  },
  executeButton: {
    flexDirection: 'row',
    backgroundColor: Colors.green,
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  disabledButton: { opacity: 0.6 },
  executeButtonText: { color: Colors.foreground, fontSize: 16, fontWeight: '600' },
  resultBox: { marginTop: 16, backgroundColor: Colors.cardLight, borderRadius: 8, padding: 12, maxHeight: 200 },
  resultLabel: { fontSize: 12, color: Colors.muted, marginBottom: 8 },
  resultScroll: { maxHeight: 160 },
  resultText: { fontSize: 12, fontFamily: 'monospace', color: Colors.cyan, lineHeight: 18 },
});
