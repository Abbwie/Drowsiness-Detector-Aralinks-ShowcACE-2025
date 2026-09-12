/// Where the app looks for the relay, and the key it presents.
///
/// Both come from --dart-define, never from a literal in this file: the repo
/// is public and a key committed here is a key that has to be rotated. The
/// defaults are empty on purpose, so a forgotten define fails loudly on the
/// login screen instead of quietly pointing at nothing.
///
///   flutter run --dart-define=API_URL=https://...  --dart-define=API_KEY=...
///
/// run.ps1 (gitignored) holds the real values -- copy run.example.ps1.
library;

const String apiUrl = String.fromEnvironment('API_URL');
const String apiKey = String.fromEnvironment('API_KEY');

bool get isConfigured => apiUrl.isNotEmpty && apiKey.isNotEmpty;
