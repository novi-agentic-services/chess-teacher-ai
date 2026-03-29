# M1 Architecture

## Services
- API (FastAPI)
- Worker (Celery)
- PostgreSQL
- RabbitMQ (broker)
- Redis (result backend + future cache)

## Queue Topology (RabbitMQ)
- `twic.download` — download TWIC zips
- `twic.parse` — parse TWIC PGN packages
- `twic.aggregate` — aggregate position move stats
- Retries via Celery autoretry; failed messages can be routed to DLQ in M2 hardening.

## M1 Definition of Done
- TWIC sources discoverable and queueable from API
- Worker downloads issue zips and marks source statuses through lifecycle
- DB schema created for game/position/tree pipeline
- Local stack boots via docker compose
