/**
 * Job Scout helper for the Applications spreadsheet (version 2).
 *
 * 1. Jobs tab: when you set Status to "Applied", the job is added to the
 *    Applications tab (once).
 * 2. Applications tab: when you type a Rejection Date, the status becomes
 *    "Rejected". When you set the status to Interview or Offer, "Interview
 *    Reached" becomes "Yes" and stays, even after a later rejection.
 * 3. A short email every weekday morning with the new jobs of the day.
 * 4. Backup start: GitHub's own timer has not been starting the morning runs,
 *    so at about 06:00 on weekdays this script starts the runs listed in
 *    MORNING_WORKFLOWS unless they already started today. It needs a GitHub token
 *    saved as the script property GITHUB_TOKEN (see the setup notes in the repo).
 * 5. Applications tab keeps the newest application at the top (row 2).
 *    The "Job Scout" menu has "New application at the top" for jobs you
 *    applied to outside Job Scout, and "Sort newest first".
 *
 * Setup (once): Extensions > Apps Script, paste this file over the old one,
 * save, then run `setup` from the toolbar and accept the permission prompt.
 * Columns are found by their header names, so they can be moved freely.
 */
var JOBS = 'Jobs', APPLICATIONS = 'Applications';

function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  var book = SpreadsheetApp.getActive();
  ScriptApp.newTrigger('onJobsEdit').forSpreadsheet(book).onEdit().create();
  ScriptApp.newTrigger('sendDailyEmail').timeBased().everyDays(1).atHour(8).create();
  ScriptApp.newTrigger('startMorningRuns').timeBased().everyDays(1).atHour(6).create();
  SpreadsheetApp.getUi().alert('Job Scout helper is on.\n\n' +
      '- Marking a job "Applied" in Jobs adds it to Applications.\n' +
      '- A Rejection Date in Applications sets the status to Rejected.\n' +
      '- You get an email at about 08:00 on weekdays.\n' +
      '- The morning runs are started at about 06:00 on weekdays' +
      (PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN') ? '.\n' : ' (once a GitHub token is saved).\n') +
      '- Applications shows the newest first. Use the Job Scout menu to add one by hand.');
  sortNewestFirst_(book.getSheetByName(APPLICATIONS));
}

/** Runs by itself when the spreadsheet opens. */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Job Scout')
      .addItem('New application at the top', 'newApplication')
      .addItem('Sort newest first', 'sortApplications')
      .addToUi();
}

function sortApplications() {
  sortNewestFirst_(SpreadsheetApp.getActive().getSheetByName(APPLICATIONS));
}

/** Adds an empty application with the next ID and today's date in row 2. */
function newApplication() {
  var book = SpreadsheetApp.getActive(), apps = book.getSheetByName(APPLICATIONS);
  var col = headers_(apps), width = apps.getLastColumn(), row = [];
  for (var c = 0; c < width; c++) row.push('');
  var set = function (name, value) { if (col[name] !== undefined) row[col[name]] = value; };
  set('application id', nextId_(apps, col));
  set('application date', Utilities.formatDate(new Date(), 'Europe/Athens', 'dd/MM/yyyy'));
  set('application status', 'Applied');
  apps.getRange(apps.getLastRow() + 1, 1, 1, width).setValues([row]);
  sortNewestFirst_(apps);
  apps.activate();
  apps.getRange(2, (col['company name'] === undefined ? 0 : col['company name']) + 1).activate();
}

/** Newest application (highest ID) first. Formulas in each row move with it. */
function sortNewestFirst_(apps) {
  if (!apps) return;
  var last = apps.getLastRow(), width = apps.getLastColumn(), col = headers_(apps);
  if (last < 3 || col['application id'] === undefined) return;
  apps.getRange(2, 1, last - 1, width).sort({column: col['application id'] + 1, ascending: false});
  apps.getBandings().forEach(function (band) {  // keep the striped rows covering new rows
    var r = band.getRange();
    if (r.getLastRow() < last) band.setRange(apps.getRange(r.getRow(), r.getColumn(), last - r.getRow() + 1, r.getNumColumns()));
  });
}

function nextId_(apps, col) {
  var last = apps.getLastRow(), next = 1;
  if (last > 1 && col['application id'] !== undefined) {
    apps.getRange(2, col['application id'] + 1, last - 1, 1).getValues().forEach(function (r) {
      var n = parseInt(String(r[0]).replace(/\D/g, ''), 10);
      if (n >= next) next = n + 1;
    });
  }
  return 'APP-' + ('00000' + next).slice(-5);
}

/** Header name (lower case) -> 0-based column index. */
function headers_(sheet) {
  var map = {};
  sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].forEach(function (h, i) {
    var name = String(h).trim().toLowerCase();
    if (name && !(name in map)) map[name] = i;
  });
  return map;
}

function touches_(range, index) {
  return index !== undefined && range.getColumn() <= index + 1 && range.getLastColumn() >= index + 1;
}

// Kept under this name so the trigger made by an earlier setup still works.
function onJobsEdit(e) {
  var range = e.range, sheet = range.getSheet(), name = sheet.getName();
  if (name === JOBS) jobsEdited_(sheet, range);
  if (name === APPLICATIONS) applicationsEdited_(sheet, range);
}

function jobsEdited_(sheet, range) {
  var col = headers_(sheet);
  if (!touches_(range, col['status'])) return;
  var width = sheet.getLastColumn();
  for (var row = Math.max(2, range.getRow()); row <= range.getLastRow(); row++) {
    var values = sheet.getRange(row, 1, 1, width).getValues()[0];
    if (String(values[col['status']]).trim() !== 'Applied') continue;
    var job = {};
    Object.keys(col).forEach(function (key) { job[key] = values[col[key]]; });
    addApplication_(job);
  }
}

function applicationsEdited_(sheet, range) {
  var col = headers_(sheet);
  var rejected = col['rejection date'], status = col['application status'], reached = col['interview reached'];
  if (status === undefined) return;
  var first = Math.max(2, range.getRow()), count = range.getLastRow() - first + 1;
  if (count < 1) return;
  var statusRange = sheet.getRange(first, status + 1, count, 1), statuses = statusRange.getValues();
  if (touches_(range, rejected)) {
    var dates = sheet.getRange(first, rejected + 1, count, 1).getValues(), changed = false;
    for (var i = 0; i < count; i++) {
      if (String(dates[i][0]).trim() !== '' && statuses[i][0] !== 'Rejected') {
        if (reached !== undefined && /^(interview|offer)$/i.test(String(statuses[i][0]).trim())) {
          sheet.getRange(first + i, reached + 1).setValue('Yes');
        }
        statuses[i][0] = 'Rejected';
        changed = true;
      }
    }
    if (changed) statusRange.setValues(statuses);
  }
  if (touches_(range, status) && reached !== undefined) {
    for (var k = 0; k < count; k++) {
      if (/^(interview|offer)$/i.test(String(statuses[k][0]).trim())) {
        sheet.getRange(first + k, reached + 1).setValue('Yes');
      }
    }
  }
}

function addApplication_(job) {
  var apps = SpreadsheetApp.getActive().getSheetByName(APPLICATIONS);
  var col = headers_(apps), width = apps.getLastColumn();
  var link = String(job['link'] || '');
  var last = apps.getLastRow();
  if (last > 1 && col['job url'] !== undefined && link) {  // never add the same job twice
    var links = apps.getRange(2, col['job url'] + 1, last - 1, 1).getValues();
    for (var i = 0; i < links.length; i++) if (String(links[i][0]) === link) return;
  }
  var type = String(job['type'] || ''), work = String(job['work'] || '');
  var remote = work === 'Remote' || type.indexOf('Remote') === 0;
  var place = String(job['location'] || '');
  var values = {
    'application id': nextId_(apps, col),
    'company name': job['company'],
    'job title': job['title'],
    'location': place,
    'country': place.split(',').pop().trim(),
    'work type': work || (remote ? 'Remote' : 'On-site / Hybrid'),
    'remote from greece': type === 'Remote GR' ? 'Yes' : (remote ? 'Check' : 'No'),
    'salary': job['salary'] || '',
    'ai fit score': job['ai fit'] === undefined ? '' : job['ai fit'],
    'job url': link,
    'application date': Utilities.formatDate(new Date(), 'Europe/Athens', 'dd/MM/yyyy'),
    'application status': 'Applied',
    'application source': 'Job Scout: ' + job['source'],
    'notes': 'Scout score ' + job['score'] + ' (' + job['label'] + ')'
  };
  var row = [];
  for (var c = 0; c < width; c++) row.push('');
  Object.keys(values).forEach(function (name) { if (col[name] !== undefined) row[col[name]] = values[name]; });
  apps.getRange(last + 1, 1, 1, width).setValues([row]);
  sortNewestFirst_(apps);
}

var REPO = 'YOUR_GITHUB_USER/job-scout';  // your copy of this repository
var MORNING_WORKFLOWS = ['scout.yml'];

/** Weekday backup start for the morning runs. Skips a workflow that already ran today. */
function startMorningRuns() {
  var day = parseInt(Utilities.formatDate(new Date(), 'Europe/Athens', 'u'), 10);
  if (day > 5) return;
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) return;
  var today = Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd');
  var api = 'https://api.github.com/repos/' + REPO + '/actions/workflows/';
  var headers = {Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json'};
  MORNING_WORKFLOWS.forEach(function (file) {
    var runs = JSON.parse(UrlFetchApp.fetch(api + file + '/runs?branch=main&created=' + today, {headers: headers}).getContentText());
    var started = (runs.workflow_runs || []).some(function (r) {
      return r.event === 'schedule' || r.event === 'workflow_dispatch';
    });
    if (started) return;
    UrlFetchApp.fetch(api + file + '/dispatches', {
      method: 'post', headers: headers, contentType: 'application/json',
      payload: JSON.stringify({ref: 'main'})
    });
  });
}

function sendDailyEmail() {
  var now = new Date();
  var day = parseInt(Utilities.formatDate(now, 'Europe/Athens', 'u'), 10);  // 1 = Monday
  if (day > 5) return;
  var book = SpreadsheetApp.getActive(), sheet = book.getSheetByName(JOBS);
  if (!sheet || sheet.getLastRow() < 2) return;
  var col = headers_(sheet);
  var today = Utilities.formatDate(now, 'Europe/Athens', 'yyyy-MM-dd');
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).getValues().filter(function (r) {
    var found = r[col['found']];
    if (found instanceof Date) found = Utilities.formatDate(found, 'Europe/Athens', 'yyyy-MM-dd');
    return String(found) === today;
  });
  if (!rows.length) return;  // no run today, or nothing new: no email
  var score = function (r) { return Number(r[col['score']]) || 0; };
  var strong = rows.filter(function (r) { return score(r) >= 70; }).length;
  var good = rows.filter(function (r) { return score(r) >= 50 && score(r) < 70; }).length;
  rows.sort(function (a, b) { return score(b) - score(a); });
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
  var list = rows.slice(0, 15).map(function (r) {
    var ai = col['ai fit'] !== undefined && r[col['ai fit']] !== '' ? ' · AI fit ' + r[col['ai fit']] : '';
    var pay = col['salary'] !== undefined && r[col['salary']] ? ' · ' + esc(r[col['salary']]) : '';
    return '<li><b>' + score(r) + '</b>' + ai + ' · <a href="' + r[col['link']] + '">' + esc(r[col['title']]) +
           '</a> · ' + esc(r[col['company']]) + ' · ' + esc(r[col['type']]) + pay + '</li>';
  }).join('');
  var url = book.getUrl() + '#gid=' + sheet.getSheetId();
  MailApp.sendEmail({
    to: Session.getEffectiveUser().getEmail(),
    subject: 'Job Scout: ' + rows.length + ' new jobs, ' + strong + ' rated 70+',
    htmlBody: '<p>' + rows.length + ' new jobs today: ' + strong + ' rated 70+, ' + good +
              ' rated 50 to 69.</p><ol>' + list + '</ol><p><a href="' + url + '">Open the Jobs tab</a></p>'
  });
}
