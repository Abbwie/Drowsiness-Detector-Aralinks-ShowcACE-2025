/// Where the app looks for the relay, and the key it presents.
///
/// Both are compiled in from the repo's .env, never from a literal in this
/// file: the repo is public and a key committed here is a key that has to be
/// rotated. The defaults are empty on purpose, so a forgotten define fails
/// loudly on the login screen instead of quietly pointing at nothing.
///
/// Nothing needs typing. Any of these picks the values up on its own:
///
///   * F5 / Run and Debug in VS Code      (.vscode/launch.json)
///   * .\run.ps1                          (from vigiwatch_app)
///   * flutter run --dart-define-from-file=../.env
///
/// All three read the same gitignored .env at the repo root, which is also
/// where the detector gets its copy.
library;

const String apiUrl = String.fromEnvironment('API_URL');
const String apiKey = String.fromEnvironment('API_KEY');

bool get isConfigured => apiUrl.isNotEmpty && apiKey.isNotEmpty;
