//! xAI-FAF-RAG: Cache-first RAG using Grok Collections + LAZY-RAG
//!
//! Rust implementation of the xAI-FAF-RAG integrator.
//! Raw HTTP calls to xAI API - no SDK dependency.
//!
//! # Architecture
//! ```text
//! Query
//!   |
//!   v
//! LAZY-RAG Cache (sub-μs)
//!   |-- HIT --> Return immediately
//!   |-- MISS --> Grok Collections API
//!                     |
//!                     v
//!                Cache result --> Return
//! ```

use std::collections::HashMap;
use std::path::Path;
use std::sync::RwLock;

use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE};
use reqwest::multipart::{Form, Part};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;
use tracing::{debug, error, info, warn};

/// Base URL for xAI API
const XAI_API_BASE: &str = "https://api.x.ai/v1";

/// Default collection name
const DEFAULT_COLLECTION_NAME: &str = "FAF Elite Palace";

/// Default model for chat
const DEFAULT_MODEL: &str = "grok-4-fast";

/// Default embedding model
const DEFAULT_EMBEDDING: &str = "grok-embedding-small";

/// Default retrieval mode
const DEFAULT_RETRIEVAL_MODE: &str = "hybrid";

/// Custom error types
#[derive(Error, Debug)]
pub enum XAIError {
    #[error("Authentication failed: {0}")]
    Authentication(String),

    #[error("Rate limited: {0}")]
    RateLimit(String),

    #[error("API error ({status}): {message}")]
    Api { status: u16, message: String },

    #[error("Request failed: {0}")]
    Request(#[from] reqwest::Error),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Missing API key: {0}")]
    MissingKey(String),

    #[error("File not found: {0}")]
    FileNotFound(String),
}

pub type Result<T> = std::result::Result<T, XAIError>;

/// Search result from Collections API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub snippet: String,
    pub file_name: String,
    pub score: f64,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Collection info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Collection {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

/// Chat message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

/// Cache statistics
#[derive(Debug, Clone)]
pub struct CacheStats {
    pub size: usize,
    pub enabled: bool,
}

/// xAI-FAF-RAG Integrator
///
/// Cache-first RAG using Grok Collections + LAZY-RAG caching.
pub struct XAIFafRag {
    client: Client,
    api_key: String,
    management_api_key: Option<String>,
    collection_name: String,
    collection_id: String,
    enable_cache: bool,
    cache: RwLock<HashMap<String, String>>,
}

impl XAIFafRag {
    /// Create a new XAIFafRag instance
    ///
    /// # Arguments
    /// * `api_key` - xAI API key for reads (or reads from XAI_API_KEY env)
    /// * `management_api_key` - xAI management key for writes (or reads from XAI_MANAGEMENT_API_KEY env)
    /// * `collection_name` - Name for the collection (default: "FAF Elite Palace")
    /// * `enable_cache` - Enable LAZY-RAG cache layer (default: true)
    pub async fn new(
        api_key: Option<String>,
        management_api_key: Option<String>,
        collection_name: Option<String>,
        enable_cache: bool,
    ) -> Result<Self> {
        let api_key = api_key
            .or_else(|| std::env::var("XAI_API_KEY").ok())
            .ok_or_else(|| XAIError::MissingKey("XAI_API_KEY required".to_string()))?;

        let management_api_key =
            management_api_key.or_else(|| std::env::var("XAI_MANAGEMENT_API_KEY").ok());

        let collection_name = collection_name.unwrap_or_else(|| DEFAULT_COLLECTION_NAME.to_string());

        let client = Client::new();

        let mut integrator = Self {
            client,
            api_key,
            management_api_key,
            collection_name,
            collection_id: String::new(),
            enable_cache,
            cache: RwLock::new(HashMap::new()),
        };

        integrator.collection_id = integrator.get_or_create_collection().await?;
        info!("Initialized XAIFafRag with collection: {}", integrator.collection_id);

        Ok(integrator)
    }

    /// Build authorization headers
    fn auth_headers(&self) -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(
            AUTHORIZATION,
            HeaderValue::from_str(&format!("Bearer {}", self.api_key)).unwrap(),
        );
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
        headers
    }

    /// Get existing collection or create new one
    async fn get_or_create_collection(&self) -> Result<String> {
        // List existing collections
        let url = format!("{}/collections", XAI_API_BASE);
        let resp = self
            .client
            .get(&url)
            .headers(self.auth_headers())
            .send()
            .await?;

        if resp.status() == 401 {
            return Err(XAIError::Authentication("Invalid API key".to_string()));
        }

        if resp.status() == 429 {
            warn!("Rate limited during collection setup. Retrying...");
            tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
            return Box::pin(self.get_or_create_collection()).await;
        }

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let text = resp.text().await.unwrap_or_default();
            return Err(XAIError::Api {
                status,
                message: text,
            });
        }

        #[derive(Deserialize)]
        struct ListResponse {
            data: Vec<Collection>,
        }

        let list: ListResponse = resp.json().await?;

        // Check for existing collection
        for coll in list.data {
            if coll.name == self.collection_name {
                info!("Found existing collection: {}", coll.id);
                return Ok(coll.id);
            }
        }

        // Create new collection
        let mgmt_key = self
            .management_api_key
            .as_ref()
            .ok_or_else(|| XAIError::MissingKey("XAI_MANAGEMENT_API_KEY required to create collection".to_string()))?;

        info!("Creating new collection: {}", self.collection_name);

        #[derive(Serialize)]
        struct CreateRequest {
            name: String,
            description: String,
            model_name: String,
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            AUTHORIZATION,
            HeaderValue::from_str(&format!("Bearer {}", mgmt_key)).unwrap(),
        );
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

        let resp = self
            .client
            .post(&url)
            .headers(headers)
            .json(&CreateRequest {
                name: self.collection_name.clone(),
                description: "Eternal .FAF DNA + docs for Grok agents".to_string(),
                model_name: DEFAULT_EMBEDDING.to_string(),
            })
            .send()
            .await?;

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let text = resp.text().await.unwrap_or_default();
            return Err(XAIError::Api {
                status,
                message: text,
            });
        }

        #[derive(Deserialize)]
        struct CreateResponse {
            collection_id: String,
        }

        let created: CreateResponse = resp.json().await?;
        Ok(created.collection_id)
    }

    /// Sync .faf file and supporting documents to collection
    pub async fn sync_faf(
        &self,
        faf_path: &str,
        supporting: Option<Vec<&str>>,
    ) -> Result<bool> {
        let mgmt_key = self
            .management_api_key
            .as_ref()
            .ok_or_else(|| XAIError::MissingKey("XAI_MANAGEMENT_API_KEY required for uploads".to_string()))?;

        let mut files: Vec<(&str, &str, &str)> = vec![(faf_path, "project.faf", "text/yaml")];

        if let Some(ref supporting_files) = supporting {
            for path in supporting_files {
                let name = Path::new(path)
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("unknown");
                files.push((path, name, "application/octet-stream"));
            }
        }

        let mut success = true;

        for (path, name, content_type) in files {
            if !Path::new(path).exists() {
                error!("File not found: {}", path);
                success = false;
                continue;
            }

            let data = tokio::fs::read(path).await?;

            let url = format!("{}/collections/{}/documents", XAI_API_BASE, self.collection_id);

            let mut headers = HeaderMap::new();
            headers.insert(
                AUTHORIZATION,
                HeaderValue::from_str(&format!("Bearer {}", mgmt_key)).unwrap(),
            );

            let form = Form::new()
                .text("name", name.to_string())
                .part(
                    "file",
                    Part::bytes(data)
                        .file_name(name.to_string())
                        .mime_str(content_type)?,
                );

            info!("Uploading: {}", name);

            let resp = self
                .client
                .post(&url)
                .headers(headers)
                .multipart(form)
                .send()
                .await?;

            if resp.status() == 429 {
                warn!("Rate limited during upload. Waiting...");
                tokio::time::sleep(tokio::time::Duration::from_secs(15)).await;
                return Box::pin(self.sync_faf(faf_path, supporting)).await;
            }

            if !resp.status().is_success() {
                let status = resp.status().as_u16();
                let text = resp.text().await.unwrap_or_default();
                error!("Failed to upload {}: {} - {}", name, status, text);
                success = false;
            } else {
                info!("Uploaded: {}", name);
            }
        }

        Ok(success)
    }

    /// Search the collection directly
    pub async fn search(
        &self,
        query: &str,
        num_results: Option<usize>,
        retrieval_mode: Option<&str>,
    ) -> Result<Vec<SearchResult>> {
        let retrieval_mode = retrieval_mode.unwrap_or(DEFAULT_RETRIEVAL_MODE);
        let num_results = num_results.unwrap_or(5);

        // Check cache
        if self.enable_cache {
            let cache_key = self.cache_key(query, retrieval_mode);
            if let Ok(cache) = self.cache.read() {
                if let Some(cached) = cache.get(&cache_key) {
                    debug!("Cache hit");
                    return Ok(serde_json::from_str(cached)?);
                }
            }
        }

        let url = format!("{}/collections/search", XAI_API_BASE);

        #[derive(Serialize)]
        struct SearchRequest {
            query: String,
            collection_ids: Vec<String>,
            retrieval_mode: String,
            num_results: usize,
        }

        let resp = self
            .client
            .post(&url)
            .headers(self.auth_headers())
            .json(&SearchRequest {
                query: query.to_string(),
                collection_ids: vec![self.collection_id.clone()],
                retrieval_mode: retrieval_mode.to_string(),
                num_results,
            })
            .send()
            .await?;

        if resp.status() == 429 {
            warn!("Rate limited during search");
            return Ok(vec![]);
        }

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let text = resp.text().await.unwrap_or_default();
            error!("Search failed: {} - {}", status, text);
            return Ok(vec![]);
        }

        let results: Vec<SearchResult> = resp.json().await?;

        // Cache result
        if self.enable_cache {
            let cache_key = self.cache_key(query, retrieval_mode);
            if let Ok(mut cache) = self.cache.write() {
                cache.insert(cache_key, serde_json::to_string(&results)?);
            }
        }

        Ok(results)
    }

    /// Query with RAG-enhanced chat (tool-calling)
    pub async fn query(
        &self,
        question: &str,
        model: Option<&str>,
        system_prompt: Option<&str>,
    ) -> Result<String> {
        let model = model.unwrap_or(DEFAULT_MODEL);
        let system_prompt = system_prompt.unwrap_or(
            "You are a truth-seeking Grok agent. Use the FAF collection for eternal project context.",
        );

        // Check cache
        if self.enable_cache {
            let cache_key = self.cache_key(question, "chat");
            if let Ok(cache) = self.cache.read() {
                if let Some(cached) = cache.get(&cache_key) {
                    debug!("Cache hit for chat query");
                    return Ok(cached.clone());
                }
            }
        }

        let url = format!("{}/chat/completions", XAI_API_BASE);

        #[derive(Serialize)]
        struct Tool {
            r#type: String,
            function: ToolFunction,
        }

        #[derive(Serialize)]
        struct ToolFunction {
            name: String,
            parameters: serde_json::Value,
        }

        #[derive(Serialize)]
        struct ChatRequest {
            model: String,
            messages: Vec<Message>,
            tools: Vec<Tool>,
        }

        let tools = vec![Tool {
            r#type: "function".to_string(),
            function: ToolFunction {
                name: "collections_search".to_string(),
                parameters: serde_json::json!({
                    "collection_ids": [self.collection_id],
                    "retrieval_mode": DEFAULT_RETRIEVAL_MODE
                }),
            },
        }];

        let messages = vec![
            Message {
                role: "system".to_string(),
                content: system_prompt.to_string(),
            },
            Message {
                role: "user".to_string(),
                content: question.to_string(),
            },
        ];

        let resp = self
            .client
            .post(&url)
            .headers(self.auth_headers())
            .json(&ChatRequest {
                model: model.to_string(),
                messages,
                tools,
            })
            .send()
            .await?;

        if resp.status() == 429 {
            warn!("Rate limited during query");
            return Ok("Rate limited - please retry".to_string());
        }

        if resp.status() == 401 {
            return Ok("Authentication failed - check API keys".to_string());
        }

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let text = resp.text().await.unwrap_or_default();
            error!("Query failed: {} - {}", status, text);
            return Ok(format!("Error: {}", text));
        }

        #[derive(Deserialize)]
        struct ChatResponse {
            choices: Vec<Choice>,
        }

        #[derive(Deserialize)]
        struct Choice {
            message: ChoiceMessage,
        }

        #[derive(Deserialize)]
        struct ChoiceMessage {
            content: Option<String>,
        }

        let response: ChatResponse = resp.json().await?;
        let content = response
            .choices
            .first()
            .and_then(|c| c.message.content.clone())
            .unwrap_or_default();

        // Cache result
        if self.enable_cache {
            let cache_key = self.cache_key(question, "chat");
            if let Ok(mut cache) = self.cache.write() {
                cache.insert(cache_key, content.clone());
            }
        }

        Ok(content)
    }

    /// Generate cache key
    fn cache_key(&self, query: &str, mode: &str) -> String {
        let combined = format!("{}:{}:{}", query, mode, self.collection_id);
        let mut hasher = Sha256::new();
        hasher.update(combined.as_bytes());
        hex::encode(&hasher.finalize()[..8])
    }

    /// Clear the cache
    pub fn clear_cache(&self) {
        if let Ok(mut cache) = self.cache.write() {
            cache.clear();
            info!("Cache cleared");
        }
    }

    /// Get cache statistics
    pub fn cache_stats(&self) -> CacheStats {
        let size = self.cache.read().map(|c| c.len()).unwrap_or(0);
        CacheStats {
            size,
            enabled: self.enable_cache,
        }
    }

    /// Get collection ID
    pub fn collection_id(&self) -> &str {
        &self.collection_id
    }

    /// Get collection name
    pub fn collection_name(&self) -> &str {
        &self.collection_name
    }
}

/// Convenience function to create an integrator
pub async fn create_integrator() -> Result<XAIFafRag> {
    XAIFafRag::new(None, None, None, true).await
}

#[cfg(test)]
mod tests {
    use super::*;

    // === Cache Key Tests ===

    #[test]
    fn test_cache_key_generation() {
        let key1 = {
            let combined = format!("{}:{}:{}", "test query", "hybrid", "coll123");
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            hex::encode(&hasher.finalize()[..8])
        };

        let key2 = {
            let combined = format!("{}:{}:{}", "test query", "hybrid", "coll123");
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            hex::encode(&hasher.finalize()[..8])
        };

        assert_eq!(key1, key2);
        assert_eq!(key1.len(), 16);
    }

    #[test]
    fn test_cache_key_different_queries() {
        let key1 = {
            let combined = format!("{}:{}:{}", "query A", "hybrid", "coll123");
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            hex::encode(&hasher.finalize()[..8])
        };

        let key2 = {
            let combined = format!("{}:{}:{}", "query B", "hybrid", "coll123");
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            hex::encode(&hasher.finalize()[..8])
        };

        assert_ne!(key1, key2);
    }

    #[test]
    fn test_cache_key_different_modes() {
        let key1 = {
            let combined = format!("{}:{}:{}", "query", "hybrid", "coll123");
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            hex::encode(&hasher.finalize()[..8])
        };

        let key2 = {
            let combined = format!("{}:{}:{}", "query", "semantic", "coll123");
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            hex::encode(&hasher.finalize()[..8])
        };

        assert_ne!(key1, key2);
    }

    // === Cache Stats Tests ===

    #[test]
    fn test_cache_stats_default() {
        let cache: RwLock<HashMap<String, String>> = RwLock::new(HashMap::new());
        let size = cache.read().map(|c| c.len()).unwrap_or(0);
        assert_eq!(size, 0);
    }

    #[test]
    fn test_cache_stats_with_entries() {
        let cache: RwLock<HashMap<String, String>> = RwLock::new(HashMap::new());
        {
            let mut c = cache.write().unwrap();
            c.insert("key1".to_string(), "value1".to_string());
            c.insert("key2".to_string(), "value2".to_string());
        }
        let size = cache.read().map(|c| c.len()).unwrap_or(0);
        assert_eq!(size, 2);
    }

    #[test]
    fn test_cache_clear() {
        let cache: RwLock<HashMap<String, String>> = RwLock::new(HashMap::new());
        {
            let mut c = cache.write().unwrap();
            c.insert("key1".to_string(), "value1".to_string());
        }
        assert_eq!(cache.read().unwrap().len(), 1);

        {
            let mut c = cache.write().unwrap();
            c.clear();
        }
        assert_eq!(cache.read().unwrap().len(), 0);
    }

    // === Error Type Tests ===

    #[test]
    fn test_error_display_authentication() {
        let err = XAIError::Authentication("Invalid key".to_string());
        assert!(err.to_string().contains("Authentication"));
        assert!(err.to_string().contains("Invalid key"));
    }

    #[test]
    fn test_error_display_rate_limit() {
        let err = XAIError::RateLimit("Too many requests".to_string());
        assert!(err.to_string().contains("Rate limited"));
    }

    #[test]
    fn test_error_display_api() {
        let err = XAIError::Api {
            status: 400,
            message: "Bad request".to_string(),
        };
        assert!(err.to_string().contains("400"));
        assert!(err.to_string().contains("Bad request"));
    }

    #[test]
    fn test_error_display_missing_key() {
        let err = XAIError::MissingKey("XAI_API_KEY required".to_string());
        assert!(err.to_string().contains("Missing API key"));
    }

    #[test]
    fn test_error_display_file_not_found() {
        let err = XAIError::FileNotFound("/path/to/file".to_string());
        assert!(err.to_string().contains("File not found"));
    }

    // === Struct Tests ===

    #[test]
    fn test_search_result_serialization() {
        let result = SearchResult {
            snippet: "Test snippet".to_string(),
            file_name: "test.faf".to_string(),
            score: 0.95,
            metadata: HashMap::new(),
        };

        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("Test snippet"));
        assert!(json.contains("test.faf"));
        assert!(json.contains("0.95"));

        let parsed: SearchResult = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.snippet, "Test snippet");
        assert_eq!(parsed.file_name, "test.faf");
        assert!((parsed.score - 0.95).abs() < 0.001);
    }

    #[test]
    fn test_search_result_deserialization_without_metadata() {
        let json = r#"{"snippet":"test","file_name":"file.txt","score":0.5}"#;
        let result: SearchResult = serde_json::from_str(json).unwrap();
        assert!(result.metadata.is_empty());
    }

    #[test]
    fn test_message_serialization() {
        let msg = Message {
            role: "user".to_string(),
            content: "Hello".to_string(),
        };

        let json = serde_json::to_string(&msg).unwrap();
        let parsed: Message = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.role, "user");
        assert_eq!(parsed.content, "Hello");
    }

    #[test]
    fn test_collection_serialization() {
        let coll = Collection {
            id: "coll_123".to_string(),
            name: "Test Collection".to_string(),
            description: Some("A test".to_string()),
        };

        let json = serde_json::to_string(&coll).unwrap();
        let parsed: Collection = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.id, "coll_123");
        assert_eq!(parsed.name, "Test Collection");
        assert_eq!(parsed.description, Some("A test".to_string()));
    }

    #[test]
    fn test_collection_without_description() {
        let json = r#"{"id":"coll_123","name":"Test"}"#;
        let coll: Collection = serde_json::from_str(json).unwrap();
        assert!(coll.description.is_none());
    }

    #[test]
    fn test_cache_stats_struct() {
        let stats = CacheStats {
            size: 42,
            enabled: true,
        };
        assert_eq!(stats.size, 42);
        assert!(stats.enabled);
    }

    // === Constants Tests ===

    #[test]
    fn test_defaults() {
        assert_eq!(DEFAULT_COLLECTION_NAME, "FAF Elite Palace");
        assert_eq!(DEFAULT_MODEL, "grok-4-fast");
        assert_eq!(DEFAULT_EMBEDDING, "grok-embedding-small");
        assert_eq!(DEFAULT_RETRIEVAL_MODE, "hybrid");
        assert!(XAI_API_BASE.starts_with("https://"));
    }

    // === Concurrent Cache Access Test ===

    #[test]
    fn test_concurrent_cache_read() {
        use std::sync::Arc;
        use std::thread;

        let cache: Arc<RwLock<HashMap<String, String>>> = Arc::new(RwLock::new(HashMap::new()));

        // Pre-populate
        {
            let mut c = cache.write().unwrap();
            c.insert("key".to_string(), "value".to_string());
        }

        let handles: Vec<_> = (0..10)
            .map(|_| {
                let cache = Arc::clone(&cache);
                thread::spawn(move || {
                    for _ in 0..100 {
                        let c = cache.read().unwrap();
                        assert_eq!(c.get("key"), Some(&"value".to_string()));
                    }
                })
            })
            .collect();

        for h in handles {
            h.join().unwrap();
        }
    }

    // === Cache Throughput Test ===

    #[test]
    fn test_cache_lookup_performance() {
        use std::time::Instant;

        let cache: RwLock<HashMap<String, String>> = RwLock::new(HashMap::new());

        // Pre-populate with 1000 entries
        {
            let mut c = cache.write().unwrap();
            for i in 0..1000 {
                c.insert(format!("key_{}", i), format!("value_{}", i));
            }
        }

        // Measure lookup time
        let start = Instant::now();
        let iterations = 10000;

        for i in 0..iterations {
            let key = format!("key_{}", i % 1000);
            let c = cache.read().unwrap();
            let _ = c.get(&key);
        }

        let elapsed = start.elapsed();
        let per_lookup_ns = elapsed.as_nanos() / iterations as u128;

        // Cache lookups should be under 1ms (typically sub-microsecond)
        assert!(
            per_lookup_ns < 1_000_000,
            "Cache lookup took {}ns, expected < 1ms",
            per_lookup_ns
        );
    }
}
