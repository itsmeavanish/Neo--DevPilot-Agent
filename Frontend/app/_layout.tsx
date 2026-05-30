import React, { useState, useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../lib/theme';
import configManager from '../lib/config';
import { checkPairingCode, getPairedLaptopStatus, LaptopStatus } from '../lib/api';

function PairingScreen({ onPaired }: { onPaired: () => void }) {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showUrlModal, setShowUrlModal] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState(configManager.backendUrl);

  const handlePair = async () => {
    const cleanCode = code.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    if (cleanCode.length < 4) {
      setError('Please enter the pairing code from your laptop');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const status = await checkPairingCode(code);
      if (status.online) {
        await configManager.pairWithLaptop(status.pairingCode, status.hostname);
        onPaired();
      } else {
        setError('Laptop found but not online. Make sure the agent is running.');
      }
    } catch (err: any) {
      setError(err.message || 'Invalid pairing code');
    } finally {
      setLoading(false);
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
      setShowUrlModal(false);
      Alert.alert('Success', 'Server URL updated successfully');
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to save Server URL');
    }
  };

  return (
    <View style={styles.container}>
      {/* Settings / Server URL Button */}
      <TouchableOpacity
        style={styles.serverSettingsButton}
        onPress={() => {
          setServerUrlInput(configManager.backendUrl);
          setShowUrlModal(true);
        }}
      >
        <Ionicons name="cog-outline" size={24} color={Colors.muted} />
      </TouchableOpacity>

      <View style={styles.content}>
        <Ionicons name="laptop-outline" size={80} color={Colors.primary} />
        <Text style={styles.title}>Connect to Your Laptop</Text>
        <Text style={styles.subtitle}>
          Enter the pairing code shown on your laptop&apos;s JARVIS Agent window.
        </Text>
        <Text style={styles.hint}>
          On a real phone: in Settings, set Server URL to your PC&apos;s ngrok HTTPS URL (not localhost). The phone must use the same tunnel as this app.
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Enter Pairing Code (e.g., A1B2C3)"
          placeholderTextColor={Colors.muted}
          value={code}
          onChangeText={(text) => {
            setCode(text.toUpperCase());
            setError('');
          }}
          autoCapitalize="characters"
          autoCorrect={false}
          maxLength={8}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handlePair}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color={Colors.foreground} />
          ) : (
            <>
              <Ionicons name="link" size={20} color={Colors.foreground} />
              <Text style={styles.buttonText}>Connect</Text>
            </>
          )}
        </TouchableOpacity>

        <View style={styles.instructions}>
          <Text style={styles.instructionsTitle}>How to get your pairing code:</Text>
          <Text style={styles.instructionStep}>1. Run install.bat on your laptop</Text>
          <Text style={styles.instructionStep}>2. Click "JARVIS Agent" on desktop</Text>
          <Text style={styles.instructionStep}>3. Copy the 6-character code shown</Text>
        </View>
      </View>

      {/* Server URL Config Modal */}
      <Modal visible={showUrlModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Configure Server URL</Text>
              <TouchableOpacity onPress={() => setShowUrlModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Enter your backend server URL (e.g. ngrok HTTPS URL or public server domain).
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="https://your-server.ngrok-free.dev"
              placeholderTextColor={Colors.muted}
              value={serverUrlInput}
              onChangeText={setServerUrlInput}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowUrlModal(false)}
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
    </View>
  );
}

function ConnectedScreen({ laptop, onDisconnect }: { laptop: LaptopStatus; onDisconnect: () => void }) {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: Colors.background },
        }}
      >
        <Stack.Screen name="(tabs)" />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  const [isLoading, setIsLoading] = useState(true);
  const [isPaired, setIsPaired] = useState(false);
  const [laptop, setLaptop] = useState<LaptopStatus | null>(null);

  useEffect(() => {
    checkPairing();
  }, []);

  const checkPairing = async () => {
    await configManager.init();

    if (configManager.isPaired) {
      const status = await getPairedLaptopStatus();
      if (status) {
        setLaptop(status);
        setIsPaired(true);
      }
    }
    setIsLoading(false);
  };

  const handlePaired = async () => {
    const status = await getPairedLaptopStatus();
    setLaptop(status);
    setIsPaired(true);
  };

  const handleDisconnect = async () => {
    await configManager.unpair();
    setIsPaired(false);
    setLaptop(null);
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!isPaired) {
    return (
      <>
        <StatusBar style="light" />
        <PairingScreen onPaired={handlePaired} />
      </>
    );
  }

  return <ConnectedScreen laptop={laptop!} onDisconnect={handleDisconnect} />;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  content: {
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: Colors.foreground,
    marginTop: 24,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: Colors.muted,
    textAlign: 'center',
    marginBottom: 12,
    lineHeight: 22,
  },
  hint: {
    fontSize: 13,
    color: Colors.primary,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
    paddingHorizontal: 8,
  },
  input: {
    width: '100%',
    backgroundColor: Colors.card,
    borderRadius: 12,
    padding: 16,
    fontSize: 24,
    fontWeight: 'bold',
    color: Colors.foreground,
    textAlign: 'center',
    letterSpacing: 4,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 16,
  },
  error: {
    color: Colors.red,
    fontSize: 14,
    marginBottom: 16,
    textAlign: 'center',
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary,
    width: '100%',
    padding: 16,
    borderRadius: 12,
    gap: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: Colors.foreground,
    fontSize: 18,
    fontWeight: '600',
  },
  instructions: {
    marginTop: 48,
    padding: 20,
    backgroundColor: Colors.card,
    borderRadius: 12,
    width: '100%',
  },
  instructionsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.foreground,
    marginBottom: 12,
  },
  instructionStep: {
    fontSize: 14,
    color: Colors.muted,
    marginBottom: 8,
    lineHeight: 20,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: Colors.muted,
    fontSize: 16,
  },
  serverSettingsButton: {
    position: 'absolute',
    top: 50,
    right: 24,
    padding: 10,
    zIndex: 10,
  },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: Colors.card, borderRadius: 16, padding: 20, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 20, fontWeight: 'bold', color: Colors.foreground },
  modalDescription: { fontSize: 14, color: Colors.muted, marginBottom: 16, lineHeight: 20 },
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
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 12 },
  modalButton: {
    backgroundColor: Colors.primary,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalButtonText: { color: Colors.background, fontSize: 15, fontWeight: '600' },
  modalSecondaryButton: {
    backgroundColor: Colors.cardLight,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalSecondaryButtonText: { color: Colors.foreground, fontSize: 15, fontWeight: '500' },
});
