import 'package:flutter/material.dart';
import 'login_page.dart';
import 'theme.dart';

void main() => runApp(const VigiWatchApp());

class VigiWatchApp extends StatelessWidget {
  const VigiWatchApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VigiWatch',
      debugShowCheckedModeBanner: false,
      theme: vigiWatchTheme(),
      home: const LoginPage(),
    );
  }
}
