import 'package:flutter/material.dart';

import 'config.dart';
import 'login_page.dart';
import 'theme.dart';
import 'widgets.dart';

void main() => runApp(const VigiWatchApp());

class VigiWatchApp extends StatelessWidget {
  const VigiWatchApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VigiWatch',
      debugShowCheckedModeBanner: false,
      theme: appTheme(),
      home: isConfigured ? const LoginPage() : const _NotConfigured(),
    );
  }
}

/// Built without --dart-define=API_URL/API_KEY. Saying so here is friendlier
/// than letting every request fail with the same error behind a login form.
class _NotConfigured extends StatelessWidget {
  const _NotConfigured();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Logo(size: 44),
                const SizedBox(height: 28),
                const Text('Not configured',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 10),
                const Text(
                  'This build has no relay address or API key. Launch it with '
                  'run.ps1, or pass --dart-define=API_URL and '
                  '--dart-define=API_KEY.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13, color: muted),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
