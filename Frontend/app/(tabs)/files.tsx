import { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Modal,
  ScrollView,
  RefreshControl,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../lib/theme';
import {
  listDirectory,
  readFile,
  getProjectInfo,
  FileInfo,
  FileContent,
  ProjectInfo,
} from '../../lib/api';
import configManager from '../../lib/config';

export default function FilesScreen() {
  const [currentPath, setCurrentPath] = useState('');
  const [pathInput, setPathInput] = useState('');
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHidden, setShowHidden] = useState(false);
  const [projectInfo, setProjectInfo] = useState<ProjectInfo | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // File viewer modal
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [showFileModal, setShowFileModal] = useState(false);

  // Navigation history
  const [history, setHistory] = useState<string[]>([]);
  const [workspaceRoot, setWorkspaceRoot] = useState('');

  useEffect(() => {
    void configManager.init().then(() => {
      setWorkspaceRoot(configManager.workspaceRoot);
    });
  }, []);

  const loadDirectory = useCallback(async (path: string, addToHistory = true) => {
    if (!path.trim()) {
      setError('Enter a path to browse');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await listDirectory(path, showHidden);
      if (result.error) {
        setError(result.error);
      } else {
        setFiles(result.files);
        setCurrentPath(result.path);
        if (addToHistory && currentPath && currentPath !== path) {
          setHistory(prev => [...prev, currentPath]);
        }

        // Load project info
        const info = await getProjectInfo(path);
        if (!info.error) {
          setProjectInfo(info);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load directory');
    } finally {
      setLoading(false);
    }
  }, [currentPath, showHidden]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    if (currentPath) {
      await loadDirectory(currentPath, false);
    }
    setRefreshing(false);
  }, [currentPath, loadDirectory]);

  const openFile = async (file: FileInfo) => {
    if (file.is_dir) {
      loadDirectory(file.path);
    } else {
      setFileLoading(true);
      setShowFileModal(true);
      try {
        const content = await readFile(file.path);
        setSelectedFile(content);
      } catch (err) {
        setSelectedFile({
          path: file.path,
          content: `Error loading file: ${err instanceof Error ? err.message : 'Unknown error'}`,
          lines: 0,
          language: 'text',
          size: 0,
          error: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setFileLoading(false);
      }
    }
  };

  const goBack = () => {
    if (history.length > 0) {
      const prevPath = history[history.length - 1];
      setHistory(prev => prev.slice(0, -1));
      loadDirectory(prevPath, false);
    }
  };

  const goToParent = () => {
    if (currentPath) {
      const parts = currentPath.replace(/\\/g, '/').split('/');
      if (parts.length > 1) {
        parts.pop();
        const parentPath = parts.join('/') || '/';
        loadDirectory(parentPath);
      }
    }
  };

  const getFileIcon = (file: FileInfo): keyof typeof Ionicons.glyphMap => {
    if (file.is_dir) return 'folder';

    const ext = file.extension.toLowerCase();
    const iconMap: Record<string, keyof typeof Ionicons.glyphMap> = {
      '.js': 'logo-javascript',
      '.jsx': 'logo-react',
      '.ts': 'logo-javascript',
      '.tsx': 'logo-react',
      '.py': 'logo-python',
      '.json': 'code-slash',
      '.html': 'logo-html5',
      '.css': 'logo-css3',
      '.md': 'document-text',
      '.txt': 'document-text',
      '.yml': 'settings',
      '.yaml': 'settings',
      '.env': 'key',
      '.git': 'git-branch',
      '.png': 'image',
      '.jpg': 'image',
      '.jpeg': 'image',
      '.svg': 'image',
      '.pdf': 'document',
    };
    return iconMap[ext] || 'document';
  };

  const getFileColor = (file: FileInfo): string => {
    if (file.is_dir) return Colors.yellow;

    const ext = file.extension.toLowerCase();
    const colorMap: Record<string, string> = {
      '.js': '#F7DF1E',
      '.jsx': '#61DAFB',
      '.ts': '#3178C6',
      '.tsx': '#61DAFB',
      '.py': '#3776AB',
      '.json': '#E8A317',
      '.html': '#E34F26',
      '.css': '#1572B6',
      '.md': '#FFFFFF',
      '.env': Colors.green,
    };
    return colorMap[ext] || Colors.muted;
  };

  const setAsProjectRoot = async () => {
    if (!currentPath) return;
    await configManager.setWorkspaceRoot(currentPath);
    setWorkspaceRoot(currentPath);
    Alert.alert(
      'Project root set',
      `Agent missions will use:\n${currentPath}\n\nOpen Mission to run multi-file tasks in this folder.`
    );
  };

  const formatSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const renderFileItem = ({ item }: { item: FileInfo }) => (
    <TouchableOpacity style={styles.fileItem} onPress={() => openFile(item)}>
      <View style={styles.fileIconContainer}>
        <Ionicons name={getFileIcon(item)} size={24} color={getFileColor(item)} />
      </View>
      <View style={styles.fileInfo}>
        <Text style={styles.fileName} numberOfLines={1}>{item.name}</Text>
        <Text style={styles.fileDetails}>
          {item.is_dir ? 'Folder' : formatSize(item.size)}
        </Text>
      </View>
      {item.is_dir && (
        <Ionicons name="chevron-forward" size={20} color={Colors.muted} />
      )}
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {/* Path input */}
      <View style={styles.pathContainer}>
        <View style={styles.pathInputRow}>
          <TextInput
            style={styles.pathInput}
            value={pathInput}
            onChangeText={setPathInput}
            placeholder="Enter path (e.g., C:\Projects or ~/code)"
            placeholderTextColor={Colors.muted}
            onSubmitEditing={() => loadDirectory(pathInput)}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity
            style={styles.goButton}
            onPress={() => loadDirectory(pathInput)}
          >
            <Ionicons name="arrow-forward" size={20} color={Colors.foreground} />
          </TouchableOpacity>
        </View>

        {/* Current path & navigation */}
        {currentPath && (
          <View style={styles.navRow}>
            <TouchableOpacity
              style={[styles.navButton, !history.length && styles.navButtonDisabled]}
              onPress={goBack}
              disabled={!history.length}
            >
              <Ionicons name="arrow-back" size={18} color={history.length ? Colors.foreground : Colors.muted} />
            </TouchableOpacity>
            <TouchableOpacity style={styles.navButton} onPress={goToParent}>
              <Ionicons name="arrow-up" size={18} color={Colors.foreground} />
            </TouchableOpacity>
            <Text style={styles.currentPath} numberOfLines={1}>{currentPath}</Text>
            <TouchableOpacity
              style={styles.hiddenToggle}
              onPress={() => {
                setShowHidden(!showHidden);
                if (currentPath) loadDirectory(currentPath, false);
              }}
            >
              <Ionicons
                name={showHidden ? 'eye' : 'eye-off'}
                size={18}
                color={showHidden ? Colors.primary : Colors.muted}
              />
            </TouchableOpacity>
            <TouchableOpacity style={styles.projectRootBtn} onPress={() => void setAsProjectRoot()}>
              <Ionicons name="folder-open" size={18} color={Colors.primary} />
            </TouchableOpacity>
          </View>
        )}
        {workspaceRoot ? (
          <Text style={styles.workspaceHint} numberOfLines={2}>
            Agent project: {workspaceRoot}
          </Text>
        ) : null}
      </View>

      {/* Project info */}
      {projectInfo && !projectInfo.error && (
        <View style={styles.projectInfo}>
          <View style={styles.projectHeader}>
            <Text style={styles.projectName}>{projectInfo.name}</Text>
            <View style={styles.projectBadge}>
              <Text style={styles.projectType}>{projectInfo.type}</Text>
            </View>
          </View>
          <View style={styles.projectStats}>
            {projectInfo.has_git && (
              <View style={styles.statItem}>
                <Ionicons name="git-branch" size={14} color={Colors.orange} />
                <Text style={styles.statText}>Git</Text>
              </View>
            )}
            <View style={styles.statItem}>
              <Ionicons name="code" size={14} color={Colors.blue} />
              <Text style={styles.statText}>{projectInfo.code_files} files</Text>
            </View>
          </View>
        </View>
      )}

      {/* Error */}
      {error && (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={20} color={Colors.red} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Loading */}
      {loading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      )}

      {/* File list */}
      {!loading && files.length > 0 && (
        <FlatList
          data={files}
          renderItem={renderFileItem}
          keyExtractor={item => item.path}
          style={styles.fileList}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={Colors.primary}
            />
          }
        />
      )}

      {/* Empty state */}
      {!loading && !error && currentPath && files.length === 0 && (
        <View style={styles.emptyContainer}>
          <Ionicons name="folder-open-outline" size={48} color={Colors.muted} />
          <Text style={styles.emptyText}>This folder is empty</Text>
        </View>
      )}

      {/* Initial state */}
      {!loading && !error && !currentPath && (
        <View style={styles.emptyContainer}>
          <Ionicons name="folder-outline" size={48} color={Colors.muted} />
          <Text style={styles.emptyText}>Enter a path to browse files</Text>
          <Text style={styles.emptySubtext}>Examples:</Text>
          <Text style={styles.examplePath}>C:\Users\YourName\Projects</Text>
          <Text style={styles.examplePath}>~/code/my-project</Text>
        </View>
      )}

      {/* File content modal */}
      <Modal
        visible={showFileModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowFileModal(false)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowFileModal(false)}>
              <Ionicons name="close" size={24} color={Colors.foreground} />
            </TouchableOpacity>
            <Text style={styles.modalTitle} numberOfLines={1}>
              {selectedFile?.path.split(/[/\\]/).pop() || 'File'}
            </Text>
            <View style={styles.modalBadge}>
              <Text style={styles.modalLanguage}>
                {selectedFile?.language || 'text'}
              </Text>
            </View>
          </View>

          {fileLoading ? (
            <View style={styles.modalLoading}>
              <ActivityIndicator size="large" color={Colors.primary} />
            </View>
          ) : (
            <ScrollView style={styles.codeContainer} horizontal>
              <ScrollView>
                <Text style={styles.codeText}>{selectedFile?.content}</Text>
              </ScrollView>
            </ScrollView>
          )}

          {selectedFile && !fileLoading && (
            <View style={styles.fileStats}>
              <Text style={styles.fileStatText}>
                {selectedFile.lines} lines | {formatSize(selectedFile.size)}
              </Text>
            </View>
          )}
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
  pathContainer: {
    padding: 12,
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  pathInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  pathInput: {
    flex: 1,
    backgroundColor: Colors.cardLight,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: Colors.foreground,
    fontSize: 14,
    fontFamily: 'monospace',
  },
  goButton: {
    backgroundColor: Colors.primary,
    borderRadius: 8,
    padding: 10,
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 8,
  },
  navButton: {
    backgroundColor: Colors.cardLight,
    borderRadius: 6,
    padding: 6,
  },
  navButtonDisabled: {
    opacity: 0.5,
  },
  currentPath: {
    flex: 1,
    color: Colors.muted,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  hiddenToggle: {
    padding: 6,
  },
  projectRootBtn: {
    padding: 6,
  },
  workspaceHint: {
    marginTop: 6,
    color: Colors.primary,
    fontSize: 11,
    fontFamily: 'monospace',
  },
  projectInfo: {
    padding: 12,
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  projectHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  projectName: {
    color: Colors.foreground,
    fontSize: 16,
    fontWeight: '600',
  },
  projectBadge: {
    backgroundColor: Colors.primary + '30',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  projectType: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '500',
  },
  projectStats: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 8,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    color: Colors.muted,
    fontSize: 12,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    margin: 12,
    padding: 12,
    backgroundColor: Colors.red + '20',
    borderRadius: 8,
  },
  errorText: {
    color: Colors.red,
    fontSize: 14,
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    color: Colors.muted,
    fontSize: 14,
  },
  fileList: {
    flex: 1,
  },
  fileItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  fileIconContainer: {
    width: 40,
    alignItems: 'center',
  },
  fileInfo: {
    flex: 1,
    marginLeft: 8,
  },
  fileName: {
    color: Colors.foreground,
    fontSize: 14,
    fontWeight: '500',
  },
  fileDetails: {
    color: Colors.muted,
    fontSize: 12,
    marginTop: 2,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    gap: 8,
  },
  emptyText: {
    color: Colors.muted,
    fontSize: 16,
    marginTop: 12,
  },
  emptySubtext: {
    color: Colors.muted,
    fontSize: 12,
    marginTop: 16,
  },
  examplePath: {
    color: Colors.primary,
    fontSize: 12,
    fontFamily: 'monospace',
    marginTop: 4,
  },
  modalContainer: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: Colors.card,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: 12,
  },
  modalTitle: {
    flex: 1,
    color: Colors.foreground,
    fontSize: 16,
    fontWeight: '600',
  },
  modalBadge: {
    backgroundColor: Colors.primary + '30',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  modalLanguage: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '500',
  },
  modalLoading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  codeContainer: {
    flex: 1,
    backgroundColor: Colors.card,
  },
  codeText: {
    color: Colors.foreground,
    fontSize: 13,
    fontFamily: 'monospace',
    padding: 16,
    lineHeight: 20,
  },
  fileStats: {
    padding: 12,
    backgroundColor: Colors.card,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    alignItems: 'center',
  },
  fileStatText: {
    color: Colors.muted,
    fontSize: 12,
  },
});
