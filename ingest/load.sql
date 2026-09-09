-- Reel Crew -- ClickHouse ingestion.
-- IMDb publishes gzipped TSVs daily; ClickHouse reads them straight from the URL,
-- so there is no ETL script. Run each statement separately: the HTTP interface
-- rejects multi-statement bodies.
--
-- Data: https://datasets.imdbws.com  (personal / non-commercial licence)
-- Nulls arrive as the literal \N, so every raw column is String and is cast
-- with ...OrDefault when the denormalized table is built. Fighting types on
-- ingest is the classic time sink here.

-- ---------------------------------------------------------------- 1. staging
CREATE TABLE IF NOT EXISTS name_basics (
  nconst String, primaryName String, birthYear String, deathYear String,
  primaryProfession String, knownForTitles String
) ENGINE = MergeTree ORDER BY nconst;

CREATE TABLE IF NOT EXISTS title_basics (
  tconst String, titleType String, primaryTitle String, originalTitle String,
  isAdult String, startYear String, endYear String, runtimeMinutes String, genres String
) ENGINE = MergeTree ORDER BY tconst;

CREATE TABLE IF NOT EXISTS title_ratings (
  tconst String, averageRating String, numVotes String
) ENGINE = MergeTree ORDER BY tconst;

CREATE TABLE IF NOT EXISTS title_principals (
  tconst String, ordering String, nconst String, category String, job String, characters String
) ENGINE = MergeTree ORDER BY (category, tconst);

-- ------------------------------------------------- 2. pull straight from IMDb
-- Fire these and move on; all four finished in ~52s on a ClickHouse Cloud trial.
INSERT INTO title_ratings
SELECT * FROM url('https://datasets.imdbws.com/title.ratings.tsv.gz','TSVWithNames',
  'tconst String, averageRating String, numVotes String')
SETTINGS input_format_null_as_default=1, max_http_get_redirects=10, max_execution_time=3000;

INSERT INTO title_basics
SELECT * FROM url('https://datasets.imdbws.com/title.basics.tsv.gz','TSVWithNames',
  'tconst String, titleType String, primaryTitle String, originalTitle String, isAdult String,
   startYear String, endYear String, runtimeMinutes String, genres String')
SETTINGS input_format_null_as_default=1, max_http_get_redirects=10, max_execution_time=3000;

INSERT INTO name_basics
SELECT * FROM url('https://datasets.imdbws.com/name.basics.tsv.gz','TSVWithNames',
  'nconst String, primaryName String, birthYear String, deathYear String,
   primaryProfession String, knownForTitles String')
SETTINGS input_format_null_as_default=1, max_http_get_redirects=10, max_execution_time=3000;

INSERT INTO title_principals
SELECT * FROM url('https://datasets.imdbws.com/title.principals.tsv.gz','TSVWithNames',
  'tconst String, ordering String, nconst String, category String, job String, characters String')
SETTINGS input_format_null_as_default=1, max_http_get_redirects=10, max_execution_time=3000;

-- --------------------------------------------- 3. one wide denormalized table
-- ClickHouse rewards denormalization; there is no star schema here on purpose.
CREATE TABLE IF NOT EXISTS crew_credits (
  nconst      String,
  name        String,
  category    LowCardinality(String),
  job         String,
  tconst      String,
  title       String,
  title_type  LowCardinality(String),
  year        UInt16,
  genres      Array(String),
  rating      Float32,
  votes       UInt32
) ENGINE = MergeTree ORDER BY (category, nconst, year);

-- Filters applied at build time: released formats only, titles with enough votes
-- to be rankable, and reel-crew crew plus the director/writer/producer
-- anchors that make the collaboration graph meaningful.
-- 101,655,603 raw credits -> 1,295,494 rankable crew credits in ~6s.
INSERT INTO crew_credits
SELECT
  p.nconst,
  n.primaryName,
  p.category,
  p.job,
  p.tconst,
  b.primaryTitle,
  b.titleType,
  toUInt16OrDefault(b.startYear),
  arrayFilter(x -> x != '', splitByChar(',', b.genres)),
  toFloat32OrDefault(r.averageRating),
  toUInt32OrDefault(r.numVotes)
FROM title_principals AS p
INNER JOIN title_basics  AS b ON p.tconst = b.tconst
INNER JOIN title_ratings AS r ON p.tconst = r.tconst
LEFT  JOIN name_basics   AS n ON p.nconst = n.nconst
WHERE b.titleType IN ('movie','tvSeries','tvMiniSeries')
  AND toUInt32OrDefault(r.numVotes) > 100
  AND p.category IN ('cinematographer','editor','composer','production_designer',
                     'casting_director','director','writer','producer')
SETTINGS max_execution_time=3000, join_algorithm='parallel_hash';

-- sanity
SELECT count() FROM crew_credits;
