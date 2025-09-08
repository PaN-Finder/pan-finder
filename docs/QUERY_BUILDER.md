# Describe the Search query

TODO UPDATE IT, MAKE IT FRESH

## Similarity Rank calculation

```sql
SELECT
    -- d.doi,
    rank () OVER (ORDER BY d.summary_vector <=> '{intention_vector}'::vector ASC) AS similarity_rank,                
    -- 0 AS filter_rank,
    -- 0 AS keyword_rank
FROM document d
WHERE 
    d.summary_vector <=> '{intention_vector}'::vector < 0.5
ORDER BY similarity_rank
LIMIT 5
```

Use the `<=>` operator to calculate the cosine distance between the `summary_vector` and the `intention_vector`. 
The row with the smallest distance (i.e., most similar vector) gets rank 1. The row with the next smallest distance gets rank 2, and so on.
List only the top 5 most similar documents which have a distance less than 0.5.

Example:
| (rank) | (distance) |
| ------ | ---------- |
| 1      | 0.1        |
| 2      | 0.2        |
| 3      | 0.3        |

## Filter rank calculation

```sql
SELECT
    -- d.doi,
    -- 0 AS similarity_rank,
    1 AS filter_rank,
    -- 0 AS keyword_rank
FROM document d
WHERE 
    -- Filter condition is dinamically generated based on the user input
ORDER BY filter_rank
```

If the row is returned by the filter subquery, the `filter_rank` is set to 1. Otherwise, it is set to 0. To be sure every row has the same rank!

## Keyword rank calculation

```sql
SELECT
    -- d.doi,
    -- 0 AS similarity_rank,
    -- 0 AS filter_rank,
    rank() OVER (ORDER BY ts_rank_cd(to_tsvector('english', d.title || ' ' || d.text), to_tsquery('english', '{keywords}')) DESC) AS keyword_rank
FROM document d
WHERE
    to_tsvector('english', d.title || ' ' || d.text) @@ to_tsquery('english', '{keywords}')
ORDER BY keyword_rank
LIMIT 5
```

Use the `ts_rank_cd` function to calculate the rank of the row based on the `title` and `text` columns. The rank is based on the `keywords` provided in the query. The row with the highest rank gets rank 1. The row with the next highest rank gets rank 2, and so on.

- Documents containing more of the keywords get a higher ranking. 
- Documents with rare keywords get boosted more if a keyword appears rarely in the database, ts_rank_cd assigns it a higher weight, making those documents rank higher.
- Common words have less impact 

## Score calculation
```sql
SELECT
    searches.doi,
    sum(rrf_score(similarity_rank) + rrf_score(filter_rank) + rrf_score(keyword_rank)) AS score,
    sum(rrf_score(similarity_rank)) AS similarity_score,
    sum(rrf_score(filter_rank)) AS filter_score,
    sum(rrf_score(keyword_rank)) AS keyword_score
FROM searches ...
```

The `rrf_score` function is used to calculate the mean reciprocal score of the rank(s). 
- `score`: The sum of the `rrf_score` of the `similarity_rank`, `filter_rank`, and `keyword_rank`.
- `similarity_score`: The sum of the `rrf_score` of the `similarity_rank`.
- `filter_score`: The sum of the `rrf_score` of the `filter_rank`.
- `keyword_score`: The sum of the `rrf_score` of the `keyword_rank`.

## Ranking based on Scores

- The primary ranking is determined by `Score`.
- If two or more rows have the same `Score`, the one with the highest `Similarity Score` appears first.
- If `Similarity Score` is also tied, `Filter Score` is used next.
- If all the above are tied, `Keyword Score` is used as the final tiebreaker.
