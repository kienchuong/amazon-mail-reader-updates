
// Deploy this as a Google Apps Script Web App attached to your Google Sheet.
// Access: "Anyone with the link" is acceptable only if SECRET is strong and private.
const SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_SECRET';
const SHEET_NAME = 'Payments';
const COLUMNS = ['Ngày', 'Account name', 'Currency', 'Amount', 'Payment ID'];

function displayDate(value) {
  if (value instanceof Date && !isNaN(value)) {
    return Utilities.formatDate(value, Session.getScriptTimeZone(), 'dd/MM');
  }
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[3]}/${match[2]}` : String(value || '');
}

function paymentKey(row) {
  return [displayDate(row[0]), row[1], row[2], row[3], row[4]].join('|');
}

function prepareSheet(sheet) {
  const lastRow = sheet.getLastRow();
  const oldHeader = lastRow > 0 ? sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0] : [];
  const isLegacy = oldHeader[0] === 'mail_date' && oldHeader[2] === 'account_email';

  if (isLegacy && lastRow > 1) {
    const legacy = sheet.getRange(2, 1, lastRow - 1, Math.max(sheet.getLastColumn(), 6)).getValues();
    const migrated = legacy.map(row => [displayDate(row[0]), row[1], row[3], row[4], row[5]]);
    sheet.getRange(2, 1, migrated.length, COLUMNS.length).setValues(migrated);
  }

  sheet.getRange(1, 1, 1, COLUMNS.length).setValues([COLUMNS]);
  sheet.getRange(2, 1, Math.max(lastRow - 1, 1), 1).setNumberFormat('@');
  if (sheet.getMaxColumns() > COLUMNS.length) {
    sheet.hideColumns(COLUMNS.length + 1, sheet.getMaxColumns() - COLUMNS.length);
  }
}

function doPost(e) {
  const payload = JSON.parse(e.postData.contents || '{}');
  if (payload.secret !== SECRET) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'Unauthorized' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);

  prepareSheet(sheet);

  const existing = new Set();
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    const values = sheet.getRange(2, 1, lastRow - 1, COLUMNS.length).getValues();
    values.forEach(row => existing.add(paymentKey(row)));
  }

  let appended = 0;
  (payload.rows || []).forEach(row => {
    const values = [
      displayDate(row.mail_date),
      row.account_name || '',
      row.currency || '',
      row.amount ?? '',
      row.payment_id || '',
    ];
    const key = paymentKey(values);
    if (existing.has(key)) return;
    sheet.appendRow(values);
    existing.add(key);
    appended += 1;
  });

  const paymentRows = sheet.getLastRow() - 1;
  if (paymentRows > 1) {
    sheet.getRange(2, 1, paymentRows, COLUMNS.length).sort({ column: 2, ascending: true });
  }

  return ContentService.createTextOutput(JSON.stringify({ ok: true, appended }))
    .setMimeType(ContentService.MimeType.JSON);
}

