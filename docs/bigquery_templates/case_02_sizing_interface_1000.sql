-- BigQuery SQL Template (REFERENCE ONLY) — Case 2 sizing / interface
-- NOT executed by the app. Dry-run and billing review required.

/*
SELECT publication_number, title, abstract, assignee, year, country_code, family_id
FROM `your-project.patents.publications`
WHERE LOWER(title) LIKE '%sizing%' OR LOWER(abstract) LIKE '%interface%'
LIMIT 1000
*/
