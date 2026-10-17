CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE rate_limits (
	key VARCHAR(100) NOT NULL,
	"window" INTEGER NOT NULL,
	count INTEGER NOT NULL,
	PRIMARY KEY (key, "window")
);
CREATE TABLE tenants (
	name VARCHAR(120) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE documents (
	tenant_id VARCHAR(36) NOT NULL,
	name VARCHAR(255) NOT NULL,
	min_role INTEGER NOT NULL,
	version INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	size INTEGER NOT NULL,
	error TEXT,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, name),
	UNIQUE (id, tenant_id),
	CHECK (min_role BETWEEN 0 AND 2),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_documents_status ON documents (status);
CREATE INDEX ix_documents_tenant_id ON documents (tenant_id);
CREATE TABLE employees (
	tenant_id VARCHAR(36) NOT NULL,
	department VARCHAR(80) NOT NULL,
	joined_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_employees_tenant_id ON employees (tenant_id);
CREATE TABLE users (
	tenant_id VARCHAR(36) NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash TEXT NOT NULL,
	role VARCHAR(16) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (role IN ('ADMIN','MANAGER','EMPLOYEE')),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	UNIQUE (email)
);
CREATE INDEX ix_users_tenant_id ON users (tenant_id);
CREATE TABLE conversations (
	tenant_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	title VARCHAR(160) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_conversations_user_id ON conversations (user_id);
CREATE INDEX ix_conversations_tenant_id ON conversations (tenant_id);
CREATE TABLE document_chunks (
	tenant_id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	version INTEGER NOT NULL,
	text TEXT NOT NULL,
	page INTEGER,
	section VARCHAR(512) NOT NULL,
	source VARCHAR(255) NOT NULL,
	embedding VECTOR(384) NOT NULL,
	search_vector TSVECTOR NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id, tenant_id) REFERENCES documents (id, tenant_id) ON DELETE CASCADE,
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_document_chunks_tenant_id ON document_chunks (tenant_id);
CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);
CREATE INDEX ix_chunks_search ON document_chunks USING gin (search_vector);
CREATE INDEX ix_chunks_vector ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE document_versions (
	tenant_id VARCHAR(36) NOT NULL,
	document_id VARCHAR(36) NOT NULL,
	version INTEGER NOT NULL,
	content BYTEA NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(document_id, tenant_id) REFERENCES documents (id, tenant_id) ON DELETE CASCADE,
	UNIQUE (document_id, version),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_document_versions_document_id ON document_versions (document_id);
CREATE INDEX ix_document_versions_tenant_id ON document_versions (tenant_id);
CREATE TABLE evaluations (
	tenant_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	status VARCHAR(20) NOT NULL,
	dataset_version VARCHAR(32) NOT NULL,
	results JSON NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_evaluations_tenant_id ON evaluations (tenant_id);
CREATE TABLE messages (
	conversation_id VARCHAR(36) NOT NULL,
	role VARCHAR(16) NOT NULL,
	content TEXT NOT NULL,
	citations JSON NOT NULL,
	query_id VARCHAR(36),
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);
CREATE INDEX ix_messages_query_id ON messages (query_id);
CREATE TABLE queries (
	tenant_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	conversation_id VARCHAR(36),
	question TEXT NOT NULL,
	rewritten_query TEXT NOT NULL,
	route VARCHAR(16) NOT NULL,
	status VARCHAR(20) NOT NULL,
	answer TEXT NOT NULL,
	grounding VARCHAR(24) NOT NULL,
	latency_ms FLOAT,
	token_usage JSON,
	estimated_cost FLOAT,
	trace JSON NOT NULL,
	error TEXT,
	request_id VARCHAR(36) NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE SET NULL
);
CREATE INDEX ix_queries_user_id ON queries (user_id);
CREATE INDEX ix_queries_tenant_id ON queries (tenant_id);
CREATE TABLE feedback (
	query_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	rating INTEGER NOT NULL,
	comment TEXT NOT NULL,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (query_id, user_id),
	CHECK (rating IN (-1, 1)),
	FOREIGN KEY(query_id) REFERENCES queries (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE retrieval_results (
	query_id VARCHAR(36) NOT NULL,
	chunk_id VARCHAR(36),
	metadata_snapshot JSON NOT NULL,
	dense_score FLOAT,
	lexical_score FLOAT,
	rrf_score FLOAT NOT NULL,
	reranker_score FLOAT,
	id VARCHAR(36) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(query_id) REFERENCES queries (id) ON DELETE CASCADE,
	FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE SET NULL
);
CREATE INDEX ix_retrieval_results_query_id ON retrieval_results (query_id);
