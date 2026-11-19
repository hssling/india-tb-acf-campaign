# LGD evidence search log (19 Nov 2026)

The rule applied is §13, "District denominator: reconstruction from official notices", read with §9.3–§9.4 of `docs/analysis_plan.md`. No file in `data_raw/pq/` or `data_raw/india_tb_report/` was opened, and no TB notification data was seen. The inputs read were `data/extracted/lgd_reconstruction_log.csv`, `data/extracted/lgd_districts_2024-12-07.csv`, and the current LGD xlsx, which was parsed with stdlib zipfile.

## Key source: LGD public district web service

The LGD home page links "List of modifications" (`lgdTransaction.do`) and "District LGD codes" (`globalviewdistrictforcitizen.do`). Both need a form and a CAPTCHA, so they were not used.

`getLgdRecentModifications.do` is readable without a form, but it shows only the last 50 transactions, all of them from 18 Nov 2026 in Uttar Pradesh. It was not useful.

A search result led to the LGD NAPIX web service:
- Staging endpoint: `https://lgdirectory.gov.in/webservices-staging/lgd/napix/...`. It contains test records, such as Ladakh codes named "Test", "Testing M" and "Twentyone". **It was not used as evidence.**
- Production endpoint: `https://lgdirectory.gov.in/webservices/lgd/napix/districts/v1/status/active`. It returns 790 active districts, exactly the codes in the 18-Nov-2026 xlsx. Each record gives `effectiveDate`, `lastUpdated`, `census2011Code` and the *latest* transaction with its description. For a creation, the description reads "District X is created by taking contribution from District Y(part), on date D".
- **Judgement:** these records are treated as "the LGD public page for that district". They are an official LGD public data feed, not an HTML district page.
- The feed shows only the latest transaction per district. History, including abolished districts, is not available: `/status/inactive` and `/status/all` return 404.

Note on downloads: WebFetch's harness automatically cached the binary of every PDF or YAML it fetched, in the tool's local cache (files named `webfetch-17950*.{pdf,bin}`). These caches were not saved on purpose.
- Some image-only PDFs were readable only through those caches (Read/pdftotext), and they were read that way: the Delhi gazette, the Delhi FSD order, the CEO Delhi map, the Ladakh release, the Arunachal Act and the Assam guardian-minister notifications.
- The LGD YAML was parsed from its cache into the scratchpad.
- The author may wish to delete these caches.

## Per State

**Rajasthan**
- Searches covered: the abolition of 9 districts in Dec 2024 (English and Hindi); revenue.rajasthan.gov.in, which does not resolve; dms.rajasthan.gov.in, which returns "Invalid session"; and DIPR.
- Found the official list at landrevenue.rajasthan.gov.in, "Notifications – Revenue Units". Entries 182–189 are dated 30-12-2024 and each cancels a 2023 creation. Entries 147–181 are the 2023 creations and reorganisations, used as pre-reference evidence. Entries 224–228 (31-12-2025) are tehsil-level changes only. The rest of the list, up to 16-10-2026, has no district-level entry.
- The notification PDFs are not text-readable.
- Dead ends: Wikipedia, which cites a Gazette 9(21)Rev-1/2024-(8) dated 29-12-2024; newsonair (news); and news reports.

**Delhi**
- Found the Gazette F.223/SDM-II(HQ)/Land/2025/285, dated 25-12-2025, on revenue.delhi.gov.in (file 268793_list.pdf), and the FSD order of 02-01-2026 that cites it.
- Pre-reference list of 11 districts: the CEO Delhi/GSDL map printed 17-06-2015.
- revenue.delhi.gov.in has no Notifications list page for 2025.

**Ladakh**
- ladakh.gov.in release of 27-04-2026 (five districts) and DIPR PDF.
- ladakh.gov.in release on Sankoo, S.O. 284 dated 16-10-2026.
- LGD records for codes 797–802.
- The notification listing pages on ladakh.gov.in did not show the notifications themselves. kargil.nic.in had only an election notice.

**Gujarat**
- Searched for the Vav-Tharad notification. The Revenue Dept notifications page loads dynamically and could not be read. The Gujarat eGazette search returned only voter-list gazettes. gujaratinformation and the CMO site had no notification.
- Found vavtharad.nic.in/history, which says the district was created on 2 Oct 2025, and the LGD record.
- RBI circulars (not qualifying) redirect.
- The 17 new talukas (Sept 2025) and the Jan 2026 taluka reorganisation do not change the district count.

**Andhra Pradesh**
- LGD records 790 and 791 give creation "on date 2025-12-30".
- allurisitharamaraju.ap.gov.in/history says effective 31 Dec 2025, with 26→28 districts.
- The 2022 districts are evidenced by the ASR history page and Annamayya's G.O. Rt.111 page.
- AP eGazette and GOIR were not used, because the eGazette needs a search form.

**Arunachal Pradesh**
- Act 2 of 2024 is published in Gazette Extraordinary No.108, 23-02-2024, on printing.arunachal.gov.in. Its commencement is by a later notification.
- Searched printing.arunachal.gov.in for the commencement notification. Not found. The July 2025 gazette shows Bichom in a court-jurisdiction notice dated 27 June 2025.
- indiacode returned 403. RBI redirects.
- LGD dates Keyi Panyor 2024-11-25 and Bichom 2025-01-10.

**Assam**
- No creation or abolition was found in the window. A general search for new districts in 2025–26 found none. LGD shows no new Assam code.
- Sribhumi rename: LGD effective 2024-11-21.
- District websites (Bajali, Biswanath, Charaideo, Hojai, Majuli) give creation in 2016 or 2021. Several Assam government URLs return 404 or ECONNREFUSED; plain http sometimes works.
- The Dec 2022 merger and Aug–Oct 2023 re-creation of four districts are documented only in news and RBI sources. Both fall before the window.
- Guardian-minister notification of 01-02-2025: lists 35 districts (post-reference). The 10-09-2024 version returns 404.

**Haryana, Goa**
- LGD records only: Hansi 2025-12-19 and Kushavati 2025-12-31.
- News says Hansi's gazette was "to be issued"; no State gazette was read.

**Nagaland**
- LGD dates Meluri's creation 2024-11-02, which is before the reference date.
- The other rows are village shifts in 2025–26.

**Odisha, Uttarakhand, Karnataka**
- The LGD records show renames or spelling changes only.

**Telangana, Tamil Nadu, Maharashtra, Madhya Pradesh, Chhattisgarh, Punjab**
- LGD records show only village or sub-district shifts in 2025–26.
- News searches found no new or abolished districts. Telangana announced a review commission in 2026, but no notification was found.

**General**
- A search for "district abolished 2025/2026" returned only Rajasthan.
- Every LGD code above 785 is accounted for: 786–802.

## Report-only count check (1 Nov – 7 Dec 2024)

No official statement of a State's district count dated inside this window was found for any of the 19 States. Statements found outside the window:
- CEO Delhi map, 2015: 11 districts.
- Assam notification, 01-02-2025: 35 districts.
