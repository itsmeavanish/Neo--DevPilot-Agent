import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
  TextInput,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../lib/theme';
import configManager from '../../lib/config';
import {
  getPairedLaptopStatus,
  checkHealth,
  LaptopStatus,
  getAIProviders,
  getFreeLLMStatus,
  setFreeLLMConfig,
  autoConfigureFreeLLM,
  executeCommand,
} from '@/lib/api';

export default function SettingsScreen() {
  const [laptop, setLaptop] = useState<LaptopStatus | null>(null);
  const [serverOnline, setServerOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [disconnected, setDisconnected] = useState(false);

  // AI Provider states
  const [aiProviders, setAiProviders] = useState<any>(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [freellmStatus, setFreellmStatus] = useState<any>(null);

  // Device management states
  const [showCommandModal, setShowCommandModal] = useState(false);
  const [deviceCommand, setDeviceCommand] = useState('');
  const [commandResult, setCommandResult] = useState<string | null>(null);
  const [executingCommand, setExecutingCommand] = useState(false);

  // Modal states
  const [showFreellmModal, setShowFreellmModal] = useState(false);
  const [showServerUrlModal, setShowServerUrlModal] = useState(false);

  // Input states
  const [freellmKeyInput, setFreellmKeyInput] = useState('');
  const [freellmUrlInput, setFreellmUrlInput] = useState('https://neo-devpilot-agent.onrender.com/v1');
  const [serverUrlInput, setServerUrlInput] = useState('');

  useEffect(() => {
    loadStatus();
    loadAIStatus();
  }, []);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const health = await checkHealth();
      setServerOnline(health.status === 'ok');

      const status = await getPairedLaptopStatus();
      setLaptop(status);
    } catch {
      setServerOnline(false);
    } finally {
      setLoading(false);
    }
  };

  const loadAIStatus = async () => {
    setLoadingAI(true);
    try {
      const providers = await getAIProviders();
      setAiProviders(providers);

      let freellmStat = await getFreeLLMStatus();
      setFreellmStatus(freellmStat);

      // Auto-configure FreeLLM in background if not already configured
      if (!freellmStat.success) {
        autoConfigureFreeLLM().then(async (autoResult) => {
          if (autoResult.success) {
            const updated = await getFreeLLMStatus();
            setFreellmStatus(updated);
          }
        }).catch(() => {});
      }
    } catch (error) {
      console.warn('Failed to load AI status:', error);
    } finally {
      setLoadingAI(false);
    }
  };

  const handleDeviceCommand = async () => {
    if (!deviceCommand.trim()) return;
    setExecutingCommand(true);
    setCommandResult(null);
    try {
      const result = await executeCommand(deviceCommand.trim());
      setCommandResult(
        result.success
          ? result.stdout || 'Command executed successfully'
          : result.error || result.stderr || 'Command failed'
      );
    } catch (error: any) {
      setCommandResult(`Error: ${error.message}`);
    } finally {
      setExecutingCommand(false);
    }
  };

  const handleFreellmConfig = async () => {
    if (!freellmKeyInput.trim() || !freellmUrlInput.trim()) {
      Alert.alert('Error', 'Please enter a FreeLLM API key and URL');
      return;
    }

    try {
      const result = await setFreeLLMConfig(freellmKeyInput.trim(), freellmUrlInput.trim());
      if (result.success) {
        setShowFreellmModal(false);
        setFreellmKeyInput('');
        await loadAIStatus();
        Alert.alert('Success', 'FreeLLM configured successfully.');
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to configure FreeLLM');
    }
  };

  const handleFreellmAutoConfig = async () => {
    try {
      const result = await autoConfigureFreeLLM();
      if (result.success) {
        setShowFreellmModal(false);
        await loadAIStatus();
        Alert.alert('Success', 'FreeLLM auto-configured with permanent device key.');
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to auto-configure FreeLLM');
    }
  };

  const handleSaveServerUrl = async () => {
    let url = serverUrlInput.trim();
    if (!url) {
      Alert.alert('Error', 'Please enter a Server URL');
      return;
    }
    if (!/^https?:\/\//i.test(url)) {
      url = 'https://' + url;
    }
    try {
      await configManager.setBackendUrl(url, true);
      setShowServerUrlModal(false);
      await loadStatus();
      Alert.alert('Success', 'Server URL updated successfully');
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to save Server URL');
    }
  };

  const handleDisconnect = () => {
    Alert.alert(
      'Disconnect Laptop',
      'Are you sure you want to disconnect from this laptop? You will need to restart the app and enter the pairing code again.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: async () => {
            await configManager.unpair();
            setDisconnected(true);
          },
        },
      ]
    );
  };

  if (disconnected) {
    return (
      <View style={styles.disconnectedContainer}>
        <Ionicons name="checkmark-circle" size={64} color={Colors.green} />
        <Text style={styles.disconnectedTitle}>Disconnected</Text>
        <Text style={styles.disconnectedText}>
          Please close and reopen the app to pair with a new laptop.
        </Text>
      </View>
    );
  }

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Settings</Text>
      </View>

      {/* Paired Laptop Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Paired Laptop</Text>
        <View style={styles.card}>
          <View style={styles.cardRow}>
            <Ionicons name="laptop-outline" size={24} color={Colors.primary} />
            <View style={styles.cardInfo}>
              <Text style={styles.cardTitle}>{laptop?.hostname || configManager.laptopName || 'My Laptop'}</Text>
              <Text style={styles.cardSubtitle}>Code: {configManager.pairingCode}</Text>
            </View>
            <View style={styles.statusBadge}>
              <View style={[styles.statusDot, { backgroundColor: laptop?.online ? Colors.green : Colors.red }]} />
              <Text style={[styles.statusText, { color: laptop?.online ? Colors.green : Colors.red }]}>
                {laptop?.online ? 'Online' : 'Offline'}
              </Text>
            </View>
          </View>
        </View>
      </View>

      {/* Server Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Server Connection</Text>
        <View style={styles.card}>
          <View style={styles.cardRow}>
            <Ionicons name="cloud-outline" size={24} color={Colors.primary} />
            <View style={styles.cardInfo}>
              <Text style={styles.cardTitle}>JARVIS Server</Text>
              <Text style={styles.cardSubtitle} numberOfLines={1}>{configManager.backendUrl}</Text>
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <TouchableOpacity
                style={styles.configButton}
                onPress={() => {
                  setServerUrlInput(configManager.backendUrl);
                  setShowServerUrlModal(true);
                }}
              >
                <Ionicons name="create-outline" size={16} color={Colors.muted} />
              </TouchableOpacity>
              <View style={styles.statusBadge}>
                <View style={[styles.statusDot, { backgroundColor: serverOnline ? Colors.green : Colors.red }]} />
                <Text style={[styles.statusText, { color: serverOnline ? Colors.green : Colors.red }]}>
                  {serverOnline ? 'Online' : 'Offline'}
                </Text>
              </View>
            </View>
          </View>
        </View>
      </View>

      {/* Device Management */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Device Management</Text>
        <View style={styles.card}>
          <View style={styles.cardRow}>
            <Ionicons name="laptop-outline" size={24} color={Colors.primary} />
            <View style={styles.cardInfo}>
              <Text style={styles.cardTitle}>{laptop?.hostname || 'My Laptop'}</Text>
              <Text style={styles.cardSubtitle}>{laptop?.platform || 'Windows'}</Text>
            </View>
            <View style={styles.statusBadge}>
              <View style={[styles.statusDot, { backgroundColor: laptop?.online ? Colors.green : Colors.red }]} />
              <Text style={[styles.statusText, { color: laptop?.online ? Colors.green : Colors.red }]}>
                {laptop?.online ? 'Online' : 'Offline'}
              </Text>
            </View>
          </View>
          {laptop?.online && (
            <TouchableOpacity
              style={[styles.actionButton, { marginTop: 12, marginBottom: 0 }]}
              onPress={() => setShowCommandModal(true)}
            >
              <Ionicons name="terminal" size={20} color={Colors.foreground} />
              <Text style={styles.actionButtonText}>Run Command</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* AI Configuration - FreeLLM Only */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>AI Provider</Text>
          {loadingAI && <ActivityIndicator size="small" color={Colors.primary} />}
        </View>

        <View style={styles.providerCard}>
          <View style={styles.providerHeader}>
            <Ionicons name="infinite-outline" size={20} color={Colors.primary} />
            <Text style={styles.providerName}>FreeLLM</Text>
            <View style={[styles.statusDot, {
              backgroundColor: (freellmStatus?.success || aiProviders?.providers?.freellm?.available) ? Colors.green : Colors.red
            }]} />
          </View>
          <Text style={styles.providerStatus}>
            {freellmStatus?.message || aiProviders?.providers?.freellm?.message || 'Checking...'}
          </Text>
          <View style={styles.providerActions}>
            <TouchableOpacity
              style={[styles.providerButton, styles.activeProvider]}
              disabled
            >
              <Text style={[styles.providerButtonText, styles.activeProviderText]}>Active</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.configButton}
              onPress={() => setShowFreellmModal(true)}
            >
              <Ionicons name="settings-outline" size={16} color={Colors.foreground} />
            </TouchableOpacity>
          </View>
        </View>
      </View>

      {/* Actions */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Actions</Text>

        <TouchableOpacity style={styles.actionButton} onPress={loadStatus}>
          <Ionicons name="refresh-outline" size={22} color={Colors.foreground} />
          <Text style={styles.actionButtonText}>Refresh Connection Status</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.actionButton} onPress={loadAIStatus}>
          <Ionicons name="sparkles-outline" size={22} color={Colors.foreground} />
          <Text style={styles.actionButtonText}>Refresh AI Status</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.actionButton, styles.dangerButton]} onPress={handleDisconnect}>
          <Ionicons name="unlink-outline" size={22} color={Colors.red} />
          <Text style={[styles.actionButtonText, { color: Colors.red }]}>Disconnect Laptop</Text>
        </TouchableOpacity>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.card}>
          <Text style={styles.aboutText}>JARVIS DevPilot</Text>
          <Text style={styles.aboutVersion}>Version 1.0.0</Text>
          <Text style={styles.aboutDesc}>
            Control your laptop from your phone using AI-powered commands.
          </Text>
        </View>
      </View>

      <View style={styles.bottomPadding} />

      {/* FreeLLM Config Modal */}
      <Modal visible={showFreellmModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Configure FreeLLM</Text>
              <TouchableOpacity onPress={() => setShowFreellmModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Tap "Auto Configure" to get a permanent device key, or enter one manually.
            </Text>
            <TouchableOpacity style={[styles.modalButton, { marginBottom: 16, backgroundColor: Colors.green }]} onPress={handleFreellmAutoConfig}>
              <Text style={styles.modalButtonText}>Auto Configure (Recommended)</Text>
            </TouchableOpacity>
            <Text style={[styles.inputLabel, { textAlign: 'center', marginBottom: 8 }]}>— or enter manually —</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="freellmapi-..."
              placeholderTextColor={Colors.muted}
              value={freellmKeyInput}
              onChangeText={setFreellmKeyInput}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
            <Text style={styles.inputLabel}>Server URL</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="https://neo-devpilot-agent.onrender.com/v1"
              placeholderTextColor={Colors.muted}
              value={freellmUrlInput}
              onChangeText={setFreellmUrlInput}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity style={[styles.modalButton, styles.modalSecondaryButton]} onPress={() => setShowFreellmModal(false)}>
                <Text style={styles.modalSecondaryButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalButton} onPress={handleFreellmConfig}>
                <Text style={styles.modalButtonText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Server URL Modal */}
      <Modal visible={showServerUrlModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Configure Server URL</Text>
              <TouchableOpacity onPress={() => setShowServerUrlModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Enter your backend server URL (your PC's LAN IP or ngrok HTTPS URL).
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="https://neo-api-oths.onrender.com"
              placeholderTextColor={Colors.muted}
              value={serverUrlInput}
              onChangeText={setServerUrlInput}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowServerUrlModal(false)}
              >
                <Text style={styles.modalSecondaryButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalButton} onPress={handleSaveServerUrl}>
                <Text style={styles.modalButtonText}>Save URL</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Device Command Modal */}
      <Modal visible={showCommandModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Run Command</Text>
              <TouchableOpacity onPress={() => { setShowCommandModal(false); setCommandResult(null); }}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <TextInput
              style={styles.modalInput}
              placeholder="Enter command..."
              placeholderTextColor={Colors.muted}
              value={deviceCommand}
              onChangeText={setDeviceCommand}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity
              style={[styles.modalButton, { marginBottom: 12 }, executingCommand && { opacity: 0.6 }]}
              onPress={handleDeviceCommand}
              disabled={executingCommand}
            >
              {executingCommand ? (
                <ActivityIndicator size="small" color={Colors.background} />
              ) : (
                <Text style={styles.modalButtonText}>Execute</Text>
              )}
            </TouchableOpacity>
            {commandResult && (
              <View style={{ backgroundColor: Colors.cardLight, borderRadius: 8, padding: 12, maxHeight: 200 }}>
                <ScrollView>
                  <Text style={{ fontSize: 12, fontFamily: 'monospace', color: Colors.foreground, lineHeight: 18 }}>{commandResult}</Text>
                </ScrollView>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.background },
  header: { padding: 20, paddingBottom: 10 },
  headerTitle: { fontSize: 28, fontWeight: 'bold', color: Colors.foreground },
  section: { paddingHorizontal: 20, marginBottom: 24 },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: Colors.muted, marginBottom: 12, textTransform: 'uppercase' },
  card: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardRow: { flexDirection: 'row', alignItems: 'center' },
  cardInfo: { flex: 1, marginLeft: 12 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: Colors.foreground },
  cardSubtitle: { fontSize: 13, color: Colors.muted, marginTop: 2 },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 13, fontWeight: '500' },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.card,
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    gap: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  dangerButton: {
    borderColor: Colors.red + '40',
  },
  actionButtonText: { fontSize: 16, color: Colors.foreground, fontWeight: '500' },
  aboutText: { fontSize: 18, fontWeight: '600', color: Colors.foreground },
  aboutVersion: { fontSize: 14, color: Colors.muted, marginTop: 4 },
  aboutDesc: { fontSize: 14, color: Colors.muted, marginTop: 12, lineHeight: 20 },
  bottomPadding: { height: 40 },
  disconnectedContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.background, padding: 40 },
  disconnectedTitle: { fontSize: 24, fontWeight: 'bold', color: Colors.foreground, marginTop: 16 },
  disconnectedText: { fontSize: 16, color: Colors.muted, textAlign: 'center', marginTop: 12, lineHeight: 24 },

  // AI Provider Styles
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  providerCard: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  providerHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  providerName: { flex: 1, fontSize: 16, fontWeight: '600', color: Colors.foreground, marginLeft: 8 },
  providerStatus: { fontSize: 13, color: Colors.muted, marginBottom: 12, lineHeight: 18 },
  providerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  providerButton: {
    flex: 1,
    backgroundColor: Colors.cardLight,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  activeProvider: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  providerButtonText: { fontSize: 14, fontWeight: '500', color: Colors.foreground },
  activeProviderText: { color: Colors.background },
  configButton: {
    width: 32,
    height: 32,
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },

  // Modal Styles
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: Colors.card, borderRadius: 16, padding: 20, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 20, fontWeight: 'bold', color: Colors.foreground },
  modalDescription: { fontSize: 14, color: Colors.muted, marginBottom: 16, lineHeight: 20 },
  inputLabel: { fontSize: 14, fontWeight: '500', color: Colors.foreground, marginBottom: 8, marginTop: 8 },
  modalInput: {
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: Colors.foreground,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 16,
  },
  modalActions: { flexDirection: 'row', gap: 12 },
  modalButton: {
    flex: 1,
    backgroundColor: Colors.primary,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  modalSecondaryButton: { backgroundColor: Colors.cardLight, borderWidth: 1, borderColor: Colors.border },
  modalButtonText: { color: Colors.background, fontSize: 16, fontWeight: '600' },
  modalSecondaryButtonText: { color: Colors.foreground, fontSize: 16, fontWeight: '600' },
});
