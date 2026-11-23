// Fails when text wrapped in t('...') has no French or Arabic entry,
// and lists entries nothing uses any more. Run: pnpm check:i18n
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { ar } from '../src/lib/locales/ar.ts'
import { fr } from '../src/lib/locales/fr.ts'

const SRC = new URL('../src/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const CALL = /\bt\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")/g

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === 'locales' ? [] : files(path)
    return /\.(ts|tsx)$/.test(name) ? [path] : []
  })
}

const used = new Set()
for (const file of files(SRC)) {
  for (const m of readFileSync(file, 'utf8').matchAll(CALL)) used.add((m[1] ?? m[2]).replace(/\\(['"])/g, '$1'))
}

let failed = false
for (const [name, dict] of [['fr', fr], ['ar', ar]]) {
  const missing = [...used].filter((k) => !(k in dict))
  const unused = Object.keys(dict).filter((k) => !used.has(k))
  if (missing.length) {
    failed = true
    console.error(`${name}: ${missing.length} missing\n` + missing.map((k) => `  ${JSON.stringify(k)}`).join('\n'))
  }
  if (unused.length) console.warn(`${name}: ${unused.length} unused\n` + unused.map((k) => `  ${JSON.stringify(k)}`).join('\n'))
}
console.log(`${used.size} texts checked in French and Arabic.`)
process.exit(failed ? 1 : 0)
