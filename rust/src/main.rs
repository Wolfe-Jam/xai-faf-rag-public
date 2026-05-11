//! xAI-FAF-RAG CLI (Rust)
//!
//! Command-line interface for the Rust xAI-FAF-RAG integrator.
//!
//! Usage:
//!     xai-faf-rag sync project.faf [--supporting docs.pdf,spec.md]
//!     xai-faf-rag search "query" [--mode hybrid|semantic|keyword] [--limit 5]
//!     xai-faf-rag query "What are the project goals?"
//!     xai-faf-rag stats
//!     xai-faf-rag clear-cache

use clap::{Parser, Subcommand};
use tracing::Level;
use tracing_subscriber::FmtSubscriber;

use xai_faf_rag::create_integrator;

#[derive(Parser)]
#[command(name = "xai-faf-rag")]
#[command(about = "xAI-FAF-RAG: Cache-first RAG with Grok Collections (Rust)", long_about = None)]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Enable verbose output
    #[arg(short, long, global = true)]
    verbose: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Sync .faf file to collection
    Sync {
        /// Path to .faf file
        faf_path: String,

        /// Comma-separated supporting files
        #[arg(short, long)]
        supporting: Option<String>,
    },

    /// Search the collection
    Search {
        /// Search query
        query: String,

        /// Retrieval mode: hybrid, semantic, keyword
        #[arg(short, long, default_value = "hybrid")]
        mode: String,

        /// Number of results
        #[arg(short, long, default_value = "5")]
        limit: usize,
    },

    /// RAG-enhanced query
    Query {
        /// Question to ask
        question: String,

        /// Grok model to use
        #[arg(short, long)]
        model: Option<String>,

        /// Custom system prompt
        #[arg(short, long)]
        system: Option<String>,
    },

    /// Show stats
    Stats,

    /// Clear cache
    ClearCache,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    // Initialize logging
    let level = if cli.verbose { Level::DEBUG } else { Level::INFO };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(level)
        .with_target(false)
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    // Load .env if present
    dotenvy::dotenv().ok();

    // Check for API key
    if std::env::var("XAI_API_KEY").is_err() {
        eprintln!("Error: XAI_API_KEY environment variable required");
        std::process::exit(1);
    }

    match cli.command {
        Commands::Sync { faf_path, supporting } => {
            let integrator = create_integrator().await?;

            let supporting_files: Option<Vec<&str>> = supporting
                .as_ref()
                .map(|s| s.split(',').map(|f| f.trim()).collect());

            let success = integrator
                .sync_faf(&faf_path, supporting_files)
                .await?;

            if success {
                println!("✓ Synced {} to collection {}", faf_path, integrator.collection_id());
                if let Some(s) = supporting {
                    println!("  Supporting files: {}", s);
                }
            } else {
                println!("✗ Failed to sync {}", faf_path);
                std::process::exit(1);
            }
        }

        Commands::Search { query, mode, limit } => {
            let integrator = create_integrator().await?;

            let results = integrator
                .search(&query, Some(limit), Some(&mode))
                .await?;

            if results.is_empty() {
                println!("No results found.");
            } else {
                println!("Found {} results:\n", results.len());
                for (i, result) in results.iter().enumerate() {
                    let snippet = if result.snippet.len() > 200 {
                        format!("{}...", &result.snippet[..200])
                    } else {
                        result.snippet.clone()
                    };
                    println!("{}. [{:.3}] {}", i + 1, result.score, result.file_name);
                    println!("   {}\n", snippet);
                }
            }
        }

        Commands::Query { question, model, system } => {
            let integrator = create_integrator().await?;

            let response = integrator
                .query(&question, model.as_deref(), system.as_deref())
                .await?;

            println!("{}", response);
        }

        Commands::Stats => {
            let integrator = create_integrator().await?;
            let stats = integrator.cache_stats();

            println!("Collection: {}", integrator.collection_id());
            println!("Collection Name: {}", integrator.collection_name());
            println!("Cache Enabled: {}", stats.enabled);
            println!("Cache Size: {} entries", stats.size);
        }

        Commands::ClearCache => {
            let integrator = create_integrator().await?;
            integrator.clear_cache();
            println!("✓ Cache cleared");
        }
    }

    Ok(())
}
