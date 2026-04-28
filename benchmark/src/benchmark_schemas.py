import logging
from helpers.postgres_client import PostgresClient

logging.basicConfig(level=logging.INFO)


def main():
    try:
        with PostgresClient() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    -------------------------------------------------------
                    -- Test pairs
                    -------------------------------------------------------

                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_type WHERE typname = 'test_pair_type'
                        ) THEN
                            CREATE TYPE test_pair_type AS ENUM ('synthetic', 'expert');
                        END IF;
                    END$$;

                    DROP TABLE IF EXISTS test_pairs CASCADE;
                    CREATE TABLE IF NOT EXISTS test_pairs (
                        tpId UUID PRIMARY KEY,
                        userPrompt TEXT,
                        targetDoi TEXT,
                        expectedRank INTEGER DEFAULT 0,
                        promptID UUID,
                        expertName TEXT,
                        groupId TEXT,
                        type test_pair_type,
                        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        deprecated TIMESTAMP
                    );

                    DROP INDEX IF EXISTS test_pair_doi_idx;
                    CREATE INDEX test_pair_doi_idx ON test_pairs (targetDoi);

                    DROP INDEX IF EXISTS test_pair_group_id_idx;
                    CREATE INDEX test_pair_group_id_idx ON test_pairs (groupId);

                    DROP INDEX IF EXISTS test_pair_type_idx;
                    CREATE INDEX test_pair_type_idx ON test_pairs (type);

                    DROP INDEX IF EXISTS test_pair_unique_idx;
                    CREATE UNIQUE INDEX test_pair_unique_idx ON test_pairs (userPrompt, targetDoi);

                    -------------------------------------------------------
                    -- benchmarks_run
                    -- store information about each run
                    -------------------------------------------------------
                    DROP TABLE IF EXISTS benchmarks_run CASCADE;
                    CREATE TABLE IF NOT EXISTS benchmarks_run (
                        runId UUID PRIMARY KEY,
                        startedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        endedAt TIMESTAMP,
                        hyperparameters JSONB
                    );

                    -- Run Index
                    DROP INDEX IF EXISTS benchmarks_run_idx;
                    CREATE UNIQUE INDEX benchmarks_run_idx ON benchmarks_run (runId);

                    -------------------------------------------------------
                    -- benchmarks_run
                    -- store information about each run for each test pair
                    -------------------------------------------------------
                    DROP TABLE IF EXISTS benchmarks_run_test CASCADE;
                    CREATE TABLE IF NOT EXISTS benchmarks_run_test (
                        testId UUID PRIMARY KEY,
                        runId UUID REFERENCES benchmarks_run(runId),
                        tpId UUID REFERENCES test_pairs(tpId),
                        intention TEXT,
                        keywords TEXT[],
                        filters JSONB,
                        rank INTEGER,
                        runTime decimal,
                        extractionTime decimal,
                        buildingTime decimal,
                        queryTime decimal,
                        sqlQuery TEXT,
                        resultsSet JSONB
                    );

                    -- Run Index
                    DROP INDEX IF EXISTS benchmarks_run_test_idx;
                    CREATE INDEX benchmarks_run_test_idx ON benchmarks_run_test (runId);

                    -- Test pair Index
                    DROP INDEX IF EXISTS benchmarks_run_test_test_pair_idx;
                    CREATE INDEX benchmarks_run_test_test_pair_idx ON benchmarks_run_test (tpId);

                    -------------------------------------------------------
                    -- test_pair_metrics_values
                    -- stores all the values of each metrics for test pairs
                    -------------------------------------------------------
                    DROP TABLE IF EXISTS test_pair_metrics_values CASCADE;
                    CREATE TABLE IF NOT EXISTS test_pair_metrics_values (
                        id UUID PRIMARY KEY,
                        runId UUID REFERENCES benchmarks_run(runId),
                        testId UUID REFERENCES benchmarks_run_test(testId),
                        metric TEXT,
                        value DECIMAL
                    );

                    DROP INDEX IF EXISTS test_pair_metrics_values_run_idx;
                    CREATE INDEX test_pair_metrics_values_run_idx ON test_pair_metrics_values (runId);

                    DROP INDEX IF EXISTS test_pair_metrics_values_test_idx;
                    CREATE INDEX test_pair_metrics_values_test_idx ON test_pair_metrics_values (testId);

                    DROP INDEX IF EXISTS test_pair_metrics_values_metrics_idx;
                    CREATE INDEX test_pair_metrics_values_metrics_idx ON test_pair_metrics_values (metric);

                    -------------------------------------------------------
                    -- run_metrics_values
                    -- stores all the values of each metrics for each run
                    -------------------------------------------------------
                    DROP TABLE IF EXISTS run_metrics_values CASCADE;
                    CREATE TABLE IF NOT EXISTS run_metrics_values (
                        id UUID PRIMARY KEY,
                        runId UUID REFERENCES benchmarks_run(runId),
                        metric TEXT,
                        value DECIMAL
                    );

                    DROP INDEX IF EXISTS run_metrics_values_run_idx;
                    CREATE INDEX run_metrics_values_run_idx ON run_metrics_values (runId);

                    DROP INDEX IF EXISTS run_metrics_values_metrics_idx;
                    CREATE INDEX run_metrics_values_metrics_idx ON run_metrics_values (metric);

                    """
                )

            conn.commit()
    except Exception as e:
        logging.error("Error during schema creation", exc_info=True)
        raise


if __name__ == "__main__":
    main()
