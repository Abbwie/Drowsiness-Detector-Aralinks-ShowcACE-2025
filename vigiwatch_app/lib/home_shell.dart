import 'package:flutter/material.dart';
import 'history_page.dart';
import 'home_page.dart';
import 'login_page.dart';
import 'settings_page.dart';
import 'theme.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;

  void logout() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const LoginPage()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: bg,
        title: const Text('VigiWatch'),
      ),
      body: IndexedStack(
        index: index,
        children: [
          HomePage(onSeeAll: () => setState(() => index = 1)),
          const HistoryPage(),
          SettingsPage(onLogout: logout),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        height: 62,
        backgroundColor: card,
        indicatorColor: red,
        selectedIndex: index,
        onDestinationSelected: (i) => setState(() => index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.list), label: 'History'),
          NavigationDestination(
              icon: Icon(Icons.settings_outlined), label: 'Settings'),
        ],
      ),
    );
  }
}
