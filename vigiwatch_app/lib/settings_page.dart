import 'package:flutter/material.dart';

import 'settings_store.dart';
import 'theme.dart';

class SettingsPage extends StatefulWidget {
  final VoidCallback onLogout;
  const SettingsPage({super.key, required this.onLogout});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final store = SettingsStore();

  // Seeded from the store's defaults so the page renders before the saved
  // values come back off disk.
  late final name = TextEditingController(text: store.emergencyName);
  late final number = TextEditingController(text: store.emergencyNumber);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    await store.load();
    if (!mounted) return;
    setState(() {
      name.text = store.emergencyName;
      number.text = store.emergencyNumber;
    });
  }

  @override
  void dispose() {
    name.dispose();
    number.dispose();
    super.dispose();
  }

  Future<void> save() async {
    store.emergencyName = name.text;
    store.emergencyNumber = number.text;
    await store.save();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Settings saved')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Emergency contact', style: TextStyle(fontSize: 16)),
        const SizedBox(height: 4),
        const Text(
          'We send this person a message if you keep getting drowsy.',
          style: TextStyle(fontSize: 13, color: muted),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: name,
          decoration: const InputDecoration(hintText: 'Name'),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: number,
          keyboardType: TextInputType.phone,
          decoration: const InputDecoration(hintText: 'Phone number'),
        ),
        const SizedBox(height: 28),
        const Text('Alerts', style: TextStyle(fontSize: 16)),
        const SizedBox(height: 12),
        _Toggle(
          label: 'Voice alert',
          value: store.voiceAlertOn,
          onChanged: (v) => setState(() => store.voiceAlertOn = v),
        ),
        _Toggle(
          label: 'Buzzer',
          value: store.buzzerOn,
          onChanged: (v) => setState(() => store.buzzerOn = v),
        ),
        const SizedBox(height: 8),
        const Text(
          'Saved on this phone. The detector still reads its own settings '
          'from the laptop.',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 28),
        FilledButton(onPressed: save, child: const Text('Save')),
        const SizedBox(height: 10),
        OutlinedButton(
          onPressed: widget.onLogout,
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(48),
            side: const BorderSide(color: line),
            foregroundColor: red,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
          child: const Text('Logout'),
        ),
      ],
    );
  }
}

class _Toggle extends StatelessWidget {
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _Toggle({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.only(left: 14, right: 6),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: line),
      ),
      child: Row(
        children: [
          Expanded(child: Text(label, style: const TextStyle(fontSize: 14))),
          Switch(
            value: value,
            activeThumbColor: Colors.white,
            activeTrackColor: red,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}
