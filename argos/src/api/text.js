// Forme de comparaison utilisée par la recherche, enregistrée comme fonction SQLite par openDb :
// décomposition Unicode (NFD) puis suppression des accents combinants, et minuscules.
export function normalize(text) {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}
