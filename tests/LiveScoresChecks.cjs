// Run: node tests/LiveScoresChecks.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
let now = Date.parse('2026-10-29T18:00:00Z');
class ClockDate extends Date {
  constructor(...args) { super(...(args.length ? args : [now])); }
  static now() { return now; }
}
let writes = 0, reads = 0, fetchCount = 0, statusCode = 200, locked = false;
class Range {
  constructor(sheet, row, col, rows = 1, cols = 1) { Object.assign(this, {sheet, row, col, rows, cols}); }
  getValues() { reads++; return Array.from({length: this.rows}, (_, r) => Array.from({length: this.cols}, (_, c) => {
    const row = this.sheet.values[this.row + r - 1], value = row?.[this.col + c - 1] ?? '';
    if (typeof value === 'string' && value.includes('ABS(I')) return row[8] === '' || row[9] === '' ? '' : Math.abs(row[8] - row[9]);
    return value;
  })); }
  getValue() { return this.getValues()[0][0]; }
  getDisplayValues() { return this.getValues().map(row => row.map(String)); }
  setValue(value) { writes++; this.sheet.values[this.row - 1][this.col - 1] = value; }
}
class Sheet {
  constructor(name, values) { Object.assign(this, {name, values}); }
  getName() { return this.name; }
  getDataRange() { return new Range(this, 1, 1, this.values.length, this.values[0].length); }
  getRange(...args) { return new Range(this, ...args); }
}
const sheets = new Map(), properties = new Map(), triggers = [];
const book = {getId: () => 'test-book', getSheetByName: name => sheets.get(name),
  getSpreadsheetTimeZone: () => 'America/New_York', toast() {}};
const payload = {header: {id: '401234567', timeValid: true, competitions: [{
  date: '2026-12-12T17:00:00Z', status: {type: {state: 'in', completed: false, name: 'STATUS_IN_PROGRESS'}},
  competitors: [{homeAway: 'away', score: '7', team: {location: 'Away'}},
    {homeAway: 'home', score: '14', team: {location: 'Home'}}],
  broadcasts: [{media: {shortName: 'ABC'}}]}]}, gameInfo: {venue: {fullName: 'Live venue'}}};
const context = vm.createContext({Date: ClockDate, console,
  SpreadsheetApp: {getActiveSpreadsheet: () => book, flush() {}},
  PropertiesService: {getScriptProperties: () => ({getProperty: key => properties.get(key),
    setProperty: (key, value) => properties.set(key, value)})},
  LockService: {getScriptLock: () => ({tryLock: () => !locked, releaseLock() {}})},
  ScriptApp: {getProjectTriggers: () => [...triggers], deleteTrigger: trigger => triggers.splice(triggers.indexOf(trigger), 1),
    newTrigger(handler) { const trigger = {handler, getHandlerFunction: () => handler}; const builder = {
      timeBased: () => builder, at: date => { trigger.at = date; return builder; },
      everyMinutes: minutes => { trigger.minutes = minutes; return builder; }, create: () => triggers.push(trigger)}; return builder; }},
  Utilities: {formatDate(date, zone, pattern) { return new Intl.DateTimeFormat(pattern === 'yyyy-MM-dd' ? 'en-CA' : 'en-US',
    {timeZone: zone, ...(pattern === 'yyyy-MM-dd' ? {year: 'numeric', month: '2-digit', day: '2-digit'} : {hour: 'numeric', minute: '2-digit', hour12: true})}).format(date); }},
  UrlFetchApp: {fetch(url) {
    fetchCount++;
    const response = structuredClone(payload);
    if (url.endsWith('401999999')) {
      response.header.id = '401999999';
      response.header.timeValid = true;
      response.header.competitions[0].date = '2027-01-01T17:00:00Z';
      response.header.competitions[0].status.type = {state: 'pre', completed: false, name: 'STATUS_SCHEDULED'};
      response.header.competitions[0].competitors.forEach(team => { team.team.location = team.homeAway === 'home' ? 'Future home' : 'Future away'; });
    }
    return {getResponseCode: () => statusCode, getContentText: () => JSON.stringify(response)};
  }}
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../sheets/LiveScores.gs'), 'utf8'), context);
const invoke = (name, ...args) => context[name](...args);
const headers = [...vm.runInContext('MBCC.headers', context)];
const row = data => headers.map(key => data[key] ?? '');
const live = new Sheet('live_scores_and_games', [headers,
  row({game_id: '401234567', game_name: 'Bowl', game_date: '2026-12-12', game_time: '12:00 PM',
    game_home_team: 'TBD', game_away_team: 'TBD', status: 'scheduled', winner: 'TBD', verified: false,
    upset_indicator: '=UPSET_FORMULA()', unanimous_indicator: '=UNANIMOUS_FORMULA()', team_focus_indicator: '=FOCUS_FORMULA()',
    point_difference: '=IF(OR(I2="",J2=""),"",ABS(I2-J2))'}),
  row({game_id: '401999999', game_name: 'Future game', game_date: '2027-01-01', status: 'scheduled', verified: false})]);
const source = new Sheet('unlive_games', [['game_name', 'game_id', 'game_date', 'game_time', 'game_home_team', 'game_away_team'],
  ['Bowl', '401234567', '2026-12-12', '12:00 PM', 'Home', 'Away']]);
const human = new Sheet('scores', [['game', 'home_team_score', 'away_team_score', 'upset_indicator', 'untouched_formula', 'point_difference'],
  ['Bowl', 14, 7, 1, '=SUM(1,2)', 7]]);
sheets.set(live.name, live); sheets.set(source.name, source); sheets.set(human.name, human);
const originals = JSON.stringify([source.values, human.values]);
const value = key => live.values[1][headers.indexOf(key)];
invoke('startMBCCLiveUpdates');
assert.equal(triggers.length, 1);
assert.equal(triggers[0].handler, 'beginMBCCScoreChecks');
assert.equal(triggers[0].at.toISOString(), '2026-12-05T05:00:00.000Z');
invoke('startMBCCLiveUpdates');
assert.equal(triggers.length, 1);
reads = 0;
invoke('refreshMBCCLiveScores'); invoke('beginMBCCScoreChecks');
assert.equal(reads, 0); assert.equal(writes, 0); assert.equal(fetchCount, 0);

now = Date.parse('2026-12-05T04:59:59.999Z');
invoke('refreshMBCCLiveScores'); invoke('beginMBCCScoreChecks');
assert.equal(reads, 0); assert.equal(writes, 0); assert.equal(fetchCount, 0);
now += 1; // December 5, midnight Eastern.
payload.header.timeValid = false;
payload.header.competitions[0].status.type = {state: 'pre', completed: false, name: 'STATUS_SCHEDULED'};
payload.header.competitions[0].competitors.forEach(team => { team.team.location = 'TBD'; });
invoke('beginMBCCScoreChecks');
assert.equal(triggers[0].minutes, 5);
assert.equal(fetchCount, 2); // Both uploaded games are eligible for pregame schedule discovery.
assert.equal(value('game_time'), 'TBD');
assert.equal(value('home_team_score'), ''); // Pregame responses cannot create a fake score.
assert.equal(value('away_team_score'), '');
assert.equal(value('verified'), false);
assert.equal(value('game_verified'), false);
now += 7200000 - 1;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, 2);
now += 1;
payload.header.timeValid = true;
payload.header.competitions[0].competitors.forEach(team => { team.team.location = team.homeAway === 'home' ? 'Home' : 'Away'; });
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, 3); // Retry the unresolved game at two hours; settled future game is skipped.
assert.equal(value('game_time'), '12:00 PM');
assert.equal(value('game_verified'), true);
assert.equal(value('verified'), false);
now += 3 * 86400000;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, 3); // All schedules are set; no more pregame ESPN requests.
assert.equal(value('game_verified'), true); // A settled upcoming schedule does not expire.
assert.equal(value('verified'), false);

now = Date.parse('2026-12-12T18:00:00Z');
fetchCount = 0;
payload.header.competitions[0].status.type = {state: 'in', completed: false, name: 'STATUS_IN_PROGRESS'};
invoke('beginMBCCScoreChecks');
assert.equal(triggers.length, 1);
assert.equal(triggers[0].handler, 'refreshMBCCLiveScores');
assert.equal(triggers[0].minutes, 5);
assert.equal(fetchCount, 1); // Settled upcoming game stays skipped; game-day polling begins.
assert.equal(value('game_home_team'), 'Home'); // TBD slots resolve by event ID and side.
assert.equal(value('game_away_team'), 'Away');
assert.equal(value('home_team_score'), 14);
assert.equal(value('verified'), true);
assert.equal(value('game_verified'), true);
// Full-column checkboxes and formulas below the schedule do not create games.
const rowsBeforeBlank = live.values.length;
live.values.push(row({verified: false, game_verified: false, point_difference: 0,
  upset_indicator: 0, unanimous_indicator: 0, team_focus_indicator: 0, winner: 'TBD', status: 'scheduled'}));
const fetchesBeforeBlank = fetchCount, blankBefore = JSON.stringify(live.values.at(-1));
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, fetchesBeforeBlank);
assert.equal(JSON.stringify(live.values.at(-1)), blankBefore);
live.values.length = rowsBeforeBlank;
assert.equal(value('point_difference'), '=IF(OR(I2="",J2=""),"",ABS(I2-J2))');
assert.equal(value('upset_indicator'), '=UPSET_FORMULA()');
assert.equal(value('unanimous_indicator'), '=UNANIMOUS_FORMULA()');
assert.equal(value('team_focus_indicator'), '=FOCUS_FORMULA()');
assert.equal(live.values.length, 3); // Uploaded rows/order are preserved.
assert.equal(live.values[2][headers.indexOf('game_id')], '401999999');
human.values[1][1] = 0;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, 1);
assert.equal(value('verified'), false);
assert.equal(value('verification'), 'Score mismatch');
assert.equal(value('game_verified'), true);
human.values[1][1] = 14;
human.values[1][5] = 8; // The formula result participates in the same score checkbox.
invoke('refreshMBCCLiveScores');
assert.equal(value('verified'), false);
assert.equal(value('game_verified'), true);
human.values[1][5] = 7;
source.values[1][3] = '1:00 PM';
invoke('refreshMBCCLiveScores');
assert.equal(value('verified'), true);
assert.equal(value('game_verified'), false);
source.values[1][3] = '12:00 PM';
now += 299999;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, 1); // Manual invocation cannot poll before five minutes.
now += 1;
statusCode = 403;
const lastGood = value('last_fetched_at');
invoke('refreshMBCCLiveScores');
assert.equal(value('home_team_score'), 14);
assert.equal(value('last_fetched_at'), lastGood);
assert.match(value('fetch_error'), /401234567: HTTP 403/);
assert.equal(value('verified'), false);
assert.equal(value('verification'), 'Unable to verify');
assert.equal(value('upset_indicator'), '=UPSET_FORMULA()');
assert.equal(value('unanimous_indicator'), '=UNANIMOUS_FORMULA()');
assert.equal(value('team_focus_indicator'), '=FOCUS_FORMULA()');
assert.equal(JSON.stringify([source.values, human.values]), originals);

// Finals stop only after both verification groups match, and do not age out.
statusCode = 200;
payload.header.competitions[0].status.type = {state: 'post', completed: true, name: 'STATUS_FINAL'};
now += 300000;
invoke('refreshMBCCLiveScores');
assert.equal(value('status'), 'final');
assert.equal(value('verified'), true);
assert.equal(value('game_verified'), true);
const confirmedFetches = fetchCount, confirmedAt = value('last_fetched_at');
now += 3 * 86400000;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, confirmedFetches);
assert.equal(value('last_fetched_at'), confirmedAt);
assert.equal(value('verified'), true);
assert.equal(value('game_verified'), true);
human.values[1][5] = 8;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, confirmedFetches + 1); // Reference edits reopen a final.
assert.equal(value('verified'), false);
assert.equal(value('game_verified'), true);
human.values[1][5] = 7;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, confirmedFetches + 1);
assert.equal(value('verified'), true);
source.values[1][3] = '1:00 PM';
now += 300000;
invoke('refreshMBCCLiveScores');
assert.equal(fetchCount, confirmedFetches + 2);
assert.equal(value('game_verified'), false);
source.values[1][3] = '12:00 PM';
invoke('refreshMBCCLiveScores');
assert.equal(value('game_verified'), true);
assert.equal(JSON.stringify([source.values, human.values]), originals);
locked = true;
const before = writes;
invoke('refreshMBCCLiveScores');
assert.equal(writes, before);
invoke('stopMBCCLiveUpdates');
assert.equal(triggers.length, 0);
assert.equal(context.setupMBCCLiveScores, undefined);
assert.equal(context.useMBCC2026BowlSchedule, undefined);
assert.equal(context.mbccDiscoverBowls, undefined);

const zeros = {status: 'live', source: 'ESPN', last_fetched_at: new ClockDate().toISOString(), home_team_score: 0, away_team_score: 0, point_difference: 0};
assert.equal(invoke('mbccVerify', zeros, zeros, new ClockDate())[0], 'Verified');
assert.equal(invoke('mbccVerify', zeros, {home_team_score: '', away_team_score: 0}, new ClockDate())[0], 'Not verified');
assert.equal(invoke('mbccVerify', {...zeros, last_fetched_at: new ClockDate(now - 11 * 60000).toISOString()}, zeros, new ClockDate())[0], 'Unable to verify');
assert.equal(invoke('mbccVerify', {...zeros, last_fetched_at: new ClockDate(now - 6 * 60000).toISOString()}, zeros, new ClockDate())[0], 'Verified');
const dueAt = new ClockDate('2026-12-13T05:01:00Z'), zone = 'America/New_York';
assert.equal(invoke('mbccDue', {game_date: '2026-12-12', status: 'live'}, dueAt, zone), true); // Past midnight.
assert.equal(invoke('mbccDue', {game_date: '2026-12-12', status: 'scheduled'}, dueAt, zone), false);
assert.equal(invoke('mbccDue', {game_date: '2026-12-14', status: 'scheduled'}, dueAt, zone), true);
assert.equal(invoke('mbccDue', {game_date: '2026-12-12', status: 'final', verified: true, game_verified: false}, dueAt, zone), true);
assert.equal(invoke('mbccDue', {game_date: '2026-12-12', status: 'final', verified: true, game_verified: true}, dueAt, zone), false);
assert.equal(invoke('mbccDue', {game_date: '2026-12-12', status: 'final', verified: 'FALSE', game_verified: 'TRUE'}, dueAt, zone), true);
assert.throws(() => invoke('mbccParseESPN', payload, {game_id: '9'}), /another game/);
const tied = structuredClone(payload);
tied.header.competitions[0].status.type = {state: 'post', completed: true, name: 'STATUS_FINAL'};
tied.header.competitions[0].competitors[1].score = '7';
assert.throws(() => invoke('mbccParseESPN', tied, {game_id: '401234567'}), /cannot be tied/);
console.log('Score updater checks passed: December 5 activation, two-hour schedule checks until set, five-minute game-day polling, confirmed finals stop, formula preservation and delayed activation.');
