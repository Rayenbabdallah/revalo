/**
 * Interface language: English, French or Arabic (right to left).
 *
 * The English text is the key, so the code stays readable and a missing
 * translation falls back to English instead of showing an id. Plurals are
 * written "one form|other form" in English and French; Arabic entries give
 * each form Intl.PluralRules asks for (zero, one, two, few, many, other).
 *
 * The language is read once at start. Changing it reloads the page, so text
 * in module-level tables is always in the right language.
 * `npm run check:i18n` fails when a key has no French or Arabic entry.
 */

import { ar } from './locales/ar'
import { fr } from './locales/fr'

export type Locale = 'en' | 'fr' | 'ar'
export type Entry = string | Partial<Record<Intl.LDMLPluralRule, string>>
export type Dictionary = Record<string, Entry>

export const LOCALES: { id: Locale; name: string }[] = [
  { id: 'en', name: 'English' },
  { id: 'fr', name: 'Français' },
  { id: 'ar', name: 'العربية' },
]

const KEY = 'revalo.locale'
const DICTIONARIES: Record<Exclude<Locale, 'en'>, Dictionary> = { fr, ar }

function detect(): Locale {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'en' || saved === 'fr' || saved === 'ar') return saved
  } catch {
    /* storage blocked: fall back to the browser language */
  }
  const browser = (typeof navigator !== 'undefined' ? navigator.language : 'en').slice(0, 2)
  return browser === 'fr' || browser === 'ar' ? browser : 'en'
}

const locale: Locale = detect()
const plurals = new Intl.PluralRules(locale)

export const getLocale = () => locale
export const isRtl = () => locale === 'ar'

/** The locale for Intl formatting: Tunisian conventions, always Latin digits. */
export const intlLocale = () => ({ en: 'en-GB', fr: 'fr-TN', ar: 'ar-TN-u-nu-latn' })[locale]

/** Store the choice and reload, so every label is drawn again in the new language. */
export function setLocale(next: Locale) {
  if (next === locale) return
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* not stored: the reload falls back to the browser language */
  }
  window.location.reload()
}

/** Set the page language and direction once, before the first render. */
export function applyDocumentLocale() {
  document.documentElement.lang = locale
  document.documentElement.dir = isRtl() ? 'rtl' : 'ltr'
}

type Params = Record<string, string | number>

function pick(entry: Entry | undefined, key: string, count: number | undefined): string {
  if (count === undefined) {
    return typeof entry === 'string' ? entry : (entry?.other ?? key)
  }
  const rule = plurals.select(count)
  if (entry && typeof entry === 'object') return entry[rule] ?? entry.other ?? key
  const forms = (entry ?? key).split('|')
  if (forms.length === 1) return forms[0]
  return rule === 'one' ? forms[0] : forms[forms.length - 1]
}

/** Translate `key`, filling {placeholders} from `params`; `params.count` picks the plural. */
export function t(key: string, params?: Params): string {
  const entry = locale === 'en' ? undefined : DICTIONARIES[locale][key]
  const count = typeof params?.count === 'number' ? params.count : undefined
  const text = pick(entry, key, count)
  return params ? text.replace(/\{(\w+)\}/g, (m, name: string) => (name in params ? String(params[name]) : m)) : text
}
