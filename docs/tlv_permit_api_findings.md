# Tel Aviv Building Permit Search — API Investigation Findings

**Site:** https://rishuybniya.tel-aviv.gov.il/resident-licensing/licensing-request-pages/request-search  
**Investigated:** 2026-07-15  
**Method:** Live browser instrumentation (XHR prototype interception, reCAPTCHA token capture, direct API calls)

---

## API Hostname

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

## Runtime Config Files

The app fetches two JSON files on startup to resolve the API hostname at runtime.

### `GET /assets/env.json`

```json
{ "env": "prod", "ver": 1 }
```

Selects `prod.json` as the active config.

### `GET /assets/prod.json` (full relevant content)

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

## Search Endpoint

Captured verbatim from Angular's own XHR via prototype-level interception.

### Request

```
POST https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/publicApi/ResidentLicensing/Request/getRequest
```

**Headers** (exactly what Angular sends — no extras):

```
Content-Type:       application/json
Accept:             application/json, text/plain, */*
X-Client-Assertion: <reCAPTCHA Enterprise v3 token>
```

No APIM subscription key. No `Authorization: Bearer`. No cookies (cross-origin XHR without `withCredentials`).

**Body** (example: gush=6627, helka=1 search):

```json
{
  "submissionId": 0,
  "licenseId":    0,
  "streetCode":   0,
  "houseNumber":  null,
  "entrance":     null,
  "blockNumber":  6627,
  "parcelNumber": 1
}
```

All seven fields are always present. Zero / null = "not filtering on this field." The Angular app sends no `pageNumber` or `pageSize` — pagination either uses a server-side default or all results are returned in one call.

### Response Envelope

HTTP status is always `200 OK` when the token is valid. Success vs. failure is indicated by the inner `status` field:

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

Note: the key is `"execption"` (sic) — not `"exception"`. `status: 1` = success, `status: 2` = error.

### Result Record Field Names

Extracted from Angular Material `mat-column-*` / `cdk-column-*` CSS classes on the results page (reliable even without live data).

**Table 1 — "בקשות מידע" (Information / online-submission requests):**

| Field | Hebrew header |
|---|---|
| `requestId` | # |
| `address` | כתובת |
| `requestType` | סוג הבקשה |
| `requestStatus` | סטטוס בקשה |

**Table 2 — "בקשות להיתר" (Building permit requests):**

| Field | Hebrew header |
|---|---|
| `dataNumber` | # |
| `licenseNumber` | בקשת רישוי |
| `address` | כתובת |
| `requestType` | סוג הבקשה |
| `requestStatus` | סטטוס בקשה |
| `link` | *(no header — action column)* |

The `data` field in the response likely contains two sub-arrays corresponding to these two tables. The exact key names for those arrays (e.g. `submissionRequests` / `licenseRequests`) could not be confirmed due to the backend outage described below.

### Backend Outage During Testing

All permit search calls during this session returned HTTP 200 with this body:

```json
{
  "status":     2,
  "errorCode":  500,
  "execption":  "",
  "stackTrace": "at ExternalServices.Handlers.HttpHandler`1.Post[ResponseType](...) in HttpHandler.cs:line 241\r\nat ExternalServices.Services.TlvNativAPI.NativRequestPost[ResponseType](...)\r\nat LogicServices.Services.ResidentLicensing.RequestService.getRequest(ResidentRequest data) in RequestService.cs:line 31\r\nat NativRishuyWebApi.Controllers.ResidentLicensing.RequestController.Get..."
}
```

The stack trace reveals the internal service chain:

```
RequestController → RequestService.getRequest → NativRequestPost → HttpHandler (external call)
```

The failure is in the downstream **"Nativ" municipal backend**, not the API gateway. The gateway accepted all valid-token requests with HTTP 200. All search parameter combinations returned this same error, indicating the Nativ system was completely down during this session.

---

## reCAPTCHA Requirement

**reCAPTCHA is strictly enforced at the API gateway — not just client-side.**

| Condition | HTTP status | Response body |
|---|---|---|
| No `X-Client-Assertion` header | `400` | `Missing assertion` |
| Invalid / fake token | `400` | `Invalid assertion` |
| Valid Enterprise v3 token | `200` | Backend response (or Nativ 500 during outage) |

### Implementation details

- **Type:** Google reCAPTCHA **Enterprise** v3 (not standard v3)
- **Site key:** `6Lfl1nwrAAAAAJKMOLVFqNm0qIgbtqOqQlC2G97i`
- **Header name:** `X-Client-Assertion`
- **Token acquisition:**
  ```javascript
  grecaptcha.enterprise.execute(
    "6Lfl1nwrAAAAAJKMOLVFqNm0qIgbtqOqQlC2G97i",
    { action: "submit" }
  )
  ```
- **`SkipRecaptcha: false`** — no production config toggle to bypass
- Tokens are single-use and expire in ~2 minutes; a scraper must obtain a **fresh token per request**

---

## Street Code Lookup Endpoint

Required to populate `streetCode` when searching by address. **No auth header needed.**

```
GET https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/publicApi/Address/SearchTlvStreets/{streetName}
```

**Example — searching for "דיזנגוף":**

```json
{
  "data": [
    { "id": 187, "caption": "דיזנגוף" },
    { "id": 408, "caption": "כיכר צינה דיזנגוף" }
  ],
  "status":        1,
  "errorCode":     0,
  "execption":     "",
  "handleError":   true,
  "handleSuccess": false
}
```

Use `id` as the `streetCode` value in the search request body.

---

## Detail Page / Endpoint

The `link` column in permit results leads to the `/building-permit` module (per `systemName` in prod.json). Navigating to `https://rishuybniya.tel-aviv.gov.il/building-permit` immediately triggers an Azure B2C MSAL redirect:

```
https://b2ctam.b2clogin.com/b2ctam.onmicrosoft.com/b2c_1a_nativprd_signin/oauth2/v2.0/authorize
  ?client_id=840568d3-d24a-4dbf-a803-4b5c08bef460
  &scope=openid profile https://b2ctam.onmicrosoft.com/NativRishuyWebApi/ReadWrite offline_access
  &redirect_uri=https://rishuybniya.tel-aviv.gov.il/
  &response_type=code   (PKCE flow)
```

Direct API calls to the detail endpoint return `401 WWW-Authenticate: Bearer` without a valid MSAL token:

```
GET https://apimtlvprd.tel-aviv.gov.il/prd/RishuiBniyaWeb/api/ResidentLicensing/Request/{id}
→ 401
```

**The detail module requires full Azure B2C login and is not accessible to unauthenticated scrapers.**

---

## Other Known Endpoints (from static JS analysis, not runtime-confirmed)

| Path | Notes |
|---|---|
| `/publicApi/ResidentLicensing/Message` | — |
| `/publicApi/ResidentLicensing/Employee` | — |
| `/publicApi/ResidentLicensing/ReferenceMaterials` | Returns 401 without Bearer — requires login |
| `/publicApi/Register/CheckIdentity` | — |
| `/publicApi/B2CRegistration` | — |

---

## Summary for Scraper Design

| Item | Value |
|---|---|
| **API host** | `https://apimtlvprd.tel-aviv.gov.il` |
| **Search endpoint** | `POST /prd/RishuiBniyaWeb/publicApi/ResidentLicensing/Request/getRequest` |
| **Auth for search** | `X-Client-Assertion: <reCAPTCHA Enterprise v3 token>` — mandatory, gateway-enforced |
| **Auth for details** | Azure B2C Bearer token — requires real user login, not scriptable without automation |
| **Street code lookup** | `GET /prd/RishuiBniyaWeb/publicApi/Address/SearchTlvStreets/{name}` — no auth |
| **Pagination** | Not present in Angular's own request body; behavior unknown due to backend outage |
| **Backend status** | Downstream "Nativ" system was fully down during this session; gateway and reCAPTCHA validation are functional |
| **Biggest scraper obstacle** | reCAPTCHA Enterprise v3 — requires a real browser context or third-party solving service to obtain valid tokens |
