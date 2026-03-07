-- Initial DB Schema
CREATE TABLE IF NOT EXISTS watchlist (
    ticker VARCHAR PRIMARY KEY,
    name VARCHAR,
    sector VARCHAR
);
