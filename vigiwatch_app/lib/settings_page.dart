import 'package:flutter/material.dart';

import 'api.dart';
import 'settings_store.dart';
import 'theme.dart';

class SettingsPage extends StatefulWidget {
  final VigiWatchApi api;
  final VoidCallback onLogout;
  const SettingsPage({super.key, required this.api, required this.onLogout});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final store = SettingsStore();

  /// Why the switches might not match what the detector is running. Null when
  /// the last exchange with the relay worked.
  String? syncError;

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

    // The relay holds the switches, because that is where the detector reads
    // them from. This phone's cache is only what we show until the real values
    // arrive -- a reinstall, or a second phone, would otherwise display its own
    // defaults and push them over the top on the next save.
    try {
      final remote = await widget.api.settings();
      if (!mounted) return;
      setState(() {
        store.voiceAlertOn = remote.voiceAlertOn;
        store.buzzerOn = remote.buzzerOn;
        syncError = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => syncError = e.message);
    }
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

    // Local first, so a relay that cannot be reached still leaves the driver's
    // choice on this screen instead of snapping back on the next rebuild.
    var message = 'Settings saved';
    try {
      final stored = await widget.api.saveSettings(AlertSettings(
        buzzerOn: store.buzzerOn,
        voiceAlertOn: store.voiceAlertOn,
      ));
      if (!mounted) return;
      setState(() {
        store.voiceAlertOn = stored.voiceAlertOn;
        store.buzzerOn = stored.buzzerOn;
        syncError = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => syncError = e.message);
      // Named plainly: a driver who thinks they armed the buzzer and did not
      // is worse off than one who knows the save only got as far as the phone.
      message = 'Saved on this phone only - the detector was not reached.';
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
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
        Text(
          syncError == null
              ? 'These reach the detector within a few seconds of saving. The '
                  'emergency contact above stays on this phone.'
              : 'Not synced with the detector: $syncError',
          style: TextStyle(
              fontSize: 12, color: syncError == null ? muted : red),
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
