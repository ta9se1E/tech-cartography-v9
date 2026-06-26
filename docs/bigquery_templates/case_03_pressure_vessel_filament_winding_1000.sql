-- BigQuery SQL Template (REFERENCE ONLY) — Case 3 pressure vessel / FW
-- NOT executed by the app. Dry-run and billing review required.

/*
SELECT publication_number, title, abstract, assignee, year, country_code, family_id
FROM `your-project.patents.publications`
WHERE LOWER(title) LIKE '%pressure vessel%' OR LOWER(abstract) LIKE '%filament winding%'
LIMIT 1000
*/
