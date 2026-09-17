import 'package:shared_preferences/shared_preferences.dart';

/// The driver's own preferences, kept on the phone.
///
/// The emergency contact is local only -- the detector reads its number from
/// its own .env on the laptop. The two alert switches do reach it, through
/// PUT /settings on the relay, which the detector polls; what is stored here
/// is a cache so the page can render before that answers. SettingsPage owns
/// the syncing, which keeps this class free of the network.
class SettingsStore {
  static const _kName = 'emergency_name';
  static const _kNumber = 'emergency_number';
  static const _kVoice = 'voice_alert_on';
  static const _kBuzzer = 'buzzer_on';
  static const _kDriver = 'driver_name';

  String emergencyName = 'Mama';
  String emergencyNumber = '+63 967 009 2434';
  bool voiceAlertOn = true;
  bool buzzerOn = false;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    emergencyName = p.getString(_kName) ?? emergencyName;
    emergencyNumber = p.getString(_kNumber) ?? emergencyNumber;
    voiceAlertOn = p.getBool(_kVoice) ?? voiceAlertOn;
    buzzerOn = p.getBool(_kBuzzer) ?? buzzerOn;
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kName, emergencyName);
    await p.setString(_kNumber, emergencyNumber);
    await p.setBool(_kVoice, voiceAlertOn);
    await p.setBool(_kBuzzer, buzzerOn);
  }

  /// Remembering the name lets the home page greet the driver before the
  /// first request comes back.
  static Future<void> rememberDriver(String name) async =>
      (await SharedPreferences.getInstance()).setString(_kDriver, name);

  static Future<String?> lastDriver() async =>
      (await SharedPreferences.getInstance()).getString(_kDriver);
}
