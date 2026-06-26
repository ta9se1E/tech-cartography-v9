-- BigQuery SQL Template (REFERENCE ONLY) — Case 1 PAN graphitization
-- Phase27J.0: This template is NOT executed by the app.
-- Run manually in BigQuery console after dry-run / cost review.
-- Export result CSV to cases/case_01_pan_graphitization/large_candidates/

-- Example placeholder query structure (adjust table/dataset for your environment):
/*
SELECT
  publication_number,
  title,
  abstract,
  assignee,
  EXTRACT(YEAR FROM publication_date) AS year,
  country_code,
  family_id,
  publication_date
FROM `your-project.patents.publications`
WHERE
  LOWER(title) LIKE '%carbon fiber%'
  OR LOWER(title) LIKE '%polyacrylonitrile%'
  OR LOWER(abstract) LIKE '%graphitization%'
LIMIT 1000
*/

-- Upload exported CSV via Input tab or:
-- python scripts/run_v8_large_candidate_import.py --case-id case_01_pan_graphitization --input <csv>
