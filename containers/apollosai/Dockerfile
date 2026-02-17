ARG APOLLOS_VERSION=latest
ARG BASE="ghcr.io/jrmatherly/apollosai"
FROM ${BASE}:${APOLLOS_VERSION}

LABEL org.apollosai.component="enterprise-server"

# Copy ApollosAI enterprise layer
# Python deps (msal, pyjwt, etc.) are already installed in the base image
# via the root pyproject.toml — no pip install needed
COPY --chown=openhands:openhands --chmod=770 apollosai /app/apollosai

ENV OPENHANDS_CONFIG_CLS=apollosai.server.config.ApollosAIServerConfig

CMD ["uvicorn", "apollosai.app_server:app", "--host", "0.0.0.0", "--port", "3000"]
