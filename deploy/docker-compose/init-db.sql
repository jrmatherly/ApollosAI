-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for UUID generation (fallback if uuidv7 not available)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
