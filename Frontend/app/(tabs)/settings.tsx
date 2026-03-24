import { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Linking,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, FontSize, BorderRadius } from '@/lib/theme';
import {
  checkHealth,
  ping,
  API_CONFIG,
  getAIProviders,
  setAIProvider,
  AIProvidersResponse,
  getGitHubAuthStatus,
  githubLogin,
  githubLogout,
  GitHubAuthStatus,
  getApiUrl,
  updateApiConfig,
} from '@/lib/api';
import configManager, { ServerProfile } from '@/lib/config';

type ConnectionStatus = 'checking' | 'connected' | 'disconnected';

export default function SettingsScreen() {
  const [apiUrl, setApiUrl] = useState('');
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('checking');
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [aiProviders, setAiProviders] = useState<AIProvidersResponse | null>(null);
  const [changingProvider, setChangingProvider] = useState(false);
  const [githubAuth, setGithubAuth] = useState<GitHubAuthStatus | null>(null);
  const [loadingGithub, setLoadingGithub] = useState(false);

  // Server profiles state
  const [serverProfiles, setServerProfiles] = useState<ServerProfile[]>([]);
  const [activeProfile, setActiveProfile] = useState<ServerProfile | null>(null);
  const [showAddServer, setShowAddServer] = useState(false);
  const [newServerName, setNewServerName] = useState('');
  const [newServerUrl, setNewServerUrl] = useState('');
  const [newServerKey, setNewServerKey] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);

  // Initialize config manager
  useEffect(() => {
    const initConfig = async () => {
      await configManager.init();
      setServerProfiles(configManager.serverProfiles);
      setActiveProfile(configManager.activeProfile);
      setApiUrl(configManager.backendUrl);
      updateApiConfig();
    };
    initConfig();
  }, []);

  const testConnection = useCallback(async () => {
    setConnectionStatus('checking');
    setPingResult(null);
    try {
      const health = await checkHealth();
      if (health.status === 'ok') {
        setConnectionStatus('connected');
        try {
          const p = await ping();
          setPingResult(`Ping: ${p.message} (authenticated)`);
        } catch {
          setPingResult('Health OK, but auth ping failed — check API key');
        }
        loadAIProviders();
        loadGitHubAuth();
      } else {
        setConnectionStatus('disconnected');
      }
    } catch {
      setConnectionStatus('disconnected');
    }
  }, []);

  const loadAIProviders = async () => {
    try {
      const providers = await getAIProviders();
      setAiProviders(providers);
    } catch (err) {
      console.error('Failed to load AI providers:', err);
    }
  };

  const loadGitHubAuth = async () => {
    try {
      const status = await getGitHubAuthStatus();
      setGithubAuth(status);
    } catch (err) {
      console.error('Failed to load GitHub auth status:', err);
    }
  };

  const handleGitHubLogin = async () => {
    setLoadingGithub(true);
    try {
      const result = await githubLogin();
      if (result.success && result.auth_url) {
        Alert.alert(
          'GitHub Login',
          'To authenticate with GitHub:\n\n1. Run "gh auth login" in terminal on your computer\n2. Follow the prompts in your browser\n3. Return here and tap "Refresh Status"',
          [
            { text: 'Open GitHub', onPress: () => Linking.openURL(result.auth_url!) },
            { text: 'OK' },
          ]
        );
      } else {
        Alert.alert('Info', result.message);
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to initiate login');
    } finally {
      setLoadingGithub(false);
    }
  };

  const handleGitHubLogout = async () => {
    Alert.alert(
      'Logout from GitHub',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            setLoadingGithub(true);
            try {
              await githubLogout();
              await loadGitHubAuth();
              await loadAIProviders();
            } catch (err) {
              Alert.alert('Error', err instanceof Error ? err.message : 'Failed to logout');
            } finally {
              setLoadingGithub(false);
            }
          },
        },
      ]
    );
  };

  const handleSetProvider = async (provider: string) => {
    setChangingProvider(true);
    try {
      const result = await setAIProvider(provider);
      if (result.success) {
        await loadAIProviders();
        Alert.alert('Success', result.message);
      } else {
        Alert.alert('Error', result.message);
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Failed to set provider');
    } finally {
      setChangingProvider(false);
    }
  };

  const getProviderIcon = (provider: string): keyof typeof Ionicons.glyphMap => {
    switch (provider) {
      case 'copilot': return 'logo-github';
      case 'ollama': return 'hardware-chip';
      case 'openai': return 'cloud';
      case 'cursor': return 'code-slash';
      default: return 'sparkles';
    }
  };

  // Server profile handlers
  const handleAddServer = async () => {
    if (!newServerName.trim() || !newServerUrl.trim()) {
      Alert.alert('Error', 'Please enter server name and URL');
      return;
    }

    // Clean up URL
    let url = newServerUrl.trim();
    if (!url.startsWith('http')) {
      url = 'https://' + url;
    }
    url = url.replace(/\/$/, '');

    setTestingConnection(true);
    const result = await configManager.testConnection(url);
    setTestingConnection(false);

    if (!result.success) {
      Alert.alert(
        'Connection Failed',
        `Could not connect to ${url}\n\n${result.message}\n\nAdd anyway?`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Add Anyway',
            onPress: async () => {
              const profile = await configManager.addServerProfile(newServerName, url, newServerKey);
              setServerProfiles(configManager.serverProfiles);
              setShowAddServer(false);
              resetAddServerForm();
            },
          },
        ]
      );
      return;
    }

    const profile = await configManager.addServerProfile(newServerName, url, newServerKey);
    setServerProfiles(configManager.serverProfiles);
    setShowAddServer(false);
    resetAddServerForm();
    Alert.alert('Success', `Server "${newServerName}" added!\n\n${result.message}`);
  };

  const resetAddServerForm = () => {
    setNewServerName('');
    setNewServerUrl('');
    setNewServerKey('');
  };

  const handleSwitchServer = async (profile: ServerProfile) => {
    const success = await configManager.switchToProfile(profile.id);
    if (success) {
      setActiveProfile(configManager.activeProfile);
      setApiUrl(configManager.backendUrl);
      updateApiConfig();
      testConnection();
      Alert.alert('Switched', `Now connected to "${profile.name}"`);
    }
  };

  const handleDeleteServer = (profile: ServerProfile) => {
    if (serverProfiles.length <= 1) {
      Alert.alert('Error', 'You need at least one server profile');
      return;
    }

    Alert.alert(
      'Delete Server',
      `Are you sure you want to delete "${profile.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            await configManager.deleteServerProfile(profile.id);
            setServerProfiles(configManager.serverProfiles);
            setActiveProfile(configManager.activeProfile);
            if (profile.id === activeProfile?.id) {
              updateApiConfig();
              testConnection();
            }
          },
        },
      ]
    );
  };

  useEffect(() => {
    testConnection();
  }, [testConnection]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.iconContainer}>
          <Ionicons name="settings" size={18} color={Colors.primary} />
        </View>
        <View>
          <Text style={styles.title}>Settings</Text>
          <Text style={styles.subtitle}>Configure your JARVIS connection</Text>
        </View>
      </View>

      {/* Server Profiles - MULTIPLE LAPTOPS */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Ionicons name="laptop-outline" size={18} color={Colors.primary} />
          <Text style={styles.cardTitle}>Server Profiles</Text>
        </View>
        <Text style={styles.helpTextTop}>
          Add multiple servers to switch between different laptops
        </Text>

        {/* Server List */}
        <View style={styles.serverList}>
          {serverProfiles.map((profile) => (
            <TouchableOpacity
              key={profile.id}
              style={[
                styles.serverItem,
                activeProfile?.id === profile.id && styles.serverItemActive,
              ]}
              onPress={() => handleSwitchServer(profile)}
            >
              <View style={styles.serverInfo}>
                <View style={styles.serverNameRow}>
                  {activeProfile?.id === profile.id && (
                    <Ionicons name="checkmark-circle" size={16} color={Colors.green} />
                  )}
                  <Text style={[
                    styles.serverName,
                    activeProfile?.id === profile.id && styles.serverNameActive,
                  ]}>
                    {profile.name}
                  </Text>
                </View>
                <Text style={styles.serverUrl} numberOfLines={1}>
                  {profile.url}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.deleteServerBtn}
                onPress={() => handleDeleteServer(profile)}
              >
                <Ionicons name="trash-outline" size={18} color={Colors.red} />
              </TouchableOpacity>
            </TouchableOpacity>
          ))}
        </View>

        {/* Add Server Button */}
        <TouchableOpacity
          style={styles.addServerBtn}
          onPress={() => setShowAddServer(true)}
        >
          <Ionicons name="add-circle" size={20} color={Colors.primary} />
          <Text style={styles.addServerBtnText}>Add Another Laptop/Server</Text>
        </TouchableOpacity>
      </View>

      {/* Connection Status */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Ionicons
            name={connectionStatus === 'connected' ? 'wifi' : connectionStatus === 'disconnected' ? 'wifi-outline' : 'sync'}
            size={18}
            color={
              connectionStatus === 'connected'
                ? Colors.green
                : connectionStatus === 'disconnected'
                ? Colors.red
                : Colors.amber
            }
          />
          <Text style={styles.cardTitle}>Connection Status</Text>
        </View>

        <View
          style={[
            styles.statusBox,
            {
              backgroundColor:
                connectionStatus === 'connected'
                  ? Colors.greenBg
                  : connectionStatus === 'disconnected'
                  ? Colors.redBg
                  : Colors.amberBg,
              borderColor:
                connectionStatus === 'connected'
                  ? Colors.greenBorder
                  : connectionStatus === 'disconnected'
                  ? Colors.redBorder
                  : Colors.amberBorder,
            },
          ]}
        >
          <View style={styles.statusRow}>
            {connectionStatus === 'checking' ? (
              <ActivityIndicator size="small" color={Colors.amber} />
            ) : (
              <Ionicons
                name={connectionStatus === 'connected' ? 'checkmark-circle' : 'close-circle'}
                size={22}
                color={connectionStatus === 'connected' ? Colors.green : Colors.red}
              />
            )}
            <View style={{ flex: 1 }}>
              <Text
                style={[
                  styles.statusTitle,
                  {
                    color:
                      connectionStatus === 'connected'
                        ? Colors.greenLight
                        : connectionStatus === 'disconnected'
                        ? Colors.redLight
                        : Colors.amberLight,
                  },
                ]}
              >
                {connectionStatus === 'connected'
                  ? 'Connected'
                  : connectionStatus === 'disconnected'
                  ? 'Disconnected'
                  : 'Checking...'}
              </Text>
              <Text style={styles.pingResult} numberOfLines={1}>{apiUrl}</Text>
              {pingResult && <Text style={styles.pingResult}>{pingResult}</Text>}
            </View>
          </View>
        </View>

        <TouchableOpacity
          style={styles.testBtn}
          onPress={testConnection}
          disabled={connectionStatus === 'checking'}
        >
          <Text style={styles.testBtnText}>Test Connection Again</Text>
        </TouchableOpacity>
      </View>

      {/* GitHub Authentication */}
      {connectionStatus === 'connected' && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Ionicons name="logo-github" size={18} color={Colors.foreground} />
            <Text style={styles.cardTitle}>GitHub Account</Text>
            {loadingGithub && <ActivityIndicator size="small" color={Colors.primary} style={{ marginLeft: 8 }} />}
          </View>

          {githubAuth ? (
            <View>
              <View
                style={[
                  styles.statusBox,
                  {
                    backgroundColor: githubAuth.authenticated ? Colors.greenBg : Colors.amberBg,
                    borderColor: githubAuth.authenticated ? Colors.greenBorder : Colors.amberBorder,
                  },
                ]}
              >
                <View style={styles.statusRow}>
                  <Ionicons
                    name={githubAuth.authenticated ? 'checkmark-circle' : 'alert-circle'}
                    size={22}
                    color={githubAuth.authenticated ? Colors.green : Colors.amber}
                  />
                  <View style={{ flex: 1 }}>
                    <Text
                      style={[
                        styles.statusTitle,
                        { color: githubAuth.authenticated ? Colors.greenLight : Colors.amberLight },
                      ]}
                    >
                      {githubAuth.authenticated ? `@${githubAuth.username}` : 'Not signed in'}
                    </Text>
                    <Text style={styles.pingResult}>{githubAuth.message}</Text>
                  </View>
                </View>
              </View>

              <View style={styles.githubActions}>
                {githubAuth.authenticated ? (
                  <TouchableOpacity style={styles.logoutBtn} onPress={handleGitHubLogout}>
                    <Ionicons name="log-out-outline" size={16} color={Colors.red} />
                    <Text style={styles.logoutBtnText}>Sign Out</Text>
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity style={styles.loginBtn} onPress={handleGitHubLogin}>
                    <Ionicons name="log-in-outline" size={16} color={Colors.background} />
                    <Text style={styles.loginBtnText}>Sign in with GitHub</Text>
                  </TouchableOpacity>
                )}
                <TouchableOpacity style={styles.refreshBtn} onPress={() => { loadGitHubAuth(); loadAIProviders(); }}>
                  <Ionicons name="refresh" size={16} color={Colors.primary} />
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <View style={styles.loadingProviders}>
              <ActivityIndicator size="small" color={Colors.muted} />
              <Text style={styles.loadingText}>Checking GitHub status...</Text>
            </View>
          )}
        </View>
      )}

      {/* AI Provider Selection */}
      {connectionStatus === 'connected' && aiProviders && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Ionicons name="sparkles" size={18} color={Colors.primary} />
            <Text style={styles.cardTitle}>AI Assistant</Text>
            {changingProvider && <ActivityIndicator size="small" color={Colors.primary} style={{ marginLeft: 8 }} />}
          </View>

          <View style={styles.providerList}>
            {Object.entries(aiProviders.providers).map(([key, provider]) => (
              <TouchableOpacity
                key={key}
                style={[
                  styles.providerItem,
                  provider.selected && styles.providerSelected,
                  !provider.available && styles.providerUnavailable,
                ]}
                onPress={() => provider.available && handleSetProvider(key)}
                disabled={!provider.available || changingProvider}
              >
                <View style={styles.providerIconContainer}>
                  <Ionicons
                    name={getProviderIcon(key)}
                    size={20}
                    color={provider.selected ? Colors.primary : provider.available ? Colors.foreground : Colors.muted}
                  />
                </View>
                <View style={styles.providerInfo}>
                  <Text style={[
                    styles.providerName,
                    provider.selected && styles.providerNameSelected,
                    !provider.available && styles.providerNameUnavailable,
                  ]}>
                    {key.charAt(0).toUpperCase() + key.slice(1)}
                  </Text>
                  <Text style={styles.providerMessage} numberOfLines={1}>
                    {provider.message}
                  </Text>
                </View>
                {provider.selected && <Ionicons name="checkmark-circle" size={20} color={Colors.green} />}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* How to use on other laptops */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Ionicons name="help-circle" size={18} color={Colors.primary} />
          <Text style={styles.cardTitle}>Multi-Laptop Setup</Text>
        </View>
        <Text style={styles.instructionText}>
          To use JARVIS on another laptop:
        </Text>
        <View style={styles.stepList}>
          <Text style={styles.stepItem}>1. Start JARVIS backend on that laptop</Text>
          <Text style={styles.stepItem}>2. Run ngrok: <Text style={styles.code}>ngrok http 8000</Text></Text>
          <Text style={styles.stepItem}>3. Copy the ngrok URL (https://xxx.ngrok-free.dev)</Text>
          <Text style={styles.stepItem}>4. Tap "Add Another Laptop/Server" above</Text>
          <Text style={styles.stepItem}>5. Enter a name and paste the URL</Text>
        </View>
      </View>

      {/* Add Server Modal */}
      <Modal visible={showAddServer} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add New Server</Text>
              <TouchableOpacity onPress={() => { setShowAddServer(false); resetAddServerForm(); }}>
                <Ionicons name="close" size={24} color={Colors.muted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Server Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., Work Laptop, Home PC"
              placeholderTextColor={Colors.muted}
              value={newServerName}
              onChangeText={setNewServerName}
            />

            <Text style={styles.inputLabel}>Server URL</Text>
            <TextInput
              style={styles.input}
              placeholder="https://xxx.ngrok-free.dev"
              placeholderTextColor={Colors.muted}
              value={newServerUrl}
              onChangeText={setNewServerUrl}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />

            <Text style={styles.inputLabel}>API Key (optional)</Text>
            <TextInput
              style={styles.input}
              placeholder="Leave empty if no auth required"
              placeholderTextColor={Colors.muted}
              value={newServerKey}
              onChangeText={setNewServerKey}
              autoCapitalize="none"
              secureTextEntry
            />

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.cancelBtn]}
                onPress={() => { setShowAddServer(false); resetAddServerForm(); }}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.addBtn]}
                onPress={handleAddServer}
                disabled={testingConnection}
              >
                {testingConnection ? (
                  <ActivityIndicator size="small" color={Colors.foreground} />
                ) : (
                  <Text style={styles.addBtnText}>Add Server</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
    paddingBottom: Spacing.xxl * 2,
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
  card: {
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  cardTitle: {
    fontSize: FontSize.sm,
    fontWeight: 'bold',
    color: Colors.foreground,
  },
  helpTextTop: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginBottom: Spacing.md,
  },
  serverList: {
    gap: Spacing.sm,
  },
  serverItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  serverItemActive: {
    borderColor: Colors.green,
    backgroundColor: Colors.greenBg,
  },
  serverInfo: {
    flex: 1,
  },
  serverNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  serverName: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.foreground,
  },
  serverNameActive: {
    color: Colors.green,
  },
  serverUrl: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 2,
  },
  deleteServerBtn: {
    padding: Spacing.sm,
  },
  addServerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Spacing.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.primary,
    borderRadius: BorderRadius.md,
    borderStyle: 'dashed',
    gap: Spacing.sm,
  },
  addServerBtnText: {
    fontSize: FontSize.sm,
    color: Colors.primary,
    fontWeight: '500',
  },
  statusBox: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  statusTitle: {
    fontSize: FontSize.sm,
    fontWeight: '600',
  },
  pingResult: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 2,
  },
  testBtn: {
    marginTop: Spacing.md,
  },
  testBtnText: {
    fontSize: FontSize.xs,
    color: Colors.primary,
  },
  input: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: FontSize.sm,
    color: Colors.foreground,
    marginBottom: Spacing.md,
  },
  inputLabel: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginBottom: Spacing.xs,
  },
  helpText: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: Spacing.sm,
  },
  code: {
    fontFamily: 'monospace',
    backgroundColor: Colors.codeBg,
    color: Colors.primary,
    paddingHorizontal: 4,
  },
  providerList: {
    gap: Spacing.sm,
  },
  providerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  providerSelected: {
    backgroundColor: Colors.primaryBg,
    borderColor: Colors.primary,
  },
  providerUnavailable: {
    opacity: 0.5,
  },
  providerIconContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.cardLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  providerInfo: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  providerName: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.foreground,
  },
  providerNameSelected: {
    color: Colors.primary,
  },
  providerNameUnavailable: {
    color: Colors.muted,
  },
  providerMessage: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    marginTop: 2,
  },
  loadingProviders: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.lg,
    gap: Spacing.sm,
  },
  loadingText: {
    fontSize: FontSize.xs,
    color: Colors.muted,
  },
  refreshBtn: {
    padding: Spacing.sm,
  },
  githubActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.md,
  },
  loginBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.foreground,
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.md,
    gap: Spacing.xs,
  },
  loginBtnText: {
    fontSize: FontSize.sm,
    fontWeight: '600',
    color: Colors.background,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  logoutBtnText: {
    fontSize: FontSize.xs,
    color: Colors.red,
  },
  instructionText: {
    fontSize: FontSize.sm,
    color: Colors.foreground,
    marginBottom: Spacing.sm,
  },
  stepList: {
    gap: Spacing.xs,
  },
  stepItem: {
    fontSize: FontSize.xs,
    color: Colors.muted,
    lineHeight: 20,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.lg,
  },
  modalContent: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.xl,
    width: '100%',
    maxWidth: 400,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  modalTitle: {
    fontSize: FontSize.lg,
    fontWeight: 'bold',
    color: Colors.foreground,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.md,
  },
  modalBtn: {
    flex: 1,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  cancelBtn: {
    backgroundColor: Colors.surface,
  },
  addBtn: {
    backgroundColor: Colors.primary,
  },
  cancelBtnText: {
    fontSize: FontSize.sm,
    color: Colors.muted,
    fontWeight: '600',
  },
  addBtnText: {
    fontSize: FontSize.sm,
    color: Colors.foreground,
    fontWeight: '600',
  },
});
