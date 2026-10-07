const test = require('node:test');
const assert = require('node:assert');
const { slugify } = require('./slug');
test('minuscules et tirets', () => assert.equal(slugify('Hello World'), 'hello-world'));
test('accents retirés', () => assert.equal(slugify('Été à Paris'), 'ete-a-paris'));
test('ponctuation et espaces multiples', () => assert.equal(slugify('  Bonjour,   le monde ! '), 'bonjour-le-monde'));
