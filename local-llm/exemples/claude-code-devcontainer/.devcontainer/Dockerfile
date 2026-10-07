# Image du dev container : outils de base et Claude Code, version figée.
# Version allégée du Dockerfile de référence d'Anthropic (sans zsh, git-delta ni pare-feu :
# l'isolement vient du réseau Docker "internal").
FROM node:22

ARG TZ
ENV TZ="$TZ"
ARG CLAUDE_CODE_VERSION=2.1.291

RUN apt-get update && apt-get install -y --no-install-recommends \
  less git procps unzip jq nano curl \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/share/npm-global /workspace /home/node/.claude && \
  chown -R node:node /usr/local/share /workspace /home/node/.claude

ENV DEVCONTAINER=true
WORKDIR /workspace

USER node
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
ENV EDITOR=nano
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}
