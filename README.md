# chess-teacher-ai

M1 foundation for a ChessBase-like online app with mandatory TWIC corpus ingestion.

## M1 Delivered
- FastAPI service with TWIC sync/status endpoints
- RabbitMQ-backed Celery worker pipeline
- PostgreSQL schema for TWIC sources, games, positions, game_positions, and position_move_stats
- Docker Compose stack (api, worker, postgres, rabbitmq, redis)
- Initial TWIC list fetch + download enqueue flow

## Run locally

```bash
docker compose up --build
```

API:
- `GET /health`
- `GET /api/twic/status`
- `POST /api/twic/sync`

## Notes
- TWIC source list endpoint may evolve over time; parser is isolated in `api/app/twic.py` for easy updates.
- Redis is included for caching extensibility; RabbitMQ is mandatory broker for workers.
