import 'package:flutter/material.dart';

import 'api.dart';
import 'home_shell.dart';
import 'settings_store.dart';
import 'theme.dart';
import 'widgets.dart';

class LoginPage extends StatefulWidget {
  /// Injectable so the widget tests can sign in without a network.
  final VigiWatchApi? api;

  const LoginPage({super.key, this.api});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  late final VigiWatchApi api = widget.api ?? VigiWatchApi();

  final username = TextEditingController();
  final password = TextEditingController();

  bool busy = false;
  String? error;

  @override
  void dispose() {
    username.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> login() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });

    try {
      final name = await api.login(username.text.trim(), password.text);
      await SettingsStore.rememberDriver(name);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => HomeShell(api: api, driverName: name),
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => error = e.message);
    } finally {
      // The page is gone on success, so only touch state if it is still here.
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Center(child: Logo(size: 48, withMotto: true)),
                  const SizedBox(height: 40),
                  const Text('Sign in', style: TextStyle(fontSize: 22)),
                  const SizedBox(height: 16),
                  TextField(
                    controller: username,
                    enabled: !busy,
                    autocorrect: false,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(hintText: 'Username'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: password,
                    enabled: !busy,
                    obscureText: true,
                    textInputAction: TextInputAction.go,
                    onSubmitted: (_) => login(),
                    decoration: const InputDecoration(hintText: 'Password'),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: 14),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.error_outline, color: red, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            error!,
                            style: const TextStyle(fontSize: 13, color: red),
                          ),
                        ),
                      ],
                    ),
                  ],
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: busy ? null : login,
                    child: busy
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Login'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
