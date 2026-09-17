import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'history_page.dart';
import 'home_page.dart';
import 'login_page.dart';
import 'settings_page.dart';
import 'theme.dart';

/// How often the live tile asks the relay what the detector is seeing. The
/// detector heartbeats about once a second; polling that fast from a phone
/// would burn battery for no visible gain.
const _statusEvery = Duration(seconds: 3);

/// The history moves only when an episode fires, so it can lag well behind.
const _eventsEvery = Duration(seconds: 30);

class HomeShell extends StatefulWidget {
  final VigiWatchApi api;
  final String driverName;

  const HomeShell({super.key, required this.api, required this.driverName});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int index = 0;

  LiveStatus status = LiveStatus.offline();
  List<DrowsyEvent> events = [];

  bool loadingEvents = true;
  String? eventsError;
  String? statusError;

  Timer? _statusTimer;
  Timer? _eventsTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refreshStatus();
    _refreshEvents();
    _startPolling();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopPolling();
    widget.api.close();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // No point polling a relay the driver cannot see. Resuming refreshes at
    // once so the tile is never showing a reading from before the pause.
    if (state == AppLifecycleState.resumed) {
      _refreshStatus();
      _refreshEvents();
      _startPolling();
    } else {
      _stopPolling();
    }
  }

  void _startPolling() {
    _stopPolling();
    _statusTimer = Timer.periodic(_statusEvery, (_) => _refreshStatus());
    _eventsTimer = Timer.periodic(_eventsEvery, (_) => _refreshEvents());
  }

  void _stopPolling() {
    _statusTimer?.cancel();
    _eventsTimer?.cancel();
    _statusTimer = null;
    _eventsTimer = null;
  }

  Future<void> _refreshStatus() async {
    try {
      final next = await widget.api.status();
      if (!mounted) return;
      setState(() {
        status = next;
        statusError = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      // Keep the last reading on screen but stop calling it live, so a dropped
      // request cannot leave a stale ALERT looking current.
      setState(() {
        statusError = e.message;
        status = LiveStatus(
          state: 'OFFLINE',
          perclos: status.perclos,
          updatedAt: status.updatedAt,
          online: false,
        );
      });
    }
  }

  Future<void> _refreshEvents() async {
    try {
      final next = await widget.api.events(days: 7);
      if (!mounted) return;
      setState(() {
        events = next;
        eventsError = null;
        loadingEvents = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        eventsError = e.message;
        loadingEvents = false;
      });
    }
  }

  Future<void> refreshAll() async {
    await Future.wait([_refreshStatus(), _refreshEvents()]);
  }

  Future<void> clearHistory() async {
    try {
      final removed = await widget.api.clearEvents();
      if (!mounted) return;
      setState(() {
        events = [];
        eventsError = null;
      });
      _say(removed == 0
          ? 'There was nothing to delete'
          : removed == 1
              ? 'Deleted 1 episode'
              : 'Deleted $removed episodes');
    } on ApiException catch (e) {
      if (!mounted) return;
      _say(e.message);
    }
  }

  Future<void> deleteEvent(int id) async {
    // Dropped from the list before the request goes out, because a Dismissible
    // whose item is still in the tree after the swipe throws. That makes this
    // optimistic, so a failure has to put the row back.
    final before = events;
    setState(() => events = events.where((e) => e.id != id).toList());
    try {
      await widget.api.deleteEvent(id);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => events = before);
      _say('Could not delete that: ${e.message}');
    }
  }

  void _say(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  void logout() {
    _stopPolling();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => LoginPage(api: widget.api)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: bg,
        title: const Text('Sentra'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: refreshAll,
          ),
        ],
      ),
      body: IndexedStack(
        index: index,
        children: [
          HomePage(
            driverName: widget.driverName,
            status: status,
            events: events,
            loading: loadingEvents,
            error: eventsError ?? statusError,
            onRefresh: refreshAll,
            onSeeAll: () => setState(() => index = 1),
          ),
          HistoryPage(
            events: events,
            loading: loadingEvents,
            error: eventsError,
            onRefresh: _refreshEvents,
            onClear: clearHistory,
            onDelete: deleteEvent,
          ),
          SettingsPage(api: widget.api, onLogout: logout),
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
