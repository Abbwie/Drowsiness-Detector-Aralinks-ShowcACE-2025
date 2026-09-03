import 'package:flutter/material.dart';
import 'dashboard_page.dart';
import 'history_page.dart';
import 'login_page.dart';
import 'mock_data.dart';
import 'theme.dart';
import 'widgets.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          DashboardPage(onSeeAll: () => setState(() => _index = 1)),
          const HistoryPage(),
          const ProfilePage(),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: VW.surface,
          border: Border(top: BorderSide(color: VW.line)),
        ),
        child: NavigationBarTheme(
          data: NavigationBarThemeData(
            backgroundColor: Colors.transparent,
            indicatorColor: VW.red.withValues(alpha: 0.18),
            labelTextStyle: WidgetStateProperty.resolveWith(
              (states) => TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
                color: states.contains(WidgetState.selected)
                    ? VW.text
                    : VW.muted,
              ),
            ),
            iconTheme: WidgetStateProperty.resolveWith(
              (states) => IconThemeData(
                size: 22,
                color:
                    states.contains(WidgetState.selected) ? VW.red : VW.muted,
              ),
            ),
          ),
          child: NavigationBar(
            height: 66,
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.space_dashboard_outlined),
                selectedIcon: Icon(Icons.space_dashboard_rounded),
                label: 'Tracker',
              ),
              NavigationDestination(
                icon: Icon(Icons.history_rounded),
                label: 'History',
              ),
              NavigationDestination(
                icon: Icon(Icons.person_outline_rounded),
                selectedIcon: Icon(Icons.person_rounded),
                label: 'Profile',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
        children: [
          const Text(
            'Profile',
            style: TextStyle(
                fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -1),
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: VW.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: VW.line),
            ),
            child: Row(
              children: [
                Container(
                  width: 58,
                  height: 58,
                  decoration: const BoxDecoration(
                      color: VW.red, shape: BoxShape.circle),
                  alignment: Alignment.center,
                  child: Text(
                    mockDriver.initials,
                    style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 19,
                        color: Colors.white),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        mockDriver.name,
                        style: const TextStyle(
                            fontSize: 17, fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        mockDriver.email,
                        style:
                            const TextStyle(fontSize: 12.5, color: VW.muted),
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 3),
                      Text(
                        mockDriver.vehicle,
                        style:
                            const TextStyle(fontSize: 12.5, color: VW.muted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 22),
          const Text(
            'Detection settings',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          const _SettingRow(
            icon: Icons.tune_rounded,
            title: 'Alert sensitivity',
            value: 'Standard',
          ),
          const _SettingRow(
            icon: Icons.timer_outlined,
            title: 'Escalate after',
            value: '5 alerts / 60s',
          ),
          const _SettingRow(
            icon: Icons.contact_phone_outlined,
            title: 'Emergency contact',
            value: '+63 967 009 2434',
          ),
          const _SettingRow(
            icon: Icons.volume_up_outlined,
            title: 'Buzzer',
            value: 'Not connected',
            valueColor: VW.amber,
          ),
          const SizedBox(height: 26),
          OutlinedButton(
            onPressed: () => Navigator.of(context).pushReplacement(
              MaterialPageRoute(builder: (_) => const LoginPage()),
            ),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
              side: const BorderSide(color: VW.line),
              foregroundColor: VW.red,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
            child: const Text('Sign out',
                style: TextStyle(fontWeight: FontWeight.w700)),
          ),
          const SizedBox(height: 20),
          const Center(child: BrandMark(size: 30, showTagline: false)),
          const SizedBox(height: 6),
          const Center(
            child: Text(
              'Mockup build - no live data',
              style: TextStyle(fontSize: 11, color: VW.muted),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final Color valueColor;

  const _SettingRow({
    required this.icon,
    required this.title,
    required this.value,
    this.valueColor = VW.muted,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 14),
      decoration: BoxDecoration(
        color: VW.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: VW.line),
      ),
      child: Row(
        children: [
          Icon(icon, size: 19, color: VW.muted),
          const SizedBox(width: 14),
          Expanded(
            child: Text(title,
                style: const TextStyle(
                    fontSize: 14, fontWeight: FontWeight.w600)),
          ),
          Text(value, style: TextStyle(fontSize: 13, color: valueColor)),
          const SizedBox(width: 6),
          const Icon(Icons.chevron_right_rounded, size: 19, color: VW.muted),
        ],
      ),
    );
  }
}
