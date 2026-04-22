# 📄 Mem0-Cognitive Paper

This directory contains the LaTeX source code for the paper:

**"Mem0-Cognitive: Emotion-Weighted Forgetting and Sleep Consolidation for Adaptive LLM Memory"**

*Authors: Hongyi Zhou and Contributors*

## 🎯 Target Venues

- **Primary**: ACL 2026 / EMNLP 2026 (Theme Track: NLP for Cognitive Modeling)
- **Secondary**: AAAI 2027, NAACL 2026

## 📁 File Structure

```
paper/
├── main.tex                    # Main document with preamble
├── references.bib              # Bibliography database
├── sections/
│   ├── introduction.tex        # Section 1: Introduction & Contributions
│   ├── related_work.tex        # Section 2: Related Work
│   ├── methodology.tex         # Section 3: Method (with formulas)
│   ├── experiments.tex         # Section 4: Experiments & Results
│   └── conclusion.tex          # Section 5: Conclusion & Future Work
├── figures/                    # Placeholder for figures (to be generated)
│   ├── architecture.pdf        # System architecture diagram
│   └── memory_growth.pdf       # Memory growth comparison plot
└── README.md                   # This file
```

## 🔨 Compilation Instructions

### Option 1: Local Compilation (Requires TeX Live)

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get install texlive-full texlive-xetex texlive-science

# Compile with pdflatex
pdflatex main.tex
bibtex main.tex
pdflatex main.tex
pdflatex main.tex

# Output: main.pdf
```

### Option 2: Overleaf (Recommended for Collaboration)

1. Create a new project on [Overleaf](https://www.overleaf.com)
2. Upload all `.tex` and `.bib` files
3. Upload `acl_natbib.sty` from the ACL 2026 author kit
4. Click "Recompile"

### Option 3: Docker (Reproducible Environment)

```bash
docker run --rm -v $(pwd):/data blang/latex:ubuntu \
  bash -c "cd /data && pdflatex main.tex && bibtex main.tex && pdflatex main.tex && pdflatex main.tex"
```

## 📝 Key Sections to Complete

Before submission, ensure the following are finalized:

- [ ] **Figure 1**: System architecture diagram (use TikZ or draw.io)
- [ ] **Figure 2**: Memory growth comparison plot (from `cognitive_benchmark.py`)
- [ ] **Table 1**: Main results (already in `experiments.tex`, verify numbers)
- [ ] **Table 2**: Ablation study (run ablation experiments)
- [ ] **Table 3**: LoCoMo benchmark results (integrate external evaluation)
- [ ] **Appendix**: Add full prompt templates and hyperparameter settings

## 🎨 Narrative Framework

The paper follows the **"Dynamic Evolution vs Static Storage"** narrative:

1. **Problem**: Existing systems assume "FIFO or Accumulation-Only" → Semantic Quicksand
2. **Gap**: No principled cognitive framework for online, personalized memory management
3. **Solution**: Mem0-Cognitive reframes memory as Active Inference
4. **Contributions**: 
   - Cognitively-inspired framework (3 modules)
   - Algorithmic formalization (Salience Gate, Affective Retention Score)
   - CognitiveBench benchmark
   - Empirical findings (55% token savings, 29% retention boost)

## 📊 Required Experiments Checklist

Based on advisor feedback, complete these before submission:

- [x] Main comparison table (4 baselines + ours)
- [ ] **Ablation Study** (w/o emotion, w/o consolidation, w/o meta-learning)
- [ ] **LoCoMo Benchmark** integration (external validation)
- [ ] **Memory Growth Visualization** (qualitative evidence)
- [ ] **Case Study** (real-world dialogue examples showing consolidation)

## 🗓️ Timeline (Per Advisor Guidance)

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Rewrite Abstract & Intro | Updated `introduction.tex` ✅ |
| 2 | Run Ablation Experiments | Table 2 data |
| 3 | Integrate LoCoMo Benchmark | Table 3 data |
| 4 | Generate Figures & Polish | Final PDF draft |
| 5 | Pre-review with Advisor | Feedback incorporation |
| 6 | Submit to ACL/EMNLP | Camera-ready ready |

## 📞 Contact

For questions about the paper or collaboration opportunities:
- **Hongyi Zhou**: hongyi.zhou@example.com
- **GitHub Issues**: https://github.com/mem0ai/mem0/issues

---

**Good luck with ACL/EMNLP 2026 submission!** 🚀
