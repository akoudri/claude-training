// Convertit un titre en identifiant d'URL.
function slugify(titre) {
  return titre.toLowerCase().replace(/ /g, '-');
}
module.exports = { slugify };
