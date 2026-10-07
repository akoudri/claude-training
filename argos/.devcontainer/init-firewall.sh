#!/usr/bin/env bash
# Pare-feu sortant du devcontainer Argos, sur le modèle de init-firewall.sh du devcontainer
# de référence d'Anthropic. Tout trafic sortant est refusé, sauf vers les hôtes listés.
# Rejouable : chaque exécution repart de zéro (lancé en postCreate et en postStart).
set -euo pipefail

# Hôtes autorisés : ceux d'Argos (allowlist du lab M4) et ceux dont Claude Code et VS Code
# ont besoin pour fonctionner.
DOMAINS=(
  registry.npmjs.org                 # dépendances npm
  api.notifications-argos.example    # service de notification (fictif : ne se résout pas)
  api.anthropic.com                  # Claude Code
  claude.ai
  platform.claude.com
  console.anthropic.com
  sentry.io
  marketplace.visualstudio.com       # extensions VS Code
  vscode.blob.core.windows.net
  update.code.visualstudio.com
)
SET=argos-allowed

# 1. Repartir de zéro, en laissant passer le trafic le temps de résoudre les hôtes.
iptables -P OUTPUT ACCEPT
iptables -F OUTPUT
ipset destroy "$SET" 2>/dev/null || true
ipset create "$SET" hash:net

# 2. Plages de GitHub (git push/pull, Codespaces), publiées par l'API meta.
if meta=$(curl -fsS --max-time 10 https://api.github.com/meta); then
  jq -r '(.web + .api + .git)[] | select(contains(":") | not)' <<<"$meta" \
    | while read -r cidr; do ipset add -exist "$SET" "$cidr"; done
else
  echo "init-firewall : plages GitHub indisponibles, GitHub restera bloqué" >&2
fi

# 3. Adresses IPv4 de chaque hôte autorisé.
for domain in "${DOMAINS[@]}"; do
  ips=$(dig +short A "$domain" | grep -E '^[0-9.]+$' || true)
  if [[ -z "$ips" ]]; then
    echo "init-firewall : $domain ne se résout pas, ignoré" >&2
    continue
  fi
  for ip in $ips; do ipset add -exist "$SET" "$ip"; done
done

# 4. Règles : boucle locale, DNS, réseau de l'hôte (Docker, Codespaces), connexions établies,
#    hôtes autorisés ; tout le reste est rejeté immédiatement (pas d'attente de timeout).
host_net=$(ip route | awk '/default/ {print $3}' | sed 's/\.[0-9]*$/.0\/24/')
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
[[ -n "$host_net" ]] && iptables -A OUTPUT -d "$host_net" -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m set --match-set "$SET" dst -j ACCEPT
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited
iptables -P OUTPUT DROP

# IPv6 : tout bloquer sauf la boucle locale (aucun hôte autorisé n'est résolu en IPv6).
if ip6tables -L OUTPUT >/dev/null 2>&1; then
  ip6tables -P OUTPUT ACCEPT
  ip6tables -F OUTPUT
  ip6tables -A OUTPUT -o lo -j ACCEPT
  ip6tables -P OUTPUT DROP
fi

# 5. Vérifier par un essai de contournement, pas seulement par l'absence d'erreur.
if curl -fsS --max-time 5 https://example.com >/dev/null 2>&1; then
  echo "init-firewall : ÉCHEC, example.com reste joignable" >&2
  exit 1
fi
if ! curl -fsS --max-time 10 https://registry.npmjs.org/ >/dev/null; then
  echo "init-firewall : ÉCHEC, registry.npmjs.org n'est pas joignable" >&2
  exit 1
fi
echo "init-firewall : pare-feu actif (example.com bloqué, registry.npmjs.org joignable)"
