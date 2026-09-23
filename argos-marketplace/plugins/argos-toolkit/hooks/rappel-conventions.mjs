// Hook SessionStart : rappelle à Claude la convention la plus souvent oubliée sur Argos.
console.log(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext:
        '[argos-toolkit] Rappel : statuts et priorités Argos sont en minuscules ; ' +
        "l'historique importé contient « Closed », « High »… : toujours normaliser la casse avant de comparer.",
    },
  }),
);
