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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '@/lib/theme';
import configManager from '@/lib/config';
import { checkPairingCode, getPairedLaptopStatus, LaptopStatus } from '@/lib/api';

function PairingScreen({ onPaired }: { onPaired: () => void }) {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handlePair = async () => {
    const cleanCode = code.toUpperCase().trim();
    if (cleanCode.length < 4) {
      setError('Please enter the pairing code from your laptop');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const status = await checkPairingCode(cleanCode);
      if (status.online) {
        await configManager.pairWithLaptop(cleanCode, status.hostname);
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

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Ionicons name="laptop-outline" size={80} color={Colors.primary} />
        <Text style={styles.title}>Connect to Your Laptop</Text>
        <Text style={styles.subtitle}>
          Enter the pairing code shown on your laptop's JARVIS Agent window
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
    marginBottom: 32,
    lineHeight: 22,
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
});
