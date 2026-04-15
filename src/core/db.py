
import os
import json
import uuid
import psycopg

from psycopg.rows import dict_row
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase

load_dotenv()

# ─────────────────────────────────────────────────────
# DB CONFIG
# ─────────────────────────────────────────────────────

# 🔹 RAG DATABASE (documents + embeddings)
RAG_DB_URI = os.getenv("PG_CONNECTION_STRING")
RAG_PSYCOPG_URI = RAG_DB_URI.replace("postgresql+psycopg", "postgresql")

# 🔥 SQL AGENT DATABASE (banking seed data)
SQL_AGENT_DB_URI = os.getenv("SQL_DB_URL")
SQL_AGENT_PSYCOPG_URI = SQL_AGENT_DB_URI.replace("postgresql+psycopg", "postgresql")


# ─────────────────────────────────────────────────────
# CONNECTION HELPERS
# ─────────────────────────────────────────────────────

def get_db_conn():
    """RAG DB connection"""
    return psycopg.connect(RAG_PSYCOPG_URI, row_factory=dict_row)


def get_sql_database():
    """(Backward compatibility - DO NOT REMOVE)"""
    return SQLDatabase.from_uri(RAG_DB_URI)


# 🔥 NEW → SQL AGENT DB
def get_sql_agent_db():
    return SQLDatabase.from_uri(SQL_AGENT_DB_URI)


def get_sql_agent_conn():
    return psycopg.connect(SQL_AGENT_PSYCOPG_URI, row_factory=dict_row)


# ─────────────────────────────────────────────────────
# INIT RAG DATABASE
# ─────────────────────────────────────────────────────
def init_db():
    with get_db_conn() as conn:
        with conn.cursor() as cur:

            # DOCUMENTS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY,
                    filename TEXT,
                    file_path TEXT,
                    ingested_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # MULTIMODAL CHUNKS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS multimodal_chunks (
                    id UUID PRIMARY KEY,
                    doc_id UUID,
                    content TEXT,
                    chunk_type TEXT,
                    page_number INT,
                    section TEXT,
                    source_file TEXT,
                    element_type TEXT,
                    image_path TEXT,
                    mime_type TEXT,
                    position INT,
                    metadata JSONB,
                    embedding TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

        conn.commit()


# ─────────────────────────────────────────────────────
# INIT SQL AGENT DATABASE (BANKING SCHEMA)
# ─────────────────────────────────────────────────────
def init_sql_agent_db():
    with get_sql_agent_conn() as conn:
        with conn.cursor() as cur:

            # EXTENSIONS
            cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

            # ACCOUNTS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id VARCHAR(20) PRIMARY KEY,
                    customer_name VARCHAR(100),
                    account_type VARCHAR(20),
                    branch_code VARCHAR(10),
                    ifsc_code VARCHAR(15),
                    mobile VARCHAR(15),
                    email VARCHAR(100),
                    kyc_status VARCHAR(20),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # TRANSACTIONS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    txn_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    account_id VARCHAR(20),
                    txn_date DATE,
                    txn_type VARCHAR(10),
                    amount NUMERIC(15,2),
                    balance_after NUMERIC(15,2),
                    description VARCHAR(200),
                    channel VARCHAR(20),
                    merchant_name VARCHAR(100),
                    category VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # LOAN ACCOUNTS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS loan_accounts (
                    loan_id VARCHAR(20) PRIMARY KEY,
                    account_id VARCHAR(20),
                    loan_type VARCHAR(30),
                    principal NUMERIC(15,2),
                    outstanding NUMERIC(15,2),
                    disbursed_date DATE,
                    emi_amount NUMERIC(15,2),
                    next_emi_date DATE,
                    interest_rate NUMERIC(5,2),
                    tenure_months INT,
                    emi_paid INT DEFAULT 0,
                    status VARCHAR(20),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # FIXED DEPOSITS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fixed_deposits (
                    fd_id VARCHAR(20) PRIMARY KEY,
                    account_id VARCHAR(20),
                    principal NUMERIC(15,2),
                    interest_rate NUMERIC(5,2),
                    tenure_days INT,
                    start_date DATE,
                    maturity_date DATE,
                    maturity_amount NUMERIC(15,2),
                    interest_payout VARCHAR(20),
                    status VARCHAR(20),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # CREDIT CARDS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS credit_cards (
                    card_id VARCHAR(20) PRIMARY KEY,
                    account_id VARCHAR(20),
                    card_variant VARCHAR(30),
                    credit_limit NUMERIC(15,2),
                    available_limit NUMERIC(15,2),
                    outstanding_amt NUMERIC(15,2),
                    due_date DATE,
                    min_due NUMERIC(15,2),
                    status VARCHAR(20),
                    issued_date DATE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # CARD TRANSACTIONS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS card_transactions (
                    txn_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    card_id VARCHAR(20),
                    txn_date DATE,
                    txn_type VARCHAR(20),
                    amount NUMERIC(15,2),
                    merchant_name VARCHAR(100),
                    category VARCHAR(50),
                    is_international BOOLEAN,
                    currency VARCHAR(5),
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

        conn.commit()


# ─────────────────────────────────────────────────────
# SEED SQL AGENT DATA
# ─────────────────────────────────────────────────────
def seed_sql_agent_data():
    with get_sql_agent_conn() as conn:
        with conn.cursor() as cur:

            # ACCOUNTS
            cur.execute("""
                INSERT INTO accounts (account_id, customer_name, account_type)
                VALUES
                ('1345367', 'James Mitchell', 'savings'),
                ('2456789', 'Sarah Thompson', 'salary')
                ON CONFLICT DO NOTHING;
            """)

            # TRANSACTIONS
            cur.execute("""
                INSERT INTO transactions (
                    account_id, txn_date, txn_type, amount, description
                )
                VALUES
                ('1345367', '2026-01-03', 'credit', 85000, 'Salary'),
                ('1345367', '2026-01-05', 'debit', 15000, 'EMI'),
                ('1345367', '2026-01-07', 'debit', 4500, 'Groceries')
                ON CONFLICT DO NOTHING;
            """)

        conn.commit()


# ─────────────────────────────────────────────────────
# DOCUMENT INSERT
# ─────────────────────────────────────────────────────
def upsert_document(filename: str, file_path: str) -> str:
    doc_id = str(uuid.uuid4())

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO documents (id, filename, file_path)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (doc_id, filename, file_path))

            doc_id = cur.fetchone()["id"]

        conn.commit()

    return str(doc_id)


# ─────────────────────────────────────────────────────
# STORE CHUNKS
# ─────────────────────────────────────────────────────
def store_chunks(chunks: list[dict], doc_id: str):

    with get_db_conn() as conn:
        with conn.cursor() as cur:

            for idx, chunk in enumerate(chunks):

                embedding = chunk.get("embedding")

                if isinstance(embedding, list):
                    embedding = str(embedding)

                cur.execute("""
                    INSERT INTO multimodal_chunks (
                        id, doc_id, content, chunk_type,
                        page_number, section, source_file,
                        element_type, image_path, mime_type,
                        position, metadata, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    doc_id,
                    chunk.get("content"),
                    chunk.get("chunk_type"),
                    chunk.get("page_number"),
                    chunk.get("section"),
                    chunk.get("source_file"),
                    chunk.get("element_type"),
                    chunk.get("image_path"),
                    chunk.get("mime_type"),
                    idx,
                    json.dumps(chunk.get("metadata", {})),
                    embedding
                ))

        conn.commit()


# ─────────────────────────────────────────────────────
# FETCH CHUNKS (RAG)
# ─────────────────────────────────────────────────────
def fetch_chunks(limit: int = 50, chunk_type: str | None = None):

    type_clause = "WHERE mc.chunk_type = %(chunk_type)s" if chunk_type else ""

    sql = f"""
        SELECT
            mc.id,
            mc.content,
            mc.chunk_type,
            mc.page_number,
            mc.section,
            mc.source_file,
            mc.element_type,
            mc.image_path,
            mc.mime_type,
            mc.position,
            mc.metadata,
            mc.embedding,
            d.ingested_at AS created_date
        FROM multimodal_chunks mc
        LEFT JOIN documents d ON mc.doc_id = d.id
        {type_clause}
        LIMIT %(limit)s
    """

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "chunk_type": chunk_type,
                "limit": limit
            })
            rows = cur.fetchall()

    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────
# DEBUG
# ─────────────────────────────────────────────────────
def show_tables(db_type="rag"):
    conn_fn = get_db_conn if db_type == "rag" else get_sql_agent_conn

    with conn_fn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
            """)
            return cur.fetchall()

