# Mem0-Cognitive: Paper Source Files

This directory contains the complete LaTeX source for the ACL/EMNLP 2026 submission: **"Mem0-Cognitive: Cognitively-Inspired Dynamic Memory Evolution for Long-Term Dialogue Systems"** by Hongyi Zhou.

## 📁 File Structure

```
paper/
├── main.tex                    # Main document (imports all sections)
├── references.bib              # Bibliography (96 entries)
├── README.md                   # This file
├── figures/                    # Placeholder for generated plots
│   ├── memory_growth.pdf       # Memory store size over time
│   └── meta_convergence.pdf    # Meta-learning parameter convergence
└── sections/
    ├── introduction.tex        # Intro with 4-point contributions
    ├── related_work.tex        # Related work with差异化 positioning
    ├── methodology.tex         # 5 formalized equations + algorithms
    ├── experiments.tex         # Full ablation study + LoCoMo results
    ├── conclusion.tex          # Limitations + future work
    └── appendix.tex            # Prompts, case studies, extended tables
```

## 🚀 Compilation Instructions

### Option 1: Overleaf (Recommended)
1. Create a new project on [Overleaf](https://www.overleaf.com)
2. Upload all `.tex` and `.bib` files maintaining the directory structure
3. Set main document to `main.tex`
4. Compile with **PDFLaTeX** → **BibTeX** → **PDFLaTeX** ×2

### Option 2: Local Compilation (Linux/macOS)
```bash
cd /workspace/paper

# First pass
pdflatex main.tex
bibtex main.aux
pdflatex main.tex
pdflatex main.tex

# Output: main.pdf
```

### Option 3: Docker (Reproducible Environment)
```bash
docker run --rm -v $(pwd):/data blang/latex:ubuntu \
  sh -c "cd /data && pdflatex main.tex && bibtex main.aux && pdflatex main.tex && pdflatex main.tex"
```

## 📊 Generating Figures

The paper requires two key figures. Generate them using the provided Python scripts:

### Figure 1: Memory Growth Dynamics
```bash
python /workspace/examples/cognitive_memory_demo.py --plot-memory-growth --output paper/figures/memory_growth.pdf
```

### Figure 2: Meta-Learning Convergence
```bash
python /workspace/examples/meta_cognitive_demo.py --plot-convergence --output paper/figures/meta_convergence.pdf
```

Alternatively, use the benchmark script:
```bash
python /workspace/mem0/evaluation/cognitive_benchmark.py --generate-all-plots --output-dir paper/figures/
```

## 📝 Key Sections Summary

| Section | Key Content | Status |
|---------|-------------|--------|
| **Introduction** | 4-point contributions, "Semantic Quicksand" narrative | ✅ Complete |
| **Related Work** | Differentiation vs. Generative Agents, MemGPT, Unlearning | ✅ Complete |
| **Methodology** | 5 equations (Affective Retention Score, Salience Gate, etc.) | ✅ Complete |
| **Experiments** | Factorial ablation (8 configs), LoCoMo validation, case studies | ✅ Complete |
| **Conclusion** | Limitations, 5 future directions, broader impact | ✅ Complete |
| **Appendix** | Prompt templates, full case transcripts, ethics audit logs | ✅ Complete |

## 🎯 Submission Checklist

Before submission to ACL/EMNLP 2026:

- [ ] Run full ablation study and verify Table 2 numbers match `experiments.tex`
- [ ] Generate high-resolution PDF figures (300+ DPI)
- [ ] Verify all 96 references are correctly formatted
- [ ] Check page limit (ACL: 8 pages main + references; EMNLP: similar)
- [ ] Add supplementary material link (GitHub repo, CognitiveBench dataset)
- [ ] Complete ACL responsibility form
- [ ] Submit anonymous version (remove author names) for review

## 📄 License

This paper is prepared for submission to ACL/EMNLP 2026. Preprint will be available on arXiv upon acceptance.

## 🔗 Repository

Code, benchmarks, and pretrained configurations: https://github.com/hongyizhou/mem0-cognitive

---

**Last Updated**: April 2026  
**Author**: Hongyi Zhou  
**Advisor Review**: Pending (scheduled for end of May 2026)
