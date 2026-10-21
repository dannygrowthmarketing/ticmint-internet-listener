/**
 * No-key alternative to the service-account push (pull model).
 *
 * The scheduled GitHub Action commits data/leads.csv and data/runs.csv every
 * 6 hours. This script, bound to the Google Sheet, pulls both files every hour
 * on a time-driven trigger and rewrites the "Leads" and "Run log" tabs,
 * keeping any Status a person typed in.
 *
 * Setup: Sheet > Extensions > Apps Script > paste this file > run setup() once
 * and approve the permissions. That's it.
 */
const REPO_RAW = 'https://raw.githubusercontent.com/dannygrowthmarketing/ticmint-internet-listener/main/data/';

function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('refresh').timeBased().everyHours(1).create();
  refresh();
}

function refresh() {
  const book = SpreadsheetApp.getActive();
  writeTab_(book, 'Leads', fetchCsv_('leads.csv'), 'lead_id', 'status');
  const runs = fetchCsv_('runs.csv');
  writeTab_(book, 'Run log', [runs[0]].concat(runs.slice(1).reverse()));
  const meta = tab_(book, 'About');
  meta.getRange('A1:B3').setValues([
    ['Sheet last refreshed (UTC)', new Date().toISOString()],
    ['Source', 'github.com/dannygrowthmarketing/ticmint-internet-listener'],
    ['Refresh', 'Apps Script hourly trigger pulling the agent\'s committed output'],
  ]);
}

function fetchCsv_(name) {
  const res = UrlFetchApp.fetch(REPO_RAW + name + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error(name + ' -> HTTP ' + res.getResponseCode());
  return Utilities.parseCsv(res.getContentText());
}

function tab_(book, name) {
  return book.getSheetByName(name) || book.insertSheet(name);
}

function writeTab_(book, name, rows, keyCol, keepCol) {
  const sh = tab_(book, name);
  if (keyCol && sh.getLastRow() > 1) {
    const cur = sh.getDataRange().getValues();
    const k = cur[0].indexOf(keyCol), s = cur[0].indexOf(keepCol);
    const nk = rows[0].indexOf(keyCol), ns = rows[0].indexOf(keepCol);
    if (k >= 0 && s >= 0 && nk >= 0 && ns >= 0) {
      const typed = {};
      cur.slice(1).forEach(r => { if (r[s]) typed[r[k]] = r[s]; });
      rows.slice(1).forEach(r => { if (typed[r[nk]]) r[ns] = typed[r[nk]]; });
    }
  }
  sh.clearContents();
  const width = Math.max.apply(null, rows.map(r => r.length));
  const grid = rows.map(r => r.concat(Array(width - r.length).fill('')));
  sh.getRange(1, 1, grid.length, width).setValues(grid);
  sh.setFrozenRows(1);
}
