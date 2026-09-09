#!/usr/bin/env bash
cd "$(dirname "$0")/.."
S="SETTINGS input_format_null_as_default=1, max_http_get_redirects=10, max_execution_time=3000"

( echo "[basics] start $(date +%T)"
  CH_TIMEOUT=3000 ./scripts/ch.sh "INSERT INTO title_basics SELECT * FROM url('https://datasets.imdbws.com/title.basics.tsv.gz','TSVWithNames','tconst String, titleType String, primaryTitle String, originalTitle String, isAdult String, startYear String, endYear String, runtimeMinutes String, genres String') $S"
  echo "[basics] done $(date +%T) exit=$?" ) &

( echo "[names] start $(date +%T)"
  CH_TIMEOUT=3000 ./scripts/ch.sh "INSERT INTO name_basics SELECT * FROM url('https://datasets.imdbws.com/name.basics.tsv.gz','TSVWithNames','nconst String, primaryName String, birthYear String, deathYear String, primaryProfession String, knownForTitles String') $S"
  echo "[names] done $(date +%T) exit=$?" ) &

( echo "[principals] start $(date +%T)"
  CH_TIMEOUT=3000 ./scripts/ch.sh "INSERT INTO title_principals SELECT * FROM url('https://datasets.imdbws.com/title.principals.tsv.gz','TSVWithNames','tconst String, ordering String, nconst String, category String, job String, characters String') $S"
  echo "[principals] done $(date +%T) exit=$?" ) &

wait
echo "=== ALL RAW INGESTS FINISHED $(date +%T) ==="
