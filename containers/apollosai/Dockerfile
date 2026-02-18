ARG APOLLOS_VERSION=latest
ARG BASE="ghcr.io/jrmatherly/apollosai"
FROM ${BASE}:${APOLLOS_VERSION}

LABEL org.apollosai.component="enterprise-server"

# Overlay BOTH openhands/ and apollosai/ from the repo so that a single
# `docker compose build app` picks up ALL code changes without needing
# to rebuild the heavy base image. The base image provides Python deps,
# frontend build, OS setup, and user creation — this layer just refreshes
# the Python source.
COPY --chown=openhands:openhands --chmod=770 openhands /app/openhands
COPY --chown=openhands:openhands --chmod=770 apollosai /app/apollosai

ENV OPENHANDS_CONFIG_CLS=apollosai.server.config.ApollosAIServerConfig

CMD ["uvicorn", "apollosai.app_server:app", "--host", "0.0.0.0", "--port", "3000"]
