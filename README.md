# Kimai CalDAV Bridge Docker

A lightweight Kimai CalDAV bridge built with Python and Docker.

Created by Jan Hüls "finex7070" StickyStoneStudio GmbH 🚀

---

## Features

- 📆 Automatic import Absences and Public Holidays into CalDAV calender
- 📈 Built-in `/metrics` endpoint for Prometheus / Grafana monitoring
- 🐳 Dockerized for fast, reproducible deployment

---

## Getting Started

### 1. Clone and Deploy

```bash
git clone https://github.com/finex7070/kimai-caldav-bridge.git
cd kimai-caldav-bridge
# Edit the docker-compose.yml file
docker compose up -d
```

---

## Environment Variables

| Variable                  | Description                                     | Required | Default                                               |
|---------------------------|-------------------------------------------------|----------|-------------------------------------------------------|
| `KIMAI_API_URL`           | Base URL of the Kimai API                       | yes      | https://kimai.example.com/api                         |
| `KIMAI_API_KEY`           | Kimai API Key (Profile -> API Access)           | yes      | changeme                                              |
| `CALDAV_URL`              | CalDAV URL of the calender                      | yes      | https://caldav.example.com/dav/username/Calendar/name |
| `CALDAV_USERNAME`         | CalDAV username                                 | no       | username                                              |
| `CALDAV_PASSWORD`         | CalDAV password                                 | no       | changeme                                              |
| `SKIP_VERIFY_CERTIFICATE` | Skip ssl certificate verification               | no       | false                                                 |

---

## API Endpoints

| Path                      | Method(s)                      | Description                                |
|---------------------------|--------------------------------|--------------------------------------------|
| `/healthz`                | `GET`                          | Healthcheck endpoint                       |
| `/metrics`                | `GET`                          | Prometheus metrics (for Grafana)           |

---

## How It Works

1. Discovery: The bridge fetches public holidays and absences from Kimai within a dynamic time window (last year to next year).
2. Synchronization: It compares these entries with existing events in the CalDAV calendar using unique IDs.
3. Update: New events are created, changed events are updated, and deleted entries (that are no longer in Kimai) are removed from the calendar.

---

## Requirements

- ⏱️ Kimai + [Kiami Working hours, vacation, sickness, public holidays Plugin](https://www.kimai.org/store/controlling.html)
- 🐳 Docker + Docker Compose
- 🔐 A valid Kimai API key
- 📆 CalDAV URL to a calender with read + write access

---

## Monitoring

Export metrics to Prometheus:

```text
GET /metrics
```

Sample output:
```text
# HELP public_holidays_total Number of public holidays currently synced
# TYPE public_holidays_total gauge
public_holidays_total 12.0
# HELP absences_total Number of absences currently synced
# TYPE absences_total gauge
absences_total 45.0
# HELP sync_errors_total Total number of errors encountered during sync
# TYPE sync_errors_total counter
sync_errors_total 0.0
```

---

## License

GNU Affero General Public License v3.0 (AGPLv3)

This project is open-source and available under the AGPLv3 license.

✅ Commercial Use: You are free to use this software for commercial purposes (e.g., hosting for clients).
✅ Modification: You are free to modify the code to suit your needs.
🔄 Copyleft: If you modify the software and make it available to others (including as a hosted service / SaaS), you must release your modifications under the same AGPLv3 license. Closed-source proprietary forks are not allowed.

See the LICENSE file for full details.

---

> Made with ❤️ by Jan Hüls "finex7070" [StickyStoneStudio GmbH](https://www.stickystonestudio.com)
