# AI Concepts Out of Scope for This Project

This project covers RAG (Retrieval-Augmented Generation) end-to-end. The following
AI/ML concepts are **not covered** and should be studied separately.

---

## Not Covered At All

### Model Training & Fine-tuning
- Backpropagation, loss functions, optimizers, learning rate schedules
- Fine-tuning / adapter training (LoRA, QLoRA, full fine-tune)
- Transfer learning — adapting a pre-trained model to a specific domain
- This project uses models as-is (inference only), never trains anything

### Classical Machine Learning
- Supervised learning on tabular data (sklearn, XGBoost, LightGBM)
- Feature engineering, feature selection
- Cross-validation, hyperparameter tuning (GridSearch, Optuna)
- Classification, regression, clustering
- Bias-variance tradeoff, overfitting/underfitting diagnostics
- Precision/recall/F1 in a classification context (vs. retrieval context)

### NLP Beyond RAG
- Text classification, sentiment analysis
- Named Entity Recognition (NER), sequence labeling
- Machine translation
- Summarization (abstractive and extractive)
- Tokenization internals (BPE, WordPiece, SentencePiece)

### Reinforcement Learning
- RLHF (Reinforcement Learning from Human Feedback) — how LLMs are aligned
- Reward modeling, PPO, DPO
- Classic RL: Q-learning, policy gradient, environments

### Generative Models (Non-LLM)
- Diffusion models (Stable Diffusion, DALL-E)
- GANs (Generative Adversarial Networks)
- VAEs (Variational Autoencoders)

### Multimodal AI
- Vision-language models (image + text)
- Speech recognition / TTS
- Video understanding

### Recommendation Systems
- Collaborative filtering, content-based filtering
- Matrix factorization, embedding-based recommendations
- Ranking and personalization

### Time Series
- Forecasting (ARIMA, Prophet, neural forecasting)
- Anomaly detection on temporal data

### Knowledge Graphs
- Graph databases, triple stores
- Graph neural networks (GNNs)
- Structured knowledge representation

---

## Covered Partially / Indirectly

### MLOps
- **Covered**: monitoring, eval in CI, drift detection, scheduled runs
- **Not covered**: model registry, A/B testing, canary deployments, feature stores,
  experiment tracking platforms (MLflow, W&B)

### Scaling & Infrastructure
- **Covered**: single-machine FAISS, Docker, basic deployment
- **Not covered**: distributed inference, GPU cluster management, model serving
  at scale (Triton, vLLM, TGI), load balancing, batched inference

### Structured Output / Function Calling
- **Covered**: basic structured prompts (CP12), agent tool use (CP16)
- **Not covered**: deep integration with OpenAI function calling, JSON mode,
  constrained decoding, grammar-based generation

---

## Priority Study Recommendations

If targeting AI engineer roles, the two biggest gaps to address are:

1. **Fine-tuning** — every serious AI team adapts models. Build a small project
   where you LoRA fine-tune a model on a classification or instruction-following task.

2. **Classical ML fundamentals** — interview staple. Know bias-variance, overfitting,
   precision-recall, ROC, cross-validation. No project needed, but must be able to
   explain clearly.
