// Behavior tests for the page's pure logic: canonTitle (cross-source dedupe
// families), humanizeItem (LINQ kitchen shorthand), noSchoolMap + nextSchoolDay
// (structural calendar). These are the behaviors a later edit silently breaks.
//
// Run from anywhere:  node tests/page-tests.js     (exit 0 = pass)

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'site', 'index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

// DOM stubs — enough for the script's boot to no-op
const els = {};
const el = id => els[id] || (els[id] = { id, innerHTML: '', textContent: '', value: '', disabled: false,
  dataset: {}, handlers: {}, addEventListener(ev, fn) { this.handlers[ev] = fn; },
  reset() {}, showModal() {}, close() {} });

function makeSandbox(asOf) {
  const RealDate = Date;
  class FakeDate extends RealDate {
    constructor(...a) { a.length ? super(...a) : super(asOf); }
    static now() { return new RealDate(asOf).getTime(); }
  }
  return {
    document: { getElementById: el, querySelectorAll: () => [], title: '', querySelector: () => null },
    Date: FakeDate,
    fetch: () => Promise.reject(new Error('no network in tests')),
    setInterval: () => {}, setTimeout: (f) => {},
    console, Promise, JSON, Math, RegExp, String, Number, Array, Object, Set, Map, URL,
  };
}

let pass = 0, fail = 0;
const t = (name, cond) => {
  if (cond) { pass++; }
  else { fail++; console.error(`  FAIL: ${name}`); }
};

// ---------- canonTitle: cross-source event families ----------
{
  const sb = makeSandbox('2026-09-04T09:00:00');
  vm.createContext(sb);
  vm.runInContext(script, sb);
  const c = (...a) => vm.runInContext(`canonTitle(${JSON.stringify(a[0])})`, sb);
  t('gather family collapses', c('Harvest Gather TBD') === c('Autumn Gather'));
  t('fall festival family collapses', c('Autumn Festival') === c('Fall Festival'));
  t('move-a-thon family collapses', c('Move a Thon and Color Run') === c('Move-a-thon'));
  t('board meetings collapse', c('HUSD Board Meeting') === c('Board Meeting TBD'));
  t('no-school variants collapse', c('No School: Staff Development Day') === c('Teacher In-Service — No School'));
  t('winter festival family collapses', c('Winter Lantern Walk') === c('Winter Festival'));
  t('break ranges collapse', c('Winter Break (through Jan 1)') === c('Winter Break- No School'));
  t('unrelated events do NOT collapse', c('Honor Assembly') !== c('Honor Week'));
  t('spring vs fall festival distinct', c('Spring Festival') !== c('Fall Festival'));
}

// ---------- humanizeItem: LINQ kitchen shorthand ----------
{
  const sb = makeSandbox('2026-09-04T09:00:00');
  vm.createContext(sb);
  vm.runInContext(script, sb);
  const h = s => vm.runInContext(`humanizeItem(${JSON.stringify(s)})`, sb);
  t('brand hoisted with grain', h('Bagel, WG, Dos Pisano') === "Dos Pisano's whole-grain bagel");
  t('brand hoisted with flavor', h("Croissant, choc, Dos Pisano's") === "Dos Pisano's chocolate croissant");
  t('house-with brand becomes prefix', h("Pizza, house with Dos Pisano's") === "House-made Dos Pisano's pizza");
  t('housemade hoisted', h('Whole wheat pancakes, housemade') === 'House-made whole wheat pancakes');
  t('kitchen noise dropped', h('Peas, frozen') === 'Peas');
  t('allergen qualifier kept', h('Tamale, Bean and cheese, WG, Gluten free') === 'Whole-grain tamale, Bean and cheese, Gluten free');
  t('USDA meal-pattern codes dropped', h('Macaroni and cheese, 2 M/MA, 1 WG') === 'Macaroni and cheese');
  t('parenthesized meal codes dropped', h('Mac and cheese (2 M/MA, 1 WG)') === 'Mac and cheese');
  t('already-clean names untouched', h('Shredded chicken tacos') === 'Shredded chicken tacos');
}

// ---------- noSchoolMap + nextSchoolDay (structural calendar) ----------
const yc = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', 'calendar-year.json'), 'utf8'));
{
  const sb = makeSandbox('2026-09-04T09:00:00');   // Friday before Labor Day weekend
  vm.createContext(sb);
  vm.runInContext(script, sb);
  vm.runInContext(`NSM = noSchoolMap(YC); NSD = nextSchoolDay(new Date(), NSM);`, Object.assign(sb, { YC: yc }));
  t('labor day mapped', vm.runInContext(`NSM.get('2026-09-07')`, sb) === 'Labor Day — No School');
  t('in-service day mapped', vm.runInContext(`NSM.get('2026-10-12')`, sb) === 'Teacher In-Service — No School');
  t('break range expanded (mid)', vm.runInContext(`NSM.has('2026-11-25')`, sb) === true);
  t('break range expanded (end)', vm.runInContext(`NSM.has('2026-11-27')`, sb) === true);
  t('regular school day unmapped', vm.runInContext(`NSM.get('2026-09-08')`, sb) === undefined);
  t('friday before 3-day weekend -> tuesday', vm.runInContext(`isoOf(NSD)`, sb) === '2026-09-08');
}
{
  const sb = makeSandbox('2026-09-13T09:00:00');   // a regular Sunday
  vm.createContext(sb);
  vm.runInContext(script, sb);
  vm.runInContext(`NSM2 = noSchoolMap(YC); NSD2 = nextSchoolDay(new Date(), NSM2);`, Object.assign(sb, { YC: yc }));
  t('regular sunday -> monday', vm.runInContext(`isoOf(NSD2)`, sb) === '2026-09-14');
}

// ---------- absenceMailto ----------
{
  const sb = makeSandbox('2026-09-25T08:00:00');
  vm.createContext(sb);
  vm.runInContext(script, sb);
  const m = (...a) => vm.runInContext(`absenceMailto(${JSON.stringify(a[0])}, ${JSON.stringify(a[1])}, ${JSON.stringify(a[2])}, ${JSON.stringify(a[3])})`, sb);
  const entry = {grade: '3rd Grade', email: '3rdgradeabsence@harmonyusd.org'};
  const href = m(entry, 'Rey', '2026-09-25', 'fever');
  t('mailto targets grade email', href.startsWith('mailto:3rdgradeabsence@harmonyusd.org?'));
  t('subject encoded with name+grade+date', href.includes(encodeURIComponent('Absence — Rey (3rd Grade), 2026-09-25')));
  t('reason included when given', href.includes(encodeURIComponent('Reason: fever')));
  t('blank name falls back to Student', m(entry, '', '2026-09-25', '').includes(encodeURIComponent('Absence — Student')));
  t('blank reason omitted', !m(entry, 'X', '2026-09-25', '  ').includes('Reason'));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
