--
-- PostgreSQL database dump
--

\restrict XDCllgb7ovak2t7L0zZ2rsxcSuUejnPgHdfkpu6RJoRPCvSTUurOfhgpVNA7jFL

-- Dumped from database version 17.4 (Debian 17.4-1.pgdg120+2)
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: unit; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unit WITH SCHEMA public;


--
-- Name: EXTENSION unit; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unit IS 'SI units extension';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: filter_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.filter_type AS ENUM (
    'EXPLICIT',
    'DERIVED',
    'INFERRED'
);


--
-- Name: cast_to_bool(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.cast_to_bool(text) RETURNS boolean
    LANGUAGE plpgsql
    AS $_$
                    BEGIN
                        RETURN $1::BOOLEAN;
                    EXCEPTION
                        WHEN others THEN
                            RETURN NULL;
                    END;
                    $_$;


--
-- Name: cast_to_float(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.cast_to_float(text) RETURNS double precision
    LANGUAGE plpgsql
    AS $_$
                    BEGIN
                        RETURN $1::FLOAT;
                    EXCEPTION
                        WHEN others THEN
                            RETURN NULL;
                    END;
                    $_$;


--
-- Name: cast_to_int(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.cast_to_int(text) RETURNS bigint
    LANGUAGE plpgsql
    AS $_$
                    BEGIN
                        RETURN $1::BIGINT;
                    EXCEPTION
                        WHEN others THEN
                            RETURN NULL;
                    END;
                    $_$;


--
-- Name: cast_to_numeric(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.cast_to_numeric(text) RETURNS numeric
    LANGUAGE plpgsql
    AS $_$
                    BEGIN
                        RETURN $1::NUMERIC;
                    EXCEPTION
                        WHEN others THEN
                            RETURN NULL;
                    END;
                    $_$;


--
-- Name: cast_to_timestamp(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.cast_to_timestamp(text) RETURNS timestamp without time zone
    LANGUAGE plpgsql
    AS $_$
                    BEGIN
                        RETURN $1::TIMESTAMP;
                    EXCEPTION
                        WHEN others THEN
                            RETURN NULL;
                    END;
                    $_$;


--
-- Name: rrf_score(bigint, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rrf_score(rank bigint, rrf_k integer DEFAULT 50) RETURNS numeric
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE
    AS $$
BEGIN
	IF rank = 0 THEN RETURN 0.0; END IF;

	RETURN 1.0 / (rank + rrf_k);
END;
$$;


--
-- Name: to_unit(numeric, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.to_unit(val numeric, unit_text text) RETURNS public.unit
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
                    DECLARE
                    u TEXT := btrim(unit_text);
                    l TEXT := lower(u);
                    seconds_per_year NUMERIC := 31557600; -- 365.25 days
                    eV_to_J NUMERIC := 1.602176634e-19;   -- exact (2019 SI)
                    BEGIN
                    -- Empty or whitespace-only unit → NULL
                    IF u = '' THEN
                        RETURN NULL;
                    END IF;

                    -- Context-dependent unit not convertible without extra metadata → NULL
                    IF l = 'rlu' THEN
                        RETURN NULL;
                    END IF;

                    -- Dimensionless / percent
                    IF l IN ('%','percent','percentage') THEN
                        RETURN (val / 100.0) * '1'::unit; -- ratio
                    END IF;

                    -- Temperature: interpret "C" as Celsius; store/compare in Kelvin
                    IF u IN ('C','degC','°C','oC','celsius','Celsius') THEN
                        RETURN (val + 273.15) * '1 K'::unit;
                    END IF;

                    -- Kelvin synonyms
                    IF u IN ('K','k','Kelvin','kelvin') THEN
                        RETURN val * '1 K'::unit;
                    END IF;

                    -- Ampere (electric current)
                    IF u = 'A' OR l IN ('ampere','amp','amps','amperes') THEN
                        RETURN val * '1 A'::unit;
                    END IF;

                    -- Ångström family (length): 1 Å = 1e-10 m
                    -- IMPORTANT: Use Å/Angstrom tokens; plain 'A' is reserved for Ampere.
                    IF u IN ('Å','AA','Ang','ang','Angstrom','angstrom','Angström','angström') THEN
                        RETURN (val * 1e-10) * '1 m'::unit;
                    END IF;

                    -- Reciprocal Å squared → m^-2: 1/Å² = 1e20 m^-2
                    IF u IN ('1/Å²','1/Å^2','1/AA^2','1/Ang^2','1/ang^2','1/Angstrom^2','1/angstrom^2') THEN
                        RETURN (val * 1e20) * '1 m^-2'::unit;
                    END IF;

                    -- Magnetic flux density: Gauss → Tesla
                    IF u = 'G' OR l = 'gauss' THEN
                        RETURN (val * 1e-4) * '1 T'::unit;
                    END IF;

                    -- Energy (electron-volt family) → Joule
                    -- Case-sensitive first to distinguish MeV (mega) vs meV (milli)
                    IF u = 'MeV' THEN RETURN (val * 1e6  * eV_to_J) * '1 J'::unit; END IF; -- mega
                    IF u = 'meV' THEN RETURN (val * 1e-3  * eV_to_J) * '1 J'::unit; END IF; -- milli
                    IF u = 'keV' THEN RETURN (val * 1e3  * eV_to_J) * '1 J'::unit; END IF; -- kilo
                    IF u = 'ueV' THEN RETURN (val * 1e-6  * eV_to_J) * '1 J'::unit; END IF; -- micro (ASCII 'u')
                    IF u = 'eV'  THEN RETURN (val *         eV_to_J) * '1 J'::unit; END IF; -- base
                    -- Permissive lowercase variants
                    IF l = 'mev' THEN RETURN (val * 1e6  * eV_to_J) * '1 J'::unit; END IF;  -- assume MeV if only lowercase
                    IF l = 'kev' THEN RETURN (val * 1e3  * eV_to_J) * '1 J'::unit; END IF;
                    IF l = 'ev'  THEN RETURN (val *         eV_to_J) * '1 J'::unit; END IF;
                    IF l = 'uev' THEN RETURN (val * 1e-6  * eV_to_J) * '1 J'::unit; END IF;

                    -- Concentration: 1 mg/mL = 1 kg/m^3 exactly
                    IF u IN ('mg/ml','mg/mL','mg_per_ml','mg per ml') THEN
                        RETURN val * '1 kg/m^3'::unit;
                    END IF;

                    -- Biochem: kDa → kg (1 Da = 1.66053906660e-27 kg)
                    IF u IN ('kDa','KDa','kda') THEN
                        RETURN (val * 1e3 * 1.66053906660e-27) * '1 kg'::unit;
                    END IF;

                    -- Time: years → seconds
                    IF l IN ('year','years','yr','yrs') THEN
                        RETURN (val * seconds_per_year) * '1 s'::unit;
                    END IF;

                    -- Textual normalizations before fallback
                    IF l = 'hertz'   THEN u := 'Hz'; END IF;
                    IF l IN ('second','seconds','sec','secs') THEN u := 's'; END IF;
                    IF u = 'Degree'  THEN u := 'deg'; END IF;
                    IF u = 'um'      THEN u := 'µm'; END IF;   -- ASCII micro -> µ
                    IF u = 'Bytes'   THEN u := 'B'; END IF;    -- plural -> symbol

                    -- Radiation dose and rate
                    IF u = 'Gy'  OR l = 'gy'    THEN RETURN val * '1 J/kg'::unit;       END IF;
                    IF u = 'kGy' OR l = 'kgy'   THEN RETURN (val * 1e3) * '1 J/kg'::unit; END IF;
                    IF u = 'Gy/s' OR l = 'gy/s' THEN RETURN val * '1 J/kg/s'::unit;     END IF;

                    -- Fallback: let postgresql-unit parse clean SI tokens; on failure return NULL
                    BEGIN
                        RETURN (val || ' ' || u)::unit;
                    EXCEPTION
                        WHEN others THEN
                        RETURN NULL;
                    END;
                    END
                    $$;


--
-- Name: update_document_tsvector(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_document_tsvector() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
	NEW.title_text_search_vector = to_tsvector('english', coalesce(NEW.title, '') || ' ' || coalesce(NEW.text, ''));
	RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: chunk; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chunk (
    id integer NOT NULL,
    document_id integer,
    chunk_number integer,
    text text,
    text_vector public.vector(384)
);


--
-- Name: chunk_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chunk_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chunk_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chunk_id_seq OWNED BY public.chunk.id;


--
-- Name: document; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document (
    id integer NOT NULL,
    doi text,
    title text,
    text text,
    summary text,
    title_summary_vector public.vector(384),
    raw jsonb,
    facility_id integer,
    raw_tsvector tsvector,
    title_text_search_vector tsvector
);


--
-- Name: document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_id_seq OWNED BY public.document.id;


--
-- Name: facility; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.facility (
    id integer NOT NULL,
    name text
);


--
-- Name: facility_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.facility_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: facility_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.facility_id_seq OWNED BY public.facility.id;


--
-- Name: feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feedback (
    id integer NOT NULL,
    statistic_id uuid NOT NULL,
    feedback_type text NOT NULL,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT feedback_feedback_type_check CHECK ((feedback_type = ANY (ARRAY['positive'::text, 'negative'::text])))
);


--
-- Name: feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.feedback_id_seq OWNED BY public.feedback.id;


--
-- Name: filter; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.filter (
    id integer NOT NULL,
    document_id integer,
    key text,
    value text,
    unit text,
    type public.filter_type,
    value_boolean boolean,
    value_timestamp timestamp without time zone,
    value_numeric numeric,
    value_si public.unit
);
ALTER TABLE ONLY public.filter ALTER COLUMN document_id SET STATISTICS 1000;
ALTER TABLE ONLY public.filter ALTER COLUMN key SET STATISTICS 1000;
ALTER TABLE ONLY public.filter ALTER COLUMN value SET STATISTICS 1000;
ALTER TABLE ONLY public.filter ALTER COLUMN value_boolean SET STATISTICS 1000;
ALTER TABLE ONLY public.filter ALTER COLUMN value_timestamp SET STATISTICS 1000;
ALTER TABLE ONLY public.filter ALTER COLUMN value_numeric SET STATISTICS 1000;
ALTER TABLE ONLY public.filter ALTER COLUMN value_si SET STATISTICS 1000;


--
-- Name: filter_description; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.filter_description (
    id integer NOT NULL,
    filter_key_name text NOT NULL,
    description text NOT NULL,
    description_vector public.vector(384)
);


--
-- Name: filter_description_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.filter_description_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: filter_description_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.filter_description_id_seq OWNED BY public.filter_description.id;


--
-- Name: filter_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.filter_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: filter_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.filter_id_seq OWNED BY public.filter.id;


--
-- Name: filter_key; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.filter_key (
    name text,
    name_vector public.vector(384)
);


--
-- Name: migration; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.migration (
    id integer NOT NULL,
    filename text NOT NULL,
    applied_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: migration_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.migration_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: migration_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.migration_id_seq OWNED BY public.migration.id;


--
-- Name: statistic; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.statistic (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    search_query text NOT NULL,
    structured_data jsonb NOT NULL,
    results jsonb NOT NULL,
    execution_time_ms integer NOT NULL,
    modified_query_id uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    sql_query text
);


--
-- Name: chunk id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk ALTER COLUMN id SET DEFAULT nextval('public.chunk_id_seq'::regclass);


--
-- Name: document id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document ALTER COLUMN id SET DEFAULT nextval('public.document_id_seq'::regclass);


--
-- Name: facility id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility ALTER COLUMN id SET DEFAULT nextval('public.facility_id_seq'::regclass);


--
-- Name: feedback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback ALTER COLUMN id SET DEFAULT nextval('public.feedback_id_seq'::regclass);


--
-- Name: filter id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter ALTER COLUMN id SET DEFAULT nextval('public.filter_id_seq'::regclass);


--
-- Name: filter_description id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter_description ALTER COLUMN id SET DEFAULT nextval('public.filter_description_id_seq'::regclass);


--
-- Name: migration id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration ALTER COLUMN id SET DEFAULT nextval('public.migration_id_seq'::regclass);


--
-- Name: chunk chunk_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk
    ADD CONSTRAINT chunk_pkey PRIMARY KEY (id);


--
-- Name: document document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_pkey PRIMARY KEY (id);


--
-- Name: facility facility_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facility
    ADD CONSTRAINT facility_pkey PRIMARY KEY (id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (id);


--
-- Name: feedback feedback_statistic_id_metadata_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_statistic_id_metadata_key UNIQUE (statistic_id, metadata);


--
-- Name: filter_description filter_description_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter_description
    ADD CONSTRAINT filter_description_pkey PRIMARY KEY (id);


--
-- Name: filter filter_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter
    ADD CONSTRAINT filter_pkey PRIMARY KEY (id);


--
-- Name: migration migration_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration
    ADD CONSTRAINT migration_filename_key UNIQUE (filename);


--
-- Name: migration migration_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration
    ADD CONSTRAINT migration_pkey PRIMARY KEY (id);


--
-- Name: statistic statistic_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.statistic
    ADD CONSTRAINT statistic_pkey PRIMARY KEY (id);


--
-- Name: filter_description uq_filter_description_key_desc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter_description
    ADD CONSTRAINT uq_filter_description_key_desc UNIQUE (filter_key_name, description);


--
-- Name: chunk_document_id_chunk_number_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX chunk_document_id_chunk_number_idx ON public.chunk USING btree (document_id, chunk_number);


--
-- Name: chunk_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunk_document_id_idx ON public.chunk USING btree (document_id);


--
-- Name: chunk_text_vector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX chunk_text_vector_idx ON public.chunk USING hnsw (text_vector public.vector_cosine_ops);


--
-- Name: document_doi_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX document_doi_idx ON public.document USING btree (doi);


--
-- Name: document_raw_tsvector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_raw_tsvector_idx ON public.document USING gin (raw_tsvector);


--
-- Name: document_title_summary_vector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_title_summary_vector_idx ON public.document USING hnsw (title_summary_vector public.vector_cosine_ops);


--
-- Name: document_title_text_search_vector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_title_text_search_vector_idx ON public.document USING gin (title_text_search_vector);


--
-- Name: document_to_tsvector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_to_tsvector_idx ON public.document USING gin (to_tsvector('english'::regconfig, ((title || ' '::text) || text)));


--
-- Name: facility_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX facility_name_idx ON public.facility USING btree (name);


--
-- Name: filter_description_vector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_description_vector_idx ON public.filter_description USING hnsw (description_vector public.vector_cosine_ops);


--
-- Name: filter_doc_key_btree_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_doc_key_btree_idx ON public.filter USING btree (document_id, key);


--
-- Name: filter_document_id_key_value_prefix_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_document_id_key_value_prefix_idx ON public.filter USING btree (key, value text_pattern_ops) INCLUDE (document_id);


--
-- Name: filter_key_document_id_covering_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_key_document_id_covering_idx ON public.filter USING btree (key, document_id) INCLUDE (value, value_timestamp, value_numeric, value_boolean, value_si);


--
-- Name: filter_key_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX filter_key_name_idx ON public.filter_key USING btree (name);


--
-- Name: filter_key_name_vector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_key_name_vector_idx ON public.filter_key USING hnsw (name_vector public.vector_cosine_ops);


--
-- Name: filter_key_value_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_key_value_idx ON public.filter USING btree (key, value) INCLUDE (document_id);


--
-- Name: filter_value_trgm_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX filter_value_trgm_idx ON public.filter USING gin (value public.gin_trgm_ops);


--
-- Name: idx_feedback_statistic_id_metadata; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_statistic_id_metadata ON public.feedback USING btree (statistic_id, metadata);


--
-- Name: document document_tsvector_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER document_tsvector_update BEFORE INSERT OR UPDATE ON public.document FOR EACH ROW EXECUTE FUNCTION public.update_document_tsvector();


--
-- Name: chunk chunk_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chunk
    ADD CONSTRAINT chunk_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id);


--
-- Name: document document_facility_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document
    ADD CONSTRAINT document_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id);


--
-- Name: feedback feedback_statistic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_statistic_id_fkey FOREIGN KEY (statistic_id) REFERENCES public.statistic(id) ON DELETE CASCADE;


--
-- Name: filter filter_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter
    ADD CONSTRAINT filter_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.document(id);


--
-- Name: filter_description fk_filter_description_filter_key; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filter_description
    ADD CONSTRAINT fk_filter_description_filter_key FOREIGN KEY (filter_key_name) REFERENCES public.filter_key(name) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict XDCllgb7ovak2t7L0zZ2rsxcSuUejnPgHdfkpu6RJoRPCvSTUurOfhgpVNA7jFL

