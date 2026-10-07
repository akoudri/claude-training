# Image de base : même version majeure de Node que .nvmrc (22), Debian bookworm.
FROM mcr.microsoft.com/devcontainers/javascript-node:22-bookworm

# Outils du pare-feu sortant (init-firewall.sh) : iptables, ipset, dig, ip, jq.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      iptables ipset dnsutils iproute2 jq \
 && rm -rf /var/lib/apt/lists/*
