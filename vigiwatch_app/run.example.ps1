# Copy to run.ps1 (gitignored) and fill in the real values, then: .\run.ps1
# API_KEY must match the one set on the Railway service and in the detector's .env.

$env:VW_API_URL = "https://your-app.up.railway.app"
$env:VW_API_KEY = "paste-the-shared-key-here"

flutter run `
  --dart-define=API_URL=$env:VW_API_URL `
  --dart-define=API_KEY=$env:VW_API_KEY
