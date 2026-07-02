-- ArXiv Database Schema
-- Tables: publication, author, categories, publication_author

-- Publication table
CREATE TABLE IF NOT EXISTS publication (
    id TEXT PRIMARY KEY,
    submitter TEXT,
    title TEXT NOT NULL,
    abstract TEXT,
    doi TEXT,
    journal_ref TEXT,
    license TEXT,
    authors TEXT,
    update_date TEXT,
    latest_version TEXT,
    latest_version_date TEXT,
    downloaded INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Categories table (many-to-many with publications)
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publication_id TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    FOREIGN KEY (publication_id) REFERENCES publication(id),
    UNIQUE(publication_id, category, subcategory)
);

-- Authors table
CREATE TABLE IF NOT EXISTS author (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    middle_name TEXT,
    UNIQUE(first_name, last_name, middle_name)
);

-- Link table for publication-author relationship
CREATE TABLE IF NOT EXISTS publication_author (
    publication_id TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    author_order INTEGER,
    FOREIGN KEY (publication_id) REFERENCES publication(id),
    FOREIGN KEY (author_id) REFERENCES author(id),
    PRIMARY KEY (publication_id, author_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_publication_update_date ON publication(update_date);
CREATE INDEX IF NOT EXISTS idx_publication_downloaded ON publication(downloaded);
CREATE INDEX IF NOT EXISTS idx_categories_publication ON categories(publication_id);
CREATE INDEX IF NOT EXISTS idx_categories_category ON categories(category);
CREATE INDEX IF NOT EXISTS idx_categories_cat_subcat ON categories(category, subcategory);
CREATE INDEX IF NOT EXISTS idx_author_last_name ON author(last_name);
CREATE INDEX IF NOT EXISTS idx_publication_author_author ON publication_author(author_id);
