import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { View, Text, StyleSheet } from 'react-native';
import { useState, useEffect } from 'react';
import { checkHealth } from '../../lib/api';
import  { Colors } from '../../lib/theme';
function TabBarIcon({ name, color, size }: { name: keyof typeof Ionicons.glyphMap; color: string; size: number }) {
  return <Ionicons name={name} size={size} color={color} />;
}

export default function TabLayout() {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const res = await checkHealth();
        setIsConnected(res.status === 'ok');
      } catch {
        setIsConnected(false);
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.muted,
        tabBarStyle: {
          backgroundColor: Colors.card,
          borderTopColor: Colors.border,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
        },
        headerStyle: {
          backgroundColor: Colors.card,
          borderBottomColor: Colors.border,
          borderBottomWidth: 1,
        },
        headerTintColor: Colors.foreground,
        headerTitleStyle: {
          fontWeight: 'bold',
          fontSize: 18,
        },
        headerRight: () => (
          <View style={styles.statusContainer}>
            <View style={[styles.statusDot, { backgroundColor: isConnected ? Colors.green : Colors.red }]} />
            <Text style={[styles.statusText, { color: isConnected ? Colors.green : Colors.red }]}>
              {isConnected ? 'Online' : 'Offline'}
            </Text>
          </View>
        ),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'JARVIS',
          tabBarLabel: 'Chat',
          tabBarIcon: ({ color, size }) => <TabBarIcon name="chatbubbles" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="ide"
        options={{
          title: 'IDE',
          tabBarLabel: 'IDE',
          tabBarIcon: ({ color, size }) => <TabBarIcon name="code-slash" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="files"
        options={{
          title: 'Workspace',
          tabBarLabel: 'Workspace',
          tabBarIcon: ({ color, size }) => <TabBarIcon name="folder-open" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="commands"
        options={{
          href: null,
        }}
      />
      <Tabs.Screen
        name="devices"
        options={{
          href: null,
        }}
      />
      <Tabs.Screen
        name="mission"
        options={{
          title: 'Mission',
          tabBarLabel: 'Mission',
          tabBarIcon: ({ color, size }) => <TabBarIcon name="pulse" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, size }) => <TabBarIcon name="settings" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="analytics"
        options={{
          href: null, // Hide from main tabs, still accessible
        }}
      />
      <Tabs.Screen
        name="tasks"
        options={{
          href: null, // Hide from tab bar
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
    backgroundColor: Colors.cardLight,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
});
