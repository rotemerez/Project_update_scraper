# Tel Aviv Building Permit Search — API Investigation Findings

**Site:** https://rishuybniya.tel-aviv.gov.il/resident-licensing/licensing-request-pages/request-search  
**Method:** Live browser instrumentation (XHR prototype interception, reCAPTCHA token capture, direct API calls)

---

## Session 1 — 2026-07-15 (Initial Discovery)

### API Hostname

```
https://apimtlvprd.tel-aviv.gov.il
```

Three base paths on this host:

| Path | Purpose | Auth |
|---|---|---|
| `/prd/RishuiBniyaWeb/publicApi` | Public permit search | reCAPTCHA Enterprise v3 |
| `/prd/RishuiBniyaWeb/api` | Authenticated operations | Azure B2C Bearer token |
| `/prd/RishuiBniyaWeb` | Base (url2) | — |

---

### Runtime Config Files

The app fetches two JSON files on startup to resolve the API hostname at runtime.

**`GET /assets/env.json`:**
```json
{ "env": "prod", "ver": 1 }
```

**`GET /assets/prod.json`:**
```json
{
  "url":       "https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/api",
  "url2":      "https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb",
  "urlPublic": "https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/publicApi",

  "Recaptcha": {
    "ProtectedRoutes": ["/ResidentLicensing", "Register/CheckIdentity"],
    "SiteKey": "6Lfl1nwrAAAAAJKMOLVFqNm0qIgbtqOqQlC2G97i",
    "SkipRecaptcha": false
  },

  "systemName": {
    "1": "/building-permit",
    "4": "/online-supervision"
  },

  "AuthSettings": {
    "conf": {
      "auth": {
        "clientId": "840568d3-d24a-4dbf-a803-4b5c08bef460",
        "authority": "https://b2ctam.b2clogin.com/b2ctam.onmicrosoft.com/B2C_1A_NATIVPRD_SIGNIN",
        "redirectUri": "https://rishuybniya.tel-aviv.gov.il/",
        "knownAuthorities": ["https://b2ctam.b2clogin.com"]
      },
      "cache": { "cacheLocation": "localStorage", "storeAuthStateInCookie": true }
    },
    "intercept": {
      "protectedResourceMap": {
        "https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/api": ["<Azure B2C scopes>"]
      }
    }
  }
}
```

---

### Search Endpoint (captured from Angular's own XHR)

```
POST https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/publicApi/ResidentLicensing/Request/getRequest
```

**Headers:**
```
Content-Type:       application/json
Accept:             application/json, text/plain, */*
X-Client-Assertion: <reCAPTCHA Enterprise v3 token>
```

No APIM subscription key. No `Authorization: Bearer`. No cookies.

**Request body schema (as sent by Angular):**
```json
{
  "submissionId": 0,
  "licenseId":    0,
  "streetCode":   0,
  "houseNumber":  null,
  "entrance":     "",
  "blockNumber":  6627,
  "parcelNumber": 1
}
```

Zero / null / `""` = not filtering on that field.

**Response envelope:**
```json
{
  "data":           { },
  "status":         1,
  "errorCode":      0,
  "execption":      "",
  "stackTrace":     "",
  "message":        "",
  "displayMessage": "",
  "handleError":    true,
  "handleSuccess":  false
}
```

`status: 1` = success, `status: 2` = error. Key is `"execption"` (sic).

**Result sub-array names** (inferred from Angular Material `mat-column-*` CSS classes — no live data returned due to backend outage, see below):

- `data.residentLicenseRequest` — building permit requests ("בקשות להיתר"), columns: `dataNumber`, `licenseNumber`, `address`, `requestType`, `requestStatus`, `link`
- `data.requestDataList` — information/online-submission requests ("בקשות מידע"), columns: `requestId`, `address`, `requestType`, `requestStatus`

---

### reCAPTCHA Requirement

**Enforced at the API gateway, not just client-side:**

| Condition | HTTP status | Body |
|---|---|---|
| No `X-Client-Assertion` header | `400` | `Missing assertion` |
| Invalid / fake token | `400` | `Invalid assertion` |
| Valid Enterprise v3 token | `200` | Backend response |

- **Type:** Google reCAPTCHA **Enterprise** v3
- **Site key:** `6Lfl1nwrAAAAAJKMOLVFqNm0qIgbtqOqQlC2G97i`
- **Header name:** `X-Client-Assertion`
- **Token acquisition:** `grecaptcha.enterprise.execute(siteKey, { action: "submit" })`
- Tokens are single-use, expire ~2 minutes — fresh token required per request
- `SkipRecaptcha: false` — no production bypass

---

### Street Code Lookup Endpoint

Required to populate `streetCode` for address-based searches. **No auth header needed.**

```
GET https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/publicApi/Address/SearchTlvStreets/{streetName}
```

Example response for "דיזנגוף":
```json
{
  "data": [
    { "id": 187, "caption": "דיזנגוף" },
    { "id": 408, "caption": "כיכר צינה דיזנגוף" }
  ],
  "status": 1,
  "errorCode": 0
}
```

---

### Detail Page / Endpoint

The `link` column in permit results leads to the `/building-permit` module. Navigating there triggers an Azure B2C MSAL redirect — full login required. Direct API call:

```
GET https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/api/ResidentLicensing/Request/{id}
→ 401 WWW-Authenticate: Bearer
```

Not accessible to unauthenticated scrapers.

---

### Session 1 Backend Status

All permit search calls returned HTTP 200 with inner `status: 2, errorCode: 500`. Stack trace pointed to the downstream "Nativ" municipal system failing inside `NativRequestPost`. Believed at the time to be a service outage.

---

## Session 2 — 2026-07-15 (Follow-up — Backend Confirmed Working)

### Root Cause of Session 1 "Outage"

**Not a true outage.** The Session 1 manual test calls all used `entrance: null` in the request body. The Nativ backend requires `entrance: ""` (empty string). Sending `null` consistently triggers the internal 500 error regardless of other parameters.

The Angular app itself always sends `entrance: ""`, which is why the one form-submitted XHR captured in Session 1 returned `status: 1` — it happened to use the correct value.

**Fix:** Always send `entrance: ""`, never `entrance: null`.

---

### Response Structure — Confirmed with Real Data

Tested with `streetCode: 187` (Dizengoff), `houseNumber: 50`, `entrance: ""`.

**`data.residentLicenseRequest`** — building permit records. Real sample:
```json
{
  "requestId":     83297,
  "dataNumber":    "25-00888",
  "submissionStr": "35870",
  "licenseNumber": "26-0052",
  "requestType":   "שינויים שינוי ללא תוספת שטח/חזית",
  "address":       "דיזנגוף 45, דיזנגוף 50, דיזנגוף 61, דיזנגוף 64, המלך ג'ורג' 57, המלך ג'ורג' 59, המלך ג'ורג' 61, המלך ג'ורג' 75",
  "requestStatus": "בדיקה מרחבית מחלקת רישוי",
  "link":          "לפרטי הבקשה"
}
```

| Field | Type | Notes |
|---|---|---|
| `requestId` | integer | Internal DB ID |
| `dataNumber` | string | Online submission number, format `"YY-NNNNN"` |
| `submissionStr` | string | Secondary numeric submission reference |
| `licenseNumber` | string | Display permit number, format `"YY-NNNN"` |
| `requestType` | string | Permit type, Hebrew |
| `address` | string | Street address(es), Hebrew; may list multiple addresses |
| `requestStatus` | string | Current status, Hebrew |
| `link` | string | Always `"לפרטי הבקשה"` — label for detail page link |

**`data.requestDataList`** — information/online-submission records. Real sample:
```json
{
  "requestId":     1001,
  "dataNumber":    "",
  "requestType":   "תוספת בניה או קומות (לא בק\"ק)",
  "address":       "רחוב דיזנגוף מס' 50 ",
  "requestStatus": "פניה נדחתה"
}
```

Same five fields as above; does **not** include `licenseNumber`, `submissionStr`, or `link`.

---

### Permit Number Format

`licenseId` in the request body is an integer. It maps to the display `licenseNumber` as follows:

| `licenseId` (request) | `licenseNumber` (response) |
|---|---|
| `20260001` | `"26-0001"` |
| `20260052` | `"26-0052"` |
| `20260620` | `"26-0620"` |
| `20260624` | `"26-0624"` |

Format: `20` + 2-digit year + 4-digit zero-padded sequence.

---

### Permit Number Scan Results (2026, as of 2026-07-15)

Probed to find the current ceiling:

| `licenseId` | Found | `licenseNumber` | Address |
|---|---|---|---|
| 20260500 | ✅ | 26-0500 | — |
| 20260620 | ✅ | 26-0620 | בבלי 11 (confirmed full record) |
| 20260621 | ✅ | 26-0621 | הפטיש 10 |
| 20260622 | ✅ | 26-0622 | ששון 13, תשבי 8 |
| 20260623 | ✅ | 26-0623 | החרמון 2, אחווה 13 |
| 20260624 | ✅ | 26-0624 | האלקושי 5 |
| 20260625 | ❌ | — | — |
| 20260626 | ❌ | — | — |
| 20260630 | ❌ | — | — |
| 20260650 | ❌ | — | — |
| 20260700 | ❌ | — | — |
| 20261000 | ❌ | — | — |

**Current ceiling: `26-0624` / `licenseId: 20260624`**

---

### Scan Strategy Notes

- The sequence is **mostly but not perfectly sequential** — gaps exist (e.g. 625 and 626 missing while 620–624 are all present)
- "Not found" (`status: 1` with empty `residentLicenseRequest`) is a gap, not the end of the sequence
- A scraper should use a **consecutive-miss threshold** (e.g. stop after 20+ sequential not-found) rather than stopping at the first gap
- Approximately 620+ permits issued in Tel Aviv in the first ~6.5 months of 2026 (~95/month)

---

## Summary for Scraper Design

| Item | Value |
|---|---|
| **API host** | `https://apimtlvprd.tel-aviv.gov.il` |
| **Search endpoint** | `POST /prd/RishuiBniyaWeb/publicApi/ResidentLicensing/Request/getRequest` |
| **Auth** | `X-Client-Assertion: <reCAPTCHA Enterprise v3 token>` — mandatory, gateway-enforced |
| **Critical body gotcha** | `entrance` must be `""` not `null` — `null` causes backend 500 |
| **Result sub-arrays** | `data.residentLicenseRequest` (permits) · `data.requestDataList` (info requests) |
| **Permit number format** | `licenseId` = `20YY` + 4-digit seq; maps to display `"YY-NNNN"` |
| **Current ceiling (2026-07-15)** | `26-0624` / `licenseId: 20260624` |
| **Sequence density** | ~95 permits/month; mostly sequential with occasional gaps |
| **Street code lookup** | `GET /publicApi/Address/SearchTlvStreets/{name}` — no auth needed |
| **Details page** | Requires Azure B2C login — not publicly accessible |
| **Biggest scraper obstacle** | reCAPTCHA Enterprise v3 — requires real browser context or solving service |
