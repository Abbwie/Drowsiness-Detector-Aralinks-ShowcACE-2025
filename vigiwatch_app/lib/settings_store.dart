import 'package:shared_preferences/shared_preferences.dart';

/// The driver's own preferences.
///
/// All of these now live on the relay, which the detector polls -- the phone
/// copy is a cache so the page can render before the network answers. The
/// emergency contact used to be the exception, kept only here while the
/// detector messaged a number compiled into its source, which meant this
/// screen promised something that never happened. SettingsPage owns the
/// syncing, which keeps this class free of the network.
class SettingsStore {
  static const _kName = 'emergency_name';
  static const _kNumber = 'emergency_number';
  static const _kVoice = 'voice_alert_on';
  static const _kBuzzer = 'buzzer_on';
  static const _kNotify = 'notify_contact_on';
  static const _kDriver = 'driver_name';

  // Blank, not a real number. A default that dials a real person is one
  // misread screen away from messaging a stranger, and this file is public.
  String emergencyName = '';
  String emergencyNumber = '';
  bool voiceAlertOn = true;
  bool buzzerOn = false;
  bool notifyContactOn = false;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    emergencyName = p.getString(_kName) ?? emergencyName;
    emergencyNumber = p.getString(_kNumber) ?? emergencyNumber;
    voiceAlertOn = p.getBool(_kVoice) ?? voiceAlertOn;
    buzzerOn = p.getBool(_kBuzzer) ?? buzzerOn;
    notifyContactOn = p.getBool(_kNotify) ?? notifyContactOn;
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kName, emergencyName);
    await p.setString(_kNumber, emergencyNumber);
    await p.setBool(_kVoice, voiceAlertOn);
    await p.setBool(_kBuzzer, buzzerOn);
    await p.setBool(_kNotify, notifyContactOn);
  }

  /// Remembering the name lets the home page greet the driver before the
  /// first request comes back.
  static Future<void> rememberDriver(String name) async =>
      (await SharedPreferences.getInstance()).setString(_kDriver, name);

  static Future<String?> lastDriver() async =>
      (await SharedPreferences.getInstance()).getString(_kDriver);
}
