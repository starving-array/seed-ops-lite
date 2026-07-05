# Architecture Evolution Proposals

This document proposes structural upgrades for the next major release (v4.0.0).

---

## 1. Cloud-Native Scalability
- **Shared Storage Backend**: Upgrade the SQLite WAL database layer to a distributed database engine like Postgres for horizontal worker scaling.
- **Distributed Event Architecture**: Route events through messaging layers (e.g. RabbitMQ or Redis PubSub) to decouple workers.

---

## 2. Dynamic Plugin Framework
- Allow third-party packages to inject custom consensus policies or notification providers dynamically using entry point registries.
