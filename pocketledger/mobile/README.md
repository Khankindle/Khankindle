# PocketLedger Android app

Flutter client that photographs a notebook page and sends it to `extract_server.py` on the laptop. The Gemini key never goes on the phone.

- **Process ledger** sends the photo to `POST /api/extract`. The reply includes the statement and the trader's Business Health Score, shown in a card above the summary.
- **Check health score** calls `GET /api/health` for the business name and category on screen, without a new photo.
- Captures join the same history as the Streamlit app when the business name and category match.

```
flutter pub get
flutter test        # widget tests, including the health score card
flutter run         # or: flutter build apk
```

See the main [README](../README.md#android) for the server address to use on an emulator or a phone.
