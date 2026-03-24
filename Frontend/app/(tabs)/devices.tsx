import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  RefreshControl,
  Modal,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '@/lib/theme';
import {
  listDevices,
  registerDevice,
  deleteDevice,
  executeOnDevice,
  getDeviceStatus,
  rotateDeviceToken,
  DeviceInfo,
} from '@/lib/api';

export default function DevicesScreen() {
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCommandModal, setShowCommandModal] = useState(false);
  const [newDeviceName, setNewDeviceName] = useState('');
  const [selectedDevice, setSelectedDevice] = useState<DeviceInfo | null>(null);
  const [command, setCommand] = useState('');
  const [commandResult, setCommandResult] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [newDeviceToken, setNewDeviceToken] = useState<string | null>(null);

  const loadDevices = useCallback(async () => {
    try {
      const deviceList = await listDevices();
      setDevices(deviceList);
    } catch (error: any) {
      console.error('Failed to load devices:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDevices();
    // Refresh device status every 30 seconds
    const interval = setInterval(loadDevices, 30000);
    return () => clearInterval(interval);
  }, [loadDevices]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadDevices();
  }, [loadDevices]);

  const handleAddDevice = async () => {
    if (!newDeviceName.trim()) {
      Alert.alert('Error', 'Please enter a device name');
      return;
    }

    try {
      const device = await registerDevice(newDeviceName.trim());
      setNewDeviceToken(device.token);
      setDevices(prev => [...prev, device]);
      setNewDeviceName('');
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to add device');
    }
  };

  const handleDeleteDevice = (device: DeviceInfo) => {
    Alert.alert(
      'Delete Device',
      `Are you sure you want to delete "${device.name}"? This action cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteDevice(device.id);
              setDevices(prev => prev.filter(d => d.id !== device.id));
            } catch (error: any) {
              Alert.alert('Error', error.message || 'Failed to delete device');
            }
          },
        },
      ]
    );
  };

  const handleRotateToken = async (device: DeviceInfo) => {
    Alert.alert(
      'Rotate Token',
      `This will invalidate the current token for "${device.name}". You'll need to update the remote agent with the new token.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Rotate',
          style: 'destructive',
          onPress: async () => {
            try {
              const result = await rotateDeviceToken(device.id);
              Alert.alert(
                'Token Rotated',
                `New token: ${result.token.substring(0, 20)}...\n\nUpdate your remote agent with this new token.`
              );
            } catch (error: any) {
              Alert.alert('Error', error.message || 'Failed to rotate token');
            }
          },
        },
      ]
    );
  };

  const handleExecuteCommand = async () => {
    if (!selectedDevice || !command.trim()) return;

    setExecuting(true);
    setCommandResult(null);

    try {
      const result = await executeOnDevice(selectedDevice.id, command.trim());
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

  const openCommandModal = (device: DeviceInfo) => {
    setSelectedDevice(device);
    setCommand('');
    setCommandResult(null);
    setShowCommandModal(true);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return Colors.green;
      case 'connecting':
        return Colors.yellow;
      default:
        return Colors.red;
    }
  };

  const renderDevice = (device: DeviceInfo) => (
    <View key={device.id} style={styles.deviceCard}>
      <View style={styles.deviceHeader}>
        <View style={styles.deviceInfo}>
          <View style={styles.deviceNameRow}>
            <Ionicons name="laptop-outline" size={24} color={Colors.primary} />
            <Text style={styles.deviceName}>{device.name}</Text>
          </View>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: getStatusColor(device.status) }]} />
            <Text style={[styles.statusText, { color: getStatusColor(device.status) }]}>
              {device.status.charAt(0).toUpperCase() + device.status.slice(1)}
            </Text>
          </View>
        </View>
        <View style={styles.deviceActions}>
          {device.status === 'online' && (
            <TouchableOpacity
              style={[styles.actionButton, styles.executeButton]}
              onPress={() => openCommandModal(device)}
            >
              <Ionicons name="terminal" size={18} color={Colors.foreground} />
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={[styles.actionButton, styles.rotateButton]}
            onPress={() => handleRotateToken(device)}
          >
            <Ionicons name="refresh" size={18} color={Colors.foreground} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, styles.deleteButton]}
            onPress={() => handleDeleteDevice(device)}
          >
            <Ionicons name="trash" size={18} color={Colors.red} />
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.deviceDetails}>
        {device.hostname && (
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Hostname:</Text>
            <Text style={styles.detailValue}>{device.hostname}</Text>
          </View>
        )}
        {device.platform && (
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Platform:</Text>
            <Text style={styles.detailValue}>{device.platform}</Text>
          </View>
        )}
        {device.last_seen && (
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Last seen:</Text>
            <Text style={styles.detailValue}>
              {new Date(device.last_seen).toLocaleString()}
            </Text>
          </View>
        )}
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Capabilities:</Text>
          <View style={styles.capabilitiesRow}>
            {device.capabilities.map((cap, i) => (
              <View key={i} style={styles.capabilityBadge}>
                <Text style={styles.capabilityText}>{cap}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading devices...</Text>
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
        {/* Header Section */}
        <View style={styles.headerSection}>
          <Text style={styles.headerTitle}>Connected Devices</Text>
          <Text style={styles.headerSubtitle}>
            Manage your laptops and execute remote commands
          </Text>
        </View>

        {/* Add Device Button */}
        <TouchableOpacity style={styles.addButton} onPress={() => setShowAddModal(true)}>
          <Ionicons name="add-circle" size={24} color={Colors.foreground} />
          <Text style={styles.addButtonText}>Add New Device</Text>
        </TouchableOpacity>

        {/* Device List */}
        {devices.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="laptop-outline" size={64} color={Colors.muted} />
            <Text style={styles.emptyTitle}>No Devices</Text>
            <Text style={styles.emptySubtitle}>
              Add a device and run the remote agent on your laptop to connect it.
            </Text>
          </View>
        ) : (
          devices.map(renderDevice)
        )}

        {/* Instructions */}
        <View style={styles.instructionsCard}>
          <Text style={styles.instructionsTitle}>How to Connect a Laptop</Text>
          <View style={styles.step}>
            <Text style={styles.stepNumber}>1</Text>
            <Text style={styles.stepText}>Add a new device above to get a token</Text>
          </View>
          <View style={styles.step}>
            <Text style={styles.stepNumber}>2</Text>
            <Text style={styles.stepText}>Copy the remote_agent.py to your laptop</Text>
          </View>
          <View style={styles.step}>
            <Text style={styles.stepNumber}>3</Text>
            <Text style={styles.stepText}>Run: python remote_agent.py --server YOUR_SERVER --token YOUR_TOKEN</Text>
          </View>
          <View style={styles.step}>
            <Text style={styles.stepNumber}>4</Text>
            <Text style={styles.stepText}>The device will appear as "Online" when connected</Text>
          </View>
        </View>
      </ScrollView>

      {/* Add Device Modal */}
      <Modal visible={showAddModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Add New Device</Text>

            {newDeviceToken ? (
              <>
                <View style={styles.successBox}>
                  <Ionicons name="checkmark-circle" size={48} color={Colors.green} />
                  <Text style={styles.successText}>Device Created!</Text>
                </View>
                <Text style={styles.tokenLabel}>Your Device Token:</Text>
                <View style={styles.tokenBox}>
                  <Text style={styles.tokenText} selectable>
                    {newDeviceToken}
                  </Text>
                </View>
                <Text style={styles.tokenWarning}>
                  Save this token! It won't be shown again.
                </Text>
                <TouchableOpacity
                  style={styles.modalButton}
                  onPress={() => {
                    setNewDeviceToken(null);
                    setShowAddModal(false);
                  }}
                >
                  <Text style={styles.modalButtonText}>Done</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <TextInput
                  style={styles.input}
                  placeholder="Device Name (e.g., Work Laptop)"
                  placeholderTextColor={Colors.muted}
                  value={newDeviceName}
                  onChangeText={setNewDeviceName}
                />
                <View style={styles.modalButtons}>
                  <TouchableOpacity
                    style={[styles.modalButton, styles.cancelButton]}
                    onPress={() => setShowAddModal(false)}
                  >
                    <Text style={styles.cancelButtonText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.modalButton} onPress={handleAddDevice}>
                    <Text style={styles.modalButtonText}>Add Device</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>

      {/* Execute Command Modal */}
      <Modal visible={showCommandModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, styles.commandModalContent]}>
            <View style={styles.commandHeader}>
              <Text style={styles.modalTitle}>
                Execute on {selectedDevice?.name}
              </Text>
              <TouchableOpacity onPress={() => setShowCommandModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>

            <TextInput
              style={styles.commandInput}
              placeholder="Enter command (e.g., ls -la)"
              placeholderTextColor={Colors.muted}
              value={command}
              onChangeText={setCommand}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <TouchableOpacity
              style={[styles.executeCommandButton, executing && styles.disabledButton]}
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
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollView: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  loadingText: {
    marginTop: 12,
    color: Colors.muted,
    fontSize: 14,
  },
  headerSection: {
    padding: 20,
    paddingBottom: 0,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: Colors.foreground,
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: Colors.muted,
  },
  addButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary,
    margin: 20,
    padding: 16,
    borderRadius: 12,
    gap: 8,
  },
  addButtonText: {
    color: Colors.foreground,
    fontSize: 16,
    fontWeight: '600',
  },
  deviceCard: {
    backgroundColor: Colors.card,
    marginHorizontal: 20,
    marginBottom: 16,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  deviceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  deviceInfo: {
    flex: 1,
  },
  deviceNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  deviceName: {
    fontSize: 18,
    fontWeight: '600',
    color: Colors.foreground,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    marginLeft: 32,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '500',
  },
  deviceActions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  executeButton: {
    backgroundColor: Colors.primary,
  },
  rotateButton: {
    backgroundColor: Colors.cardLight,
  },
  deleteButton: {
    backgroundColor: Colors.cardLight,
  },
  deviceDetails: {
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    paddingTop: 12,
  },
  detailRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  detailLabel: {
    width: 100,
    fontSize: 13,
    color: Colors.muted,
  },
  detailValue: {
    flex: 1,
    fontSize: 13,
    color: Colors.foreground,
  },
  capabilitiesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  capabilityBadge: {
    backgroundColor: Colors.primary + '30',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  capabilityText: {
    fontSize: 11,
    color: Colors.primary,
    fontWeight: '500',
  },
  emptyState: {
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: Colors.foreground,
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: Colors.muted,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  instructionsCard: {
    backgroundColor: Colors.card,
    margin: 20,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  instructionsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.foreground,
    marginBottom: 16,
  },
  step: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  stepNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primary,
    color: Colors.foreground,
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
    lineHeight: 24,
    marginRight: 12,
  },
  stepText: {
    flex: 1,
    fontSize: 14,
    color: Colors.muted,
    lineHeight: 20,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: Colors.card,
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 400,
  },
  commandModalContent: {
    maxHeight: '80%',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.foreground,
    marginBottom: 20,
  },
  input: {
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    padding: 14,
    fontSize: 16,
    color: Colors.foreground,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 20,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  modalButton: {
    flex: 1,
    backgroundColor: Colors.primary,
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelButton: {
    backgroundColor: Colors.cardLight,
  },
  modalButtonText: {
    color: Colors.foreground,
    fontSize: 16,
    fontWeight: '600',
  },
  cancelButtonText: {
    color: Colors.muted,
    fontSize: 16,
    fontWeight: '600',
  },
  successBox: {
    alignItems: 'center',
    marginBottom: 20,
  },
  successText: {
    fontSize: 18,
    fontWeight: '600',
    color: Colors.green,
    marginTop: 8,
  },
  tokenLabel: {
    fontSize: 14,
    color: Colors.muted,
    marginBottom: 8,
  },
  tokenBox: {
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  tokenText: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: Colors.cyan,
    lineHeight: 18,
  },
  tokenWarning: {
    fontSize: 13,
    color: Colors.yellow,
    textAlign: 'center',
    marginBottom: 20,
  },
  commandHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  commandInput: {
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    padding: 14,
    fontSize: 14,
    fontFamily: 'monospace',
    color: Colors.foreground,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 16,
  },
  executeCommandButton: {
    flexDirection: 'row',
    backgroundColor: Colors.green,
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  disabledButton: {
    opacity: 0.6,
  },
  executeButtonText: {
    color: Colors.foreground,
    fontSize: 16,
    fontWeight: '600',
  },
  resultBox: {
    marginTop: 16,
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    padding: 12,
    maxHeight: 200,
  },
  resultLabel: {
    fontSize: 12,
    color: Colors.muted,
    marginBottom: 8,
  },
  resultScroll: {
    maxHeight: 160,
  },
  resultText: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: Colors.cyan,
    lineHeight: 18,
  },
});
