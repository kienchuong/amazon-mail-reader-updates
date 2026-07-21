// Deploy this as a Google Apps Script Web App attached to your Google Sheet.
// Access: "Anyone with the link" is acceptable only if SECRET is strong and private.
const SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_SECRET';
const SHEET_NAME = 'Payments';

function doPost(e) {
  const payload = JSON.parse(e.postData.contents || '{}');
  if (payload.secret !== SECRET) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'Unauthorized' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);

  const columns = [
    'mail_date',
    'account_name',
    'account_email',
    'currency',
    'amount',
    'payment_id',
    'from_addr',
    'subject',
    'trusted_sender',
  ];

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(columns);
  }

  const existing = new Set();
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    const values = sheet.getRange(2, 1, lastRow - 1, columns.length).getValues();
    values.forEach(row => existing.add([row[0], row[2], row[4], row[7]].join('|')));
  }

  let appended = 0;
  (payload.rows || []).forEach(row => {
    const key = [row.mail_date, row.account_email, row.amount, row.subject].join('|');
    if (existing.has(key)) return;
    sheet.appendRow(columns.map(col => row[col] ?? ''));
    existing.add(key);
    appended += 1;
  });

  return ContentService.createTextOutput(JSON.stringify({ ok: true, appended }))
    .setMimeType(ContentService.MimeType.JSON);
}
