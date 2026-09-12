# Committed template. The real run.ps1 is gitignored.
#
# run.ps1 reads API_URL and API_KEY out of the repo's .env so they never have
# to be pasted into a terminal. If you would rather keep them here instead,
# copy this file to run.ps1 and fill them in:

$url = "https://your-app.up.railway.app"
$key = "paste-the-shared-key-here"

flutter run --dart-define=API_URL=$url --dart-define=API_KEY=$key @args
