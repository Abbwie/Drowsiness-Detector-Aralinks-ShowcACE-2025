import 'package:flutter/material.dart';

import 'api.dart';
import 'privacy_page.dart';
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

  /// The driver has moved a switch since the last time the relay and this page
  /// agreed. Stops an in-flight read from overwriting a fresh tap.
  bool _touched = false;

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
        syncError = null;
        // Not if the driver has flipped something while this was still in
        // flight: a reply to a request that predates their tap must not
        // silently undo it. They would see the switch move back on its own.
        if (!_touched) {
          store.voiceAlertOn = remote.voiceAlertOn;
          store.buzzerOn = remote.buzzerOn;
          store.notifyContactOn = remote.notifyContactOn;
          store.headDropRatio = remote.headDropRatio;
          store.noFaceAlertSeconds = remote.noFaceAlertSeconds;
          store.noFaceContactSeconds = remote.noFaceContactSeconds;
          // The relay is where the contact lives now, so it wins over
          // whatever this phone last cached -- including on a reinstall, or
          // on a second phone that has never seen it.
          store.emergencyName = remote.contactName;
          store.emergencyNumber = remote.contactNumber;
          name.text = remote.contactName;
          number.text = remote.contactNumber;
        }
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
        notifyContactOn: store.notifyContactOn,
        contactName: name.text.trim(),
        contactNumber: number.text.trim(),
        headDropRatio: store.headDropRatio,
        noFaceAlertSeconds: store.noFaceAlertSeconds,
        noFaceContactSeconds: store.noFaceContactSeconds,
      ));
      if (!mounted) return;
      setState(() {
        store.voiceAlertOn = stored.voiceAlertOn;
        store.buzzerOn = stored.buzzerOn;
        store.notifyContactOn = stored.notifyContactOn;
        store.headDropRatio = stored.headDropRatio;
        store.noFaceAlertSeconds = stored.noFaceAlertSeconds;
        store.noFaceContactSeconds = stored.noFaceContactSeconds;
        // Show what the relay kept, not what was typed: trimming happens
        // there, and the detector will read that version.
        store.emergencyName = stored.contactName;
        store.emergencyNumber = stored.contactNumber;
        name.text = stored.contactName;
        number.text = stored.contactNumber;
        syncError = null;
        _touched = false;   // relay and page agree again
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
          'If you keep getting drowsy, the detector messages this person. '
          'Saved to the relay, so a change here reaches it in a few seconds.',
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
        const SizedBox(height: 10),
        _Toggle(
          label: 'Message this contact',
          value: store.notifyContactOn,
          onChanged: (v) => setState(() {
            store.notifyContactOn = v;
            _touched = true;
          }),
        ),
        const SizedBox(height: 4),
        const Text(
          'Off until you turn it on. Someone else being told where you are '
          'up to should be your decision, not a default.',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 28),
        const Text('Alerts', style: TextStyle(fontSize: 16)),
        const SizedBox(height: 12),
        _Toggle(
          label: 'Voice alert',
          value: store.voiceAlertOn,
          onChanged: (v) => setState(() {
            store.voiceAlertOn = v;
            _touched = true;
          }),
        ),
        _Toggle(
          label: 'Buzzer',
          value: store.buzzerOn,
          onChanged: (v) => setState(() {
            store.buzzerOn = v;
            _touched = true;
          }),
        ),
        const SizedBox(height: 8),
        Text(
          syncError == null
              ? 'All of these reach the detector within a few seconds of '
                  'saving.'
              : 'Not synced with the detector: $syncError',
          style: TextStyle(
              fontSize: 12, color: syncError == null ? muted : red),
        ),
        const SizedBox(height: 28),
        const Text('Detection', style: TextStyle(fontSize: 16)),
        const SizedBox(height: 4),
        const Text(
          'Where the camera sits changes what a nod looks like, so these are '
          'worth tuning per setup rather than left at one number.',
          style: TextStyle(fontSize: 13, color: muted),
        ),
        const SizedBox(height: 12),
        _Slider(
          label: 'Head-drop sensitivity',
          detail: 'Higher reacts to a smaller nod. Lower it if it calls '
              'head down while you are sitting normally.',
          value: store.headDropRatio,
          min: 0.50,
          max: 0.95,
          divisions: 9,
          format: (v) => '${(v * 100).round()}%',
          onChanged: (v) => setState(() {
            store.headDropRatio = v;
            _touched = true;
          }),
        ),
        _Slider(
          label: 'Alert if no face for',
          detail: 'Voice and buzzer, repeating until you are back in frame.',
          value: store.noFaceAlertSeconds,
          min: 5,
          max: 120,
          divisions: 23,
          format: (v) => '${v.round()}s',
          onChanged: (v) => setState(() {
            store.noFaceAlertSeconds = v;
            _touched = true;
          }),
        ),
        _Slider(
          label: 'Then message your contact after',
          detail: 'Once per absence, and only if the switch above is on.',
          value: store.noFaceContactSeconds,
          min: 10,
          max: 300,
          divisions: 29,
          format: (v) => '${v.round()}s',
          onChanged: (v) => setState(() {
            store.noFaceContactSeconds = v;
            _touched = true;
          }),
        ),
        const SizedBox(height: 28),
        const Text('About', style: TextStyle(fontSize: 16)),
        const SizedBox(height: 12),
        _LinkRow(
          label: 'Your data and what Sentra cannot do',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const PrivacyPage()),
          ),
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

class _Slider extends StatelessWidget {
  final String label;
  final String detail;
  final double value;
  final double min;
  final double max;
  final int divisions;
  final String Function(double) format;
  final ValueChanged<double> onChanged;

  const _Slider({
    required this.label,
    required this.detail,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.format,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    // Clamped before it reaches the Slider: a value from an older relay, or
    // one edited by hand, outside the range throws rather than displaying.
    final v = value.clamp(min, max);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 6),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                  child: Text(label, style: const TextStyle(fontSize: 14))),
              Text(format(v),
                  style: const TextStyle(fontSize: 14, color: red)),
            ],
          ),
          Text(detail,
              style: const TextStyle(fontSize: 11, color: muted, height: 1.4)),
          Slider(
            value: v,
            min: min,
            max: max,
            divisions: divisions,
            activeColor: red,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}

class _LinkRow extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _LinkRow({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
        decoration: BoxDecoration(
          color: card,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: line),
        ),
        child: Row(
          children: [
            Expanded(child: Text(label, style: const TextStyle(fontSize: 14))),
            const Icon(Icons.chevron_right, size: 20, color: muted),
          ],
        ),
      ),
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
