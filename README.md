# Amazon Mail Reader 0.5.0

á»¨ng dá»¥ng Windows chá»‰ Ä‘á»c Ä‘á»ƒ xem táº­p trung mail Amazon, cáº£nh bÃ¡o báº£o máº­t vÃ  thá»‘ng kÃª payment.

## An toÃ n

- Outlook/Hotmail Ä‘Äƒng nháº­p trÃªn trang chÃ­nh thá»©c cá»§a Microsoft báº±ng OAuth 2.0 + PKCE.
- Chá»‰ xin quyá»n Microsoft Graph `Mail.Read` vÃ  `User.Read`.
- App chá»‰ gá»i cÃ¡c API `GET`; khÃ´ng gá»­i, xÃ³a, di chuyá»ƒn, sá»­a hoáº·c Ä‘Ã¡nh dáº¥u mail Ä‘Ã£ Ä‘á»c.
- IMAP dÃ¹ng `SELECT readonly=True` vÃ  `BODY.PEEK`.
- Token Microsoft, App Password vÃ  Google Sheet Secret Ä‘Æ°á»£c mÃ£ hÃ³a báº±ng máº­t kháº©u chÃ­nh.
- Máº­t kháº©u email Microsoft khÃ´ng Ä‘i qua á»©ng dá»¥ng.

## Láº§n cháº¡y Ä‘áº§u

1. Má»Ÿ `run_app.bat`.
2. Chá»n thÆ° má»¥c dá»¯ liá»‡u á»Ÿ á»• khÃ¡c á»• C, vÃ­ dá»¥ `D:\AmazonMailReaderData`.
3. Táº¡o máº­t kháº©u chÃ­nh Ã­t nháº¥t 8 kÃ½ tá»± vÃ  nhá»› ká»¹ máº­t kháº©u nÃ y.
4. Náº¿u cÃ i láº¡i Windows, má»Ÿ app, chá»n láº¡i Ä‘Ãºng thÆ° má»¥c dá»¯ liá»‡u cÅ© vÃ  nháº­p máº­t kháº©u chÃ­nh.

KhÃ´ng cÃ³ cÃ¡ch khÃ´i phá»¥c náº¿u quÃªn máº­t kháº©u chÃ­nh. HÃ£y sao lÆ°u toÃ n bá»™ thÆ° má»¥c dá»¯ liá»‡u sang nÆ¡i an toÃ n.

## ÄÄƒng nháº­p Outlook/Hotmail

1. LÃ m má»™t láº§n theo file `HUONG_DAN_MICROSOFT.md` Ä‘á»ƒ láº¥y Microsoft Client ID.
2. Má»Ÿ má»¥c `CÃ i Ä‘áº·t`, nháº­p Client ID rá»“i báº¥m `LÆ°u cáº¥u hÃ¬nh`.
3. Má»Ÿ má»¥c `Accounts`, chá»n `Outlook` vÃ  báº¥m `ÄÄƒng nháº­p Microsoft`.
4. TrÃ¬nh duyá»‡t má»Ÿ trang Microsoft. Chá»n account vÃ  Ä‘á»“ng Ã½ quyá»n Ä‘á»c mail.
5. Láº·p láº¡i bÆ°á»›c 3-4 cho tá»«ng Outlook/Hotmail.

Token Ä‘Æ°á»£c lÆ°u trong kho mÃ£ hÃ³a vÃ  tá»± lÃ m má»›i. ThÃ´ng thÆ°á»ng khÃ´ng pháº£i Ä‘Äƒng nháº­p láº¡i sau khi Ä‘Ã³ng app, cáº­p nháº­t app hoáº·c sang thÃ¡ng má»›i. Microsoft cÃ³ thá»ƒ yÃªu cáº§u Ä‘Äƒng nháº­p láº¡i náº¿u quyá»n bá»‹ thu há»“i hoáº·c thay Ä‘á»•i báº£o máº­t account.

## Gmail, Yahoo vÃ  email tÃªn miá»n

PhiÃªn báº£n nÃ y chÆ°a cÃ³ OAuth cho Gmail/Yahoo. CÃ¡c loáº¡i nÃ y váº«n dÃ¹ng IMAP + App Password. Outlook khÃ´ng cÃ²n dÃ¹ng password IMAP.

## Äá»c vÃ  thá»‘ng kÃª

- Má»¥c `Inbox`: quÃ©t, tÃ¬m kiáº¿m vÃ  lá»c Payment, Reject, Amazon Account, Security.
- Ná»™i dung Ä‘áº§y Ä‘á»§ chá»‰ Ä‘Æ°á»£c táº£i khi cáº§n vÃ  khÃ´ng lÆ°u lÃ¢u dÃ i trong database.
- Má»¥c `Payment`: tá»•ng há»£p riÃªng theo tá»«ng loáº¡i tiá»n, xuáº¥t CSV hoáº·c Google Sheet.
- Google Sheet tá»± Ä‘á»“ng bá»™ sau khi quÃ©t khi tÃ¹y chá»n `Tá»± Ä‘á»“ng bá»™ sau khi quÃ©t` Ä‘Æ°á»£c báº­t.
- Google Sheet dÃ¹ng Apps Script trong file `google_sheets_webhook.gs`.
- Mobile Dashboard dÃ¹ng Supabase, Ä‘á»“ng bá»™ snapshot sau khi quÃ©t vÃ  khÃ´ng Ä‘Äƒng nháº­p email trÃªn Ä‘iá»‡n thoáº¡i. Xem `HUONG_DAN_SUPABASE.md`.

## Dá»¯ liá»‡u vÃ  cáº­p nháº­t

ChÆ°Æ¡ng trÃ¬nh vÃ  dá»¯ liá»‡u náº±m riÃªng. Database, token, cáº¥u hÃ¬nh vÃ  lá»‹ch sá»­ quÃ©t Ä‘á»u náº±m trong thÆ° má»¥c dá»¯ liá»‡u Ä‘Ã£ chá»n. Windows chá»‰ giá»¯ má»™t tá»‡p nhá» khÃ´ng nháº¡y cáº£m Ä‘á»ƒ nhá»› Ä‘Æ°á»ng dáº«n.

Má»¥c `CÃ i Ä‘áº·t` dÃ¹ng sáºµn kho `kienchuong/amazon-mail-reader-updates`. Má»—i release cáº§n cÃ³:

- gÃ³i ZIP, Æ°u tiÃªn tÃªn káº¿t thÃºc báº±ng `win64.zip`;
- file `<tÃªn-gÃ³i>.sha256` hoáº·c `SHA256SUMS.txt`;
- file `run_app.bat` á»Ÿ cáº¥p gá»‘c cá»§a ZIP.

App kiá»ƒm tra SHA-256 trÆ°á»›c khi cÃ i, giá»¯ báº£n chÆ°Æ¡ng trÃ¬nh cÅ© á»Ÿ thÆ° má»¥c `.backup` vÃ  tá»± phá»¥c há»“i náº¿u giáº£i nÃ©n lá»—i.

## Cháº¡y tá»« mÃ£ nguá»“n

YÃªu cáº§u Python 3.12 trÃªn Windows cÃ³ Tkinter vÃ  thÆ° viá»‡n trong `requirements.txt`. File `run_app.bat` Æ°u tiÃªn Python Ä‘i kÃ¨m Codex, sau Ä‘Ã³ tá»± tÃ¬m Python Ä‘Ã£ cÃ i trÃªn Windows. Náº¿u thiáº¿u CustomTkinter hoáº·c tksheet, file nÃ y tá»± cÃ i thÆ° viá»‡n trÆ°á»›c khi má»Ÿ app.

## Cáº¥u trÃºc chÃ­nh

- `app.py`: khá»Ÿi Ä‘á»™ng á»©ng dá»¥ng.
- `amzmail/ui.py`: khung cá»­a sá»•, Ä‘iá»u hÆ°á»›ng vÃ  cÃ¡c thao tÃ¡c chung.
- `amzmail/views/`: giao diá»‡n riÃªng cho Inbox, Payment, Accounts vÃ  CÃ i Ä‘áº·t.
- `amzmail/google_sheets.py`: xuáº¥t CSV vÃ  Ä‘á»“ng bá»™ Google Sheet.
- `amzmail/microsoft_graph.py`: Ä‘Äƒng nháº­p OAuth vÃ  Ä‘á»c Outlook.
- `amzmail/imap_reader.py`: Ä‘á»c Gmail, Yahoo vÃ  email tÃªn miá»n qua IMAP.
