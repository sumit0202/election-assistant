# Examples

Curated, copy-paste-ready examples for every CivicGuide endpoint. Tested
against the local dev server (`./run.sh`) and the live Cloud Run URL.

| File | What it shows |
|---|---|
| [`curl-chat.sh`](./curl-chat.sh) | Conversational `/api/chat` request |
| [`curl-polling.sh`](./curl-polling.sh) | Maps-backed polling-venue search |
| [`curl-videos.sh`](./curl-videos.sh) | YouTube explainer-video search |
| [`curl-translate.sh`](./curl-translate.sh) | Google Cloud Translation |
| [`curl-reminder.sh`](./curl-reminder.sh) | Download an `.ics` calendar reminder |
| [`curl-health.sh`](./curl-health.sh) | Liveness + version probe |
| [`python-client.py`](./python-client.py) | Minimal async Python client |

Set `BASE_URL` once and every script will use it:

```bash
export BASE_URL="http://localhost:8080"
# or
export BASE_URL="https://civicguide-<hash>-as.a.run.app"
```
