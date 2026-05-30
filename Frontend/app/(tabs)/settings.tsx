import React, { useState, useEffect, useCallback } from 'react';
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
  setAIProvider,
  getCopilotStatus,
  getCopilotModels,
  setCopilotModel,
  getGitHubTokenStatus,
  setGitHubToken,
  clearGitHubToken,
  getOpenAIStatus,
  setOpenAIConfig,
  getGeminiStatus,
  setGeminiConfig,
  getOllamaStatus,
  setOllamaConfig,
  getOllamaModels,
} from '@/lib/api';

export default function SettingsScreen() {
  const [laptop, setLaptop] = useState<LaptopStatus | null>(null);
  const [serverOnline, setServerOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [disconnected, setDisconnected] = useState(false);

  // AI Provider states
  const [aiProviders, setAiProviders] = useState<any>(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [githubTokenStatus, setGithubTokenStatus] = useState<any>(null);
  const [openaiStatus, setOpenaiStatus] = useState<any>(null);
  const [geminiStatus, setGeminiStatus] = useState<any>(null);
  const [ollamaStatus, setOllamaStatus] = useState<any>(null);

  // Copilot CLI states
  const [copilotStatus, setCopilotStatus] = useState<any>(null);
  const [copilotModels, setCopilotModels] = useState<any>(null);
  const [showCopilotModelModal, setShowCopilotModelModal] = useState(false);

  // Modal states
  const [showGitHubTokenModal, setShowGitHubTokenModal] = useState(false);
  const [showOpenAIModal, setShowOpenAIModal] = useState(false);
  const [showGeminiModal, setShowGeminiModal] = useState(false);
  const [showOllamaModal, setShowOllamaModal] = useState(false);

  // Input states
  const [githubTokenInput, setGithubTokenInput] = useState('');
  const [openaiKeyInput, setOpenaiKeyInput] = useState('');
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [ollamaHostInput, setOllamaHostInput] = useState('http://localhost:11434');
  const [ollamaModelInput, setOllamaModelInput] = useState('llama3.2:1b');
  const [showServerUrlModal, setShowServerUrlModal] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState('');

  useEffect(() => {
    loadStatus();
    loadAIStatus();
  }, []);

  const loadStatus = async () => {
    setLoading(true);
    try {
      // Check server
      const health = await checkHealth();
      setServerOnline(health.status === 'ok');

      // Check laptop
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
      // Get AI providers status
      const providers = await getAIProviders();
      setAiProviders(providers);

      // Get Copilot CLI status (replaces GitHub token status)
      const copilotStat = await getCopilotStatus();
      setCopilotStatus(copilotStat);

      // Get Copilot models
      const models = await getCopilotModels();
      setCopilotModels(models);

      // Get other provider statuses
      const openaiStat = await getOpenAIStatus();
      setOpenaiStatus(openaiStat);

      const geminiStat = await getGeminiStatus();
      setGeminiStatus(geminiStat);

      const ollamaStat = await getOllamaStatus();
      setOllamaStatus(ollamaStat);

      // Keep GitHub token status for legacy compatibility
      const githubStatus = await getGitHubTokenStatus();
      setGithubTokenStatus(githubStatus);
    } catch (error) {
      console.warn('Failed to load AI status:', error);
    } finally {
      setLoadingAI(false);
    }
  };

  const handleProviderChange = async (provider: string) => {
    try {
      const result = await setAIProvider(provider);
      if (result.success) {
        await loadAIStatus(); // Refresh status
        Alert.alert('Success', `Switched to ${provider}`);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to change provider');
    }
  };

  const handleGitHubToken = async () => {
    if (!githubTokenInput.trim()) {
      Alert.alert('Error', 'Please enter a GitHub token');
      return;
    }

    try {
      const result = await setGitHubToken(githubTokenInput.trim());
      if (result.success) {
        setShowGitHubTokenModal(false);
        setGithubTokenInput('');
        await loadAIStatus();
        Alert.alert('Success', result.message);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to save GitHub token');
    }
  };

  const handleClearGitHubToken = async () => {
    Alert.alert(
      'Clear GitHub Token',
      'Are you sure you want to clear your GitHub token? This will disable Copilot API access.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            try {
              await clearGitHubToken();
              await loadAIStatus();
              Alert.alert('Success', 'GitHub token cleared');
            } catch (error: any) {
              Alert.alert('Error', error.message || 'Failed to clear token');
            }
          },
        },
      ]
    );
  };

  const handleOpenAIConfig = async () => {
    if (!openaiKeyInput.trim()) {
      Alert.alert('Error', 'Please enter an OpenAI API key');
      return;
    }

    try {
      const result = await setOpenAIConfig(openaiKeyInput.trim());
      if (result.success) {
        setShowOpenAIModal(false);
        setOpenaiKeyInput('');
        await loadAIStatus();
        Alert.alert('Success', result.message);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to configure OpenAI');
    }
  };

  const handleGeminiConfig = async () => {
    if (!geminiKeyInput.trim()) {
      Alert.alert('Error', 'Please enter a Gemini API key');
      return;
    }

    try {
      const result = await setGeminiConfig(geminiKeyInput.trim());
      if (result.success) {
        setShowGeminiModal(false);
        setGeminiKeyInput('');
        await loadAIStatus();
        Alert.alert('Success', result.message);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to configure Gemini');
    }
  };

  const handleOllamaConfig = async () => {
    try {
      const result = await setOllamaConfig(
        ollamaHostInput.trim(),
        ollamaModelInput.trim() || 'llama3.2:1b',
        true
      );
      if (result.success) {
        setShowOllamaModal(false);
        await loadAIStatus();
        await handleProviderChange('auto');
        Alert.alert('Success', result.message);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to configure Ollama');
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

  const handleCopilotModelChange = async (selectedModel: string) => {
    try {
      const result = await setCopilotModel(selectedModel);
      if (result.success) {
        setShowCopilotModelModal(false);
        await loadAIStatus();
        Alert.alert('Success', `Copilot model changed to ${selectedModel}`);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to change Copilot model');
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
              {configManager.isBackendUrlUnsafe && (
                <Text style={{ color: 'red', marginTop: 8 }}>
                  Warning: Backend URL is set to localhost or 127.0.0.1. This will not work in production APK. Please use your ngrok or public URL.
                </Text>
              )}
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

      {/* AI Configuration */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>AI Providers</Text>
          {loadingAI && <ActivityIndicator size="small" color={Colors.primary} />}
        </View>

        {/* Current Provider */}
        {aiProviders && (
          <View style={styles.card}>
            <View style={styles.cardRow}>
              <Ionicons name="sparkles" size={24} color={Colors.primary} />
              <View style={styles.cardInfo}>
                <Text style={styles.cardTitle}>Current Provider</Text>
                <Text style={styles.cardSubtitle}>{aiProviders.current || 'None selected'}</Text>
              </View>
              <TouchableOpacity onPress={loadAIStatus}>
                <Ionicons name="refresh-outline" size={20} color={Colors.muted} />
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Provider Options */}
        {aiProviders?.providers && (
          <View style={styles.providerGrid}>
            {/* GitHub Copilot CLI */}
            <View style={styles.providerCard}>
              <View style={styles.providerHeader}>
                <Ionicons name="logo-github" size={20} color={Colors.primary} />
                <Text style={styles.providerName}>GitHub Copilot CLI</Text>
                <View style={[styles.statusDot, {
                  backgroundColor: (copilotStatus?.authentication?.status === 'authenticated' &&
                                   copilotStatus?.copilot?.status === 'available') ? Colors.green : Colors.red
                }]} />
              </View>
              <Text style={styles.providerStatus}>
                {githubTokenStatus?.success
                  ? `Token: ${githubTokenStatus.message}`
                  : copilotStatus?.authentication?.message || 'Not linked'}
                {'\n'}
                {copilotStatus?.copilot?.message || 'Checking Copilot…'}
                {copilotStatus?.model?.current ? `\nModel: ${copilotStatus.model.current}` : ''}
              </Text>
              <View style={styles.providerActions}>
                <TouchableOpacity
                  style={styles.configButton}
                  onPress={() => setShowGitHubTokenModal(true)}
                >
                  <Ionicons name="key-outline" size={16} color={Colors.primary} />
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.providerButton, aiProviders.current === 'copilot' && styles.activeProvider]}
                  onPress={() => handleProviderChange('copilot')}
                >
                  <Text style={[styles.providerButtonText, aiProviders.current === 'copilot' && styles.activeProviderText]}>
                    {aiProviders.current === 'copilot' ? 'Active' : 'Use'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.configButton}
                  onPress={() => setShowCopilotModelModal(true)}
                >
                  <Ionicons name="cog-outline" size={16} color={Colors.muted} />
                </TouchableOpacity>
              </View>
            </View>

            {/* OpenAI */}
            <View style={styles.providerCard}>
              <View style={styles.providerHeader}>
                <Ionicons name="planet-outline" size={20} color={Colors.primary} />
                <Text style={styles.providerName}>OpenAI</Text>
                <View style={[styles.statusDot, {
                  backgroundColor: aiProviders.providers.openai?.available ? Colors.green : Colors.red
                }]} />
              </View>
              <Text style={styles.providerStatus}>
                {aiProviders.providers.openai?.message || 'Not configured'}
              </Text>
              <View style={styles.providerActions}>
                <TouchableOpacity
                  style={[styles.providerButton, aiProviders.current === 'openai' && styles.activeProvider]}
                  onPress={() => handleProviderChange('openai')}
                >
                  <Text style={[styles.providerButtonText, aiProviders.current === 'openai' && styles.activeProviderText]}>
                    {aiProviders.current === 'openai' ? 'Active' : 'Use'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.configButton}
                  onPress={() => setShowOpenAIModal(true)}
                >
                  <Ionicons name="settings-outline" size={16} color={Colors.muted} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Gemini */}
            <View style={styles.providerCard}>
              <View style={styles.providerHeader}>
                <Ionicons name="sparkles-outline" size={20} color={Colors.primary} />
                <Text style={styles.providerName}>Gemini</Text>
                <View style={[styles.statusDot, {
                  backgroundColor: aiProviders.providers.gemini?.available ? Colors.green : Colors.red
                }]} />
              </View>
              <Text style={styles.providerStatus}>
                {aiProviders.providers.gemini?.message || 'Not configured'}
              </Text>
              <View style={styles.providerActions}>
                <TouchableOpacity
                  style={[styles.providerButton, aiProviders.current === 'gemini' && styles.activeProvider]}
                  onPress={() => handleProviderChange('gemini')}
                >
                  <Text style={[styles.providerButtonText, aiProviders.current === 'gemini' && styles.activeProviderText]}>
                    {aiProviders.current === 'gemini' ? 'Active' : 'Use'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.configButton}
                  onPress={() => setShowGeminiModal(true)}
                >
                  <Ionicons name="settings-outline" size={16} color={Colors.muted} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Ollama */}
            <View style={styles.providerCard}>
              <View style={styles.providerHeader}>
                <Ionicons name="hardware-chip-outline" size={20} color={Colors.primary} />
                <Text style={styles.providerName}>Ollama</Text>
                <View style={[styles.statusDot, {
                  backgroundColor: aiProviders.providers.ollama?.available ? Colors.green : Colors.red
                }]} />
              </View>
              <Text style={styles.providerStatus}>
                {aiProviders.providers.ollama?.message || 'Not running'}
              </Text>
              <View style={styles.providerActions}>
                <TouchableOpacity
                  style={[styles.providerButton, aiProviders.current === 'ollama' && styles.activeProvider]}
                  onPress={() => handleProviderChange('ollama')}
                >
                  <Text style={[styles.providerButtonText, aiProviders.current === 'ollama' && styles.activeProviderText]}>
                    {aiProviders.current === 'ollama' ? 'Active' : 'Use'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.configButton}
                  onPress={() => setShowOllamaModal(true)}
                >
                  <Ionicons name="settings-outline" size={16} color={Colors.muted} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Cursor */}
            <View style={styles.providerCard}>
              <View style={styles.providerHeader}>
                <Ionicons name="code-slash-outline" size={20} color={Colors.primary} />
                <Text style={styles.providerName}>Cursor</Text>
                <View style={[styles.statusDot, {
                  backgroundColor: aiProviders.providers.cursor?.available ? Colors.green : Colors.yellow
                }]} />
              </View>
              <Text style={styles.providerStatus}>
                {aiProviders.providers.cursor?.message || 'Coming soon'}
              </Text>
              <TouchableOpacity
                style={[styles.providerButton, { opacity: 0.5 }]}
                disabled
              >
                <Text style={styles.providerButtonText}>Soon</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
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
          <Text style={styles.actionButtonText}>Refresh AI Providers</Text>
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

      {/* GitHub Token Modal */}
      <Modal visible={showGitHubTokenModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>GitHub Token</Text>
              <TouchableOpacity onPress={() => setShowGitHubTokenModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Paste a GitHub Personal Access Token (classic) with Copilot access. This fixes
              "Copilot subscription required" when gh CLI is not logged in on the PC. Create at
              github.com/settings/tokens — enable Copilot scope if available.
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
              placeholderTextColor={Colors.muted}
              value={githubTokenInput}
              onChangeText={setGithubTokenInput}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowGitHubTokenModal(false)}
              >
                <Text style={styles.modalSecondaryButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalButton} onPress={handleGitHubToken}>
                <Text style={styles.modalButtonText}>Save Token</Text>
              </TouchableOpacity>
            </View>
            {githubTokenStatus?.success && (
              <TouchableOpacity
                style={styles.clearTokenButton}
                onPress={handleClearGitHubToken}
              >
                <Text style={styles.clearTokenText}>Clear Current Token</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </Modal>

      {/* OpenAI Modal */}
      <Modal visible={showOpenAIModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>OpenAI Configuration</Text>
              <TouchableOpacity onPress={() => setShowOpenAIModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Enter your OpenAI API key to enable GPT-4 and GPT-3.5 access.
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="sk-xxxxxxxxxxxxxxxxxxxx"
              placeholderTextColor={Colors.muted}
              value={openaiKeyInput}
              onChangeText={setOpenaiKeyInput}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowOpenAIModal(false)}
              >
                <Text style={styles.modalSecondaryButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalButton} onPress={handleOpenAIConfig}>
                <Text style={styles.modalButtonText}>Save Key</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Gemini Modal */}
      <Modal visible={showGeminiModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Gemini Configuration</Text>
              <TouchableOpacity onPress={() => setShowGeminiModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Enter your Google Gemini API key to enable Gemini 2.5 access.
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="AIzaSyxxxxxxxxxxxxxxxxxxxx"
              placeholderTextColor={Colors.muted}
              value={geminiKeyInput}
              onChangeText={setGeminiKeyInput}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowGeminiModal(false)}
              >
                <Text style={styles.modalSecondaryButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalButton} onPress={handleGeminiConfig}>
                <Text style={styles.modalButtonText}>Save Key</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Ollama Modal */}
      <Modal visible={showOllamaModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Ollama Configuration</Text>
              <TouchableOpacity onPress={() => setShowOllamaModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalDescription}>
              Configure your local Ollama instance settings.
            </Text>

            <Text style={styles.inputLabel}>Host URL:</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="http://localhost:11434"
              placeholderTextColor={Colors.muted}
              value={ollamaHostInput}
              onChangeText={setOllamaHostInput}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <Text style={styles.inputLabel}>Model:</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="llama3.2"
              placeholderTextColor={Colors.muted}
              value={ollamaModelInput}
              onChangeText={setOllamaModelInput}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowOllamaModal(false)}
              >
                <Text style={styles.modalSecondaryButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalButton} onPress={handleOllamaConfig}>
                <Text style={styles.modalButtonText}>Save Config</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Copilot Model Selection Modal */}
      <Modal visible={showCopilotModelModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Copilot Model Selection</Text>
              <TouchableOpacity onPress={() => setShowCopilotModelModal(false)}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalDescription}>
              Choose which AI model to use with GitHub Copilot CLI. Each model has different strengths for coding tasks.
            </Text>

            <View style={{marginBottom: 16}}>
              <Text style={styles.inputLabel}>Current Model: {copilotModels?.current || 'Loading...'}</Text>
            </View>

            {copilotModels?.models && Object.entries(copilotModels.models as Record<string, string[]>).map(([category, models]) => (
              <View key={category} style={{marginBottom: 16}}>
                <Text style={[styles.inputLabel, {marginBottom: 8}]}>{category}</Text>
                {models.map((model: string) => (
                  <TouchableOpacity
                    key={model}
                    style={[
                      styles.modalButton,
                      {
                        marginBottom: 8,
                        backgroundColor: copilotModels.current === model ? Colors.primary : Colors.cardLight,
                        borderColor: copilotModels.current === model ? Colors.primary : Colors.border
                      }
                    ]}
                    onPress={() => handleCopilotModelChange(model)}
                  >
                    <Text style={[
                      styles.modalButtonText,
                      { color: copilotModels.current === model ? Colors.background : Colors.foreground }
                    ]}>
                      {model}
                      {copilotModels.current === model && ' ✓'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            ))}

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSecondaryButton]}
                onPress={() => setShowCopilotModelModal(false)}
              >
                <Text style={styles.modalSecondaryButtonText}>Close</Text>
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
  providerGrid: { gap: 12 },
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
  clearTokenButton: { marginTop: 12, padding: 8, alignItems: 'center' },
  clearTokenText: { color: Colors.red, fontSize: 14, fontWeight: '500' },
});
